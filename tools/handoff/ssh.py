"""External RC3 SSH handoff for a pre-provisioned Ubuntu 22.04 host.

This caller delivers framework bytes and invokes one JBPA operation. It does not
provision infrastructure or interpret Private Agent logs/lifecycle internals.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator

from jbpa.config import load_config
from jbpa.errors import FrameworkError

from .caller import HandoffError, arguments, consume, validate
from .guest_prepare import EXPECTED_SHA, RC3, digest

ROOT = Path(__file__).resolve().parents[2]
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")
READ_RESULT = (
    "import os,sys; p=sys.argv[1]; "
    "f=os.open(p,os.O_RDONLY|os.O_NOFOLLOW); "
    "s=os.fstat(f); "
    "sys.exit(2) if not __import__('stat').S_ISREG(s.st_mode) or s.st_size>1048576 "
    "else None; "
    "sys.stdout.buffer.write(os.read(f,1048577))"
)


class SSHTransport:
    def __init__(self, target, user, key, known_hosts):
        if not SAFE.fullmatch(target) or not SAFE.fullmatch(user):
            raise HandoffError("REQUEST_INVALID")
        for path in (key, known_hosts):
            if not Path(path).is_file():
                raise HandoffError("HOST_ACCESS_UNAVAILABLE")
        self.target = target
        self.user = user
        self.options = [
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "ConnectTimeout=10",
            "-i",
            str(key),
        ]

    @property
    def address(self):
        return f"{self.user}@{self.target}"

    def command(self, argv, *, timeout=60):
        try:
            completed = subprocess.run(
                ["ssh", *self.options, "-T", self.address, shlex.join(argv)],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise HandoffError("REMOTE_EXECUTION_FAILED") from None
        if len(completed.stdout) > 1048576:
            raise HandoffError("REMOTE_OUTPUT_TOO_LARGE")
        return completed.returncode, completed.stdout.decode("utf-8", errors="replace")

    def deliver(self, local, remote):
        try:
            result = subprocess.run(
                ["scp", *self.options, "-q", str(local), f"{self.address}:{remote}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise HandoffError("RELEASE_DELIVERY_FAILED") from None
        if result.returncode:
            raise HandoffError("RELEASE_DELIVERY_FAILED")

    def result(self, path):
        code, value = self.command(["sudo", "-n", "python3", "-c", READ_RESULT, path])
        if code:
            raise HandoffError("RESULT_FILE_MISSING")
        return value


def _require(condition, reason):
    if not condition:
        raise HandoffError(reason)


class PreflightFailure(HandoffError):
    def __init__(self, reason, result):
        super().__init__(reason)
        self.result = result


def _write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)


def _preflight(transport, binary, request, path):
    command = [
        "sudo",
        "-n",
        "env",
        f"JBPA_PYTHON={Path(binary).parent.parent / '.venv/bin/python'}",
        binary,
        "validate",
        "--config",
        request["configPath"],
        "--version",
        request["paVersion"],
        "--profile",
        request["operation"],
        "--controlled-test",
        "--result-file",
        path,
    ]
    code, _ = transport.command(command, timeout=180)
    raw = transport.result(path)
    try:
        result = json.loads(raw)
        schema = json.loads((ROOT / "config/schemas/rc-result.schema.json").read_text())
        _require(Draft202012Validator(schema).is_valid(result), "PREFLIGHT_RESULT_INVALID")
        preflight = result["details"]["preflight"]
        _require(result["operation"] == "VALIDATE", "PREFLIGHT_FAILED")
        _require(result["versions"]["jbpa"] == RC3, "PREFLIGHT_RESULT_INVALID")
        if code != 0 or preflight["status"] not in {"PASS", "PASS_WITH_WARNINGS"}:
            raise PreflightFailure("PREFLIGHT_FAILED", raw)
        host = preflight["platform"]
        if not (
            host.get("system") == "Linux"
            and host.get("os") == "ubuntu"
            and host.get("version") == "22.04"
            and host.get("architecture") == "x86_64"
        ):
            raise PreflightFailure("HOST_PLATFORM_UNEXPECTED", raw)
        expected = (
            "CLEAN_HOST" if request["operation"] == "INSTALL" else "AGENT_INSTALLED_REGISTERED"
        )
        if preflight["hostState"] != expected:
            raise PreflightFailure("HOST_STATE_UNEXPECTED", raw)
    except (KeyError, TypeError, ValueError):
        raise HandoffError("PREFLIGHT_RESULT_INVALID") from None
    return raw


def run(request, transport, archive, config_source=None):
    validate(request)
    _require(request["target"] == transport.target, "REQUEST_INVALID")
    _require(request["jbpaVersion"] == RC3 and request["paVersion"] == "12.10", "REQUEST_INVALID")
    _require(request["operation"] in {"INSTALL", "REINSTALL"}, "REQUEST_INVALID")
    _require(request["controlledTest"] and request["allowUnqualified"], "REQUEST_INVALID")
    _require(digest(archive) == EXPECTED_SHA, "JBPA_RELEASE_HASH_MISMATCH")
    if request["operation"] == "INSTALL":
        _require(config_source is not None, "CONFIG_SOURCE_REQUIRED")
        try:
            load_config(config_source, request["paVersion"])
        except FrameworkError:
            raise HandoffError("CONFIG_INVALID") from None
    stage = f"/var/tmp/jbpa-handoff-{uuid.uuid4().hex}"
    code, _ = transport.command(["install", "-d", "-m", "0700", stage])
    _require(code == 0, "RELEASE_DELIVERY_FAILED")
    binary = f"/opt/jbpa/releases/{EXPECTED_SHA}/bin/jbpa"
    try:
        transport.deliver(ROOT / "tools/handoff/guest_prepare.py", f"{stage}/guest_prepare.py")
        helper = ["sudo", "-n", "python3", f"{stage}/guest_prepare.py"]
        if request["operation"] == "INSTALL":
            transport.deliver(archive, f"{stage}/release.tar.gz")
            transport.deliver(config_source, f"{stage}/agent.yaml")
            command = [
                *helper,
                "prepare",
                "--archive",
                f"{stage}/release.tar.gz",
                "--config-source",
                f"{stage}/agent.yaml",
                "--config-target",
                request["configPath"],
                "--result-parent",
                str(Path(request["resultPath"]).parent),
            ]
        else:
            command = [*helper, "verify"]
        code, output = transport.command(command, timeout=900)
        try:
            delivered = json.loads(output)
        except ValueError:
            raise HandoffError("RELEASE_DELIVERY_FAILED") from None
        _require(code == 0 and delivered.get("status") == "VERIFIED", "RELEASE_DELIVERY_FAILED")
        _require(delivered.get("sha256") == EXPECTED_SHA, "JBPA_RELEASE_HASH_MISMATCH")
        preflight_path = str(Path(request["resultPath"]).with_suffix(".preflight.json"))
        preflight = _preflight(transport, binary, request, preflight_path)
        argv = arguments(request, binary)
        code, _ = transport.command(
            [
                "sudo",
                "-n",
                "env",
                f"JBPA_PYTHON={Path(binary).parent.parent / '.venv/bin/python'}",
                *argv,
            ],
            timeout=7200,
        )
        result = transport.result(request["resultPath"])
        decision = consume(request, code, result)
        return {
            "delivery": delivered,
            "preflight": preflight,
            "result": result,
            "decision": decision,
        }
    finally:
        transport.command(["rm", "-rf", "--", stage])


def main():
    parser = argparse.ArgumentParser(description="External Ubuntu 22.04 RC3 SSH handoff")
    for arg in ("request", "release", "user", "key", "known-hosts", "evidence-dir"):
        parser.add_argument("--" + arg, required=True)
    parser.add_argument("--config-source")
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.request).read_text())
        transport = SSHTransport(request["target"], args.user, args.key, args.known_hosts)
        outcome = run(request, transport, args.release, args.config_source)
        evidence = Path(args.evidence_dir)
        evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = request["operation"].lower()
        for suffix, content in (
            ("delivery.json", json.dumps(outcome["delivery"], sort_keys=True) + "\n"),
            ("preflight.json", outcome["preflight"]),
            ("result.json", outcome["result"]),
        ):
            destination = evidence / f"{name}-{suffix}"
            _write_private(destination, content)
        _write_private(
            evidence / f"{name}-caller-result.json",
            json.dumps(outcome["decision"], sort_keys=True) + "\n",
        )
        decision = outcome["decision"]
    except PreflightFailure as exc:
        evidence = Path(args.evidence_dir)
        evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
        _write_private(evidence / f"{request['operation'].lower()}-preflight.json", exc.result)
        decision = {"success": False, "reason": str(exc)}
    except (HandoffError, KeyError, OSError, ValueError) as exc:
        decision = {
            "success": False,
            "reason": str(exc) if isinstance(exc, HandoffError) else "REQUEST_INVALID",
        }
    print(json.dumps(decision, sort_keys=True))
    return 0 if decision["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
