"""Stable RC JSON facade over the proven lifecycle implementations."""

import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from . import __version__, artifacts, bootstrap, enterprise, health, restart_health, uninstall
from .catalogue import load_catalogues, resolve
from .config import ROOT, load_config, validate_schema
from .errors import ERRORS, FrameworkError, category
from .native_linux import CREDENTIALS, LocalBackend
from .platform import detect
from .results import write_result


class Parser(bootstrap.SafeParser):
    pass


def qualification_guard(requested, entry, host, allow=False, resolved_package=None):
    key = (
        f"{host['os']}-{host['version']}-amd64"
        if host["architecture"] == "x86_64"
        else "unsupported"
    )
    qualified = (
        entry is not None
        and (resolved_package is None or resolved_package == entry["package_version"])
        and entry["qualification"]["platforms"].get(key) == "TESTED_LIVE"
    )
    if entry and entry.get("approval") == "denied":
        raise FrameworkError("ARTIFACT_NOT_APPROVED")
    if entry and entry["qualification"]["overall"] in {"BLOCKED", "DEPRECATED"}:
        raise FrameworkError("VERSION_NOT_QUALIFIED")
    if not qualified and not allow:
        raise FrameworkError(
            "LATEST_VERSION_NOT_QUALIFIED" if requested == "latest" else "VERSION_NOT_QUALIFIED"
        )
    return "QUALIFIED_VERSION" if qualified else "EXPERIMENTAL_VERSION_TEST"


class PinnedBackend(LocalBackend):
    """Latest is acquired once. The existing workflow still checks SHA and dpkg fields."""

    def __init__(self, package):
        super().__init__()
        self.package = package

    def download(self, url, destination):
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output, self.package.open("rb") as source:
            shutil.copyfileobj(source, output)


def invoke(function, argv, **kwargs):
    stream = io.StringIO()
    code = function(argv, stdout=stream, **kwargs)
    return code, json.loads(stream.getvalue())


