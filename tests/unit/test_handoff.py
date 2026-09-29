"""External caller tests: synthetic results, no cloud or product mutations."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jbpa.release_cli import envelope
from tools.handoff.caller import (
    HandoffError,
    LocalTransport,
    arguments,
    consume,
    run,
    validate,
    verify_delivery,
)

ROOT = Path(__file__).resolve().parents[2]
RC2 = "68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da"


def request():
    return {
        "schemaVersion": "1.0",
        "target": "localhost",
        "operation": "INSTALL",
        "jbpaVersion": "1.0.0-rc2",
        "paVersion": "12.10",
        "allowUnqualified": False,
        "configPath": "/etc/jbpa/agent.yaml",
        "resultPath": "/var/lib/jbpa/new-result.json",
    }


def result(code=0):
    data = envelope("install", code, {"status": "COMPLETE"})
    data["versions"]["jbpa"] = "1.0.0-rc2"  # Historical RC2 caller fixture.
    return json.dumps(data)


class RemoteMock:
    def execute(self, target, argv):
        self.target, self.argv = target, argv
        return 0

    def retrieve(self, target, path):
        self.path = path
        return result()


class HandoffTests(unittest.TestCase):
    def test_no_infrastructure_inputs(self):
        self.assertEqual(validate(request()), request())

    def test_target_required(self):
        r = request()
        del r["target"]
        with self.assertRaisesRegex(HandoffError, "REQUEST_INVALID"):
            validate(r)

    def test_azure_metadata_optional(self):
        r = request()
        r["callerMetadata"] = {"cloud": "azure", "region": "synthetic"}
        self.assertEqual(validate(r), r)

    def test_reject_infrastructure_fields(self):
        r = request()
        r["subscription"] = "synthetic"
        with self.assertRaises(HandoffError):
            validate(r)

    def test_boolean_strict(self):
        r = request()
        r["allowUnqualified"] = "false"
        with self.assertRaises(HandoffError):
            validate(r)

    def test_override_explicit_controlled(self):
        r = request()
        r.update(allowUnqualified=True, controlledTest=True)
        argv = arguments(r, "/opt/jbpa/bin/jbpa")
        self.assertEqual(argv.count("--allow-unqualified"), 1)
        self.assertIn("--controlled-test", argv)

    def test_override_denied_without_controlled(self):
        r = request()
        r["allowUnqualified"] = True
        with self.assertRaises(HandoffError):
            validate(r)

    def test_default_no_override(self):
        self.assertNotIn("--allow-unqualified", arguments(request(), "/opt/jbpa/bin/jbpa"))

    def test_command_argv(self):
        argv = arguments(request(), "/opt/jbpa/bin/jbpa")
        self.assertEqual(argv[:2], ["/opt/jbpa/bin/jbpa", "install"])
        self.assertIn("--result-file", argv)

    def test_path_rejection(self):
        r = request()
        r["resultPath"] = "/tmp/../result.json"
        with self.assertRaises(HandoffError):
            validate(r)

    def test_reinstall_capability_explicit(self):
        r = request()
        r["operation"] = "REINSTALL"
        with self.assertRaisesRegex(HandoffError, "OPERATION_UNAVAILABLE_IN_RC2"):
            validate(r)

    def test_other_command_mappings(self):
        for op, command in [
            ("HEALTH", "health"),
            ("DIAGNOSTICS", "diagnostics"),
            ("ENTERPRISE_CONFIGURE", "enterprise"),
            ("UNINSTALL", "uninstall"),
            ("ARTIFACT_VERIFY", "artifact"),
        ]:
            r = request()
            r["operation"] = op
            if op == "ENTERPRISE_CONFIGURE":
                r["expectedIdentity"] = {
                    "agentId": 1,
                    "agentGroupId": 2,
                    "agentName": "synthetic-agent",
                    "agentGroupName": "synthetic-group",
                }
            self.assertEqual(arguments(r, "/opt/jbpa/bin/jbpa")[1], command)

    def test_success(self):
        self.assertTrue(consume(request(), 0, result())["success"])

    def test_failed_result(self):
        self.assertEqual(consume(request(), 1, result(1))["reason"], "JBPA_FAILED")

    def test_nonzero_with_success(self):
        self.assertFalse(consume(request(), 2, result())["success"])

    def test_missing_result(self):
        with self.assertRaisesRegex(HandoffError, "RESULT_FILE_MISSING"):
            consume(request(), 0, None)

    def test_malformed_result(self):
        for text in ("{", "{}", "[]"):
            with self.assertRaisesRegex(HandoffError, "RESULT_SCHEMA_INVALID"):
                consume(request(), 0, text)

    def test_wrong_operation_version(self):
        data = json.loads(result())
        for field, value in [
            ("operation", "HEALTH"),
            ("versions", {"jbpa": "1.0.0-rc1", "requestedPA": None, "resolvedPA": None}),
        ]:
            d = copy.deepcopy(data)
            d[field] = value
            with self.assertRaises(HandoffError):
                consume(request(), 0, json.dumps(d))

    def test_local_no_shell(self):
        with patch("tools.handoff.caller.subprocess.run") as process:
            process.return_value.returncode = 0
            self.assertEqual(LocalTransport().execute("localhost", ["/bin/true"]), 0)
            self.assertNotIn("shell", process.call_args.kwargs)

    def test_local_wrong_host(self):
        with self.assertRaisesRegex(HandoffError, "HOST_UNREACHABLE"):
            LocalTransport().execute("remote", ["/bin/true"])

    def test_local_retrieval(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "result.json"
            text = result()
            file.write_text(text)
            self.assertEqual(LocalTransport().retrieve("localhost", str(file)), text)

    def test_local_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(HandoffError, "RESULT_FILE_MISSING"):
                LocalTransport().retrieve("localhost", str(Path(folder) / "absent"))

    def test_remote_mock_same_contract(self):
        transport = RemoteMock()
        r = request()
        r["target"] = "preprovisioned.example"
        with patch("tools.handoff.caller.verify_delivery") as verify:
            self.assertTrue(
                run(r, "/opt/jbpa/bin/jbpa", transport, archive="release", sha256=RC2)["success"]
            )
            verify.assert_called_once_with("release", RC2, "/opt/jbpa/bin/jbpa")
        self.assertEqual(transport.target, r["target"])

    def test_rc2_exact_delivery(self):
        verify_delivery(
            ROOT / "dist/jbpa-1.0.0-rc2.tar.gz", RC2, str(ROOT / "dist/jbpa-1.0.0-rc2/bin/jbpa")
        )

    def test_hash_mismatch_blocks_execution(self):
        with self.assertRaisesRegex(HandoffError, "RELEASE_DELIVERY_FAILED"):
            verify_delivery(
                ROOT / "dist/jbpa-1.0.0-rc2.tar.gz",
                "0" * 64,
                str(ROOT / "dist/jbpa-1.0.0-rc2/bin/jbpa"),
            )

    def test_no_vendor_log_parsing(self):
        source = (ROOT / "tools/handoff/caller.py").read_text()
        for vendor in ("Installer.log", "jitterbit-agent.log", "TranDb", "dpkg-query"):
            self.assertNotIn(vendor, source)

    def test_enterprise_identity_required(self):
        r = request()
        r["operation"] = "ENTERPRISE_CONFIGURE"
        with self.assertRaisesRegex(HandoffError, "REQUEST_INVALID"):
            validate(r)

    def test_enterprise_identity_forwarded(self):
        r = request()
        r["operation"] = "ENTERPRISE_CONFIGURE"
        r["expectedIdentity"] = {
            "agentId": 1,
            "agentGroupId": 2,
            "agentName": "synthetic-agent",
            "agentGroupName": "synthetic-group",
        }
        argv = arguments(r, "/opt/jbpa/bin/jbpa")
        self.assertEqual(argv[argv.index("--expected-agent-id") + 1], "1")
        self.assertEqual(argv[argv.index("--expected-agent-group-name") + 1], "synthetic-group")

    def test_rc3_reinstall_dispatch(self):
        r = request()
        r.update(
            jbpaVersion="1.0.0-rc3",
            operation="REINSTALL",
            allowUnqualified=True,
            controlledTest=True,
        )
        argv = arguments(r, "/opt/jbpa/bin/jbpa")
        self.assertEqual(argv[1], "reinstall")
        self.assertEqual(argv.count("--allow-unqualified"), 1)
        self.assertNotIn("uninstall", argv)

    def test_rc3_result_consumption(self):
        r = request()
        r.update(jbpaVersion="1.0.0-rc3", operation="REINSTALL")
        data = envelope("reinstall", 0, {"status": "COMPLETE"})
        data["versions"]["jbpa"] = "1.0.0-rc3"
        self.assertTrue(consume(r, 0, json.dumps(data))["success"])
