"""Guarded in-place Linux PA upgrade preserving the existing registration."""

import os
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from . import artifacts, host_readiness
from .azure_identity import AzureKeyVaultSecretProvider, ManagedIdentity
from .bootstrap import SafeParser, _resolve_registration_fields
from .catalogue import load_catalogues
from .config import load_config
from .errors import FrameworkError
from .host_lock import HostLock
from .local_secrets import LocalFileSecretProvider
from .native_linux import CREDENTIALS, LocalBackend, NativeLinuxWorkflow
from .pending_operations import OperationQueryError, TranDbOperationProvider
from .restart_health import SupportToolsProbe
from .security import Secret
from .uninstall import UTILS, LocalUninstallBackend

ROOT = Path("/opt/jitterbit")
BACKUP_ROOT = Path("/var/lib/jbpa/backups")
BACKUP_FILES = (
    "jitterbit.conf",
    "JdbcDrivers.conf",
    "Resources/jitterbit-agent-config.properties",
    "apache/conf/httpd.conf",
    "jre/lib/security/cacerts",
)


def _version(value):
    try:
        parts = tuple(int(part) for part in value.split("."))
    except (AttributeError, ValueError):
        raise FrameworkError("UPGRADE_STATE_UNSUPPORTED") from None
    if len(parts) != 4:
        raise FrameworkError("UPGRADE_STATE_UNSUPPORTED")
    return parts


def _files():
    paths = [ROOT / name for name in BACKUP_FILES]
    paths.extend((ROOT / "apache/conf").glob("*.crt"))
    paths.extend((ROOT / "apache/conf").glob("*.key"))
    paths.extend((ROOT / "apache/conf/extra").glob("*.conf"))
    return sorted(set(paths))


def _backup(destination):
    if BACKUP_ROOT.is_symlink():
        raise FrameworkError("UPGRADE_BACKUP_FAILED")
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(BACKUP_ROOT, 0o700)
    destination.mkdir(parents=True, mode=0o700)
    os.chmod(destination, 0o700)
    saved = []
    for source in _files():
        if not source.exists():
            continue
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 32 * 1024 * 1024:
            raise FrameworkError("UPGRADE_BACKUP_FAILED")
        info = source.stat()
        target = destination / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output, source.open("rb") as original:
            shutil.copyfileobj(original, output)
            output.flush()
            os.fsync(output.fileno())
        saved.append((source, target, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)))
    if not any(source.name == "jitterbit.conf" for source, *_ in saved):
        raise FrameworkError("UPGRADE_BACKUP_FAILED")
    return saved


def _restore_changed(saved):
    restored = []
    for source, backup, uid, gid, mode in saved:
        if source.is_symlink() or (source.exists() and not source.is_file()):
            raise FrameworkError("UPGRADE_CONFIGURATION_FAILED")
        if source.exists() and source.read_bytes() == backup.read_bytes():
            continue
        source.parent.mkdir(parents=True, exist_ok=True)
        staging = source.with_name(source.name + ".jbpa-restore-" + uuid.uuid4().hex)
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output, backup.open("rb") as original:
            shutil.copyfileobj(original, output)
            os.fchown(output.fileno(), uid, gid)
            os.fchmod(output.fileno(), mode)
            output.flush()
            os.fsync(output.fileno())
        os.replace(staging, source)
        restored.append(str(source.relative_to(ROOT)))
    return restored


