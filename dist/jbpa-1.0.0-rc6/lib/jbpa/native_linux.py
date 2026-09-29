"""Evidence-qualified native Linux Private Agent workflow.

The adapter is deliberately dependency-injected.  ``LocalBackend`` performs the
real host operations; tests use a fake backend and never require root, a network,
or Jitterbit credentials.
"""

from __future__ import annotations

import grp
import hashlib
import json
import os
import pwd
import re
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from .errors import FrameworkError
from .security import Secret

RESOURCE_DIR = "/opt/jitterbit/Resources"
REGISTER_JSON = f"{RESOURCE_DIR}/register.json"
CREDENTIALS = f"{RESOURCE_DIR}/credentials.txt"
AGENT_LOG = "/opt/jitterbit/log/jitterbit-agent.log"
JITTERBIT = "/opt/jitterbit/bin/jitterbit"

SUCCESS_MARKERS = {
    "AUTO_REGISTRATION_STARTED": "Auto Registration - Starting...",
    "AUTO_REGISTRATION_COMPLETED": "Auto Registration - Completed!",
    "CREDENTIALS_CREATED": "Read agent credentials file: /opt/jitterbit/Resources/credentials.txt",
    "HARMONY_AUTHENTICATED": "REST API RESPONSE: Status: true",
    "AGENT_LOGGED_IN": "Agent Logged in: AgentId =",
    "AGENT_SERVICES_CONNECTED": "connection to agent services has been established",
    "REQUEST_FLOW_STARTED": "Connection established, agent logged in, and request flow has commenced",
    "AGENT_SYNCHRONIZED": "Agent synchronization for agent group ID",
    "HEARTBEAT_STARTED": "Will send heart beats for AgentId",
}

REQUIRED_SERVICES = (
    "JitterbitProcessEngine",
    "Scheduler",
    "FileCleanup",
    "VerboseLogShipper",
)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class Backend(Protocol):
    def run(self, argv: list[str], env: dict[str, str] | None = None) -> CommandResult: ...
    def exists(self, path: str) -> bool: ...
    def read_text(self, path: str) -> str: ...
    def log_position(self, path: str) -> tuple[int, int] | None: ...
    def read_log_since(self, path: str, position: tuple[int, int] | None) -> str: ...
    def write_private_json(self, path: str, value: dict) -> None: ...
    def validate_json(self, path: str) -> bool: ...
    def remove_registration_input(self, path: str) -> None: ...
    def download(self, url: str, destination: str) -> None: ...
    def sha256(self, path: str) -> str: ...
    def monotonic(self) -> float: ...
    def sleep(self, seconds: int) -> None: ...


