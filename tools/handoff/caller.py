"""Transport-independent caller contract; no vendor logs or PA lifecycle logic."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
OPERATIONS = {
    "INSTALL": ["install"],
    "REINSTALL": ["reinstall"],
    "HEALTH": ["health"],
    "DIAGNOSTICS": ["diagnostics"],
    "ENTERPRISE_CONFIGURE": ["enterprise"],
    "UNINSTALL": ["uninstall", "--complete"],
    "ARTIFACT_VERIFY": ["artifact", "verify"],
}


class HandoffError(Exception):
    pass


def validate(request):
    schema = json.loads((ROOT / "tools/handoff/request.schema.json").read_text())
    if not Draft202012Validator(schema).is_valid(request):
        raise HandoffError("REQUEST_INVALID")
    for field in ("configPath", "resultPath"):
        path = Path(request[field])
        if not path.is_absolute() or ".." in path.parts or "\x00" in request[field]:
            raise HandoffError("REQUEST_INVALID")
    if request["allowUnqualified"] and (
        not request.get("controlledTest", False)
        or request["operation"] not in {"INSTALL", "REINSTALL"}
    ):
        raise HandoffError("REQUEST_INVALID")
    if request["operation"] == "REINSTALL" and request["jbpaVersion"] == "1.0.0-rc2":
        raise HandoffError("OPERATION_UNAVAILABLE_IN_RC2")
    return request


def arguments(request, binary):
    validate(request)
    if not Path(binary).is_absolute() or ".." in Path(binary).parts or "\x00" in binary:
        raise HandoffError("REQUEST_INVALID")
    op = request["operation"]
    args = [binary, *OPERATIONS[op]]
    if op in {"INSTALL", "REINSTALL", "HEALTH", "ENTERPRISE_CONFIGURE", "UNINSTALL"}:
        args += ["--config", request["configPath"]]
    if op in {"INSTALL", "REINSTALL", "ARTIFACT_VERIFY"}:
        args += ["--version", request["paVersion"]]
    if op in {"INSTALL", "REINSTALL"}:
        args += ["--non-interactive"]
        if request.get("controlledTest", False):
            args += ["--controlled-test"]
        if request["allowUnqualified"]:
            args += ["--allow-unqualified"]
    if op == "ENTERPRISE_CONFIGURE":
        for field, option in (
            ("agentId", "--expected-agent-id"),
            ("agentGroupId", "--expected-agent-group-id"),
            ("agentName", "--expected-agent-name"),
            ("agentGroupName", "--expected-agent-group-name"),
        ):
            args += [option, str(request["expectedIdentity"][field])]
    args += ["--result-file", request["resultPath"]]
    return args


def consume(request, exit_code, text):
    """Return safe generic state only; never echo error messages or raw results."""
    if text is None:
        raise HandoffError("RESULT_FILE_MISSING")
    if not isinstance(text, str) or len(text.encode()) > 1048576:
        raise HandoffError("RESULT_SCHEMA_INVALID")
    try:
        data = json.loads(text)
        schema = json.loads((ROOT / "config/schemas/rc-result.schema.json").read_text())
        Draft202012Validator(schema).validate(data)
    except (ValueError, __import__("jsonschema").ValidationError):
        raise HandoffError("RESULT_SCHEMA_INVALID") from None
    expected = request["operation"]
    if data["operation"] != expected or data["versions"]["jbpa"] != request["jbpaVersion"]:
        raise HandoffError("RESULT_SCHEMA_INVALID")
    if type(exit_code) is not int or not 0 <= exit_code <= 255:
        raise HandoffError("REMOTE_EXECUTION_FAILED")
    success = (
        exit_code == 0
        and data["status"] == "SUCCESS"
        and data["category"] == "SUCCESS"
        and data["error"] is None
    )
    return {
        "success": success,
        "reason": "SUCCESS" if success else "JBPA_FAILED",
        "category": data["category"],
        "state": data["state"],
        "retryable": data["error"]["retryable"] if data["error"] else False,
        "exitCode": exit_code,
    }


class LocalTransport:
    """Already delivered/installed runtime; never invokes a shell or installs a VM."""

    def execute(self, target, argv):
        if target != "localhost":
            raise HandoffError("HOST_UNREACHABLE")
        try:
            return subprocess.run(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3600,
                check=False,
            ).returncode
        except (OSError, subprocess.TimeoutExpired):
            raise HandoffError("REMOTE_EXECUTION_FAILED") from None

    def retrieve(self, target, path):
        try:
            file = Path(path)
            if not file.exists():
                raise HandoffError("RESULT_FILE_MISSING")
            if file.is_symlink() or not file.is_file() or file.stat().st_size > 1048576:
                raise HandoffError("RESULT_SCHEMA_INVALID")
            return file.read_text()
        except FileNotFoundError:
            raise HandoffError("RESULT_FILE_MISSING") from None
        except (OSError, UnicodeError):
            raise HandoffError("RESULT_SCHEMA_INVALID") from None


def verify_delivery(archive, sha256, binary):
    """Verify exact release bytes and installed files against their archive manifest."""
    import tarfile

    from jbpa.errors import FrameworkError
    from jbpa.release import verify

    try:
        verify(archive, sha256)
        root = Path(binary).parent.parent
        with tarfile.open(archive, "r:gz") as tar:
            member = next(m for m in tar.getmembers() if m.name.endswith("/release-manifest.json"))
            manifest = json.loads(tar.extractfile(member).read())
        if Path(binary) != root / "bin/jbpa":
            raise HandoffError("RELEASE_DELIVERY_FAILED")
        for name, digest in manifest["files"].items():
            file = root / name
            if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                raise HandoffError("RELEASE_DELIVERY_FAILED")
    except (OSError, ValueError, FrameworkError, StopIteration, tarfile.TarError):
        raise HandoffError("RELEASE_DELIVERY_FAILED") from None


def run(request, binary, transport, *, archive, sha256):
    argv = arguments(request, binary)
    verify_delivery(archive, sha256, binary)
    # Unique destination prevents stale success from an earlier invocation.
    if isinstance(transport, LocalTransport) and Path(request["resultPath"]).exists():
        raise HandoffError("RESULT_DESTINATION_EXISTS")
    code = transport.execute(request["target"], argv)
    text = transport.retrieve(request["target"], request["resultPath"])
    return consume(request, code, text)


def main():
    parser = argparse.ArgumentParser(description="External LOCAL handoff test harness")
    parser.add_argument("--request", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.request).read_text())
        decision = run(
            request, args.binary, LocalTransport(), archive=args.release, sha256=args.sha256
        )
    except (HandoffError, OSError, ValueError) as exc:
        decision = {
            "success": False,
            "reason": str(exc) if isinstance(exc, HandoffError) else "REQUEST_INVALID",
        }
    print(json.dumps(decision, sort_keys=True))
    return 0 if decision["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
