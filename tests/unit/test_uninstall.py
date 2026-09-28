import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jbpa.errors import FrameworkError
from jbpa.health import execute as health_execute
from jbpa.pending_operations import (
    ACTIVE_STATUSES,
    COUNT_SQL,
    DETAIL_SQL,
    STATUS_NAMES,
    OperationQueryError,
    TranDbOperationProvider,
)
from jbpa.pending_operations import (
    main as pending_main,
)
from jbpa.uninstall import UninstallWorkflow, execute


class PendingOperationTests(unittest.TestCase):
    def test_all_statuses_and_active_filter(self):
        self.assertEqual(set(STATUS_NAMES), set(range(12)))
        self.assertEqual(ACTIVE_STATUSES, (0, 1, 3, 8, 10))
        self.assertIn("status IN (0,1,3,8,10)", COUNT_SQL)
        self.assertIn("status IN (0,1,3,8,10)", DETAIL_SQL)
        self.assertIn("COALESCE(started_ts, entered_ts)", DETAIL_SQL)

    def test_conf_parse_and_library_environment_without_secret_output(self):
        secret = "SYNTHETIC_DB_PASSWORD"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            (root / "lib").mkdir()
            (root / "bin/psql").touch()
            (root / "lib/libpq.so.5").touch()
            env_file = root / "jitterbit-env"
            conf_file = root / "jitterbit.conf"
            env_file.write_text(f'PG_HOME="{root}"\nno_proxy=$missing\n')
            conf_file.write_text(
                "[Other]\nPassword=wrong\n[DbInfo]\n"
                f"User='jitterbit'\nPassword='{secret}'\nPort=6432\n"
            )
            calls = []

            def runner(argv, **kwargs):
                calls.append((argv, kwargs))
                return subprocess.CompletedProcess(argv, 0, "2\n", "")

            provider = TranDbOperationProvider(
                environment_file=env_file, config_file=conf_file, runner=runner
            )
            self.assertEqual(provider.active_count(), 2)
            argv, options = calls[0]
            self.assertNotIn(secret, " ".join(argv))
            self.assertEqual(options["env"]["PGPASSWORD"], secret)
            self.assertEqual(options["env"]["LD_LIBRARY_PATH"], str(root / "lib"))
            self.assertIn("TranDb", argv)

    def test_cli_count_quiet_and_failure_codes(self):
        class Provider:
            def __init__(self, count):
                self.count = count

            def active_count(self):
                return self.count

        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(pending_main(["--count"], provider=Provider(2), stdout=out, stderr=err), 2)
        self.assertEqual(out.getvalue(), "2\n")
        out = io.StringIO()
        self.assertEqual(pending_main(["--quiet"], provider=Provider(0), stdout=out), 0)
        self.assertEqual(out.getvalue(), "")

        class Broken:
            def active_count(self):
                raise OperationQueryError()

        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(pending_main(["--count"], provider=Broken(), stdout=out, stderr=err), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "PENDING_OPERATION_QUERY_FAILED\n")


class HealthCommandTests(unittest.TestCase):
    def test_local_health_does_not_claim_harmony(self):
        status = (
            "JitterbitProcessEngine is running\nJitterbitScheduler is running\n"
            "JitterbitFileCleanup is running\nJitterbitVerboseLogShipper is running\n"
            "All services are running\n"
        )
        output = io.StringIO()
        with patch("jbpa.health.JITTERBIT") as path:
            path.is_file.return_value = True
            code = health_execute(
                runner=lambda *a, **k: subprocess.CompletedProcess([], 0, status, ""),
                stdout=output,
            )
        self.assertEqual(code, 0)
        value = json.loads(output.getvalue())
        self.assertEqual(value["status"], "HEALTHY")
        self.assertIsNone(value["harmonyRegistered"])

    def test_local_health_reports_absent_agent(self):
        output = io.StringIO()
        with patch("jbpa.health.JITTERBIT") as path:
            path.is_file.return_value = False
            code = health_execute(stdout=output)
        self.assertEqual(code, 60)
        self.assertEqual(json.loads(output.getvalue())["status"], "UNHEALTHY")


