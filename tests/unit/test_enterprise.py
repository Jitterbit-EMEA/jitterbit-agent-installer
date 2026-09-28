import io
import json
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from jbpa.enterprise import TruststoreWorkflow, certificate_metadata, execute
from jbpa.errors import FrameworkError

FINGERPRINT = "a" * 64
META = {
    "sha256_fingerprint": FINGERPRINT,
    "subject": "subject=QA",
    "issuer": "issuer=QA",
    "serial": "serial=1",
    "not_before_utc": "2020-01-01T00:00:00+00:00",
    "not_after_utc": "2030-01-01T00:00:00+00:00",
    "certificate_is_ca": True,
    "extended_key_usage": None,
}


class FakeTruststore(TruststoreWorkflow):
    def __init__(self, directory):
        root = Path(directory)
        keytool = root / "keytool"
        keytool.write_text("fake")
        keytool.chmod(0o700)
        store = root / "cacerts"
        store.write_bytes(b"original-store")
        super().__init__(
            keytool=keytool,
            store=store,
            jitterbit=root / "jitterbit",
            agent_log=root / "agent.log",
            backups=root / "backups",
        )
        self.aliases = {}
        self.restarts = 0
        self.health_results = [True]

    def _tool(self, args, password):
        if args[0] == "-importcert":
            alias = args[args.index("-alias") + 1]
            self.aliases[alias] = FINGERPRINT
            self.store.write_bytes(b"modified-store")
        return subprocess.CompletedProcess(args, 0, b"", b"")

    def _alias_fingerprint(self, alias, password):
        return self.aliases.get(alias)

    def _health(self):
        return True

    def _restart_and_validate(self, log_position, timeout=300, profile=None):
        self.restarts += 1
        return self.health_results.pop(0) if self.health_results else True


class TruststoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workflow = FakeTruststore(self.temp.name)
        self.cert = Path(self.temp.name) / "qa.pem"
        self.cert.write_text("synthetic-test-certificate")
        self.intent = [
            {
                "alias": "jbpa-qa-ca",
                "certificate_source": {"path": str(self.cert), "sha256": FINGERPRINT},
            }
        ]

    def apply(self, run_id="test-run"):
        with patch("jbpa.enterprise.certificate_metadata", return_value=META):
            return self.workflow.apply(self.intent, password="synthetic", run_id=run_id)

    def test_missing_store_stops_before_mutation(self):
        self.workflow.store.unlink()
        with self.assertRaises(FrameworkError) as caught:
            self.apply()
        self.assertEqual(caught.exception.spec.name, "JKS_NOT_FOUND")
        self.assertFalse(self.workflow.backups.exists())

    def test_invalid_certificate_is_rejected_without_material_in_result(self):
        with self.assertRaises(FrameworkError) as caught:
            certificate_metadata(self.cert)
        self.assertEqual(caught.exception.spec.name, "JKS_CERT_INVALID")
        self.assertNotIn("synthetic-test-certificate", str(caught.exception))

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
    def test_pem_leaf_metadata_and_expiration(self):
        private = Path(self.temp.name) / "unit-only-key.pem"
        completed = subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(private),
                "-out",
                str(self.cert),
                "-days",
                "1",
                "-subj",
                "/CN=unit.example.invalid",
                "-addext",
                "basicConstraints=critical,CA:FALSE",
                "-addext",
                "extendedKeyUsage=serverAuth",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0)
        metadata = certificate_metadata(self.cert)
        self.assertFalse(metadata["certificate_is_ca"])
        self.assertEqual(metadata["certificate_type"], "EXPLICIT_TRUSTED_ENDPOINT")
        self.assertIn("TLS Web Server Authentication", metadata["extended_key_usage"])

        class FutureDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2100, 1, 1, tzinfo=timezone.utc)

        with patch("jbpa.enterprise.datetime", FutureDatetime):
            with self.assertRaises(FrameworkError) as caught:
                certificate_metadata(self.cert)
        self.assertEqual(caught.exception.spec.name, "JKS_CERT_INVALID")

    def test_store_password_is_passed_by_environment_only(self):
        calls = []

        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0, b"", b"")

        real = TruststoreWorkflow(
            keytool=self.workflow.keytool,
            store=self.workflow.store,
            jitterbit=self.workflow.jitterbit,
            agent_log=self.workflow.agent_log,
            backups=self.workflow.backups,
            runner=runner,
        )
        real._tool(["-list"], "synthetic-test-password")
        self.assertNotIn("synthetic-test-password", " ".join(calls[0][0]))
        self.assertEqual(calls[0][1]["env"]["JBPA_STOREPASS"], "synthetic-test-password")

    def test_fingerprint_mismatch_stops_before_backup(self):
        wrong = {**META, "sha256_fingerprint": "b" * 64}
        with patch("jbpa.enterprise.certificate_metadata", return_value=wrong):
            with self.assertRaises(FrameworkError) as caught:
                self.workflow.apply(self.intent, password="synthetic", run_id="mismatch")
        self.assertEqual(caught.exception.spec.name, "JKS_CERT_INVALID")
        self.assertFalse(self.workflow.backups.exists())

    def test_alias_conflict_stops_before_mutation(self):
        self.workflow.aliases["jbpa-qa-ca"] = "b" * 64
        with self.assertRaises(FrameworkError) as caught:
            self.apply()
        self.assertEqual(caught.exception.spec.name, "JKS_ALIAS_CONFLICT")
        self.assertEqual(self.workflow.store.read_bytes(), b"original-store")

    def test_endpoint_certificate_requires_explicit_qa_choice(self):
        leaf = {
            **META,
            "certificate_is_ca": False,
            "extended_key_usage": "TLS Web Server Authentication",
        }
        with patch("jbpa.enterprise.certificate_metadata", return_value=leaf):
            with self.assertRaises(FrameworkError) as caught:
                self.workflow.apply(self.intent, password="synthetic", run_id="leaf")
            planned = self.workflow.apply(
                self.intent,
                password="synthetic",
                run_id="leaf-plan",
                dry_run=True,
                allow_endpoint=True,
            )
        self.assertEqual(caught.exception.spec.name, "JKS_CERT_INVALID")
        self.assertEqual(planned["status"], "PLANNED")

    def test_runtime_marker_check_requires_identity_and_request_flow_not_sync(self):
        self.workflow.expected_agent_id = 646830
        self.workflow.expected_group_id = 678370
        log = (
            "REST API RESPONSE: Status: true\n"
            "Agent Logged in: AgentId = 646830; AgentGroupId = 678370\n"
            "connection to agent services has been established\n"
            "Connection established, agent logged in, and request flow has commenced\n"
            "Agent synchronization for agent group ID 678370 completed\n"
        )
        self.assertTrue(self.workflow._runtime_healthy(log))
        self.assertFalse(self.workflow._runtime_healthy(log.replace("646830", "646831")))
        self.assertTrue(self.workflow._runtime_healthy(log.replace("completed", "pending")))
        self.assertFalse(self.workflow._runtime_healthy(log.replace("request flow", "no flow")))

    def test_unconfirmed_current_health_blocks_before_backup(self):
        self.workflow.expected_agent_id = 646830
        with patch.object(self.workflow, "_current_health", return_value={"status": "UNCONFIRMED"}):
            with self.assertRaises(FrameworkError) as caught:
                self.apply()
        self.assertEqual(caught.exception.spec.name, "JKS_BASELINE_UNHEALTHY")
        self.assertFalse(self.workflow.backups.exists())
        self.assertEqual(self.workflow.store.read_bytes(), b"original-store")

    def test_import_then_idempotent_second_run(self):
        first = self.apply()
        self.assertEqual(first["status"], "SUCCESS")
        self.assertEqual(self.workflow.restarts, 1)
        self.assertEqual(Path(first["backup_path"]).read_bytes(), b"original-store")
        second = self.apply("second-run")
        self.assertEqual(second["status"], "NO_CHANGE")
        self.assertFalse(second["restart_required"])
        self.assertEqual(self.workflow.restarts, 1)

    def test_dry_run_reports_missing_alias_without_mutation(self):
        with patch("jbpa.enterprise.certificate_metadata", return_value=META):
            planned = self.workflow.apply(
                self.intent, password="synthetic", run_id="dry-run", dry_run=True
            )
        self.assertEqual(planned["status"], "PLANNED")
        self.assertEqual(planned["would_import_aliases"], ["jbpa-qa-ca"])
        self.assertEqual(self.workflow.store.read_bytes(), b"original-store")
        self.assertFalse(self.workflow.backups.exists())
        self.assertEqual(self.workflow.restarts, 0)

    def test_health_failure_restores_store_and_revalidates(self):
        self.workflow.health_results = [False, True]
        with self.assertRaises(FrameworkError) as caught:
            self.apply()
        self.assertEqual(caught.exception.spec.name, "JKS_CONFIGURATION_ROLLED_BACK")
        self.assertEqual(self.workflow.store.read_bytes(), b"original-store")
        self.assertEqual(self.workflow.restarts, 2)

    def test_rollback_failure_is_distinct(self):
        self.workflow.health_results = [False, False]
        with self.assertRaises(FrameworkError) as caught:
            self.apply()
        self.assertEqual(caught.exception.spec.name, "JKS_ROLLBACK_FAILED")


