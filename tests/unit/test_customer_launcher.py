"""Customer launcher safeguards and delegation to the governed CLI."""

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jbpa import customer


class CustomerLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=customer.ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "etc/agent.yaml"
        self.secrets = self.root / "etc/secrets"
        self.credentials = self.root / "etc/credentials.json"
        self.results = self.root / "results"
        self.patches = [
            patch.object(customer, "CONFIG", self.config),
            patch.object(customer, "SECRETS", self.secrets),
            patch.object(customer, "CREDENTIALS_FILE", self.credentials),
            patch.object(customer, "RESULTS", self.results),
            patch.object(customer, "require_qa_host"),
            patch.object(customer, "private_directory", self.make_directory),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    @staticmethod
    def make_directory(path):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)

    def test_setup_writes_one_private_json_file_and_keeps_existing_token(self):
        values = {
            "pa-registration-token": "synthetic-secret",
            "pa-cloud-url": "https://qa.example.test",
            "pa-agent-group-id": "123",
            "pa-agent-name-prefix": "test-agent",
        }
        with patch.object(customer, "prompt_details", return_value=values) as prompt:
            customer.configure()
            customer.configure()
        prompt.assert_called_once()
        self.assertEqual(
            json.loads(self.credentials.read_text())["harmony"]["registrationToken"],
            "synthetic-secret",
        )
        self.assertFalse(self.secrets.exists())
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.credentials.stat().st_mode & 0o777, 0o600)

    def test_reconfigure_replaces_token_without_printing_it(self):
        original = {
            "pa-registration-token": "synthetic-old",
            "pa-cloud-url": "https://qa.example.test",
            "pa-agent-group-id": "123",
            "pa-agent-name-prefix": "test-agent",
        }
        revised = {**original, "pa-registration-token": "synthetic-new"}
        output = io.StringIO()
        with patch.object(customer, "prompt_details", side_effect=[original, revised]):
            with patch("sys.stdout", output):
                customer.configure()
                customer.configure(replace=True)
        self.assertEqual(
            json.loads(self.credentials.read_text())["harmony"]["registrationToken"],
            "synthetic-new",
        )
        self.assertNotIn("synthetic-old", output.getvalue())
        self.assertNotIn("synthetic-new", output.getvalue())

    def test_one_private_json_source_is_imported_for_unattended_setup(self):
        source = self.root / "supplied.json"
        source.write_text(
            json.dumps(
                customer.credential_document(
                    {
                        "pa-registration-token": "synthetic-secret",
                        "pa-cloud-url": "https://qa.example.test",
                        "pa-agent-group-id": "123",
                        "pa-agent-name-prefix": "test-agent",
                    }
                )
            )
        )
        source.chmod(0o600)
        output = io.StringIO()
        with patch("sys.stdout", output):
            customer.configure(credentials_file=str(source))
        self.assertEqual(self.credentials.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.credentials.read_text())["harmony"]["agentGroupId"], 123)
        self.assertNotIn("synthetic-secret", output.getvalue())
        self.assertFalse(self.secrets.exists())

    def test_json_import_rejects_unsafe_source_before_copy(self):
        source = self.root / "supplied.json"
        source.write_text(
            (customer.ROOT / "config/examples/customer-credentials.example.json").read_text()
        )
        source.chmod(0o644)
        self.make_directory(self.credentials.parent)
        with self.assertRaisesRegex(customer.CustomerError, "private regular file"):
            customer.import_credentials(str(source))
        source.chmod(0o600)
        alias = self.root / "alias.json"
        alias.symlink_to(source)
        with self.assertRaisesRegex(customer.CustomerError, "Could not read"):
            customer.import_credentials(str(alias))
        self.assertFalse(self.credentials.exists())

    def test_unattended_run_requires_version_and_sequences_actions(self):
        with self.assertRaisesRegex(customer.CustomerError, "requires --version"):
            customer.run(non_interactive=True, credentials_file="/source.json")
        calls = []
        with (
            patch.object(customer, "ensure_runtime", side_effect=lambda: calls.append("runtime")),
            patch.object(customer, "agent_installed", return_value=False),
            patch.object(
                customer, "configure", side_effect=lambda **kw: calls.append(("setup", kw))
            ),
            patch.object(
                customer, "choose_version", side_effect=lambda v: calls.append(("version", v)) or v
            ),
            patch.object(
                customer, "install", side_effect=lambda v, **kw: calls.append(("install", v, kw))
            ),
            patch.object(customer, "verify", side_effect=lambda: calls.append("verify")),
        ):
            customer.run("12.10", non_interactive=True, credentials_file="/source.json")
        self.assertEqual(
            calls,
            [
                "runtime",
                ("setup", {"credentials_file": "/source.json"}),
                ("version", "12.10"),
                ("install", "12.10", {"non_interactive": True}),
                "verify",
            ],
        )

    def test_run_cli_passes_one_file_and_version(self):
        with (
            patch.object(customer, "require_root"),
            patch.object(customer, "run") as runner,
        ):
            code = customer.main(
                [
                    "run",
                    "--non-interactive",
                    "--credentials-file",
                    "/run/secrets/jbpa/credentials.json",
                    "--version",
                    "12.10",
                ]
            )
        self.assertEqual(code, 0)
        runner.assert_called_once_with(
            "12.10",
            non_interactive=True,
            credentials_file="/run/secrets/jbpa/credentials.json",
        )

    def test_unattended_install_requires_staged_credentials(self):
        with patch.object(customer, "agent_installed", return_value=False):
            with self.assertRaises(customer.CustomerError):
                customer.install("latest", non_interactive=True)

    def test_existing_agent_cannot_enter_install_path(self):
        with patch.object(customer, "agent_installed", return_value=True):
            with self.assertRaisesRegex(customer.CustomerError, "choose upgrade"):
                customer.install("latest")

    def test_install_delegates_controlled_interactive_to_jbpa(self):
        self.make_directory(self.config.parent)
        self.config.write_text("fixture")
        self.credentials.write_text("fixture")
        response = {
            "versions": {"resolvedPA": "12.10.1.1"},
            "registration": {"harmonyRegistered": True},
        }
        with (
            patch.object(customer, "preflight") as preflight,
            patch.object(customer, "jbpa", return_value=response) as delegated,
            patch.object(customer, "result_file", return_value=self.results / "install.json"),
            patch.object(customer, "agent_installed", return_value=False),
            patch.object(customer, "ensure_runtime"),
        ):
            customer.install("latest")
        preflight.assert_called_once_with("latest")
        args = delegated.call_args.args[0]
        self.assertEqual(args[0:2], ["install", "--interactive"])
        self.assertIn("--controlled-test", args)
        self.assertEqual(args[args.index("--version") + 1], "latest")

    def test_bad_jbpa_result_is_not_reported_as_success(self):
        bad = {"status": "FAILED", "error": {"name": "VERSION_NOT_QUALIFIED"}}
        process = subprocess.CompletedProcess([], 40, json.dumps(bad), "")
        with (
            patch.object(customer, "ensure_runtime"),
            patch.object(customer, "command", return_value=process) as runner,
        ):
            with self.assertRaisesRegex(customer.CustomerError, "VERSION_NOT_QUALIFIED"):
                customer.jbpa(["install"])
        self.assertTrue(runner.call_args.kwargs["visible_stderr"])

    def test_capacity_failure_explains_next_step_without_exposing_log(self):
        bad = {"status": "FAILED", "error": {"name": "AGENT_CAPACITY_REACHED"}}
        process = subprocess.CompletedProcess([], 51, json.dumps(bad), "")
        with (
            patch.object(customer, "ensure_runtime"),
            patch.object(customer, "command", return_value=process),
        ):
            with self.assertRaisesRegex(customer.CustomerError, "licensed capacity"):
                customer.jbpa(["install"])

    def test_interactive_child_stderr_remains_on_terminal(self):
        process = subprocess.CompletedProcess([], 0, "{}", None)
        with patch("jbpa.customer.subprocess.run", return_value=process) as runner:
            customer.command(["jbpa", "install"], capture=True, visible_stderr=True)
        self.assertEqual(runner.call_args.kwargs["stdout"], subprocess.PIPE)
        self.assertIsNone(runner.call_args.kwargs["stderr"])

    def test_private_file_does_not_follow_existing_symlink(self):
        self.make_directory(self.secrets)
        target = self.root / "outside"
        target.write_text("unchanged")
        (self.secrets / "pa-registration-token").symlink_to(target)
        with self.assertRaises(customer.CustomerError):
            customer.write_private(
                self.secrets / "pa-registration-token", "replacement", replace=True
            )
        self.assertEqual(target.read_text(), "unchanged")

    def test_verify_summarizes_latest_private_install_result(self):
        self.make_directory(self.results)
        result = self.results / "customer-install-20260928T160000Z-12345678.json"
        result.write_text(
            json.dumps(
                {
                    "operation": "INSTALL",
                    "status": "SUCCESS",
                    "versions": {"resolvedPA": "12.10.1.1"},
                    "registration": {"harmonyRegistered": True},
                    "health": {"serviceRunning": True},
                }
            )
        )
        result.chmod(0o600)
        output = io.StringIO()
        with (
            patch.object(customer, "agent_installed", return_value=True),
            patch.object(
                customer,
                "jbpa",
                return_value={
                    "details": {
                        "installedVersion": "12.10.1.1",
                        "packageState": "INSTALLED",
                        "connectionCheck": True,
                        "coreServicesHealthy": True,
                    }
                },
            ) as delegated,
            patch("sys.stdout", output),
        ):
            customer.verify()
        self.assertIn("Install verified: PA 12.10.1.1", output.getvalue())
        delegated.assert_called_once_with(["diagnostics"])
        result.chmod(0o644)
        with self.assertRaisesRegex(customer.CustomerError, "private regular file"):
            customer.verify()


if __name__ == "__main__":
    unittest.main()