def _drain(backend, operations, policy, sleeper, monotonic):
    try:
        count = operations.active_count()
    except OperationQueryError:
        raise FrameworkError("ACTIVE_OPERATION_QUERY_FAILED") from None
    if backend.command([str(UTILS), "--drain-pause"]).returncode:
        raise FrameworkError("DRAIN_PAUSE_FAILED")
    try:
        count = operations.active_count()
    except OperationQueryError:
        raise FrameworkError("ACTIVE_OPERATION_QUERY_FAILED") from None
    deadline = monotonic() + policy["drain_pause_timeout_seconds"]
    while count:
        if monotonic() >= deadline:
            raise FrameworkError("DRAIN_PAUSE_TIMEOUT")
        sleeper(policy["operation_poll_interval_seconds"])
        try:
            count = operations.active_count()
        except OperationQueryError:
            raise FrameworkError("ACTIVE_OPERATION_QUERY_FAILED") from None
    if backend.command([str(UTILS), "--drain-stop"]).returncode:
        raise FrameworkError("DRAIN_STOP_FAILED")
    deadline = monotonic() + policy["stop_timeout_seconds"]
    while backend.agent_running():
        if monotonic() >= deadline:
            raise FrameworkError("DRAIN_STOP_TIMEOUT")
        sleeper(policy["stop_poll_interval_seconds"])


def _provider(config):
    secrets = config["secrets"]
    if secrets["provider"] == "local-file":
        return LocalFileSecretProvider(secrets["directory"])
    return AzureKeyVaultSecretProvider(
        secrets["vault_uri"], ManagedIdentity(secrets["managed_identity_client_id"])
    )


