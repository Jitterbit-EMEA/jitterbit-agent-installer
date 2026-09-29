"""External SSH caller tests use a synthetic transport; no host is contacted."""

import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jbpa.release_cli import envelope
from tools.handoff.caller import HandoffError
from tools.handoff.guest_prepare import EXPECTED_SHA, DeliveryError, verify_installed
from tools.handoff.ssh import SSHTransport, run


def request(operation):
    return {
        "schemaVersion": "1.0",
        "target": "qa-ubuntu22.example",
        "operation": operation,
        "jbpaVersion": "1.0.0-rc3",
        "paVersion": "12.10",
        "allowUnqualified": True,
        "controlledTest": True,
        "configPath": "/etc/jbpa/agent.yaml",
        "resultPath": f"/var/lib/jbpa/{operation.lower()}-new-result.json",
    }


class SyntheticTransport:
    target = "qa-ubuntu22.example"

    def __init__(
        self, operation, *, preflight_status="PASS", host_state=None, host_version="22.04"
    ):
        self.operation = operation
        self.preflight_status = preflight_status
        self.host_state = host_state or (
            "CLEAN_HOST" if operation == "INSTALL" else "AGENT_INSTALLED_REGISTERED"
        )
        self.host_version = host_version
        self.commands = []
        self.deliveries = []

    def deliver(self, local, remote):
        self.deliveries.append((str(local), remote))

    def command(self, argv, **_kwargs):
        self.commands.append(argv)
        if "guest_prepare.py" in " ".join(argv):
            return 0, json.dumps({"status": "VERIFIED", "sha256": EXPECTED_SHA})
        return 0, ""

    def result(self, path):
        if path.endswith(".preflight.json"):
            result = envelope(
                "validate",
                0,
                {
                    "preflight": {
                        "profile": self.operation,
                        "status": self.preflight_status,
                        "checks": {},
                        "hostState": self.host_state,
                        "platform": {
                            "system": "Linux",
                            "os": "ubuntu",
                            "version": self.host_version,
                            "architecture": "x86_64",
                        },
                        "mutationPerformed": False,
                    }
                },
            )
            result["versions"]["jbpa"] = "1.0.0-rc3"
            return json.dumps(result)
        result = envelope(
            self.operation.lower(),
            0,
            {"status": "COMPLETE", "requestedVersion": "12.10"},
        )
        result["versions"]["jbpa"] = "1.0.0-rc3"
        return json.dumps(result)


class SSHHandoffTests(unittest.TestCase):
    def test_guest_manifest_must_match_pinned_archive(self):
        archive = Path(__file__).resolve().parents[2] / "dist/jbpa-1.0.0-rc3.tar.gz"
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(tmp)
            release = Path(tmp) / "jbpa-1.0.0-rc3"
            with patch("tools.handoff.guest_prepare._check_parent"):
                self.assertEqual(verify_installed(release, archive)["jbpaVersion"], "1.0.0-rc3")
                (release / "release-manifest.json").write_text("{}")
                with self.assertRaisesRegex(DeliveryError, "RELEASE_MANIFEST_INVALID"):
                    verify_installed(release, archive)

    def test_install_invokes_one_first_class_operation_after_preflight(self):
        transport = SyntheticTransport("INSTALL")
        with (
            patch("tools.handoff.ssh.digest", return_value=EXPECTED_SHA),
            patch("tools.handoff.ssh.load_config", return_value=({}, "config")),
        ):
            outcome = run(request("INSTALL"), transport, "/tmp/rc3.tar.gz", "/tmp/agent.yaml")
        self.assertTrue(outcome["decision"]["success"])
        self.assertEqual(len(transport.deliveries), 3)
        invocation = [c for c in transport.commands if "install" in c and "-d" not in c]
        self.assertEqual(len(invocation), 1)
        self.assertIn("--allow-unqualified", invocation[0])
        self.assertIn("--controlled-test", invocation[0])

    def test_reinstall_is_one_operation_not_composed(self):
        transport = SyntheticTransport("REINSTALL")
        with patch("tools.handoff.ssh.digest", return_value=EXPECTED_SHA):
            outcome = run(request("REINSTALL"), transport, "/tmp/rc3.tar.gz")
        self.assertTrue(outcome["decision"]["success"])
        invocation = [c for c in transport.commands if "reinstall" in c]
        self.assertEqual(len(invocation), 1)
        self.assertFalse(any("uninstall" in c for c in transport.commands))
        self.assertEqual(len(transport.deliveries), 1)

    def test_preflight_stops_mutation(self):
        transport = SyntheticTransport("INSTALL", host_state="PARTIAL_HOST")
        with (
            patch("tools.handoff.ssh.digest", return_value=EXPECTED_SHA),
            patch("tools.handoff.ssh.load_config", return_value=({}, "config")),
        ):
            with self.assertRaisesRegex(HandoffError, "HOST_STATE_UNEXPECTED"):
                run(request("INSTALL"), transport, "/tmp/rc3.tar.gz", "/tmp/agent.yaml")
        self.assertFalse(any("install" in c and "-d" not in c for c in transport.commands))

    def test_ubuntu24_target_stops_before_lifecycle(self):
        transport = SyntheticTransport("INSTALL", host_version="24.04")
        with (
            patch("tools.handoff.ssh.digest", return_value=EXPECTED_SHA),
            patch("tools.handoff.ssh.load_config", return_value=({}, "config")),
        ):
            with self.assertRaisesRegex(HandoffError, "HOST_PLATFORM_UNEXPECTED"):
                run(request("INSTALL"), transport, "/tmp/rc3.tar.gz", "/tmp/agent.yaml")
        self.assertFalse(any("install" in c and "-d" not in c for c in transport.commands))

    def test_strict_host_key_and_no_shell_interpolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            key, known = Path(tmp) / "key", Path(tmp) / "known_hosts"
            key.write_text("fixture")
            known.write_text("fixture")
            transport = SSHTransport("qa-ubuntu22.example", "azureuser", key, known)
            with patch("tools.handoff.ssh.subprocess.run") as proc:
                proc.return_value.returncode = 0
                proc.return_value.stdout = b""
                transport.command(["printf", "%s", "a;$(touch /tmp/never)"])
                argv = proc.call_args.args[0]
            self.assertIn("StrictHostKeyChecking=yes", argv)
            self.assertIn("BatchMode=yes", argv)
            self.assertEqual(argv[0], "ssh")
            self.assertIn("'a;$(touch /tmp/never)'", argv[-1])


if __name__ == "__main__":
    unittest.main()
