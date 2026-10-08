"""Offline onboarding contracts: credentials stay private and setup never installs PA."""

import importlib.util
import json
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("onboard_target", ROOT / "scripts/onboard-target.py")
onboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(onboard)


class FakeSSH:
    def __init__(self, fail_import=False):
        self.calls = []
        self.fail_import = fail_import
        self.delivered = None
        self.local_mode = None

    def require(self, argv, reason, **kwargs):
        self.calls.append(argv)
        if argv[0] == "mktemp":
            return "/var/tmp/jbpa-onboard-AbC123\n"
        if reason == "SETUP_CREDENTIAL_IMPORT_FAILED" and self.fail_import:
            raise onboard.remote.RemoteError(reason)
        return ""

    def copy(self, local, destination):
        self.delivered = json.loads(local.read_text())
        self.local_mode = local.stat().st_mode & 0o777
        self.local_path = local
        self.calls.append(["copy", str(destination)])

    def run(self, argv, **kwargs):
        self.calls.append(argv)
        return 1, ""


class OnboardingTests(unittest.TestCase):
    def test_terminal_launch_quotes_paths_and_does_not_relaunch_itself(self):
        args = SimpleNamespace(
            inventory=Path("/tmp/a folder/vms.json"),
            target="qa-vm",
            cloud_url="https://cloud.example",
            group_id=123,
            name_prefix="qa-agent",
        )
        with (
            patch.object(onboard.sys, "platform", "darwin"),
            patch.object(
                onboard.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
            ) as invoke,
        ):
            onboard.open_terminal(args)
        command = shlex.split(invoke.call_args.args[0][-1])
        self.assertEqual(command[0], "exec")
        self.assertIn(str(args.inventory.resolve()), command)
        self.assertNotIn("--open-terminal", command)
        self.assertNotIn("--token", command)

    def test_terminal_launch_failure_is_reported(self):
        args = SimpleNamespace(
            inventory=Path("/tmp/vms.json"),
            target="qa-vm",
            cloud_url="https://cloud.example",
            group_id=123,
            name_prefix="qa-agent",
        )
        with (
            patch.object(onboard.sys, "platform", "darwin"),
            patch.object(
                onboard.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)
            ),
        ):
            with self.assertRaisesRegex(onboard.remote.RemoteError, "SETUP_TERMINAL_LAUNCH_FAILED"):
                onboard.open_terminal(args)

    def test_settings_reject_unsafe_url_and_invalid_group(self):
        for url, group in [
            ("http://cloud.example", 1),
            ("https://user:pass@cloud.example", 1),
            ("https://cloud.example?token=x", 1),
            ("https://cloud.example", 0),
        ]:
            with self.subTest(url=url, group=group):
                with self.assertRaises(onboard.remote.RemoteError):
                    onboard.settings(url, group, "fixture-pa")

    def test_private_delivery_imports_credentials_without_installing_pa(self):
        ssh = FakeSSH()
        document = onboard.settings("https://cloud.example", 123, "fixture-pa")
        document["harmony"]["registrationToken"] = "synthetic"
        onboard.provision(ssh, document)
        self.assertEqual(ssh.local_mode, 0o600)
        self.assertEqual(ssh.delivered, document)
        self.assertFalse(ssh.local_path.exists())
        self.assertTrue(any("versions" in command for command in ssh.calls))
        self.assertFalse(any("install" in command or "upgrade" in command for command in ssh.calls))
        self.assertIn(["rm", "-f", "/var/tmp/jbpa-onboard-AbC123/credentials.json"], ssh.calls)
        self.assertIn(["rmdir", "/var/tmp/jbpa-onboard-AbC123"], ssh.calls)
        self.assertFalse(any("synthetic" in item for command in ssh.calls for item in command))

    def test_import_failure_still_cleans_staging(self):
        ssh = FakeSSH(fail_import=True)
        with self.assertRaises(onboard.remote.RemoteError):
            onboard.provision(ssh, onboard.settings("https://cloud.example", 123, "fixture-pa"))
        self.assertFalse(ssh.local_path.exists())
        self.assertEqual(ssh.calls[-1], ["rmdir", "/var/tmp/jbpa-onboard-AbC123"])

    def test_saved_inventory_is_private_and_keeps_other_hosts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vms.json"
            document = {
                "schemaVersion": 1,
                "targets": {"first": {"host": "a"}, "second": {"host": "b"}},
            }
            onboard.save_inventory(path, document)
            self.assertEqual(json.loads(path.read_text()), document)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaises(onboard.remote.RemoteError):
                onboard.save_inventory(link, {})

    def test_nonterminal_setup_never_prompts_or_delivers(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / "vms.json"
            inventory.write_text("{}")
            with (
                patch.object(onboard.remote, "load_target", return_value={}),
                patch.object(onboard.remote, "preflight_transport"),
                patch.object(onboard.remote, "SSH", return_value=FakeSSH()),
                patch.object(onboard.sys.stdin, "isatty", return_value=False),
                patch.object(onboard.getpass, "getpass") as prompt,
                patch.object(onboard.remote, "deliver_release") as deliver,
            ):
                code = onboard.main(
                    [
                        "--inventory",
                        str(inventory),
                        "--target",
                        "qa",
                        "--cloud-url",
                        "https://cloud.example",
                        "--group-id",
                        "123",
                        "--name-prefix",
                        "fixture-pa",
                    ]
                )
            self.assertEqual(code, 1)
            prompt.assert_not_called()
            deliver.assert_not_called()