def execute(
    argv,
    *,
    backend=None,
    operations=None,
    identity=None,
    package_runner=None,
    verify_runner=None,
    readiness_probe=None,
    lock_factory=HostLock,
    sleeper=time.sleep,
    monotonic=time.monotonic,
):
    """Resolve and validate before mutation; return a secret-free result."""
    p = SafeParser(add_help=False)
    p.add_argument("--config", required=True)
    p.add_argument("--version")
    p.add_argument("--controlled-test", action="store_true")
    p.add_argument("--allow-unqualified", action="store_true")
    p.add_argument("--non-interactive", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    config, _ = load_config(args.config, args.version)
    catalogue, _ = load_catalogues()
    backend = backend or LocalUninstallBackend()
    identity = identity or SupportToolsProbe()
    operations = operations or TranDbOperationProvider()
    package_runner = package_runner or subprocess.run
    verify_runner = verify_runner or (
        lambda resolved, metadata: NativeLinuxWorkflow(LocalBackend()).run(
            resolved, metadata, Secret(None)
        )
    )
    result = {
        "operation": "UPGRADE",
        "status": "FAILED",
        "state": "UPGRADE_INITIALIZED",
        "requestedVersion": config["agent"]["version"],
        "changed": False,
        "error": None,
    }
    try:
        state = host_readiness.classify(backend.snapshot())
        if state != "AGENT_INSTALLED_REGISTERED":
            raise FrameworkError("UPGRADE_STATE_UNSUPPORTED")
        installed = backend.package_status().split("|", 1)[1]
        baseline = identity.about()
        if not baseline or identity.connection() is not True or not backend.agent_running():
            raise FrameworkError("UPGRADE_BASELINE_UNHEALTHY")
        with tempfile.TemporaryDirectory(prefix="jbpa-upgrade-") as folder:
            manifest, package = artifacts.inspect(
                config["agent"]["version"], folder, catalogue=catalogue
            )
            target = manifest["package_version"]
            result.update(
                installedVersion=installed, packageVersion=target, resolvedArtifact=manifest
            )
            from .release_cli import qualification_guard

            logical = manifest["logical_version"]
            entry = catalogue["versions"].get(logical)
            if entry is None:
                raise FrameworkError("LATEST_VERSION_NOT_QUALIFIED")
            classification = qualification_guard(
                config["agent"]["version"],
                entry,
                host_readiness.detect(),
                args.allow_unqualified,
                target,
            )
            result["qualificationClassification"] = classification
            if not args.controlled_test and (
                entry is None
                or entry["approval"] != "approved"
                or entry["artifact_status"] != "PRODUCTION_APPROVED"
                or entry["integrity"]["classification"] != "INDEPENDENTLY_VERIFIED"
            ):
                raise FrameworkError("ARTIFACT_NOT_APPROVED")
            if classification == "EXPERIMENTAL_VERSION_TEST" and not args.controlled_test:
                raise FrameworkError("ARTIFACT_NOT_APPROVED")
            if _version(target)[0] != _version(installed)[0]:
                raise FrameworkError("UPGRADE_MAJOR_REVIEW_REQUIRED")
            if _version(target) < _version(installed):
                raise FrameworkError("UPGRADE_DOWNGRADE_DENIED")
            if target == installed:
                result.update(status="ALREADY_CURRENT", state="ALREADY_CURRENT")
                return 0, result
            preflight = host_readiness.run(
                config,
                profile="HEALTH",
                controlled_test=args.controlled_test,
                dry_run=args.dry_run,
                probe=readiness_probe,
                package_bytes=manifest["byte_size"],
            )
            result["preflight"] = preflight
            if preflight["status"] == "FAIL":
                raise FrameworkError("PREFLIGHT_FAILED")
            if args.dry_run:
                result.update(status="PLANNED", state="UPGRADE_PLANNED")
                return 0, result
            if os.geteuid() != 0 or not args.non_interactive:
                raise FrameworkError("PREFLIGHT_FAILED")
            with lock_factory():
                if backend.package_status() != f"install ok installed|{installed}":
                    raise FrameworkError("UPGRADE_STATE_UNSUPPORTED")
                backup = BACKUP_ROOT / ("upgrade-" + uuid.uuid4().hex)
                saved = _backup(backup)
                result["backupDirectory"] = str(backup)
                result["state"] = "BACKUP_COMPLETE"
                _drain(backend, operations, config["uninstall_policy"], sleeper, monotonic)
                result["state"] = "OPERATIONS_DRAINED"
                completed = package_runner(
                    ["dpkg", "--install", str(package)],
                    env={**os.environ, "silent_install": "1", "DEBIAN_FRONTEND": "noninteractive"},
                    capture_output=True,
                    text=True,
                    timeout=1800,
                    check=False,
                )
                result["changed"] = True
                if (
                    completed.returncode
                    or backend.package_status() != f"install ok installed|{target}"
                ):
                    raise FrameworkError("PACKAGE_INSTALL_FAILED")
                result["state"] = "PACKAGE_UPGRADED"
                if not Path(CREDENTIALS).is_file():
                    raise FrameworkError("UPGRADE_REGISTRATION_LOST")
                result["restoredConfigurationFiles"] = _restore_changed(saved)
                secrets = _provider(config)
                try:
                    _resolve_registration_fields(config, secrets)
                finally:
                    secrets.clear()
                metadata = next(
                    (
                        artifact
                        for artifact in entry["artifacts"]
                        if artifact["os_id"] == preflight["platform"]["os"]
                        and artifact["os_version"] == preflight["platform"]["version"]
                    ),
                    None,
                )
                if metadata is None:
                    raise FrameworkError("UPGRADE_STATE_UNSUPPORTED")
                health = verify_runner(config, metadata)
                if (
                    health["status"] != "COMPLETE"
                    or health["serviceRunning"] is not True
                    or health["harmonyRegistered"] is not True
                ):
                    raise FrameworkError("UPGRADE_HEALTH_UNCONFIRMED")
                after = identity.about()
                if (
                    not after
                    or after.get("VersionNumber") != target
                    or any(
                        after.get(key) != baseline.get(key)
                        for key in ("Agent_Name", "Agent_Group_Name")
                    )
                    or identity.connection() is not True
                ):
                    raise FrameworkError("UPGRADE_IDENTITY_UNCONFIRMED")
                result.update(
                    status="COMPLETE",
                    state="UPGRADE_COMPLETE",
                    serviceRunning=True,
                    harmonyRegistered=True,
                )
    except FrameworkError as exc:
        result["error"] = exc.as_dict()
        return exc.spec.exitCode, result
    except (OSError, subprocess.TimeoutExpired):
        exc = FrameworkError("UPGRADE_CONFIGURATION_FAILED")
        result["error"] = exc.as_dict()
        return exc.spec.exitCode, result
    return 0, result
