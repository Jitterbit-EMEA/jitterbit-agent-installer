"""Isolated enterprise configuration. Only the qualified truststore branch mutates state."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .bootstrap import SafeParser
from .config import load_config
from .errors import FrameworkError
from .host_lock import HostLock
from .restart_health import (
    Profile,
    SupportToolsProbe,
    core_services,
    evaluate,
    identity_confirmed,
    runtime_signals,
)
from .results import write_result

ROOT = Path("/opt/jitterbit")
KEYTOOL = ROOT / "jre/bin/keytool"
STORE = ROOT / "jre/lib/security/cacerts"
AGENT_LOG = ROOT / "log/jitterbit-agent.log"
JITTERBIT = ROOT / "bin/jitterbit"
BACKUPS = Path("/var/lib/jbpa/backups")
ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def command(args, *, env=None, input_bytes=None, timeout=60):
    try:
        return subprocess.run(
            args, input=input_bytes, capture_output=True, timeout=timeout, env=env, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(args, 1, b"", b"")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def certificate_der(pem_bytes):
    result = command(
        ["openssl", "x509", "-inform", "PEM", "-outform", "DER"], input_bytes=pem_bytes
    )
    if result.returncode or not result.stdout:
        raise FrameworkError("JKS_CERT_INVALID")
    return result.stdout


def certificate_fingerprint(pem_bytes):
    return hashlib.sha256(certificate_der(pem_bytes)).hexdigest()


def certificate_metadata(path):
    source = Path(path)
    if not source.is_file() or source.is_symlink() or source.stat().st_size > 1024 * 1024:
        raise FrameworkError("JKS_CERT_INVALID")
    pem = source.read_bytes()
    fingerprint = certificate_fingerprint(pem)
    details = command(
        [
            "openssl",
            "x509",
            "-in",
            str(source),
            "-noout",
            "-subject",
            "-issuer",
            "-serial",
            "-startdate",
            "-enddate",
            "-ext",
            "subjectAltName",
        ]
    )
    if details.returncode:
        raise FrameworkError("JKS_CERT_INVALID")
    profile = command(["openssl", "x509", "-in", str(source), "-noout", "-text"])
    if profile.returncode:
        raise FrameworkError("JKS_CERT_INVALID")
    profile_text = profile.stdout.decode(errors="replace")
    constraints = re.search(
        r"X509v3 Basic Constraints:[^\n]*\n\s*(CA:(?:TRUE|FALSE))", profile_text
    )
    if not constraints:
        raise FrameworkError("JKS_CERT_INVALID")
    is_ca = constraints.group(1) == "CA:TRUE"

    def extension(name):
        found = re.search(rf"X509v3 {re.escape(name)}:[^\n]*\n\s*([^\n]+)", profile_text)
        return found.group(1).strip() if found else None

    dates = dict(
        line.split("=", 1)
        for line in details.stdout.decode(errors="replace").splitlines()
        if line.startswith(("notBefore=", "notAfter="))
    )
    try:
        before = datetime.strptime(dates["notBefore"], "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
        after = datetime.strptime(dates["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
    except (KeyError, ValueError) as exc:
        raise FrameworkError("JKS_CERT_INVALID") from exc
    if not before <= datetime.now(timezone.utc) < after:
        raise FrameworkError("JKS_CERT_INVALID")
    lines = details.stdout.decode(errors="replace").splitlines()
    return {
        "sha256_fingerprint": fingerprint,
        "subject": next((x for x in lines if x.startswith("subject=")), None),
        "issuer": next((x for x in lines if x.startswith("issuer=")), None),
        "serial": next((x for x in lines if x.startswith("serial=")), None),
        "not_before_utc": before.isoformat(),
        "not_after_utc": after.isoformat(),
        "basic_constraints": constraints.group(1),
        "certificate_is_ca": is_ca,
        "certificate_type": "CA" if is_ca else "EXPLICIT_TRUSTED_ENDPOINT",
        "subject_alternative_names": extension("Subject Alternative Name"),
        "key_usage": extension("Key Usage"),
        "extended_key_usage": extension("Extended Key Usage"),
    }


class TruststoreWorkflow:
    def __init__(
        self,
        *,
        keytool=KEYTOOL,
        store=STORE,
        agent_log=AGENT_LOG,
        jitterbit=JITTERBIT,
        backups=BACKUPS,
        runner=command,
        sleeper=time.sleep,
        monotonic=time.monotonic,
        expected_agent_id=None,
        expected_group_id=None,
        support_tools=None,
        expected_agent_name=None,
        expected_group_name=None,
        expected_version="12.10.1.1",
    ):
        self.keytool, self.store, self.agent_log, self.jitterbit = map(
            Path, (keytool, store, agent_log, jitterbit)
        )
        self.backups, self.runner, self.sleeper, self.monotonic = (
            Path(backups),
            runner,
            sleeper,
            monotonic,
        )
        self.expected_agent_id = expected_agent_id
        self.expected_group_id = expected_group_id
        self.support_tools = support_tools or SupportToolsProbe()
        self.expected_agent_name = expected_agent_name
        self.expected_group_name = expected_group_name
        self.expected_version = expected_version
        self.restart_count = 0
        self.last_health = None

    def _tool(self, args, password):
        env = {**os.environ, "JBPA_STOREPASS": password}
        return self.runner(
            [
                str(self.keytool),
                *args,
                "-keystore",
                str(self.store),
                "-storepass:env",
                "JBPA_STOREPASS",
            ],
            env=env,
        )

    def _alias_fingerprint(self, alias, password):
        result = self._tool(["-exportcert", "-rfc", "-alias", alias], password)
        if result.returncode:
            return None
        try:
            return certificate_fingerprint(result.stdout)
        except FrameworkError as exc:
            raise FrameworkError("JKS_VALIDATION_FAILED") from exc

    def _health(self):
        result = self.runner([str(self.jitterbit), "status"])
        output = result.stdout.decode(errors="replace")
        return core_services(output, result.returncode)

    def _runtime_healthy(self, log_text):
        if self.expected_group_id is None:
            return all(
                marker in log_text
                for marker in (
                    "REST API RESPONSE: Status: true",
                    "Agent Logged in:",
                    "connection to agent services has been established",
                    "Connection established, agent logged in, and request flow has commenced",
                )
            )
        signals = runtime_signals(log_text, self.expected_group_id, self.expected_agent_id)
        return all(
            signals[key]
            for key in ("harmonyAuthenticated", "agentServicesConnected", "requestFlowStarted")
        )

    def _current_health(self):
        local = self.runner([str(self.jitterbit), "status"])
        output = local.stdout.decode(errors="replace")
        return evaluate(
            Profile.STEADY_STATE_EXISTING_AGENT,
            log=self.agent_log.read_text(errors="replace") if self.agent_log.is_file() else "",
            since=None,
            agent_id=self.expected_agent_id,
            group_id=self.expected_group_id,
            credentials_present=(ROOT / "Resources/credentials.txt").is_file(),
            local_core_services=core_services(output, local.returncode),
            connection=self.support_tools.connection(),
            support_services=self.support_tools.services(),
            agent_identity_confirmed=identity_confirmed(
                self.support_tools.about(),
                version=self.expected_version,
                agent_name=self.expected_agent_name,
                group_name=self.expected_group_name,
            ),
        )

    def _restart_and_validate(
        self, log_position, timeout=300, profile=Profile.POST_CONFIGURATION_RESTART
    ):
        started_at = datetime.now(timezone.utc).replace(microsecond=0)
        position = self.agent_log.stat() if self.agent_log.exists() else None
        self.restart_count += 1
        if self.runner([str(self.jitterbit), "restart"], timeout=120).returncode:
            return False
        deadline = self.monotonic() + timeout
        while self.monotonic() <= deadline:
            if self.agent_log.exists():
                raw = self.agent_log.read_bytes()
                current = self.agent_log.stat()
                added = (
                    raw[position.st_size :]
                    if position
                    and current.st_ino == position.st_ino
                    and len(raw) >= position.st_size
                    else raw
                )
                self.last_health = evaluate(
                    profile,
                    log=added.decode(errors="replace"),
                    since=started_at,
                    agent_id=self.expected_agent_id,
                    group_id=self.expected_group_id,
                    credentials_present=(ROOT / "Resources/credentials.txt").exists(),
                    local_core_services=self._health(),
                    connection=self.support_tools.connection(),
                    support_services=self.support_tools.services(),
                    rollback_file_verified=(
                        True if profile is Profile.POST_ROLLBACK_RESTART else None
                    ),
                )
                if self.last_health["status"] == "HEALTHY":
                    return True
            self.sleeper(5)
        return False

    def apply(self, certificates, *, password, run_id, dry_run=False, allow_endpoint=False):
        if (
            not self.keytool.is_file()
            or not os.access(self.keytool, os.X_OK)
            or not self.store.is_file()
        ):
            raise FrameworkError("JKS_NOT_FOUND")
        if self.store.is_symlink() or self.keytool.is_symlink():
            raise FrameworkError("JKS_NOT_FOUND")
        sysconfig = Path("/etc/sysconfig/jitterbit")
        if sysconfig.exists():
            contents = sysconfig.read_text(errors="replace")
            if (
                re.search(r"^\s*(?:export\s+)?JRE_HOME=", contents, re.M)
                or "javax.net.ssl.trustStore" in contents
            ):
                raise FrameworkError("JKS_NOT_FOUND")
        if self._tool(["-list"], password).returncode:
            raise FrameworkError("JKS_VALIDATION_FAILED")
        if not self._health():
            raise FrameworkError("JKS_BASELINE_UNHEALTHY")
        baseline = None
        if self.expected_agent_id is not None:
            baseline = self._current_health()
            if baseline is None or baseline["status"] != "HEALTHY":
                raise FrameworkError("JKS_BASELINE_UNHEALTHY")
        baseline_hash = sha256(self.store)
        intent = []
        for item in certificates:
            alias = item["alias"]
            source = item["certificate_source"]
            if not ALIAS.fullmatch(alias):
                raise FrameworkError("JKS_CERT_INVALID")
            metadata = certificate_metadata(source["path"])
            if not metadata["certificate_is_ca"] and (
                not allow_endpoint
                or "TLS Web Server Authentication" not in (metadata["extended_key_usage"] or "")
            ):
                raise FrameworkError("JKS_CERT_INVALID")
            if metadata["sha256_fingerprint"] != source["sha256"].lower():
                raise FrameworkError("JKS_CERT_INVALID")
            actual = self._alias_fingerprint(alias, password)
            if actual and actual != metadata["sha256_fingerprint"]:
                raise FrameworkError("JKS_ALIAS_CONFLICT")
            intent.append((alias, source["path"], metadata, actual))
        missing = [x for x in intent if x[3] is None]
        if dry_run:
            return {
                "status": "PLANNED",
                "changed": False,
                "restart_required": bool(missing),
                "baseline_health": baseline,
                "original_sha256": baseline_hash,
                "would_import_aliases": [x[0] for x in missing],
                "certificates": [{"alias": x[0], **x[2]} for x in intent],
            }
        if not missing:
            return {
                "status": "NO_CHANGE",
                "changed": False,
                "restart_required": False,
                "restart_performed": False,
                "restart_count": 0,
                "original_sha256": baseline_hash,
                "post_sha256": sha256(self.store),
                "steady_state_health": baseline,
                "certificates": [{"alias": x[0], **x[2]} for x in intent],
            }
        backup_dir = self.backups / run_id
        backup_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        backup = backup_dir / "cacerts"
        original_hash = sha256(self.store)
        shutil.copy2(self.store, backup)
        os.chmod(backup, 0o600)
        backup_hash = sha256(backup)
        if original_hash != backup_hash or sha256(self.store) != original_hash:
            raise FrameworkError("JKS_BACKUP_FAILED")
        previous = self.store.stat()
        log_position = self.agent_log.stat().st_size if self.agent_log.exists() else 0
        failure = None
        try:
            for alias, source, metadata, _ in missing:
                result = self._tool(
                    ["-importcert", "-trustcacerts", "-noprompt", "-alias", alias, "-file", source],
                    password,
                )
                if result.returncode:
                    raise FrameworkError("JKS_IMPORT_FAILED")
                if sha256(self.store) == original_hash:
                    raise FrameworkError("JKS_IMPORT_UNCONFIRMED")
                if self._alias_fingerprint(alias, password) != metadata["sha256_fingerprint"]:
                    raise FrameworkError("JKS_VALIDATION_FAILED")
            if self._tool(["-list"], password).returncode:
                raise FrameworkError("JKS_VALIDATION_FAILED")
            if not self._restart_and_validate(log_position):
                raise FrameworkError("JKS_VALIDATION_FAILED")
        except Exception as exc:
            failure = (
                exc if isinstance(exc, FrameworkError) else FrameworkError("JKS_VALIDATION_FAILED")
            )
        if failure:
            try:
                temporary = self.store.with_name("cacerts.jbpa-rollback")
                shutil.copy2(backup, temporary)
                os.chown(temporary, previous.st_uid, previous.st_gid)
                os.chmod(temporary, previous.st_mode & 0o777)
                os.replace(temporary, self.store)
                if sha256(self.store) != original_hash or not self._restart_and_validate(
                    self.agent_log.stat().st_size if self.agent_log.exists() else 0,
                    profile=Profile.POST_ROLLBACK_RESTART,
                ):
                    raise FrameworkError("JKS_ROLLBACK_FAILED")
            except (OSError, FrameworkError) as exc:
                raise FrameworkError("JKS_ROLLBACK_FAILED") from exc
            raise FrameworkError("JKS_CONFIGURATION_ROLLED_BACK") from failure
        return {
            "status": "SUCCESS",
            "changed": True,
            "restart_required": True,
            "restart_performed": True,
            "baseline_health": baseline,
            "backup_path": str(backup),
            "original_sha256": original_hash,
            "backup_sha256": backup_hash,
            "post_sha256": sha256(self.store),
            "restart_count": self.restart_count,
            "post_restart_health": self.last_health,
            "certificates": [{"alias": x[0], **x[2]} for x in intent],
        }


def execute(argv=None, *, workflow=None, stdout=None, effective_uid=os.geteuid):
    parser = SafeParser(description="Apply isolated PA enterprise configuration")
    parser.add_argument("--config", required=True)
    parser.add_argument("--result-file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--qa-verified-default-password", action="store_true")
    parser.add_argument("--qa-endpoint-certificate", action="store_true")
    parser.add_argument("--expected-agent-id", type=int)
    parser.add_argument("--expected-agent-group-id", type=int)
    parser.add_argument("--expected-agent-name")
    parser.add_argument("--expected-agent-group-name")
    args = parser.parse_args(argv)
    stdout = stdout or sys.stdout
    run_id = "jbpa-enterprise-" + uuid.uuid4().hex
    branches = {
        name: {"enabled": False, "status": "SKIPPED", "changed": False}
        for name in ("truststore", "ssh", "ssl", "proxy")
    }
    result = {
        "schemaVersion": 1,
        "runId": run_id,
        "status": "FAILED",
        "enterpriseConfiguration": branches,
        "error": None,
    }
    code = 0
    enabled = []
    try:
        config, _ = load_config(args.config)
        enabled = [
            name
            for name, value in (
                ("truststore", config["java_trust"]["enabled"]),
                ("ssh", config["ssh"]["enabled"]),
                ("ssl", config["ssl"]["enabled"]),
                ("proxy", config["proxy"]["enabled"]),
            )
            if value
        ]
        if len(enabled) > 1:
            raise FrameworkError("CONFIG_INVALID")
        if not enabled:
            result["status"] = "NO_CHANGE"
        elif enabled[0] != "truststore":
            selected = enabled[0]
            branches[selected]["enabled"] = True
            if selected == "proxy":
                if config["harmony"]["registration"]["strategy"] == "register-json-token":
                    raise FrameworkError("REGISTRATION_MODE_INCOMPATIBLE_WITH_PROXY")
                raise FrameworkError("PROXY_REGISTRATION_BLOCKED")
            raise FrameworkError(
                "SSH_CONFIGURATION_FAILED" if selected == "ssh" else "SSL_CONFIGURATION_FAILED"
            )
        else:
            branches["truststore"]["enabled"] = True
            if args.qa_endpoint_certificate and not args.qa_verified_default_password:
                raise FrameworkError("CONFIG_INVALID")
            if workflow is None and (
                not args.expected_agent_id
                or not args.expected_agent_group_id
                or not args.expected_agent_name
                or not args.expected_agent_group_name
            ):
                raise FrameworkError("CONFIG_INVALID")
            if effective_uid() != 0:
                raise FrameworkError("PREFLIGHT_FAILED")
            password = os.environ.get("JBPA_TRUSTSTORE_PASSWORD")
            if args.qa_verified_default_password:
                if password:
                    raise FrameworkError("CONFIG_INVALID")
                if workflow is None:
                    release = Path("/etc/os-release").read_text(errors="replace")
                    package = command(
                        ["dpkg-query", "-W", "-f=${Version}|${Status}", "jitterbit-agent"]
                    )
                    if (
                        "ID=ubuntu" not in release
                        or 'VERSION_ID="24.04"' not in release
                        or package.stdout.strip() != b"12.10.1.1|install ok installed"
                    ):
                        raise FrameworkError("PREFLIGHT_FAILED")
                password = "changeit"  # Jitterbit-documented default, verified on this QA VM.
            if not password:
                raise FrameworkError("CONFIG_INVALID")
            with HostLock("/var/lib/jbpa/bootstrap.lock"):
                branches["truststore"] = {
                    "enabled": True,
                    **(
                        workflow
                        or TruststoreWorkflow(
                            expected_agent_id=args.expected_agent_id,
                            expected_group_id=args.expected_agent_group_id,
                            expected_agent_name=args.expected_agent_name,
                            expected_group_name=args.expected_agent_group_name,
                        )
                    ).apply(
                        config["java_trust"]["certificates"],
                        password=password,
                        run_id=run_id,
                        dry_run=args.dry_run,
                        allow_endpoint=args.qa_endpoint_certificate,
                    ),
                }
            result["status"] = branches["truststore"]["status"]
    except FrameworkError as exc:
        code = exc.spec.exitCode
        result["error"] = exc.as_dict()
        result["status"] = "BLOCKED"
        if branches["truststore"]["enabled"]:
            branches["truststore"]["status"] = exc.spec.name
        elif enabled:
            branches[enabled[0]]["status"] = exc.spec.name
    except Exception:
        exc = FrameworkError("INTERNAL_ERROR")
        code = exc.spec.exitCode
        result["error"] = exc.as_dict()
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_file:
        write_result(args.result_file, output)
    stdout.write(output)
    return code


def main():
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
