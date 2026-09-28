"""Mock caller tests, explicitly not live Azure qualification."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from azure.integration.consumer import (
    consume_install,
    delivery_references,
    install_arguments,
    verify_archive,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "config/schemas/rc-result.schema.json").read_text())
PLATFORM = {"os": "ubuntu", "version": "22.04", "architecture": "x86_64"}


class AzureConsumerTests(unittest.TestCase):
    def setUp(self):
        self.result = {
            "schemaVersion": "1.0",
            "runId": "mock-only",
            "operation": "INSTALL",
            "status": "SUCCESS",
            "state": "COMPLETE",
            "category": "SUCCESS",
            "versions": {"jbpa": "1.0.0-rc2", "requestedPA": "12.10", "resolvedPA": "12.10.1.1"},
            "artifact": {},
            "platform": PLATFORM,
            "registration": {},
            "health": {},
            "enterpriseConfiguration": {},
            "error": None,
            "details": {"status": "COMPLETE", "serviceRunning": True, "harmonyRegistered": True},
        }

    def consume(self, code=0, **kwargs):
        return consume_install(
            code, json.dumps(self.result), SCHEMA, expected_platform=PLATFORM, **kwargs
        )

    def test_success(self):
        self.assertTrue(self.consume()["success"])

    def test_nonzero_exit_overrides_success_json(self):
        self.assertEqual(self.consume(30)["reason"], "JBPA_NONZERO_EXIT")

    def test_missing_result(self):
        self.assertEqual(consume_install(0, None, SCHEMA)["reason"], "MISSING_RESULT")

    def test_malformed_json(self):
        self.assertEqual(consume_install(0, "no json", SCHEMA)["reason"], "MALFORMED_RESULT_JSON")

    def test_schema_mismatch(self):
        self.result["schemaVersion"] = "2.0"
        self.assertEqual(self.consume()["reason"], "RESULT_SCHEMA_MISMATCH")

    def test_timeout_never_retries_install(self):
        result = self.consume(timed_out=True)
        self.assertEqual(result["reason"], "AZURE_DISPATCH_TIMEOUT")
        self.assertFalse(result["automaticRetry"])

    def test_hash_mismatch_stops_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive"
            path.write_bytes(b"untrusted archive")
            self.assertEqual(verify_archive(path, "0" * 64)["reason"], "JBPA_RELEASE_HASH_MISMATCH")
            self.assertTrue(
                verify_archive(path, hashlib.sha256(path.read_bytes()).hexdigest())["success"]
            )

    def test_target_os_mismatch(self):
        self.result["platform"] = {**PLATFORM, "version": "24.04"}
        self.assertEqual(self.consume()["reason"], "TARGET_OS_MISMATCH")

    def test_dispatch_arguments_explicit_unqualified_qa(self):
        args = install_arguments(
            "/opt/jbpa/bin/jbpa",
            "/etc/jbpa/agent.yaml",
            "/var/lib/jbpa/run.json",
            controlled_test=True,
            allow_unqualified=True,
        )
        self.assertEqual(args[0:2], ["/opt/jbpa/bin/jbpa", "install"])
        self.assertIn("--allow-unqualified", args)
        self.assertIn("--controlled-test", args)
        self.assertEqual(args[args.index("--version") + 1], "12.10")
        with self.assertRaises(ValueError):
            install_arguments(
                "/opt/jbpa/bin/jbpa",
                "/etc/jbpa/config",
                "/var/lib/jbpa/run",
                allow_unqualified=True,
            )

    def test_delivery_configuration_contains_only_references(self):
        value = delivery_references(["https://account.blob.core.windows.net/qa/release.tar.gz"])
        self.assertEqual(set(value), {"fileUris", "managedIdentity"})
        self.assertEqual(value["managedIdentity"], {})
        for uri in (
            "https://account.blob.core.windows.net/file?sig=credential",
            "https://user:password@example.com/file",
            "http://example.com/file",
        ):
            with self.assertRaises(ValueError):
                delivery_references([uri])

    def test_dry_run_cannot_be_install_success(self):
        self.result["details"]["status"] = "DRY_RUN"
        self.assertEqual(self.consume()["reason"], "INSTALLATION_INCOMPLETE")

    def test_mismatched_release_version(self):
        self.result["versions"]["jbpa"] = "1.0.0-rc3"
        self.assertEqual(self.consume()["reason"], "UNEXPECTED_VERSION")

    def test_transport_result_not_echoed(self):
        self.result["details"]["unexpected"] = "mock-sensitive-value"
        self.assertNotIn("mock-sensitive-value", json.dumps(self.consume()))
