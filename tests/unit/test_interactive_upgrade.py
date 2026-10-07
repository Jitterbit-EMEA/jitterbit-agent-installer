"""Interactive release selection and guarded in-place upgrade contracts."""

import io
import subprocess
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from test_native_linux import SUCCESS_LOG, FakeBackend, artifact, config

from jbpa import release_cli, upgrade
from jbpa.config import ROOT
from jbpa.errors import FrameworkError
from jbpa.native_linux import CREDENTIALS, NativeLinuxWorkflow
from jbpa.security import Secret

CONFIG = str(ROOT / "config/examples/local-file-qa.example.yaml")
HOST = {"os": "ubuntu", "version": "24.04", "architecture": "x86_64"}


class TTY(io.StringIO):
    def isatty(self):
        return True


class InteractiveTests(unittest.TestCase):
    def test_versions_lists_entire_governed_catalogue(self):
        code, data = release_cli.versions([])
        self.assertEqual(code, 0)
        self.assertEqual(data["catalogueCount"], 19)
        self.assertEqual(data["versions"][0]["packageVersion"], "12.10.1.1")
        self.assertEqual(data["dynamicLatest"], "MUTABLE_NOT_RESOLVED")

    def test_latest_prompts_with_exact_artifact_before_install(self):
        artifact = {
            "logical_version": "12.10",
            "package_version": "12.10.1.1",
            "sha256": "a" * 64,
            "runtime_qualification": "TESTED_LIVE",
        }
        reader, writer = TTY("INSTALL\n"), io.StringIO()
        with (
            patch(
                "jbpa.release_cli.artifacts.inspect",
                return_value=(artifact, Path("/tmp/fixture.deb")),
            ),
            patch("jbpa.release_cli.detect", return_value=HOST),
            patch("jbpa.release_cli.install", return_value=(0, {"status": "COMPLETE"})) as install,
        ):
            code, _ = release_cli.interactive_install(
                ["--interactive", "--config", CONFIG, "--version", "latest", "--controlled-test"],
                reader=reader,
                writer=writer,
            )
        self.assertEqual(code, 0)
        self.assertIn("12.10.1.1", writer.getvalue())
        self.assertIn("a" * 64, writer.getvalue())
        self.assertIn("--non-interactive", install.call_args.args[0])
        self.assertEqual(install.call_args.kwargs["prepared"][0], artifact)

    def test_cancellation_never_installs(self):
        artifact = {
            "logical_version": "12.10",
            "package_version": "12.10.1.1",
            "sha256": "a" * 64,
            "runtime_qualification": "TESTED_LIVE",
        }
        with (
            patch(
                "jbpa.release_cli.artifacts.inspect",
                return_value=(artifact, Path("/tmp/fixture.deb")),
            ),
            patch("jbpa.release_cli.detect", return_value=HOST),
            patch("jbpa.release_cli.install") as install,
        ):
            with self.assertRaises(FrameworkError) as caught:
                release_cli.interactive_install(
                    ["--interactive", "--config", CONFIG, "--version", "latest"],
                    reader=TTY("no\n"),
                    writer=io.StringIO(),
                )
        self.assertEqual(caught.exception.spec.name, "INTERACTIVE_ABORTED")
        install.assert_not_called()

    def test_interactive_requires_tty(self):
        with self.assertRaises(FrameworkError) as caught:
            release_cli.interactive_install(
                ["--interactive", "--config", CONFIG],
                reader=io.StringIO("INSTALL\n"),
                writer=io.StringIO(),
            )
        self.assertEqual(caught.exception.spec.name, "INTERACTIVE_TTY_REQUIRED")


class Backend:
    def __init__(self, version="12.9.2.2"):
        self.version = version
        self.commands = []

    def snapshot(self):
        return {
            "packageStatus": f"install ok installed|{self.version}",
            "rootPresent": True,
            "userPresent": True,
            "credentialsPresent": True,
            "registerPresent": False,
            "processCount": 4,
            "postgresRuntimePresent": True,
            "postgresDataPresent": True,
            "commandPathsPresent": ["/usr/bin/jitterbit"],
            "startupPathsPresent": ["/etc/init.d/jitterbit"],
        }

    def package_status(self):
        return f"install ok installed|{self.version}"

    def agent_running(self):
        return True