class FakeBackend:
    def __init__(self, *, running=True, installed=True, clean=False):
        self.running = running
        self.installed = installed
        self.clean = clean
        self.commands = []
        self.package_removed = False
        self.user_removed = False
        self.residuals_removed = False
        self.pause_failed = False
        self.stop_remains_running = False
        self.support_running = False
        self.package_remove_failed = False
        self.user_remove_failed = False

    def snapshot(self):
        return {
            "packageStatus": self.package_status(),
            "userPresent": not self.clean and not self.user_removed,
            "rootPresent": not self.clean and not self.residuals_removed,
            "credentialsPresent": not self.clean and not self.residuals_removed,
            "registerPresent": False,
            "postgresRuntimePresent": not self.clean and not self.residuals_removed,
            "postgresDataPresent": not self.clean and not self.residuals_removed,
            "processCount": len(self.product_processes()),
            "commandPathsPresent": []
            if self.clean or self.residuals_removed
            else ["/usr/bin/jitterbit"],
            "startupPathsPresent": []
            if self.clean or self.residuals_removed
            else ["/etc/init.d/jitterbit"],
        }

    def package_status(self):
        return (
            "install ok installed|12.10.1.1"
            if self.installed and not self.package_removed
            else None
        )

    def product_processes(self):
        return [100] if self.running or self.support_running else []

    def agent_running(self):
        return self.running

    def command(self, argv):
        self.commands.append(argv)
        if argv[-1] == "--drain-pause" and self.pause_failed:
            return subprocess.CompletedProcess(argv, 1, "", "")
        if argv[-1] in ("--drain-stop", "stop") and not self.stop_remains_running:
            self.running = False
        return subprocess.CompletedProcess(argv, 0, "", "")

    def remove_package(self):
        if self.package_remove_failed:
            raise FrameworkError("PACKAGE_REMOVE_FAILED")
        self.package_removed = True
        self.support_running = False

    def remove_user(self):
        if self.user_remove_failed:
            raise FrameworkError("USER_REMOVE_FAILED")
        self.user_removed = True

    def remove_residuals(self):
        self.residuals_removed = True


class FakeProvider:
    def __init__(self, counts):
        self.counts = iter(counts)

    def active_count(self):
        return next(self.counts)


def options(*, force=False, drain_timeout=10, stop_timeout=10):
    return SimpleNamespace(
        force=force,
        drain_pause_timeout_seconds=drain_timeout,
        operation_poll_interval_seconds=1,
        stop_timeout_seconds=stop_timeout,
        stop_poll_interval_seconds=1,
    )


def result():
    return json.loads(io.StringIO(_dry_result()).getvalue())


def _dry_result():
    output = io.StringIO()
    execute(["--complete", "--dry-run"], stdout=output)
    return output.getvalue()


