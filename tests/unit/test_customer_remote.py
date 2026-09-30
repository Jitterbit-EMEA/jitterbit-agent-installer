"""Offline contract tests for the controlled RC9 SSH caller."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from tools.handoff import customer_remote as remote


class CustomerRemoteTests(unittest.TestCase):
    def test_inventory_rejects_embedded_secret_and_accepts_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "key"
            known = root / "known_hosts"
            key.write_text("synthetic")
            known.write_text("synthetic")
            entry = {
                "host": "qa.example.org",
                "user": "vmuser",
                "identityFile": str(key),
                "knownHostsFile": str(known),
                "credentialsFile": "/run/secrets/jbpa/credentials.json",
            }
            inventory = root / "vms.json"
            inventory.write_text(json.dumps({"schemaVersion": 1, "targets": {"qa": entry}}))
            self.assertEqual(remote.load_target(inventory, "qa"), entry)
            entry["registrationToken"] = "synthetic-should-not-be-in-inventory"
            inventory.write_text(json.dumps({"schemaVersion": 1, "targets": {"qa": entry}}))
            with self.assertRaisesRegex(remote.RemoteError, "INVENTORY_INVALID"):
                remote.load_target(inventory, "qa")

    def test_archive_is_pinned_and_mismatch_stops_before_ssh(self):
        self.assertEqual(remote.archive_digest(remote.ARCHIVE), remote.EXPECTED_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "release.tar.gz"
            altered.write_bytes(b"not the RC9 release")
            with self.assertRaisesRegex(remote.RemoteError, "JBPA_RELEASE_HASH_MISMATCH"):
                remote.deliver_release(object(), altered)

    def test_ssh_pins_host_key_and_quotes_remote_arguments(self):
        target = {
            "host": "qa.example.org",
            "user": "vmuser",
            "identityFile": "/private/key",
            "knownHostsFile": "/private/known_hosts",
        }
        completed = subprocess.CompletedProcess([], 0, b"ok\n", b"")
        with patch.object(remote.subprocess, "run", return_value=completed) as invoke:
            code, output = remote.SSH(target).run(["printf", "%s", "one two"])
        self.assertEqual((code, output), (0, "ok\n"))
        argv = invoke.call_args.args[0]
        self.assertIn("StrictHostKeyChecking=yes", argv)
        self.assertIn("UserKnownHostsFile=/private/known_hosts", argv)
        self.assertEqual(argv[-1], "printf %s 'one two'")

    def test_remote_hash_mismatch_stops_before_extract(self):
        calls = []

        class FakeSSH:
            def require(self, argv, reason, *, timeout=60):
                calls.append(argv)
                if argv[0] == "mktemp":
                    return "/var/tmp/jbpa-remote-AbC123\n"
                if argv[0] == "sha256sum":
                    return "0" * 64 + "  release.tar.gz\n"
                return ""

            def copy(self, local, remote_path):
                calls.append(["scp", str(local), str(remote_path)])

            def run(self, argv):
                calls.append(argv)
                return 0, ""

        with self.assertRaisesRegex(remote.RemoteError, "JBPA_RELEASE_HASH_MISMATCH"):
            remote.deliver_release(FakeSSH(), remote.ARCHIVE)
        self.assertFalse(any("tar" in argv for argv in calls))

    def test_install_requires_registration_health_and_matching_result(self):
        data = {
            "schemaVersion": "1.0",
            "operation": "INSTALL",
            "versions": {"jbpa": "1.0.0-rc9", "resolvedPA": "12.10.1.1"},
            "status": "SUCCESS",
            "category": "SUCCESS",
            "error": None,
            "details": {},
            "registration": {"harmonyRegistered": True},
            "health": {"serviceRunning": True},
        }
        self.assertEqual(remote.validate_result(data, "install", 0)["status"], "SUCCESS")
        data["health"]["serviceRunning"] = False
        self.assertEqual(remote.validate_result(data, "install", 0)["status"], "FAILED")
        data["health"]["serviceRunning"] = True
        self.assertEqual(remote.validate_result(data, "install", 1)["status"], "FAILED")
        data["operation"] = "UPGRADE"
        with self.assertRaisesRegex(remote.RemoteError, "RESULT_INVALID"):
            remote.validate_result(data, "install", 0)

    def test_management_command_is_fixed_and_uses_new_result_path(self):
        calls = []

        class FakeSSH:
            def require(self, argv, reason):
                if argv == ["cat", "/etc/os-release"]:
                    return 'ID=ubuntu\nVERSION_ID="24.04"\n'
                if argv == ["uname", "-m"]:
                    return "x86_64\n"
                return ""

            def run(self, argv, *, timeout):
                calls.append(argv)
                return 0, ""

            def result(self, path):
                return {
                    "schemaVersion": "1.0",
                    "operation": "UNINSTALL",
                    "versions": {"jbpa": "1.0.0-rc9"},
                    "status": "SUCCESS",
                    "category": "SUCCESS",
                    "error": None,
                    "details": {},
                }

        with patch.object(remote.uuid, "uuid4", return_value=type("U", (), {"hex": "abc123"})()):
            result = remote.operate(FakeSSH(), {}, "uninstall", None)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(
            calls,
            [
                [
                    "sudo",
                    "-n",
                    str(remote.REMOTE_RELEASE / "bin/jbpa"),
                    "uninstall",
                    "--config",
                    "/etc/jbpa/agent.yaml",
                    "--complete",
                    "--result-file",
                    "/var/lib/jbpa/results/remote-uninstall-abc123.json",
                ]
            ],
        )

    def test_install_delegates_to_customer_launcher_and_reads_private_result(self):
        calls = []

        class FakeSSH:
            def require(self, argv, reason):
                if argv == ["cat", "/etc/os-release"]:
                    return 'ID=ubuntu\nVERSION_ID="24.04"\n'
                if argv == ["uname", "-m"]:
                    return "x86_64\n"
                return ""

            def run(self, argv, *, timeout):
                calls.append(argv)
                return 0, (
                    "Installed PA 12.10.1.1\n"
                    "Private result: /var/lib/jbpa/results/customer-install-20260930T120000Z-a1b2c3d4.json\n"
                )

            def result(self, path):
                assert str(path) == (
                    "/var/lib/jbpa/results/customer-install-20260930T120000Z-a1b2c3d4.json"
                )
                return {
                    "schemaVersion": "1.0",
                    "operation": "INSTALL",
                    "versions": {"jbpa": "1.0.0-rc9", "resolvedPA": "12.10.1.1"},
                    "status": "SUCCESS",
                    "category": "SUCCESS",
                    "error": None,
                    "details": {},
                    "registration": {"harmonyRegistered": True},
                    "health": {"serviceRunning": True},
                }

        fake = FakeSSH()
        target = {"credentialsFile": "/run/secrets/jbpa/credentials.json"}
        with patch.object(remote, "deliver_release") as deliver:
            result = remote.operate(fake, target, "install", "12.10")
        deliver.assert_called_once_with(fake, remote.ARCHIVE)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(
            calls[0],
            [
                "sudo",
                "-n",
                str(remote.REMOTE_RELEASE / "bin/jbpa-install"),
                "--non-interactive",
                "--credentials-file",
                "/run/secrets/jbpa/credentials.json",
                "--version",
                "12.10",
            ],
        )

    def test_unsupported_host_stops_before_lifecycle(self):
        class FakeSSH:
            def require(self, argv, reason):
                if argv == ["cat", "/etc/os-release"]:
                    return 'ID=ubuntu\nVERSION_ID="22.04"\n'
                if argv == ["uname", "-m"]:
                    return "x86_64\n"
                return ""

            def run(self, argv, *, timeout):
                raise AssertionError("lifecycle must not run")

        with self.assertRaisesRegex(remote.RemoteError, "HOST_PLATFORM_UNEXPECTED"):
            remote.operate(FakeSSH(), {}, "uninstall", None)

    def test_example_inventory_matches_schema(self):
        root = Path(__file__).resolve().parents[2]
        schema = json.loads((root / "config/schemas/remote-inventory.schema.json").read_text())
        example = json.loads((root / "config/examples/remote-inventory.example.json").read_text())
        Draft202012Validator(schema).validate(example)


if __name__ == "__main__":
    unittest.main()