class LocalBackend:
    """Real local implementation. Command output is retained, never streamed."""

    def __init__(self, blob_downloader=None):
        self.blob_downloader = blob_downloader

    def run(self, argv, env=None):
        completed = subprocess.run(
            argv,
            env=None if env is None else {**os.environ, **env},
            text=True,
            capture_output=True,
            check=False,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)

    def exists(self, path):
        return Path(path).exists()

    def read_text(self, path):
        return Path(path).read_text(errors="replace")

    def log_position(self, path):
        try:
            st = Path(path).stat()
            return st.st_ino, st.st_size
        except FileNotFoundError:
            return None

    def read_log_since(self, path, position):
        with open(path, "rb") as stream:
            st = os.fstat(stream.fileno())
            if position and position[0] == st.st_ino and st.st_size >= position[1]:
                stream.seek(position[1])
            return stream.read().decode("utf-8", errors="replace")

    def write_private_json(self, path, value):
        target = Path(path)
        if not target.parent.is_dir():
            raise FrameworkError("PACKAGE_INSTALL_FAILED")
        if target.exists() or target.is_symlink():
            raise FrameworkError("REGISTRATION_STATE_CONFLICT")
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        fd = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(value, stream, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chown(temporary, pwd.getpwnam("jitterbit").pw_uid, grp.getgrnam("jitterbit").gr_gid)
            os.link(temporary, target, follow_symlinks=False)
            temporary.unlink()
            directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def validate_json(self, path):
        try:
            value = json.loads(Path(path).read_text())
            return (
                isinstance(value, dict)
                and isinstance(value.get("cloudUrl"), str)
                and isinstance(value.get("agentGroupId"), int)
                and isinstance(value.get("token"), str)
                and bool(value.get("token"))
                and isinstance(value.get("agentNamePrefix"), str)
                and isinstance(value.get("retryCount"), int)
                and isinstance(value.get("retryIntervalSeconds"), int)
            )
        except (OSError, ValueError, TypeError):
            return False

    def remove_registration_input(self, path):
        target = Path(path)
        if target.exists() or target.is_symlink():
            target.unlink()

    def download(self, url, destination):
        if urlsplit(url).hostname and urlsplit(url).hostname.endswith(".blob.core.windows.net"):
            if self.blob_downloader is None:
                raise FrameworkError("DOWNLOAD_FAILED")
            self.blob_downloader(url, destination)
            return
        temporary = destination + ".partial"
        try:
            with urllib.request.urlopen(url, timeout=60) as source:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as out:
                    total = 0
                    while block := source.read(1024 * 1024):
                        total += len(block)
                        if total > 2 * 1024 * 1024 * 1024:
                            raise FrameworkError("DOWNLOAD_FAILED")
                        out.write(block)
                    out.flush()
                    os.fsync(out.fileno())
            os.replace(temporary, destination)
        except Exception as exc:
            Path(temporary).unlink(missing_ok=True)
            raise FrameworkError("DOWNLOAD_FAILED") from exc

    def sha256(self, path):
        digest = hashlib.sha256()
        with open(path, "rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        return digest.hexdigest()

    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)


class NativeLinuxWorkflow:
    """Install, register and verify one evidence-qualified native .deb agent."""

    def __init__(self, backend: Backend):
        self.backend = backend
        self.history: list[str] = []
        self.changed = False

    @property
    def state(self):
        return self.history[-1] if self.history else "INITIALIZED"

    def advance(self, state):
        self.history.append(state)

    def fail(self, name):
        error = FrameworkError(name)
        error.runtime_result = {
            "status": "FAILED",
            "state": self.state,
            "stateHistory": self.history.copy(),
            "changed": self.changed,
            "serviceRunning": None,
            "harmonyRegistered": False,
            "error": error.as_dict(),
        }
        raise error

    def _run_ok(self, argv, error, env=None):
        result = self.backend.run(argv, env)
        if result.returncode:
            self.fail(error)
        return result

    def _validate_package(self, path, artifact):
        fields = {}
        for field in ("Package", "Architecture", "Version"):
            result = self._run_ok(
                ["dpkg-deb", "--field", path, field], "ARTIFACT_METADATA_MISMATCH"
            )
            fields[field] = result.stdout.strip()
        expected_arch = (
            "amd64" if artifact["architecture"] == "x86_64" else artifact["architecture"]
        )
        if (
            fields["Package"] != "jitterbit-agent"
            or fields["Architecture"] != expected_arch
            or fields["Version"] != artifact["package_version"]
        ):
            self.fail("ARTIFACT_METADATA_MISMATCH")
        if self.backend.sha256(path).lower() != artifact["sha256"].lower():
            self.fail("CHECKSUM_FAILED")

    def _registration_document(self, config, token):
        registration = config["harmony"]["registration"]
        return {
            "cloudUrl": config["harmony"]["cloud_url"],
            "agentGroupId": config["harmony"]["agent_group_id"],
            "token": token.reveal(),
            "agentNamePrefix": config["agent"]["name"],
            "deregisterAgentOnDrainstop": registration["deregister_on_drainstop"],
            "retryCount": 10,
            "retryIntervalSeconds": 5,
        }

    def _validate_registration_input(self, config, token, credentials_before):
        if config["proxy"]["enabled"]:
            self.fail("REGISTRATION_MODE_INCOMPATIBLE_WITH_PROXY")
        for branch, error in (
            ("ssh", "SSH_CONFIGURATION_FAILED"),
            ("ssl", "SSL_CONFIGURATION_FAILED"),
            ("java_trust", "JKS_CONFIGURATION_FAILED"),
        ):
            if config[branch]["enabled"]:
                self.fail(error)
        harmony = config["harmony"]
        if (
            harmony["registration"]["strategy"] != "register-json-token"
            or not harmony["cloud_url"]
            or not harmony["agent_group_id"]
            or not config["agent"]["name"]
            or (not credentials_before and not token.reveal())
        ):
            self.fail("REGISTER_JSON_INVALID")

    def _observe(self, log, group_id):
        found = {state for state, marker in SUCCESS_MARKERS.items() if marker in log}
        if not re.search(rf"Agent Logged in: AgentId = \d+; AgentGroupId = {group_id}\b", log):
            found.discard("AGENT_LOGGED_IN")
        if not re.search(rf"Agent synchronization for agent group ID {group_id} completed\b", log):
            found.discard("AGENT_SYNCHRONIZED")
        return found

    def _runtime_failure(self, log):
        lowered = log.lower()
        if "status: false" in lowered or "unauthorized" in lowered or "invalid token" in lowered:
            return "REGISTRATION_AUTH_FAILED"
        if any(
            value in lowered
            for value in ("unknownhost", "connection refused", "network is unreachable")
        ):
            return "REGISTRATION_NETWORK_FAILED"
        if "auto registration - failed" in lowered:
            return "AUTO_REGISTRATION_FAILED"
        return None

    def _local_health(self):
        result = self.backend.run([JITTERBIT, "status"])
        healthy = result.returncode == 0 and "All services are running" in result.stdout
        healthy = healthy and all(service in result.stdout for service in REQUIRED_SERVICES)
        if not healthy:
            self.fail("LOCAL_SERVICE_FAILURE")
        self.advance("LOCAL_SERVICES_HEALTHY")

    def run(self, config, artifact, token: Secret, staging="/var/tmp/jbpa"):
        """Execute the qualified workflow and return a secret-free structured result."""
        try:
            credentials_before = self.backend.exists(CREDENTIALS)
            register_before = self.backend.exists(REGISTER_JSON)
            if register_before:
                self.fail("REGISTRATION_STATE_CONFLICT")
            self._validate_registration_input(config, token, credentials_before)

            installed = self.backend.run(["dpkg-query", "-W", "-f=${Version}", "jitterbit-agent"])
            if (
                installed.returncode == 0
                and installed.stdout.strip() != artifact["package_version"]
            ):
                self.fail("PACKAGE_INSTALL_FAILED")
            if installed.returncode == 0:
                package_status = self.backend.run(
                    ["dpkg-query", "-W", "-f=${Status}", "jitterbit-agent"]
                )
                if (
                    package_status.returncode
                    or package_status.stdout.strip() != "install ok installed"
                ):
                    self.fail("PACKAGE_INSTALL_FAILED")
            if installed.returncode != 0:
                self._run_ok(
                    ["apt-get", "-o", "DPkg::Lock::Timeout=120", "update"],
                    "PACKAGE_INSTALL_FAILED",
                    env={"DEBIAN_FRONTEND": "noninteractive"},
                )
                self._run_ok(
                    [
                        "apt-get",
                        "-o",
                        "DPkg::Lock::Timeout=120",
                        "install",
                        "-y",
                        "odbcinst",
                        "unixodbc",
                        "unzip",
                    ],
                    "PACKAGE_INSTALL_FAILED",
                    env={"DEBIAN_FRONTEND": "noninteractive"},
                )
                self._run_ok(["install", "-d", "-m", "0700", staging], "PACKAGE_INSTALL_FAILED")
                package = f"{staging}/jitterbit-agent_{artifact['package_version']}_amd64.deb"
                if not self.backend.exists(package):
                    try:
                        self.backend.download(artifact["url"], package)
                    except FrameworkError:
                        self.fail("DOWNLOAD_FAILED")
                self._validate_package(package, artifact)
                self.changed = True
                self._run_ok(
                    ["dpkg", "--install", package],
                    "PACKAGE_INSTALL_FAILED",
                    env={"silent_install": "1", "DEBIAN_FRONTEND": "noninteractive"},
                )
            if not all(
                self.backend.exists(path) for path in ("/opt/jitterbit", RESOURCE_DIR, JITTERBIT)
            ):
                self.fail("PACKAGE_INSTALL_FAILED")
            self.advance("PACKAGE_INSTALLED")
            self.advance("OPTIONAL_CONFIGURATION_COMPLETE")

            if not credentials_before:
                if self.backend.exists(CREDENTIALS):
                    self.fail("STALE_CREDENTIALS_REINTRODUCED")
                try:
                    self.backend.write_private_json(
                        REGISTER_JSON, self._registration_document(config, token)
                    )
                except FrameworkError as exc:
                    self.fail(exc.spec.name)
                except Exception:
                    self.fail("CONFIGURATION_FAILED")
                self.changed = True
                if not self.backend.validate_json(REGISTER_JSON):
                    self.fail("REGISTER_JSON_INVALID")
                self.advance("REGISTER_JSON_CREATED")
            log_position = self.backend.log_position(AGENT_LOG)
            self._run_ok([JITTERBIT, "restart"], "LOCAL_SERVICE_FAILURE")
            self.advance("AGENT_RESTART_REQUESTED")
            self.advance("WAITING_FOR_AGENT_RUNTIME")

            timeout = config["health"]["registration_timeout_seconds"]
            interval = config["health"]["poll_interval_seconds"]
            started_at = self.backend.monotonic()
            deadline = started_at + timeout
            observed = set()
            log_seen = False
            log_available_after = None
            while self.backend.monotonic() <= deadline:
                if self.backend.exists(AGENT_LOG):
                    if not log_seen:
                        self.advance("AGENT_LOG_AVAILABLE")
                        log_seen = True
                        log_available_after = self.backend.monotonic() - started_at
                    log = self.backend.read_log_since(AGENT_LOG, log_position)
                    failure = self._runtime_failure(log)
                    if failure:
                        self.fail(failure)
                    current = self._observe(log, config["harmony"]["agent_group_id"])
                    for state in SUCCESS_MARKERS:
                        if state in current and state not in observed:
                            self.advance(state)
                    observed.update(current)
                required = {
                    "HARMONY_AUTHENTICATED",
                    "AGENT_LOGGED_IN",
                    "AGENT_SERVICES_CONNECTED",
                    "REQUEST_FLOW_STARTED",
                    "AGENT_SYNCHRONIZED",
                }
                if not credentials_before:
                    required.update({"AUTO_REGISTRATION_COMPLETED", "CREDENTIALS_CREATED"})
                if required <= observed and self.backend.exists(CREDENTIALS):
                    self._local_health()
                    if not credentials_before:
                        try:
                            self.backend.remove_registration_input(REGISTER_JSON)
                        except Exception:
                            self.fail("CONFIGURATION_FAILED")
                    self.advance("COMPLETE")
                    return {
                        "status": "COMPLETE",
                        "state": self.state,
                        "stateHistory": self.history.copy(),
                        "changed": self.changed,
                        "serviceRunning": True,
                        "harmonyRegistered": True,
                        "logAvailableAfterSeconds": log_available_after,
                        "registrationDurationSeconds": self.backend.monotonic() - started_at,
                    }
                self.backend.sleep(interval)
            if not self.backend.exists(CREDENTIALS):
                self.fail("CREDENTIALS_NOT_CREATED")
            if "HARMONY_AUTHENTICATED" in observed and "AGENT_SERVICES_CONNECTED" not in observed:
                self.fail("AGENT_SERVICES_CONNECTION_FAILED")
            if "AGENT_SERVICES_CONNECTED" in observed and "AGENT_SYNCHRONIZED" not in observed:
                self.fail("SYNCHRONIZATION_FAILED")
            self.fail("REGISTRATION_TIMEOUT")
        finally:
            token.clear()