class UninstallWorkflowTests(unittest.TestCase):
    def workflow(self, backend, provider):
        clock = [0]

        def now():
            return clock[0]

        def sleep(seconds):
            clock[0] += seconds

        return UninstallWorkflow(backend, provider, sleeper=sleep, monotonic=now)

    def test_drain_then_complete_local_uninstall(self):
        backend = FakeBackend()
        data = result()
        self.workflow(backend, FakeProvider([2, 1, 0])).run(data, options())
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["drain"]["initialActiveOperations"], 2)
        self.assertEqual(data["drain"]["finalActiveOperations"], 0)
        self.assertFalse(data["drain"]["forcedStopUsed"])
        self.assertIn("--drain-pause", backend.commands[0])
        self.assertIn("--drain-stop", backend.commands[1])
        self.assertNotIn(["/opt/jitterbit/bin/jitterbit", "stop"], backend.commands)
        self.assertEqual(data["stateHistory"][-1], "LOCAL_UNINSTALL_COMPLETE")

    def test_zero_active_operations_still_drain_stops(self):
        backend = FakeBackend()
        data = result()
        self.workflow(backend, FakeProvider([0])).run(data, options())
        self.assertTrue(data["drain"]["drainStopUsed"])

    def test_timeout_does_not_stop_or_remove_by_default(self):
        backend = FakeBackend()
        data = result()
        with self.assertRaises(FrameworkError) as caught:
            self.workflow(backend, FakeProvider([2, 2])).run(data, options(drain_timeout=1))
        self.assertEqual(caught.exception.spec.name, "DRAIN_PAUSE_TIMEOUT")
        self.assertFalse(backend.package_removed)
        self.assertNotIn(["/opt/jitterbit/bin/jitterbit", "stop"], backend.commands)

    def test_explicit_force_after_drain_timeout(self):
        backend = FakeBackend()
        data = result()
        self.workflow(backend, FakeProvider([2, 2])).run(data, options(force=True, drain_timeout=1))
        self.assertTrue(data["drain"]["forcedStopUsed"])
        self.assertIn(["/opt/jitterbit/bin/jitterbit", "stop"], backend.commands)

    def test_stop_timeout_keeps_package_without_force(self):
        backend = FakeBackend()
        backend.stop_remains_running = True
        data = result()
        with self.assertRaises(FrameworkError) as caught:
            self.workflow(backend, FakeProvider([0])).run(data, options(stop_timeout=1))
        self.assertEqual(caught.exception.spec.name, "DRAIN_STOP_TIMEOUT")
        self.assertFalse(backend.package_removed)

    def test_package_failure_preserves_residual_state(self):
        backend = FakeBackend(running=False)
        backend.package_remove_failed = True
        with self.assertRaises(FrameworkError) as caught:
            self.workflow(backend, FakeProvider([])).run(result(), options())
        self.assertEqual(caught.exception.spec.name, "PACKAGE_REMOVE_FAILED")
        self.assertFalse(backend.residuals_removed)

    def test_user_failure_preserves_residual_state(self):
        backend = FakeBackend(running=False)
        backend.user_remove_failed = True
        with self.assertRaises(FrameworkError) as caught:
            self.workflow(backend, FakeProvider([])).run(result(), options())
        self.assertEqual(caught.exception.spec.name, "USER_REMOVE_FAILED")
        self.assertFalse(backend.residuals_removed)

    def test_operation_query_failure_blocks_uninstall(self):
        backend = FakeBackend()

        class Broken:
            def active_count(self):
                raise OperationQueryError()

        with self.assertRaises(FrameworkError) as caught:
            self.workflow(backend, Broken()).run(result(), options())
        self.assertEqual(caught.exception.spec.name, "ACTIVE_OPERATION_QUERY_FAILED")
        self.assertFalse(backend.package_removed)

    def test_already_stopped_skips_drain(self):
        backend = FakeBackend(running=False)
        data = result()
        self.workflow(backend, FakeProvider([])).run(data, options())
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(backend.commands, [])

    def test_stopped_core_with_bundled_support_processes(self):
        backend = FakeBackend(running=False)
        backend.support_running = True
        data = result()
        self.workflow(backend, FakeProvider([])).run(data, options())
        self.assertEqual(data["status"], "SUCCESS")
        self.assertFalse(data["drain"]["drainPauseUsed"])
        self.assertTrue(data["localUninstall"]["packageRemoved"])

    def test_idempotent_clean_host(self):
        backend = FakeBackend(running=False, installed=False, clean=True)
        data = result()
        self.workflow(backend, FakeProvider([])).run(data, options())
        self.assertEqual(data["status"], "ALREADY_UNINSTALLED")
        self.assertTrue(data["localUninstall"]["packageRemoved"])
        self.assertFalse(data["localUninstall"]["processesRemaining"])
        self.assertFalse(backend.package_removed)

    def test_dry_run_changes_nothing(self):
        out = io.StringIO()
        code = execute(["--complete", "--dry-run"], stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "PLANNED")
        self.assertIn("Harmony agent deletion is not performed", data["plan"])


if __name__ == "__main__":
    unittest.main()