def install(
    argv, prepared=None, *, lock_held=False, readiness_profile="INSTALL", readiness_probe=None
):
    argv = list(argv)
    if "--config" not in argv:
        argv += ["--config", "/etc/jbpa/agent.yaml"]
    p = Parser(add_help=False)
    p.add_argument("--allow-unqualified", action="store_true")
    args, forwarded = p.parse_known_args(argv)
    parsed = bootstrap.parser().parse_args(forwarded)
    config, _ = load_config(parsed.config, parsed.version, os.environ)
    if parsed.controlled_test and config.get("artifact_policy", {}).get(
        "require_production_approval", False
    ):
        raise FrameworkError("ARTIFACT_NOT_APPROVED")
    requested = config["agent"]["version"]
    catalogue, support = load_catalogues()
    host = detect()
    with tempfile.TemporaryDirectory(prefix="jbpa-resolve-") as directory:
        manifest = None
        package_path = None
        if prepared or requested == "latest" or args.allow_unqualified:
            manifest, package_path = prepared or artifacts.inspect(
                requested, directory, catalogue=catalogue
            )
            logical = manifest["logical_version"] or ".".join(
                manifest["package_version"].split(".")[:2]
            )
            entry = catalogue["versions"].get(logical)
        else:
            logical, entry = resolve(requested, catalogue)
        classification = qualification_guard(
            requested,
            entry,
            host,
            args.allow_unqualified,
            manifest["package_version"] if manifest else entry["package_version"],
        )
        if not parsed.controlled_test and (
            not entry
            or entry.get("approval") != "approved"
            or entry.get("artifact_status") != "PRODUCTION_APPROVED"
            or entry.get("integrity", {}).get("classification") != "INDEPENDENTLY_VERIFIED"
        ):
            raise FrameworkError("ARTIFACT_NOT_APPROVED")
        if classification == "EXPERIMENTAL_VERSION_TEST" and not parsed.controlled_test:
            raise FrameworkError("ARTIFACT_NOT_APPROVED")
        if manifest:
            catalogue = copy.deepcopy(catalogue)
            support = copy.deepcopy(support)
            entry = copy.deepcopy(entry) if entry else {"approval": "pending", "artifacts": []}
            entry["artifacts"] = [
                {
                    "os_id": host["os"],
                    "os_version": host["version"],
                    "architecture": host["architecture"],
                    "package_kind": "deb",
                    "package_version": manifest["package_version"],
                    "url": manifest["request_url"],
                    "sha256": manifest["sha256"],
                    "adapter_profile": "native-deb-register-json",
                    "runtime_validation": "not_run",
                    "evidence_refs": [],
                }
            ]
            if parsed.controlled_test:
                entry["approval"] = "approved_for_test"
            catalogue["versions"][logical] = entry
            for platform in support["platforms"]:
                if platform["os_id"] == host["os"] and platform["os_version"] == host["version"]:
                    platform["agent_versions"].append(logical)
        # Exact-version overrides canonicalize to logical without changing the caller's request.
        forwarded += ["--version", logical]
        kwargs = {
            "catalogues_provider": lambda: (catalogue, support),
            "experimental": bool(manifest),
        }
        if package_path:
            kwargs["backend_factory"] = lambda: PinnedBackend(package_path)
        from contextlib import nullcontext

        from . import host_readiness

        preflight = host_readiness.run(
            config,
            profile=readiness_profile,
            host=host,
            controlled_test=parsed.controlled_test,
            dry_run=parsed.dry_run or config["execution"]["dry_run"],
            probe=readiness_probe,
            package_bytes=manifest.get("byte_size") if manifest else None,
        )
        if preflight["status"] == "FAIL" and not (parsed.dry_run or config["execution"]["dry_run"]):
            exc = FrameworkError("PREFLIGHT_FAILED")
            code, data = exc.spec.exitCode, {"status": "FAILED", "error": exc.as_dict()}
        else:
            if lock_held:
                kwargs["lock_factory"] = lambda path: nullcontext()
            code, data = invoke(bootstrap.execute, forwarded, **kwargs)
        data["preflight"] = preflight
        data["requestedVersion"] = requested
        data["qualificationClassification"] = classification
        data["qualification"] = {
            "required": True,
            "qualified": classification == "QUALIFIED_VERSION",
            "overrideRequested": args.allow_unqualified,
            "overrideUsed": classification == "EXPERIMENTAL_VERSION_TEST",
            "executionClassification": classification,
        }
        data["resolvedArtifact"] = manifest or {
            "package_version": entry["package_version"],
            "filename": entry["filename"],
            "sha256": entry["integrity"]["sha256"],
            "runtime_qualification": entry["qualification"]["overall"],
        }
        return code, data


def version(argv):
    p = Parser()
    p.add_argument("action", nargs="?", choices=["resolve", "list"])
    p.add_argument("requested", nargs="?")
    args = p.parse_args(argv)
    catalogue, _ = load_catalogues()
    if args.action == "list":
        if args.requested:
            raise FrameworkError("CONFIG_INVALID")
        return versions([])
    if args.action is None:
        return 0, {
            "jbpaVersion": __version__,
            "aliases": catalogue["aliases"],
            "recommendedPackage": catalogue["versions"][catalogue["aliases"]["recommended"]][
                "package_version"
            ],
            "dynamicLatest": "NOT_RESOLVED",
            "capabilities": [
                "INSTALL",
                "REINSTALL",
                "UNINSTALL",
                "HEALTH",
                "DIAGNOSTICS",
                "ENTERPRISE_CONFIGURE",
                "ARTIFACT_VERIFY",
                "VALIDATE",
                "VERSIONS",
                "UPGRADE",
            ],
        }
    if not args.requested:
        raise FrameworkError("CONFIG_INVALID")
    if args.requested == "latest":
        with tempfile.TemporaryDirectory(prefix="jbpa-latest-") as directory:
            manifest, _ = artifacts.inspect("latest", directory, catalogue=catalogue)
            return 0, manifest
    logical, entry = resolve(args.requested, catalogue)
    return 0, {
        "requested_version": args.requested,
        "logical_version": logical,
        **{
            k: entry[k]
            for k in (
                "package_version",
                "filename",
                "integrity",
                "artifact_status",
                "qualification",
            )
        },
    }


