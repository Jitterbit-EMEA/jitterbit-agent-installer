"""Controlled RC9 SSH caller for a pre-provisioned Ubuntu 24.04 QA VM.

The caller handles transport and a small result contract. JBPA on the VM owns
Private Agent lifecycle work. No Harmony credential value crosses this caller.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
RELEASE = "jbpa-1.0.0-rc9"
EXPECTED_SHA256 = "596cba1ee7c6c4ce2468aa3c1d6955a238a0bd63e4a60c27866c22b2587f9231"
ARCHIVE = ROOT / "dist" / f"{RELEASE}.tar.gz"
REMOTE_ROOT = PurePosixPath("/opt/jbpa/releases")
REMOTE_RELEASE = REMOTE_ROOT / RELEASE
RESULTS = PurePosixPath("/var/lib/jbpa/results")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")
SAFE_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
RESULT_PATH = re.compile(
    r"Private result: (/var/lib/jbpa/results/customer-install-[A-Za-z0-9-]+\.json)"
)
MAX_OUTPUT = 1_048_576
READ_RESULT = (
    "import os,stat,sys; p=sys.argv[1]; "
    "f=os.open(p,os.O_RDONLY|os.O_NOFOLLOW); s=os.fstat(f); "
    "sys.exit(2) if not stat.S_ISREG(s.st_mode) or s.st_size>1048576 else None; "
    "sys.stdout.buffer.write(os.read(f,1048577))"
)
CHECK_FILES = (
    "import hashlib,pathlib,sys; root=pathlib.Path(sys.argv[1]); "
    "lines=(root/'SHA256SUMS').read_text().splitlines(); "
    "assert lines and all(len(x.split('  ',1))==2 and "
    "(root/x.split('  ',1)[1]).resolve().is_relative_to(root.resolve()) and "
    "hashlib.sha256((root/x.split('  ',1)[1]).read_bytes()).hexdigest()==x.split('  ',1)[0] "
    "for x in lines)"
)


class RemoteError(Exception):
    pass


def _path(value: object, *, local: bool) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise RemoteError("INVENTORY_INVALID")
    path = Path(value) if local else PurePosixPath(value)
    if ".." in path.parts or (local and not path.is_file()):
        raise RemoteError("INVENTORY_INVALID")
    return value


def load_target(inventory: Path, name: str) -> dict[str, str]:
    try:
        document = json.loads(inventory.read_text())
        if set(document) != {"schemaVersion", "targets"} or document["schemaVersion"] != 1:
            raise RemoteError("INVENTORY_INVALID")
        target = document["targets"][name]
        required = {"host", "user", "identityFile", "knownHostsFile"}
        if not required <= set(target) or set(target) - required - {"credentialsFile"}:
            raise RemoteError("INVENTORY_INVALID")
        if not SAFE_HOST.fullmatch(target["host"]) or not SAFE_NAME.fullmatch(target["user"]):
            raise RemoteError("INVENTORY_INVALID")
        for field in ("identityFile", "knownHostsFile"):
            _path(target[field], local=True)
        if "credentialsFile" in target:
            _path(target["credentialsFile"], local=False)
        return target
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise RemoteError("INVENTORY_INVALID") from exc


def archive_digest(archive: Path) -> str:
    if not archive.is_file():
        raise RemoteError("RELEASE_MISSING")
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != EXPECTED_SHA256:
        raise RemoteError("JBPA_RELEASE_HASH_MISMATCH")
    return digest.hexdigest()


def pinned_manifest_digest(archive: Path) -> str:
    """Read the file manifest only after authenticating the immutable archive."""
    archive_digest(archive)
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            member = bundle.extractfile(f"{RELEASE}/SHA256SUMS")
            if member is None:
                raise RemoteError("RELEASE_MANIFEST_INVALID")
            return hashlib.sha256(member.read()).hexdigest()
    except (OSError, tarfile.TarError, KeyError) as exc:
        raise RemoteError("RELEASE_MANIFEST_INVALID") from exc


class SSH:
    def __init__(self, target: dict[str, str]):
        self.address = f"{target['user']}@{target['host']}"
        self.options = [
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={target['knownHostsFile']}",
            "-o",
            "ConnectTimeout=10",
            "-i",
            target["identityFile"],
        ]

    def run(self, argv: list[str], *, timeout: int = 60) -> tuple[int, str]:
        try:
            result = subprocess.run(
                ["ssh", *self.options, "-T", self.address, shlex.join(argv)],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RemoteError("REMOTE_EXECUTION_FAILED") from exc
        if len(result.stdout) > MAX_OUTPUT or len(result.stderr) > MAX_OUTPUT:
            raise RemoteError("REMOTE_OUTPUT_TOO_LARGE")
        return result.returncode, result.stdout.decode("utf-8", errors="replace")

    def require(self, argv: list[str], reason: str, *, timeout: int = 60) -> str:
        code, output = self.run(argv, timeout=timeout)
        if code:
            raise RemoteError(reason)
        return output

    def copy(self, local: Path, remote: PurePosixPath) -> None:
        try:
            result = subprocess.run(
                ["scp", *self.options, "-q", str(local), f"{self.address}:{remote}"],
                capture_output=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RemoteError("RELEASE_DELIVERY_FAILED") from exc
        if result.returncode:
            raise RemoteError("RELEASE_DELIVERY_FAILED")

    def result(self, path: PurePosixPath) -> dict:
        raw = self.require(
            ["sudo", "-n", "python3", "-c", READ_RESULT, str(path)],
            "RESULT_FILE_MISSING",
        )
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise RemoteError("RESULT_INVALID") from exc


def deliver_release(ssh: SSH, archive: Path) -> None:
    expected_manifest = pinned_manifest_digest(archive)
    exists, _ = ssh.run(["sudo", "-n", "test", "-e", str(REMOTE_RELEASE)])
    if exists == 0:
        verify_release(ssh, expected_manifest)
        return
    stage = ssh.require(["mktemp", "-d", "/var/tmp/jbpa-remote-XXXXXX"], "RELEASE_DELIVERY_FAILED")
    stage = stage.strip()
    if not re.fullmatch(r"/var/tmp/jbpa-remote-[A-Za-z0-9]+", stage):
        raise RemoteError("RELEASE_DELIVERY_FAILED")
    remote_archive = PurePosixPath(stage) / archive.name
    try:
        ssh.copy(archive, remote_archive)
        observed = ssh.require(["sha256sum", str(remote_archive)], "JBPA_RELEASE_HASH_MISMATCH")
        if observed.split(maxsplit=1)[0] != EXPECTED_SHA256:
            raise RemoteError("JBPA_RELEASE_HASH_MISMATCH")
        ssh.require(
            ["sudo", "-n", "test", "!", "-e", str(REMOTE_RELEASE)], "RELEASE_ALREADY_PRESENT"
        )
        ssh.require(
            ["sudo", "-n", "install", "-d", "-m", "0755", str(REMOTE_ROOT)],
            "RELEASE_DELIVERY_FAILED",
        )
        ssh.require(
            ["sudo", "-n", "tar", "-xzf", str(remote_archive), "-C", str(REMOTE_ROOT)],
            "RELEASE_DELIVERY_FAILED",
            timeout=180,
        )
        verify_release(ssh, expected_manifest)
    finally:
        for command in (["rm", "-f", str(remote_archive)], ["rmdir", stage]):
            try:
                ssh.run(command)
            except RemoteError:
                pass


def verify_release(ssh: SSH, expected_manifest: str) -> None:
    observed = ssh.require(
        ["sudo", "-n", "sha256sum", str(REMOTE_RELEASE / "SHA256SUMS")],
        "RELEASE_MANIFEST_INVALID",
    )
    if observed.split(maxsplit=1)[0] != expected_manifest:
        raise RemoteError("RELEASE_MANIFEST_INVALID")
    ssh.require(
        ["sudo", "-n", "python3", "-c", CHECK_FILES, str(REMOTE_RELEASE)],
        "RELEASE_MANIFEST_INVALID",
        timeout=180,
    )


def validate_result(data: dict, action: str, exit_code: int) -> dict:
    expected = {"status": "DIAGNOSTICS", "versions": "VERSIONS"}.get(action, action.upper())
    if (
        not isinstance(data, dict)
        or data.get("schemaVersion") != "1.0"
        or data.get("operation") != expected
        or not isinstance(data.get("versions"), dict)
        or data["versions"].get("jbpa") != "1.0.0-rc9"
        or data.get("status") not in {"SUCCESS", "FAILED"}
        or data.get("category") is None
        or not isinstance(data.get("details"), dict)
    ):
        raise RemoteError("RESULT_INVALID")
    success = (
        exit_code == 0
        and data["status"] == "SUCCESS"
        and data["category"] == "SUCCESS"
        and data.get("error") is None
    )
    if action == "install":
        registration = data.get("registration")
        health = data.get("health")
        success = (
            success
            and isinstance(registration, dict)
            and registration.get("harmonyRegistered") is True
        )
        success = success and isinstance(health, dict) and health.get("serviceRunning") is True
    return {
        "status": "SUCCESS" if success else "FAILED",
        "operation": expected,
        "state": data.get("state"),
        "category": data.get("category"),
        "error": data.get("error", {}).get("name") if isinstance(data.get("error"), dict) else None,
        "runId": data.get("runId"),
        "jbpaVersion": data["versions"]["jbpa"],
        "resolvedPA": data["versions"].get("resolvedPA"),
        "registration": data.get("registration") if action == "install" else None,
        "health": data.get("health") if action in {"install", "health"} else None,
        "details": data["details"] if action in {"status", "versions"} else None,
    }


def preflight_transport(ssh: SSH) -> None:
    ssh.require(["sudo", "-n", "true"], "SUDO_UNAVAILABLE")
    release = ssh.require(["cat", "/etc/os-release"], "HOST_PLATFORM_UNEXPECTED")
    fields = dict(line.split("=", 1) for line in release.splitlines() if "=" in line)
    arch = ssh.require(["uname", "-m"], "HOST_PLATFORM_UNEXPECTED").strip()
    if (
        fields.get("ID", "").strip('"') != "ubuntu"
        or fields.get("VERSION_ID", "").strip('"') != "24.04"
        or arch != "x86_64"
    ):
        raise RemoteError("HOST_PLATFORM_UNEXPECTED")


def operate(ssh: SSH, target: dict[str, str], action: str, version: str | None) -> dict:
    preflight_transport(ssh)
    binary = str(REMOTE_RELEASE / "bin/jbpa")
    if action == "install":
        deliver_release(ssh, ARCHIVE)
        command = ["sudo", "-n", str(REMOTE_RELEASE / "bin/jbpa-install"), "--non-interactive"]
        if "credentialsFile" in target:
            command += ["--credentials-file", target["credentialsFile"]]
        command += ["--version", version]
        code, output = ssh.run(command, timeout=1800)
        match = RESULT_PATH.search(output)
        if not match:
            raise RemoteError("INSTALL_RESULT_UNAVAILABLE" if code == 0 else "INSTALL_FAILED")
        result_path = PurePosixPath(match.group(1))
        data = ssh.result(result_path)
    else:
        result_path = RESULTS / f"remote-{action}-{uuid.uuid4().hex}.json"
        command = ["sudo", "-n", binary]
        if action == "status":
            command += ["diagnostics"]
        elif action == "versions":
            command += ["versions"]
        elif action == "health":
            command += ["health", "--config", "/etc/jbpa/agent.yaml"]
        elif action == "upgrade":
            command += [
                "upgrade",
                "--config",
                "/etc/jbpa/agent.yaml",
                "--version",
                version,
                "--non-interactive",
                "--controlled-test",
            ]
        elif action == "uninstall":
            command += ["uninstall", "--config", "/etc/jbpa/agent.yaml", "--complete"]
        command += ["--result-file", str(result_path)]
        code, _ = ssh.run(command, timeout=1800 if action in {"upgrade", "uninstall"} else 180)
        data = ssh.result(result_path)
    summary = validate_result(data, action, code)
    summary["resultPath"] = str(result_path)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Controlled RC9 SSH lifecycle on one pre-provisioned QA VM"
    )
    parser.add_argument(
        "action", choices=["install", "upgrade", "uninstall", "status", "health", "versions"]
    )
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--version")
    args = parser.parse_args(argv)
    try:
        if args.action in {"install", "upgrade"} and not args.version:
            raise RemoteError("VERSION_REQUIRED")
        if args.version and not re.fullmatch(r"(?:latest|[0-9]+(?:\.[0-9]+){1,3})", args.version):
            raise RemoteError("VERSION_INVALID")
        if args.action not in {"install", "upgrade"} and args.version:
            raise RemoteError("VERSION_UNEXPECTED")
        target = load_target(args.inventory, args.target)
        result = operate(SSH(target), target, args.action, args.version)
        result["target"] = args.target
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "SUCCESS" else 1
    except RemoteError as exc:
        print(json.dumps({"status": "FAILED", "target": args.target, "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