class EnterpriseEntrypointTests(unittest.TestCase):
    def test_disabled_branches_are_no_change_without_root(self):
        config = Path(__file__).resolve().parents[2] / "config/agent.example.yaml"
        output = io.StringIO()
        code = execute(["--config", str(config)], stdout=output, effective_uid=lambda: 1000)
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "NO_CHANGE")
        self.assertTrue(
            all(x["status"] == "SKIPPED" for x in result["enterpriseConfiguration"].values())
        )

    def test_enabled_nonqualified_branch_is_blocked_without_mutation(self):
        import yaml

        config = Path(__file__).resolve().parents[2] / "config/agent.example.yaml"
        document = yaml.safe_load(config.read_text())
        document["proxy"].update({"enabled": True, "host": "proxy.example.invalid", "port": 8080})
        document["harmony"]["registration"]["strategy"] = "register-json-token"
        document["harmony"]["registration"]["token_secret_ref"] = {
            "provider": "azure-key-vault",
            "reference": "synthetic-token",
        }
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "agent.yaml"
            candidate.write_text(yaml.safe_dump(document))
            output = io.StringIO()
            code = execute(["--config", str(candidate)], stdout=output)
        self.assertNotEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["enterpriseConfiguration"]["proxy"]["status"],
            "REGISTRATION_MODE_INCOMPATIBLE_WITH_PROXY",
        )

    def test_alternate_proxy_registration_is_explicitly_blocked(self):
        import yaml

        config = Path(__file__).resolve().parents[2] / "config/agent.example.yaml"
        document = yaml.safe_load(config.read_text())
        document["proxy"].update({"enabled": True, "host": "proxy.example.invalid", "port": 8080})
        document["harmony"]["registration"]["strategy"] = "credentials-file"
        document["harmony"]["registration"]["token_secret_ref"] = None
        document["harmony"]["registration"]["username_secret_ref"] = {
            "provider": "azure-key-vault",
            "reference": "synthetic-user",
        }
        document["harmony"]["registration"]["password_secret_ref"] = {
            "provider": "azure-key-vault",
            "reference": "synthetic-password",
        }
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "agent.yaml"
            candidate.write_text(yaml.safe_dump(document))
            output = io.StringIO()
            code = execute(["--config", str(candidate)], stdout=output)
        self.assertNotEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(
            result["enterpriseConfiguration"]["proxy"]["status"],
            "PROXY_REGISTRATION_BLOCKED",
        )


if __name__ == "__main__":
    unittest.main()