def versions(argv):
    p = Parser()
    p.parse_args(argv)
    catalogue, _ = load_catalogues()
    return 0, {
        "catalogueCount": len(catalogue["versions"]),
        "dynamicLatest": "MUTABLE_NOT_RESOLVED",
        "aliases": catalogue["aliases"],
        "versions": [
            {
                "version": logical,
                "packageVersion": entry["package_version"],
                "artifactStatus": entry["artifact_status"],
                "qualification": entry["qualification"]["overall"],
                "approval": entry["approval"],
            }
            for logical, entry in catalogue["versions"].items()
        ],
    }


def interactive_install(argv, *, reader=None, writer=None):
    """Confirm the exact inspected artifact on a real TTY, then run the same installer."""
    reader, writer = reader or sys.stdin, writer or sys.stderr
    if not reader.isatty() or "--non-interactive" in argv:
        raise FrameworkError("INTERACTIVE_TTY_REQUIRED")
    forwarded = [value for value in argv if value != "--interactive"]
    p = Parser(add_help=False)
    p.add_argument("--config", default="/etc/jbpa/agent.yaml")
    p.add_argument("--version")
    p.add_argument("--allow-unqualified", action="store_true")
    args, _ = p.parse_known_args(forwarded)
    config, _ = load_config(args.config, args.version)
    if args.version is None:
        default = config["agent"]["version"]
        writer.write(f"PA version [{default}] (or latest): ")
        writer.flush()
        selected = reader.readline().strip() or default
        forwarded += ["--version", selected]
    else:
        selected = args.version
    catalogue, _ = load_catalogues()
    with tempfile.TemporaryDirectory(prefix="jbpa-interactive-") as folder:
        writer.write(f"Inspecting {selected} before installation...\n")
        writer.flush()
        manifest, package = artifacts.inspect(selected, folder, catalogue=catalogue)
        entry = catalogue["versions"].get(manifest["logical_version"])
        qualification_guard(
            selected, entry, detect(), args.allow_unqualified, manifest["package_version"]
        )
        writer.write(
            f"Package: {manifest['package_version']}\n"
            f"SHA-256: {manifest['sha256']}\n"
            f"Qualification: {manifest['runtime_qualification']}\n"
            f"Config: {args.config}\n"
            "Type INSTALL to proceed: "
        )
        writer.flush()
        if reader.readline().strip() != "INSTALL":
            raise FrameworkError("INTERACTIVE_ABORTED")
        return install(forwarded + ["--non-interactive"], prepared=(manifest, package))


def artifact(argv):
    p = Parser()
    p.add_argument("action", choices=["list", "inspect", "verify", "intake"])
    p.add_argument("--version")
    p.add_argument("--all-unqualified", action="store_true")
    p.add_argument("--metadata-dir", default=str(ROOT / "artifacts/metadata"))
    p.add_argument("--cache-dir")
    p.add_argument("--file")
    p.add_argument("--latest-observation")
    args = p.parse_args(argv)
    catalogue, _ = load_catalogues()
    if args.action == "list":
        return 0, {
            "dynamic_sources": catalogue["dynamic_sources"],
            "versions": [
                {
                    "logical_version": v,
                    "package_version": e["package_version"],
                    "artifact_status": e["artifact_status"],
                    "qualification": e["qualification"],
                }
                for v, e in catalogue["versions"].items()
            ],
        }
    if args.all_unqualified:
        if args.action != "intake" or args.version:
            raise FrameworkError("CONFIG_INVALID")
        results = artifacts.intake_all(args.metadata_dir, catalogue)
        return (20 if any(r["status"] == "FAILED" for r in results) else 0), {"results": results}
    if not args.version:
        raise FrameworkError("CONFIG_INVALID")
    with tempfile.TemporaryDirectory(prefix="jbpa-artifact-") as directory:
        manifest, path = artifacts.inspect(
            args.version, directory, catalogue=catalogue, local_file=args.file
        )
        if args.action == "verify":
            expected = (
                catalogue["versions"]
                .get(manifest["logical_version"], {})
                .get("integrity", {})
                .get("sha256")
            )
            if expected is None:
                raise FrameworkError("INSTALLER_METADATA_MISSING")
            manifest["verification"] = "MATCHED_CATALOGUE_LOCAL_DIGEST"
        if args.action == "intake":
            manifest["metadata_file"] = artifacts.save_metadata(
                {k: v for k, v in manifest.items() if k != "verification"}, args.metadata_dir
            )
        if args.cache_dir:
            manifest["cache_path"] = str(artifacts.cache_artifact(manifest, path, args.cache_dir))
        if args.version == "latest" and args.latest_observation:
            manifest["latest_observation_status"] = artifacts.latest_change(
                manifest, args.latest_observation
            )
        return 0, manifest