class Identity:
    def __init__(self, backend):
        self.backend = backend

    def about(self):
        return {
            "Agent_Name": "fixture-agent",
            "Agent_Group_Name": "fixture-group",
            "VersionNumber": self.backend.version,
        }

    def connection(self):
        return True


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.artifact = {
            "logical_version": "12.10",
            "package_version": "12.10.1.1",
            "sha256": "a" * 64,
            "byte_size": 100,
        }
        self.argv = [
            "--config",
            CONFIG,
            "--version",
            "12.10",
            "--controlled-test",
            "--non-interactive",
        ]

    def execute(self, **kwargs):
        with (
            patch(
                "jbpa.upgrade.artifacts.inspect",
                return_value=(self.artifact, Path("/tmp/fixture.deb")),
            ),
            patch("jbpa.upgrade.host_readiness.detect", return_value=HOST),
            patch(
                "jbpa.upgrade.host_readiness.run",
                return_value={"status": "PASS", "platform": HOST},
            ),
        ):
            return upgrade.execute(
                self.argv,
                backend=self.backend,
                identity=Identity(self.backend),
                lock_factory=lambda: nullcontext(),
                **kwargs,
            )

    def test_current_version_is_no_change(self):
        self.backend.version = "12.10.1.1"
        code, result = self.execute()
        self.assertEqual((code, result["status"]), (0, "ALREADY_CURRENT"))
        self.assertFalse(result["changed"])

    def test_downgrade_fails_before_mutation(self):
        self.backend.version = "12.11.0.0"
        code, result = self.execute()
        self.assertNotEqual(code, 0)
        self.assertEqual(result["error"]["name"], "UPGRADE_DOWNGRADE_DENIED")
        self.assertFalse(result["changed"])

    def test_upgrade_preserves_identity_and_checks_health(self):
        runtime = FakeBackend(
            log=SUCCESS_LOG.replace("Agent synchronization for agent group ID 200 completed", "")
        )
        runtime.files.add(CREDENTIALS)
        runtime.installed_version = "12.10.1.1"
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as folder:
            credentials = Path(folder) / "credentials.txt"
            credentials.write_text("fixture")

            def package_runner(*_args, **_kwargs):
                self.backend.version = "12.10.1.1"
                return subprocess.CompletedProcess([], 0, "", "")

            class Provider:
                def clear(self):
                    pass

            with (
                patch("jbpa.upgrade.os.geteuid", return_value=0),
                patch("jbpa.upgrade._backup", return_value=[]),
                patch("jbpa.upgrade._drain"),
                patch("jbpa.upgrade._restore_changed", return_value=[]),
                patch("jbpa.upgrade._provider", return_value=Provider()),
                patch("jbpa.upgrade._resolve_registration_fields"),
                patch("jbpa.upgrade.CREDENTIALS", str(credentials)),
            ):
                code, result = self.execute(
                    package_runner=package_runner,
                    verify_runner=lambda *_args: NativeLinuxWorkflow(runtime).run(
                        config(), artifact(package_version="12.10.1.1"), Secret(None)
                    ),
                )
        self.assertEqual(code, 0)
        self.assertEqual(result["state"], "UPGRADE_COMPLETE")
        self.assertTrue(result["changed"])
        self.assertFalse(result["runtimeVerification"]["synchronizationRequired"])
        self.assertFalse(result["runtimeVerification"]["synchronizationObserved"])

    def test_backup_restores_changed_configuration_privately(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as folder:
            product = Path(folder) / "jitterbit"
            product.mkdir()
            configuration = product / "jitterbit.conf"
            configuration.write_text("original")
            configuration.chmod(0o600)
            backup_root = Path(folder) / "backups"
            with (
                patch("jbpa.upgrade.ROOT", product),
                patch("jbpa.upgrade.BACKUP_ROOT", backup_root),
            ):
                saved = upgrade._backup(backup_root / "upgrade-fixture")
                self.assertEqual(saved[0][1].stat().st_mode & 0o777, 0o600)
                configuration.write_text("changed")
                self.assertEqual(upgrade._restore_changed(saved), ["jitterbit.conf"])
            self.assertEqual(configuration.read_text(), "original")
            self.assertEqual(configuration.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
