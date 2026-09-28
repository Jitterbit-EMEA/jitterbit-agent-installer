"""Readiness scenarios use bounded fake observations, never network or mutation."""

import copy
import subprocess
import unittest
from unittest.mock import patch

from test_uninstall import FakeBackend

from jbpa import host_readiness as hr
from jbpa.config import ROOT, load_config

HOST = {
    "os": "ubuntu",
    "version": "24.04",
    "system": "Linux",
    "architecture": "x86_64",
    "kernel": "fixture",
    "packageType": "deb",
    "codename": "noble",
    "cpuCount": 4,
    "memoryBytes": 8 * hr.GIB,
    "diskTotalBytes": 60 * hr.GIB,
}


class Probe:
    def __init__(self):
        self.priv = "ROOT"
        self.manager = "PACKAGE_MANAGER_READY"
        self.repo = "PASS"
        self.free = 20 * hr.GIB
        self.resolve = "PASS"
        self.sync = ("PASS", "TIME_SYNC_READY")
        self.net = ("PASS", "TLS_VERIFIED_HTTP_REACHABLE")
        self.secret = ("PASS", "SECRET_PROVIDER_READY")
        self.backend = FakeBackend(running=False, installed=False, clean=True)
        self.calls = []

    def privilege(self):
        return self.priv

    def package(self):
        return self.manager

    def repository(self):
        return self.repo

    def disk(self, path):
        return {"totalBytes": 60 * hr.GIB, "freeBytes": self.free, "availableBytes": self.free}

    def dns(self, host):
        self.calls.append(("dns", host))
        return self.resolve

    def network(self, url):
        self.calls.append(("net", url))
        return self.net

    def time(self):
        return self.sync

    def secrets(self, config):
        config["harmony"]["cloud_url"] = "https://harmony.example.invalid"
        self.calls.append(("secrets",))
        return self.secret

    def state(self):
        return self.backend.snapshot()


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "config/examples/azure-qa.example.yaml")[0]
        self.probe = Probe()
        self.host = copy.deepcopy(HOST)

    def run_check(self, **kwargs):
        return hr.run(self.config, host=self.host, probe=self.probe, **kwargs)

    def test_supported_os(self):
        self.assertNotEqual(self.run_check()["status"], "FAIL")

    def test_unsupported_os(self):
        self.host["os"] = "unknown"
        self.assertEqual(self.run_check()["checks"]["os"]["status"], "FAIL")

    def test_unsupported_architecture(self):
        self.host["architecture"] = "aarch64"
        self.assertEqual(
            self.run_check()["checks"]["architecture"]["reason"], "UNSUPPORTED_ARCHITECTURE"
        )

    def test_root(self):
        self.assertEqual(self.run_check()["checks"]["privilege"]["status"], "PASS")

    def test_sudo_dry_run(self):
        self.probe.priv = "SUDO_AVAILABLE"
        self.assertEqual(self.run_check(dry_run=True)["checks"]["privilege"]["status"], "WARN")

    def test_sudo_requires_explicit_elevation_for_execution(self):
        self.probe.priv = "SUDO_AVAILABLE"
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_no_privilege(self):
        self.probe.priv = "NONE"
        self.assertEqual(
            self.run_check()["checks"]["privilege"]["reason"], "INSUFFICIENT_PRIVILEGE"
        )

    def test_package_manager_busy(self):
        self.probe.manager = "PACKAGE_MANAGER_BUSY"
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_package_manager_inconsistent(self):
        self.probe.manager = "PACKAGE_MANAGER_INCONSISTENT"
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_repository_unconfirmed_blocks(self):
        self.probe.repo = "UNCONFIRMED"
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_repository_failure(self):
        self.probe.repo = "FAIL"
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_dns_failure(self):
        self.probe.resolve = "FAIL"
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_dns_timeout_unconfirmed(self):
        self.probe.resolve = "UNCONFIRMED"
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_tls_failure(self):
        self.probe.net = ("FAIL", "TLS_VERIFICATION_FAILED")
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_time_unconfirmed(self):
        self.probe.sync = ("UNCONFIRMED", "TIME_SYNC_UNCONFIRMED")
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_time_failed(self):
        self.probe.sync = ("FAIL", "TIME_SYNC_FAILED")
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_disk_insufficient(self):
        self.probe.free = hr.GIB
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_operational_disk_margin(self):
        check = self.run_check(package_bytes=hr.GIB)["checks"]["space:/opt"]
        self.assertEqual(check["evidence"]["requiredBytes"], 6 * hr.GIB)

    def test_secret_unavailable(self):
        self.probe.secret = ("FAIL", "KEY_VAULT_ACCESS_DENIED")
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_dry_run_does_not_retrieve_or_probe(self):
        result = self.run_check(dry_run=True)
        self.assertFalse(self.probe.calls)
        self.assertEqual(result["checks"]["secretProvider"]["status"], "UNCONFIRMED")

    def test_clean_host(self):
        self.assertEqual(self.run_check()["hostState"], "CLEAN_HOST")

    def test_existing_agent_install_denied(self):
        self.probe.backend = FakeBackend()
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_existing_agent_reinstall_allowed(self):
        self.probe.backend = FakeBackend()
        self.assertNotEqual(self.run_check(profile="REINSTALL")["status"], "FAIL")

    def test_partial_residuals(self):
        self.probe.backend = FakeBackend(installed=False)
        self.assertEqual(self.run_check(profile="REINSTALL")["status"], "FAIL")

    def test_qa_exception_only_24(self):
        self.host["cpuCount"] = 2
        self.assertEqual(
            self.run_check(controlled_test=True)["checks"]["cpu"]["reason"], "QA_EXCEPTION"
        )

    def test_cpu_below_minimum(self):
        self.host["cpuCount"] = 2
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_memory_below_minimum(self):
        self.host["memoryBytes"] = hr.GIB
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_unknown_memory_never_passes(self):
        self.host["memoryBytes"] = None
        self.assertEqual(self.run_check()["checks"]["memory"]["status"], "UNCONFIRMED")

    def test_nonblocking_warning_preserved(self):
        result = self.run_check()
        self.assertEqual(result["status"], "PASS_WITH_WARNINGS")
        self.assertFalse(result["checks"]["agentServices"]["blocking"])

    def test_timeout_is_bounded(self):
        with patch(
            "jbpa.host_readiness.subprocess.run", side_effect=subprocess.TimeoutExpired([], 5)
        ):
            self.assertEqual(hr.Probe().command(["fixture"], 5), (None, ""))

    def test_network_does_not_accept_tls_failure(self):
        p = hr.Probe()
        with patch.object(p, "command", return_value=(60, "")):
            self.assertEqual(
                p.network("https://example.invalid"), ("FAIL", "TLS_VERIFICATION_FAILED")
            )

    def test_network_http_auth_is_separate(self):
        p = hr.Probe()
        with patch.object(p, "command", return_value=(0, "403")):
            self.assertEqual(p.network("https://example.invalid")[0], "PASS")

    def test_snapshot_no_credentials_content(self):
        self.assertNotIn(
            "credentialsContent", self.run_check()["checks"]["existingAgent"]["evidence"]
        )

    def test_structured_schema(self):
        from jbpa.config import validate_schema

        validate_schema(self.run_check(), "host-readiness")

    def test_unknown_snapshot_not_clean(self):
        self.probe.state = lambda: {}
        result = self.run_check()
        self.assertEqual(result["hostState"], "UNKNOWN_STATE")
        self.assertEqual(result["status"], "FAIL")

    def test_actual_dpkg_audit_clean(self):
        p = hr.Probe()
        with (
            patch("jbpa.host_readiness.shutil.which", return_value="/fixture"),
            patch("jbpa.host_readiness.os.access", return_value=True),
            patch.object(p, "command", return_value=(0, "")),
            patch("jbpa.host_readiness.os.open", side_effect=FileNotFoundError),
        ):
            self.assertEqual(p.package(), "PACKAGE_MANAGER_READY")

    def test_actual_dpkg_audit_inconsistent(self):
        p = hr.Probe()
        with (
            patch("jbpa.host_readiness.shutil.which", return_value="/fixture"),
            patch("jbpa.host_readiness.os.access", return_value=True),
            patch.object(p, "command", return_value=(0, "package not configured")),
        ):
            self.assertEqual(p.package(), "PACKAGE_MANAGER_INCONSISTENT")

    def test_actual_dpkg_lock_busy(self):
        p = hr.Probe()
        with (
            patch("jbpa.host_readiness.shutil.which", return_value="/fixture"),
            patch("jbpa.host_readiness.os.access", return_value=True),
            patch.object(p, "command", return_value=(0, "")),
            patch("jbpa.host_readiness.os.open", return_value=123),
            patch("jbpa.host_readiness.os.close"),
            patch("jbpa.host_readiness.fcntl.lockf", side_effect=BlockingIOError),
        ):
            self.assertEqual(p.package(), "PACKAGE_MANAGER_BUSY")

    def test_repository_never_refreshes(self):
        p = hr.Probe()
        with patch.object(p, "command", return_value=(0, "")) as command:
            self.assertEqual(p.repository(), "PASS")
            argv = command.call_args.args[0]
            self.assertIn("-s", argv)
            self.assertIn("unzip", argv)
            self.assertNotIn("update", argv)
            self.assertNotIn("upgrade", argv)

    def test_install_gate_blocks_existing_bootstrap(self):
        from jbpa import release_cli

        ready = self.run_check()
        ready["status"] = "FAIL"
        with (
            patch("jbpa.release_cli.detect", return_value=self.host),
            patch("jbpa.host_readiness.run", return_value=ready) as engine,
            patch("jbpa.bootstrap.execute") as mutation,
        ):
            code, data = release_cli.install(
                [
                    "--config",
                    str(ROOT / "config/examples/azure-qa.example.yaml"),
                    "--controlled-test",
                    "--non-interactive",
                ]
            )
        self.assertNotEqual(code, 0)
        mutation.assert_not_called()
        engine.assert_called_once()
        self.assertEqual(data["preflight"]["status"], "FAIL")

    def test_validate_uses_canonical_engine(self):
        from jbpa import release_cli

        with patch("jbpa.host_readiness.run", return_value=self.run_check()) as engine:
            code, data = release_cli.dispatch(
                "validate", ["--config", str(ROOT / "config/examples/azure-qa.example.yaml")]
            )
        self.assertEqual(code, 0)
        engine.assert_called_once()
        self.assertIn("preflight", data)

    def test_local_failure_prevents_secret_or_network_calls(self):
        self.host["memoryBytes"] = None
        result = self.run_check()
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(self.probe.calls)
        self.assertEqual(result["checks"]["secretProvider"]["reason"], "LOCAL_PREREQUISITE_FAILED")

    def test_actual_services_unknown_never_true(self):
        snapshot = self.probe.backend.snapshot()
        snapshot["rootPresent"] = True
        backend = type(
            "StateBackend",
            (),
            {
                "snapshot": lambda self: snapshot,
                "command": lambda self, *args, **kwargs: subprocess.CompletedProcess([], 1, "", ""),
            },
        )()
        with patch("jbpa.host_readiness.LocalUninstallBackend", return_value=backend):
            self.assertIsNone(hr.Probe().state()["servicesRunning"])