def diagnostics(argv):
    p = Parser()
    p.add_argument("--profile", default="STEADY_STATE_EXISTING_AGENT")
    args = p.parse_args(argv)
    catalogue, _ = load_catalogues()
    installed = None
    state = "UNAVAILABLE"
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Version} ${Status}", "jitterbit-agent"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0:
            installed = result.stdout.split()[0]
            state = (
                "INSTALLED" if "install ok installed" in result.stdout else "RESIDUAL_OR_REMOVED"
            )
    except (OSError, subprocess.TimeoutExpired):
        pass
    matched = next(
        (e for e in catalogue["versions"].values() if e["package_version"] == installed), None
    )
    probe = restart_health.SupportToolsProbe()
    try:
        from .pending_operations import OperationQueryError, TranDbOperationProvider

        count = TranDbOperationProvider().active_count()
    except (OperationQueryError, OSError):
        count = None
    try:
        local = subprocess.run(
            ["/opt/jitterbit/bin/jitterbit", "status"], capture_output=True, timeout=15, check=False
        )
        core = restart_health.core_services(local.stdout.decode(errors="replace"), local.returncode)
    except (OSError, subprocess.TimeoutExpired):
        core = None
    return 0, {
        "platform": detect(),
        "jbpaVersion": __version__,
        "installedVersion": installed,
        "packageState": state,
        "credentialsPresent": Path(CREDENTIALS).is_file(),
        "agentIdentity": probe.about(),
        "connectionCheck": probe.connection(),
        "coreServicesHealthy": core,
        "activeOperationCount": count,
        "catalogueStatus": "KNOWN" if matched else "UNKNOWN",
        "artifactQualification": matched["artifact_status"] if matched else None,
        "currentHealthProfile": args.profile,
        "healthConfirmed": False,
    }


def health_command(argv):
    p = Parser(add_help=False)
    p.add_argument("--config")
    args, forwarded = p.parse_known_args(argv)
    if args.config:
        config, _ = load_config(args.config)
        identity = config["health"].get("expected_identity")
        if not identity:
            raise FrameworkError("CONFIG_INVALID")
        if "--profile" not in forwarded:
            forwarded += [
                "--profile",
                config["health"].get("profile", "STEADY_STATE_EXISTING_AGENT"),
            ]
        for field, option in [
            ("agent_id", "--expected-agent-id"),
            ("group_id", "--expected-agent-group-id"),
            ("agent_name", "--expected-agent-name"),
            ("group_name", "--expected-agent-group-name"),
            ("package_version", "--expected-version"),
        ]:
            if option not in forwarded:
                forwarded += [option, str(identity[field])]
    if "--profile" in forwarded:
        return invoke(restart_health.execute, forwarded)
    if forwarded:
        raise FrameworkError("CONFIG_INVALID")
    return invoke(lambda args, **kw: health.execute(**kw), [])


def uninstall_command(argv):
    p = Parser(add_help=False)
    p.add_argument("--config")
    args, forwarded = p.parse_known_args(argv)
    if args.config:
        config, _ = load_config(args.config)
        for key, value in config.get("uninstall_policy", {}).items():
            option = "--" + key.replace("_", "-")
            if option not in forwarded:
                forwarded += [option, str(value)]
    return invoke(uninstall.execute, forwarded)


