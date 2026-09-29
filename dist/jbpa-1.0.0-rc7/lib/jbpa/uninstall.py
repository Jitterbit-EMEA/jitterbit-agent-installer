"""Fail-safe native Linux decommission; Harmony identity is never deleted here."""

import argparse
import json
import os
import pwd
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .errors import FrameworkError
from .host_lock import HostLock
from .pending_operations import OperationQueryError, TranDbOperationProvider
from .results import write_result

ROOT = Path("/opt/jitterbit")
JITTERBIT = ROOT / "bin/jitterbit"
UTILS = ROOT / "bin/jitterbit-utils"
COMMANDS = ("jitterbit", "jitterbit-config", "jitterbit-utils")
PLAN = [
    "Would query active Jitterbit operations",
    "Would request drain-pause and poll until active operations reach zero",
    "Would request drain-stop and verify all product processes stop",
    "Would remove and purge jitterbit-agent with the package manager",
    "Would remove the jitterbit user and residual /opt/jitterbit state",
    "Would verify registration files, PostgreSQL, commands, processes and startup integration are absent",
    "Harmony agent deletion is not performed",
]


def _now():
    return datetime.now(timezone.utc).isoformat()


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise FrameworkError("CONFIG_INVALID")


def parser():
    p = SafeParser(description="Gracefully decommission a native Linux Jitterbit agent")
    p.add_argument("--complete", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--remove-harmony-agent", action="store_true")
    p.add_argument("--result-file")
    p.add_argument("--drain-pause-timeout-seconds", type=int, default=1800)
    p.add_argument("--operation-poll-interval-seconds", type=int, default=5)
    p.add_argument("--stop-timeout-seconds", type=int, default=300)
    p.add_argument("--stop-poll-interval-seconds", type=int, default=5)
    return p


class LocalUninstallBackend:
    """Only exact product paths and verified product-owned links are mutated."""

    def __init__(self, *, runner=subprocess.run, sleeper=time.sleep, monotonic=time.monotonic):
        self.runner = runner
        self.sleeper = sleeper
        self.monotonic = monotonic

    def command(self, argv, *, timeout=180):
        try:
            return self.runner(argv, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            return subprocess.CompletedProcess(argv, 1, "", "")

    def package_status(self):
        result = self.command(["dpkg-query", "-W", "-f=${Status}|${Version}", "jitterbit-agent"])
        return result.stdout.strip() if result.returncode == 0 else None

    def user_exists(self):
        try:
            pwd.getpwnam("jitterbit")
            return True
        except KeyError:
            return False

    def product_processes(self):
        pids = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                executable = os.readlink(entry / "exe")
                if executable.startswith(str(ROOT) + "/"):
                    pids.append(int(entry.name))
            except (OSError, PermissionError):
                continue
        return pids

    def agent_running(self):
        """Drain-stop need only stop the four agent services; package removal stops bundled support runtimes."""
        if not JITTERBIT.exists():
            return bool(self.product_processes())
        status = self.command([str(JITTERBIT), "status"], timeout=30).stdout
        stopped = "0 out of 4 services are running" in status and all(
            f"{name} is not running" in status
            for name in (
                "JitterbitProcessEngine",
                "JitterbitScheduler",
                "JitterbitFileCleanup",
                "JitterbitVerboseLogShipper",
            )
        )
        return not stopped

    def command_links(self):
        paths = []
        for name in COMMANDS:
            path = Path("/usr/bin") / name
            if path.is_symlink() or path.exists():
                paths.append(path)
        return paths

    def startup_paths(self):
        paths = [Path("/etc/init.d/jitterbit"), Path("/etc/sysconfig/jitterbit")]
        paths.extend(Path("/etc/systemd/system").glob("jitterbit.service"))
        for directory in Path("/etc").glob("rc*.d"):
            paths.extend(directory.glob("*jitterbit"))
        return [p for p in paths if p.exists() or p.is_symlink()]

    def snapshot(self):
        return {
            "packageStatus": self.package_status(),
            "userPresent": self.user_exists(),
            "rootPresent": ROOT.exists() or ROOT.is_symlink(),
            "credentialsPresent": (ROOT / "Resources/credentials.txt").exists(),
            "registerPresent": (ROOT / "Resources/register.json").exists(),
            "postgresRuntimePresent": (ROOT / "pgsql").exists(),
            "postgresDataPresent": (ROOT / "DataInterchange/pgsql").exists(),
            "processCount": len(self.product_processes()),
            "commandPathsPresent": [str(p) for p in self.command_links()],
            "startupPathsPresent": [str(p) for p in self.startup_paths()],
        }

    def remove_package(self):
        result = self.command(
            [
                "apt-get",
                "-o",
                "DPkg::Lock::Timeout=120",
                "remove",
                "--autoremove",
                "-y",
                "jitterbit-agent",
            ],
            timeout=900,
        )
        if result.returncode:
            raise FrameworkError("PACKAGE_REMOVE_FAILED")
        status = self.package_status()
        if status and status.startswith("deinstall ok config-files"):
            result = self.command(["dpkg", "--purge", "jitterbit-agent"], timeout=300)
            if result.returncode:
                raise FrameworkError("PACKAGE_REMOVE_FAILED")
        if self.package_status() is not None:
            raise FrameworkError("PACKAGE_REMOVE_FAILED")

    def remove_user(self):
        if self.user_exists():
            result = self.command(["userdel", "--remove", "--force", "jitterbit"], timeout=120)
            if result.returncode or self.user_exists():
                raise FrameworkError("USER_REMOVE_FAILED")

    def remove_residuals(self):
        if self.package_status() is not None:
            raise FrameworkError("RESIDUAL_CLEANUP_FAILED")
        try:
            if ROOT.is_symlink():
                raise FrameworkError("RESIDUAL_CLEANUP_FAILED")
            if ROOT.is_dir():
                shutil.rmtree(ROOT)
            for path in self.command_links():
                if not path.is_symlink() or not os.readlink(path).startswith(str(ROOT) + "/"):
                    raise FrameworkError("COMMAND_LINK_REMAINS")
                path.unlink()
            for path in self.startup_paths():
                if path.is_symlink():
                    target = os.readlink(path)
                    if target not in ("../init.d/jitterbit", "/etc/init.d/jitterbit"):
                        raise FrameworkError("STARTUP_INTEGRATION_REMAINS")
                    path.unlink()
                elif path in (Path("/etc/init.d/jitterbit"), Path("/etc/sysconfig/jitterbit")):
                    path.unlink()
                else:
                    raise FrameworkError("STARTUP_INTEGRATION_REMAINS")
            self.command(["systemctl", "daemon-reload"], timeout=30)
        except (OSError, shutil.Error) as exc:
            raise FrameworkError("RESIDUAL_CLEANUP_FAILED") from exc


class UninstallWorkflow:
    def __init__(self, backend, provider, *, sleeper=time.sleep, monotonic=time.monotonic):
        self.backend = backend
        self.provider = provider
        self.sleeper = sleeper
        self.monotonic = monotonic

    def _count(self):
        try:
            return self.provider.active_count()
        except OperationQueryError as exc:
            raise FrameworkError("ACTIVE_OPERATION_QUERY_FAILED") from exc

    def _command(self, argv, error):
        result = self.backend.command(argv)
        if result.returncode:
            raise FrameworkError(error)

    def _stop_wait(self, timeout, interval):
        deadline = self.monotonic() + timeout
        while self.monotonic() <= deadline:
            if not self.backend.agent_running():
                return True
            self.sleeper(interval)
        return False

    def run(self, result, args):
        history = result["stateHistory"]
        advance = history.append
        initial = self.backend.snapshot()
        result["initial"] = initial
        advance("CURRENT_STATE_CAPTURED")
        installed = bool(
            initial["packageStatus"] and initial["packageStatus"].startswith("install ok installed")
        )
        if not installed and not any(
            (
                initial["userPresent"],
                initial["rootPresent"],
                initial["processCount"],
                initial["commandPathsPresent"],
                initial["startupPathsPresent"],
            )
        ):
            result["status"] = "ALREADY_UNINSTALLED"
            result["final"] = initial
            result["localUninstall"].update(
                packageRemoved=True,
                userRemoved=True,
                jitterbitRootRemoved=True,
                registrationStateRemoved=True,
                postgresRemoved=True,
                processesRemaining=False,
                commandsRemaining=False,
                startupIntegrationRemaining=False,
            )
            advance("LOCAL_UNINSTALL_COMPLETE")
            return
        if self.backend.agent_running():
            count = self._count()
            result["drain"]["initialActiveOperations"] = count
            result["drain"]["finalActiveOperations"] = count
            advance("ACTIVE_OPERATION_CHECK_COMPLETE")
            self._command([str(UTILS), "--drain-pause"], "DRAIN_PAUSE_FAILED")
            result["drain"]["drainPauseUsed"] = True
            advance("DRAIN_PAUSE_REQUESTED")
            deadline = self.monotonic() + args.drain_pause_timeout_seconds
            while count:
                if self.monotonic() >= deadline:
                    advance("DRAIN_PAUSE_TIMEOUT")
                    if not args.force:
                        raise FrameworkError("DRAIN_PAUSE_TIMEOUT")
                    break
                advance("DRAINING_OPERATIONS")
                self.sleeper(args.operation_poll_interval_seconds)
                count = self._count()
                result["drain"]["finalActiveOperations"] = count
                result["drain"]["operationCounts"].append(count)
            if count == 0:
                advance("OPERATIONS_DRAINED")
                self._command([str(UTILS), "--drain-stop"], "DRAIN_STOP_FAILED")
                result["drain"]["drainStopUsed"] = True
                advance("DRAIN_STOP_REQUESTED")
                stopped = self._stop_wait(
                    args.stop_timeout_seconds, args.stop_poll_interval_seconds
                )
                if not stopped:
                    if not args.force:
                        raise FrameworkError("DRAIN_STOP_TIMEOUT")
                    advance("DRAIN_STOP_TIMEOUT")
            else:
                stopped = False
            if not stopped:
                if not args.force:
                    raise FrameworkError("DRAIN_STOP_TIMEOUT")
                result["drain"]["forcedStopUsed"] = True
                advance("FORCED_STOP_REQUESTED")
                self._command([str(JITTERBIT), "stop"], "FORCED_STOP_FAILED")
                if not self._stop_wait(args.stop_timeout_seconds, args.stop_poll_interval_seconds):
                    raise FrameworkError("FORCED_STOP_FAILED")
                advance("FORCED_STOP_COMPLETE")
            advance("AGENT_STOPPED")
        else:
            advance("AGENT_STOPPED")
        if self.backend.agent_running():
            raise FrameworkError("PROCESS_STILL_RUNNING")
        if self.backend.package_status() is not None:
            advance("PACKAGE_REMOVAL_STARTED")
            self.backend.remove_package()
            result["localUninstall"]["packageRemoved"] = True
            advance("PACKAGE_REMOVED")
        if self.backend.product_processes():
            raise FrameworkError("PROCESS_STILL_RUNNING")
        self.backend.remove_user()
        result["localUninstall"]["userRemoved"] = True
        advance("USER_REMOVED")
        advance("RESIDUAL_SCAN_COMPLETE")
        self.backend.remove_residuals()
        advance("RESIDUALS_REMOVED")
        final = self.backend.snapshot()
        result["final"] = final
        result["localUninstall"].update(
            jitterbitRootRemoved=not final["rootPresent"],
            registrationStateRemoved=not final["credentialsPresent"]
            and not final["registerPresent"],
            postgresRemoved=not final["postgresRuntimePresent"]
            and not final["postgresDataPresent"],
            processesRemaining=bool(final["processCount"]),
            commandsRemaining=bool(final["commandPathsPresent"]),
            startupIntegrationRemaining=bool(final["startupPathsPresent"]),
        )
        if final["packageStatus"] is not None:
            raise FrameworkError("PACKAGE_REMOVE_FAILED")
        if final["userPresent"]:
            raise FrameworkError("USER_REMOVE_FAILED")
        if final["rootPresent"]:
            raise FrameworkError("RESIDUAL_CLEANUP_FAILED")
        if not result["localUninstall"]["registrationStateRemoved"]:
            raise FrameworkError("REGISTRATION_STATE_REMAINS")
        if not result["localUninstall"]["postgresRemoved"]:
            raise FrameworkError("POSTGRES_STATE_REMAINS")
        if final["processCount"]:
            raise FrameworkError("PROCESS_STILL_RUNNING")
        if final["commandPathsPresent"]:
            raise FrameworkError("COMMAND_LINK_REMAINS")
        if final["startupPathsPresent"]:
            raise FrameworkError("STARTUP_INTEGRATION_REMAINS")
        advance("REGISTRATION_STATE_REMOVED")
        advance("POSTGRES_REMOVED")
        advance("PROCESS_VALIDATION_COMPLETE")
        advance("FILESYSTEM_VALIDATION_COMPLETE")
        advance("LOCAL_UNINSTALL_COMPLETE")
        result["status"] = "SUCCESS"


def execute(
    argv=None,
    *,
    stdout=None,
    backend=None,
    provider=None,
    effective_uid=os.geteuid,
    lock_path="/var/lib/jbpa/bootstrap.lock",
    lock_factory=HostLock,
):
    stdout = stdout or sys.stdout
    result = {
        "operation": "UNINSTALL",
        "frameworkVersion": __version__,
        "runId": "jbpa-" + uuid.uuid4().hex,
        "timestamp": _now(),
        "status": "FAILED",
        "state": "UNINSTALL_INITIALIZED",
        "stateHistory": ["UNINSTALL_INITIALIZED"],
        "error": None,
        "initial": None,
        "final": None,
        "plan": [],
        "drain": {
            "initialActiveOperations": None,
            "finalActiveOperations": None,
            "operationCounts": [],
            "drainPauseUsed": False,
            "drainStopUsed": False,
            "forcedStopUsed": False,
        },
        "localUninstall": {
            "packageRemoved": False,
            "userRemoved": False,
            "jitterbitRootRemoved": False,
            "registrationStateRemoved": False,
            "postgresRemoved": False,
            "processesRemaining": None,
            "commandsRemaining": None,
            "startupIntegrationRemaining": None,
        },
        "harmony": {
            "removalRequested": False,
            "expectedState": "STOPPED_OR_EXISTING",
            "status": "HARMONY_REMOVAL_NOT_REQUESTED",
        },
    }
    code = 0
    args = None
    try:
        args = parser().parse_args(argv)
        if not args.complete or any(
            value < 1
            for value in (
                args.drain_pause_timeout_seconds,
                args.operation_poll_interval_seconds,
                args.stop_timeout_seconds,
                args.stop_poll_interval_seconds,
            )
        ):
            raise FrameworkError("CONFIG_INVALID")
        result["harmony"]["removalRequested"] = args.remove_harmony_agent
        if args.remove_harmony_agent:
            result["harmony"]["status"] = "HARMONY_AGENT_REMOVAL_REQUIRED"
        if args.dry_run:
            result["status"] = "PLANNED"
            result["plan"] = PLAN.copy()
        else:
            if effective_uid() != 0 or sys.platform != "linux":
                raise FrameworkError("PREFLIGHT_FAILED")
            with lock_factory(lock_path):
                UninstallWorkflow(
                    backend or LocalUninstallBackend(), provider or TranDbOperationProvider()
                ).run(result, args)
    except FrameworkError as exc:
        code = exc.spec.exitCode
        result["error"] = exc.as_dict()
        result["status"] = "FAILED"
    except Exception:
        exc = FrameworkError("INTERNAL_ERROR")
        code = exc.spec.exitCode
        result["error"] = exc.as_dict()
        result["status"] = "FAILED"
    result["state"] = result["stateHistory"][-1]
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args and args.result_file:
        try:
            write_result(args.result_file, output)
        except FrameworkError as exc:
            code = exc.spec.exitCode
            result["status"] = "FAILED"
            result["error"] = exc.as_dict()
            output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    stdout.write(output)
    return code


def main():
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
