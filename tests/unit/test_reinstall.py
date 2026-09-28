"""Real removal workflow with fake host/backend and injected fresh installer."""

import copy
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from test_host_readiness import HOST, Probe
from test_uninstall import FakeBackend, FakeProvider

from jbpa import reinstall, release_cli
from jbpa.config import ROOT, validate_schema
from jbpa.errors import FrameworkError

MARKERS = [
    "REGISTER_JSON_CREATED",
    "AUTO_REGISTRATION_COMPLETED",
    "CREDENTIALS_CREATED",
    "HARMONY_AUTHENTICATED",
    "AGENT_SERVICES_CONNECTED",
    "AGENT_SYNCHRONIZED",
    "COMPLETE",
]


class ReinstallTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.probe = Probe()
        self.probe.backend = self.backend
        self.calls = []
        self.fail = None
        self.missing = None
        self.host = copy.deepcopy(HOST)
        self.identity = SimpleNamespace(
            about=lambda: {
                "Agent_Name": "fixture",
                "Agent_Group_Name": "fixture-group",
                "VersionNumber": "12.10.1.1",
            },
            connection=lambda: True,
        )
        self.argv = [
            "--config",
            str(ROOT / "config/examples/azure-qa.example.yaml"),
            "--controlled-test",
            "--non-interactive",
        ]

    def install(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if "--dry-run" in argv:
            return 0, {"status": "PLANNED"}
        if self.fail:
            exc = FrameworkError(self.fail)
            return exc.spec.exitCode, {
                "status": "FAILED",
                "error": exc.as_dict(),
                "stateHistory": ["PACKAGE_INSTALLED"],
            }
        history = [m for m in MARKERS if m != self.missing]
        return 0, {
            "status": "COMPLETE",
            "serviceRunning": True,
            "harmonyRegistered": True,
            "stateHistory": history,
        }

    def execute(self, provider=None):
        with (
            patch("jbpa.host_readiness.detect", return_value=self.host),
            patch("jbpa.reinstall.os.geteuid", return_value=0),
            patch("jbpa.uninstall.sys.platform", "linux"),
            patch(
                "jbpa.artifacts.inspect",
                return_value=(
                    {"package_version": "12.10.1.1", "byte_size": 660897206},
                    ROOT / "tests/fixtures/unused.deb",
                ),
            ),
        ):
            return reinstall.execute(
                self.argv,
                backend=self.backend,
                provider=provider or FakeProvider([0]),
                probe=self.probe,
                install_fn=self.install,
                identity_probe=self.identity,
                lock_factory=lambda: nullcontext(),
            )

    def test_success_registered(self):
        code, data = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(data["state"], "REINSTALL_COMPLETE")

    def test_unregistered_installed(self):
        original = self.backend.snapshot

        def snapshot():
            s = original()
            s["credentialsPresent"] = False
            return s

        self.backend.snapshot = snapshot
        self.assertEqual(self.execute()[0], 0)

    def test_clean_start_continues_install(self):
        self.backend = FakeBackend(installed=False, running=False, clean=True)
        self.probe.backend = self.backend
        code, data = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(data["reinstall"]["drain"], "NOT_APPLICABLE")

    def test_partial_state_rejected(self):
        self.backend.installed = False
        code, data = self.execute()
        self.assertNotEqual(code, 0)
        self.assertFalse(self.backend.commands)
        self.assertEqual(data["error"]["name"], "REINSTALL_STATE_UNSUPPORTED")

    def test_drain_failure_never_installs(self):
        self.backend.pause_failed = True
        code, data = self.execute()
        self.assertEqual(data["error"]["name"], "REINSTALL_DRAIN_FAILED")
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.backend.package_removed)

    def test_operation_provider_failure(self):
        from jbpa.pending_operations import OperationQueryError

        p = SimpleNamespace(active_count=lambda: (_ for _ in ()).throw(OperationQueryError()))
        self.assertEqual(self.execute(p)[1]["error"]["name"], "REINSTALL_DRAIN_FAILED")

    def test_complete_uninstall_reused(self):
        self.execute()
        self.assertTrue(self.backend.package_removed)
        self.assertTrue(self.backend.user_removed)
        self.assertTrue(self.backend.residuals_removed)

    def test_clean_gate_failure(self):
        self.backend.remove_residuals = lambda: None
        code, data = self.execute()
        self.assertNotEqual(code, 0)
        self.assertEqual(len(self.calls), 1)

    def test_successful_removal_but_dirty_snapshot(self):
        def removal(argv, stdout, **kwargs):
            stdout.write('{"stateHistory":["LOCAL_UNINSTALL_COMPLETE"],"status":"SUCCESS"}')
            return 0

        with patch("jbpa.uninstall.execute", side_effect=removal):
            code, data = self.execute()
        self.assertEqual(data["error"]["name"], "REINSTALL_CLEAN_HOST_FAILED")
        self.assertEqual(len(self.calls), 1)

    def test_artifact_failure_before_uninstall(self):
        with patch("jbpa.artifacts.inspect", side_effect=FrameworkError("CHECKSUM_FAILED")):
            with patch("jbpa.host_readiness.detect", return_value=self.host):
                code, data = reinstall.execute(
                    self.argv,
                    backend=self.backend,
                    probe=self.probe,
                    lock_factory=lambda: nullcontext(),
                )
        self.assertEqual(data["error"]["name"], "CHECKSUM_FAILED")
        self.assertFalse(self.backend.commands)

    def test_qualification_denied_before_uninstall(self):
        self.host["version"] = "22.04"
        code, data = self.execute()
        self.assertEqual(data["error"]["name"], "VERSION_NOT_QUALIFIED")
        self.assertFalse(self.backend.commands)

    def test_allow_unqualified_still_enforces_os_preflight(self):
        self.host["version"] = "22.04"
        self.argv += ["--allow-unqualified"]
        self.assertEqual(self.execute()[1]["error"]["name"], "PREFLIGHT_FAILED")

    def test_install_failure_preserves_last_state(self):
        self.fail = "PACKAGE_INSTALL_FAILED"
        code, data = self.execute()
        self.assertEqual(data["error"]["name"], self.fail)
        self.assertEqual(data["lastSuccessfulState"], "PACKAGE_INSTALLED")

    def test_registration_failure(self):
        self.fail = "HARMONY_REGISTRATION_FAILED"
        code, data = self.execute()
        self.assertNotEqual(code, 0)
        self.assertFalse(data["reinstall"]["freshLocalRegistrationProved"])

    def test_missing_sync_denies_success(self):
        self.missing = "AGENT_SYNCHRONIZED"
        self.assertEqual(self.execute()[1]["error"]["name"], "REINSTALL_FRESH_REGISTRATION_FAILED")

    def test_missing_fresh_credentials_denies_success(self):
        self.missing = "CREDENTIALS_CREATED"
        self.assertNotEqual(self.execute()[0], 0)

    def test_missing_auto_registration_denies_success(self):
        self.missing = "AUTO_REGISTRATION_COMPLETED"
        self.assertNotEqual(self.execute()[0], 0)

    def test_missing_harmony_denies_success(self):
        self.missing = "HARMONY_AUTHENTICATED"
        self.assertNotEqual(self.execute()[0], 0)

    def test_health_failure(self):
        self.fail = "HEALTH_CHECK_FAILED"
        self.assertNotEqual(self.execute()[0], 0)

    def test_old_and_new_identity_scoped(self):
        section = self.execute()[1]["reinstall"]
        self.assertTrue(section["previousIdentityKnown"])
        self.assertIsNotNone(section["newIdentity"])
        self.assertFalse(section["numericallyDistinctIdentityProved"])

    def test_fresh_registration_evidence(self):
        self.assertTrue(self.execute()[1]["reinstall"]["freshLocalRegistrationProved"])

    def test_state_order(self):
        history = self.execute()[1]["stateHistory"]
        self.assertLess(history.index("CLEAN_HOST_CONFIRMED"), history.index("INSTALL_STARTED"))

    def test_rc_result_schema(self):
        code, data = self.execute()
        validate_schema(release_cli.envelope("reinstall", code, data), "rc-result")

    def test_dry_run_zero_mutation(self):
        self.argv += ["--dry-run"]
        code, data = self.execute()
        self.assertEqual(data["status"], "PLANNED")
        self.assertFalse(self.calls)
        self.assertFalse(self.backend.commands)

    def test_pinned_artifact_reused(self):
        self.execute()
        self.assertEqual(self.calls[0][1]["prepared"], self.calls[1][1]["prepared"])
        self.assertTrue(self.calls[1][1]["lock_held"])

    def test_no_automatic_force(self):
        self.backend.pause_failed = True
        self.execute()
        self.assertNotIn("stop", [c[-1] for c in self.backend.commands])

    def test_target_policy_failure_before_removal(self):
        def denied(argv, **kwargs):
            exc = FrameworkError("ARTIFACT_NOT_APPROVED")
            return exc.spec.exitCode, {"error": exc.as_dict()}

        self.install = denied
        self.assertEqual(self.execute()[1]["error"]["name"], "ARTIFACT_NOT_APPROVED")
        self.assertFalse(self.backend.commands)

    def test_host_lock_collision_prevents_removal(self):
        def denied():
            raise FrameworkError("LIFECYCLE_ACTION_REQUIRED")

        with (
            patch("jbpa.host_readiness.detect", return_value=self.host),
            patch("jbpa.artifacts.inspect", return_value=({"package_version": "12.10.1.1"}, None)),
        ):
            code, data = reinstall.execute(
                self.argv,
                backend=self.backend,
                probe=self.probe,
                install_fn=self.install,
                lock_factory=denied,
            )
        self.assertEqual(data["error"]["name"], "LIFECYCLE_ACTION_REQUIRED")
        self.assertFalse(self.backend.commands)

    def test_active_operations_polling_reused(self):
        from jbpa.uninstall import UninstallWorkflow

        def workflow(backend, provider):
            return UninstallWorkflow(backend, provider, sleeper=lambda seconds: None)

        with patch("jbpa.uninstall.UninstallWorkflow", side_effect=workflow):
            code, data = self.execute(FakeProvider([2, 1, 0]))
        self.assertEqual(code, 0)
        self.assertEqual(data["uninstallResult"]["drain"]["operationCounts"], [1, 0])
        self.assertTrue(data["uninstallResult"]["drain"]["drainPauseUsed"])
        self.assertTrue(data["uninstallResult"]["drain"]["drainStopUsed"])

    def test_target_free_space_failure_before_removal(self):
        self.install = lambda argv, **kwargs: (
            0,
            {"status": "PLANNED", "preflight": {"status": "FAIL"}},
        )
        code, data = self.execute()
        self.assertEqual(data["error"]["name"], "PREFLIGHT_FAILED")
        self.assertFalse(self.backend.commands)

    def test_unqualified_22_explicit_controlled(self):
        from jbpa.config import load_config

        config = load_config(ROOT / "config/examples/azure-qa.example.yaml")[0]
        config["agent"]["expected_os"]["version"] = "22.04"
        self.host["version"] = "22.04"
        self.argv += ["--allow-unqualified"]
        with patch("jbpa.reinstall.load_config", return_value=(config, "fixture")):
            code, data = self.execute()
        self.assertEqual(code, 0)
        self.assertTrue(data["qualification"]["overrideUsed"])

    def test_timeout_retains_previous_successful_state(self):
        import json

        exc = FrameworkError("DRAIN_PAUSE_TIMEOUT")

        def removal(argv, stdout, **kwargs):
            stdout.write(
                json.dumps(
                    {
                        "status": "FAILED",
                        "error": exc.as_dict(),
                        "stateHistory": [
                            "CURRENT_STATE_CAPTURED",
                            "DRAIN_PAUSE_REQUESTED",
                            "DRAIN_PAUSE_TIMEOUT",
                        ],
                    }
                )
            )
            return exc.spec.exitCode

        with patch("jbpa.uninstall.execute", side_effect=removal):
            code, data = self.execute()
        self.assertEqual(data["error"]["name"], "REINSTALL_DRAIN_FAILED")
        self.assertEqual(data["lastSuccessfulState"], "DRAIN_PAUSE_REQUESTED")
        self.assertEqual(len(self.calls), 1)