def dispatch(command, argv):
    if command == "version":
        return version(argv)
    if command == "versions":
        return versions(argv)
    if command == "artifact":
        return artifact(argv)
    if command == "install":
        if "--interactive" in argv:
            return interactive_install(argv)
        return install(argv)
    if command == "reinstall":
        from .reinstall import execute

        return execute(argv)
    if command == "upgrade":
        from .upgrade import execute

        return execute(argv)
    if command == "uninstall":
        return uninstall_command(argv)
    if command == "enterprise":
        return invoke(enterprise.execute, argv)
    if command in {"health", "enterprise-health"}:
        return health_command(argv)
    if command == "diagnostics":
        return diagnostics(argv)
    if command == "validate":
        from .host_readiness import run

        p = Parser()
        p.add_argument("--config", required=True)
        p.add_argument("--version")
        p.add_argument(
            "--profile", choices=["INSTALL", "REINSTALL", "HEALTH", "UNINSTALL"], default="INSTALL"
        )
        p.add_argument("--controlled-test", action="store_true")
        p.add_argument("--dry-run", action="store_true")
        a = p.parse_args(argv)
        config, _ = load_config(a.config, a.version)
        result = run(
            config, profile=a.profile, controlled_test=a.controlled_test, dry_run=a.dry_run
        )
        data = {"preflight": result, "platform": result["platform"], "status": result["status"]}
        if result["status"] == "FAIL":
            exc = FrameworkError("PREFLIGHT_FAILED")
            data["error"] = exc.as_dict()
            return exc.spec.exitCode, data
        return 0, data
    if command == "regression":
        from .qualification import regression

        return regression(argv)
    raise FrameworkError("CONFIG_INVALID")


def envelope(command, code, data):
    error = data.get("error")
    if code and not error:
        name = (
            "HEALTH_CHECK_FAILED"
            if command in {"health", "enterprise-health"}
            else "REGRESSION_FAILED"
            if command == "regression"
            else "DOWNLOAD_FAILED"
            if command == "artifact"
            else "INTERNAL_ERROR"
        )
        error = FrameworkError(name).as_dict()
    if error:
        spec = ERRORS.get(error.get("name"), ERRORS["INTERNAL_ERROR"])
        error = {**error, "category": category(spec)}
    artifact_data = data.get(
        "resolvedArtifact", data if command == "artifact" and "sha256" in data else {}
    )
    result = {
        "schemaVersion": "1.0",
        "runId": data.get("runId", "jbpa-" + uuid.uuid4().hex),
        "operation": data.get(
            "operation",
            {"enterprise": "ENTERPRISE_CONFIGURE", "artifact": "ARTIFACT"}.get(
                command, command.upper()
            ),
        ),
        "status": "SUCCESS" if code == 0 else "FAILED",
        "state": data.get("state", data.get("status", "COMPLETE" if code == 0 else "FAILED")),
        "versions": {
            "jbpa": __version__,
            "requestedPA": data.get("requestedVersion", data.get("requested_version")),
            "resolvedPA": data.get("packageVersion", data.get("package_version")),
        },
        "artifact": {**artifact_data, "qualification": artifact_data.get("runtime_qualification")},
        "platform": data.get("platform", {}),
        "registration": {"harmonyRegistered": data.get("harmonyRegistered")},
        "health": data.get(
            "health",
            {
                "scope": data.get("scope"),
                "serviceRunning": data.get("serviceRunning"),
                "harmonyConfirmed": data.get("harmonyRegistered"),
            },
        ),
        "enterpriseConfiguration": data.get("enterpriseConfiguration", {}),
        "error": error,
        "category": error["category"] if error else "SUCCESS" if code == 0 else "RELEASE_ERROR",
        "details": data,
    }
    validate_schema(result, "rc-result")
    return result


def main(argv=None, stdout=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    destination = None
    command = argv.pop(0) if argv else "help"
    try:
        if "--result-file" in argv:
            index = argv.index("--result-file")
            destination = argv[index + 1]
            del argv[index : index + 2]
        if command in {"--help", "help"} or "--help" in argv:
            stdout.write(
                "jbpa: install reinstall upgrade uninstall health diagnostics validate enterprise artifact regression version versions\n"
            )
            return 0
        code, data = dispatch(command, argv)
        if command == "artifact" and argv:
            data["operation"] = "ARTIFACT_" + argv[0].upper()
    except FrameworkError as exc:
        code, data = exc.spec.exitCode, {"error": exc.as_dict()}
    except (Exception, SystemExit):
        exc = FrameworkError("CONFIG_INVALID")
        code, data = exc.spec.exitCode, {"error": exc.as_dict()}
    result = envelope(command, code, data)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if destination:
        try:
            write_result(destination, text)
        except FrameworkError as exc:
            code = exc.spec.exitCode
            text = json.dumps(envelope(command, code, {"error": exc.as_dict()}), indent=2) + "\n"
    stdout.write(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
