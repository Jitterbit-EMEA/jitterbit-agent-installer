import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jbpa.restart_health import (
    Profile,
    SupportToolsProbe,
    connection_check,
    core_services,
    evaluate,
    identity_confirmed,
    service_status_diagnostic,
    support_service_status,
)

T0 = datetime(2026, 9, 25, 21, 32, 40, tzinfo=timezone.utc)
CURRENT = (
    "2026-09-25 21:32:43 REST API RESPONSE: Status: true\n"
    "2026-09-25 21:32:43 Agent Logged in: AgentId = 646830; AgentGroupId = 678370\n"
    "2026-09-25 21:32:44 connection to agent services has been established\n"
    "2026-09-25 21:32:44 Connection established, agent logged in, and request flow has commenced\n"
    "2026-09-25 21:32:44 Will send heart beats for AgentId 646830\n"
)
SYNC = "2026-09-25 21:32:45 Agent synchronization for agent group ID 678370 completed\n"
REGISTRATION = "2026-09-25 21:32:42 Auto Registration - Completed!\n"
LOCAL = (
    "JitterbitProcessEngine is running\nJitterbitScheduler is running\n"
    "JitterbitFileCleanup is running\nJitterbitVerboseLogShipper is running\n"
    "All services are running\n"
)


def check(profile=Profile.POST_CONFIGURATION_RESTART, log=CURRENT, **changes):
    args = {
        "log": log,
        "since": T0,
        "agent_id": 646830,
        "group_id": 678370,
        "credentials_present": True,
        "local_core_services": True,
        "connection": True,
        "support_services": True,
        "rollback_file_verified": True,
    }
    args.update(changes)
    return evaluate(profile, **args)


class HealthProfileTests(unittest.TestCase):
    def test_initial_registration_requires_completed_sync(self):
        missing = check(Profile.INITIAL_REGISTRATION, REGISTRATION + CURRENT)
        self.assertEqual(missing["status"], "FAILED")
        self.assertEqual(missing["synchronizationState"], "SYNC_REQUIRED_AND_UNCONFIRMED")
        completed = check(Profile.INITIAL_REGISTRATION, REGISTRATION + CURRENT + SYNC)
        self.assertEqual(completed["status"], "HEALTHY")
        self.assertTrue(completed["synchronizationRequired"])

    def test_existing_start_and_restart_do_not_require_fresh_sync(self):
        for profile in (Profile.EXISTING_AGENT_START, Profile.EXISTING_AGENT_RESTART):
            with self.subTest(profile=profile):
                result = check(profile)
                self.assertEqual(result["status"], "HEALTHY")
                self.assertFalse(result["freshSynchronizationObserved"])

    def test_post_configuration_restart_without_fresh_sync(self):
        result = check()
        self.assertEqual(result["status"], "HEALTHY")
        self.assertEqual(result["synchronizationState"], "FRESH_SYNC_MARKER_NOT_OBSERVED")

    def test_post_rollback_restart_without_fresh_sync(self):
        self.assertEqual(check(Profile.POST_ROLLBACK_RESTART)["status"], "HEALTHY")
        self.assertEqual(
            check(Profile.POST_ROLLBACK_RESTART, rollback_file_verified=False)["status"],
            "FAILED",
        )

    def test_fresh_harmony_authentication_and_identity_required(self):
        self.assertEqual(
            check(log=CURRENT.replace("REST API RESPONSE: Status: true", "Status: false"))[
                "status"
            ],
            "FAILED",
        )
        self.assertEqual(check(log=CURRENT.replace("646830", "646831"))["status"], "FAILED")

    def test_fresh_agent_services_and_request_flow_required(self):
        self.assertEqual(
            check(log=CURRENT.replace("connection to agent services has been established", ""))[
                "status"
            ],
            "FAILED",
        )
        self.assertEqual(
            check(log=CURRENT.replace("request flow has commenced", "request flow pending"))[
                "status"
            ],
            "FAILED",
        )

    def test_historical_markers_cannot_satisfy_restart(self):
        old = CURRENT.replace("2026-09-25 21:32", "2026-09-25 19:57")
        self.assertEqual(check(log=old)["status"], "FAILED")
        self.assertEqual(
            check(
                log=old + CURRENT.replace("connection to agent services has been established", "")
            )["status"],
            "FAILED",
        )

    def test_failed_product_probes_block_health(self):
        for change in (
            {"connection": False},
            {"local_core_services": False},
            {"credentials_present": False},
        ):
            with self.subTest(change=change):
                self.assertEqual(check(**change)["status"], "FAILED")
        self.assertEqual(check(support_services=None)["status"], "HEALTHY")

    def test_existing_profiles_allow_unavailable_service_status(self):
        for profile in (
            Profile.EXISTING_AGENT_START,
            Profile.EXISTING_AGENT_RESTART,
            Profile.POST_CONFIGURATION_RESTART,
            Profile.POST_ROLLBACK_RESTART,
        ):
            with self.subTest(profile=profile):
                result = check(
                    profile, support_services=service_status_diagnostic("Command | Pid\n---", 0)
                )
                self.assertEqual(result["status"], "HEALTHY")
                self.assertEqual(result["serviceStatus"]["status"], "UNAVAILABLE")
                self.assertFalse(result["serviceStatusMandatory"])

    def test_service_launcher_failure_is_supplementary(self):
        result = check(support_services=service_status_diagnostic("", 1))
        self.assertEqual(result["serviceStatus"]["status"], "FAILED")
        self.assertEqual(result["status"], "HEALTHY")

    def test_steady_state_needs_identity_not_restart_logs(self):
        result = check(
            Profile.STEADY_STATE_EXISTING_AGENT,
            log="",
            since=None,
            agent_identity_confirmed=True,
            support_services=None,
        )
        self.assertEqual(result["status"], "HEALTHY")
        self.assertIsNone(result["logSinceUtc"])
        self.assertFalse(result["harmonyAuthenticated"])
        historical = check(
            Profile.STEADY_STATE_EXISTING_AGENT,
            log=CURRENT + SYNC,
            since=None,
            agent_identity_confirmed=True,
        )
        self.assertTrue(historical["historicalSynchronizationObserved"])
        self.assertFalse(historical["freshSynchronizationObserved"])
        self.assertEqual(historical["synchronizationState"], "NOT_REQUIRED_STEADY_STATE")

    def test_steady_state_identity_and_product_checks_are_mandatory(self):
        for changes in (
            {"agent_identity_confirmed": False},
            {"connection": False},
            {"local_core_services": False},
            {"credentials_present": False},
        ):
            options = {"since": None, "agent_identity_confirmed": True, **changes}
            self.assertEqual(
                check(Profile.STEADY_STATE_EXISTING_AGENT, **options)["status"], "FAILED"
            )

    def test_service_rows_available_remain_supporting(self):
        diagnostic = service_status_diagnostic("Command | Pid\nApache | 42\n", 0)
        result = check(support_services=diagnostic)
        self.assertEqual(result["serviceStatus"]["status"], "AVAILABLE")
        self.assertEqual(result["serviceStatus"]["rowsReturned"], 1)
        self.assertEqual(result["status"], "HEALTHY")

    def test_about_identity_must_match_all_expected_fields(self):
        about = {"VersionNumber": "12.10.1.1", "Agent_Name": "qa", "Agent_Group_Name": "group"}
        self.assertTrue(
            identity_confirmed(about, version="12.10.1.1", agent_name="qa", group_name="group")
        )
        self.assertFalse(
            identity_confirmed(about, version="12.10.1.1", agent_name="wrong", group_name="group")
        )

    def test_fresh_sync_is_supporting_for_existing_agent(self):
        result = check(log=CURRENT + SYNC)
        self.assertEqual(result["status"], "HEALTHY")
        self.assertTrue(result["freshSynchronizationObserved"])
        self.assertFalse(result["synchronizationRequired"])

    def test_core_status_requires_each_running_service(self):
        self.assertTrue(core_services(LOCAL, 0))
        self.assertFalse(core_services(LOCAL.replace("JitterbitScheduler is running", ""), 0))
        self.assertFalse(core_services(LOCAL, 1))


class SupportToolsTests(unittest.TestCase):
    def test_connection_check_requires_all_three_destinations(self):
        output = (
            "Harmony gateway is reachable\n"
            "Apache Is reachable on port 46908\nTomcat is reachable on port 46912\n"
        )
        self.assertIs(connection_check(output, 0), True)
        self.assertIsNone(connection_check(output.replace("Tomcat is reachable", "Tomcat"), 0))
        self.assertIs(connection_check("Harmony gateway is unreachable", 0), False)

    def test_empty_service_table_is_unconfirmed(self):
        header = "Command | Pid | Start time | %CPU | %MEM | Full command\n----------\n"
        self.assertIsNone(support_service_status(header, 0))
        full = header + "\n".join(
            f"{name} | {i} | now | 0 | 0 | {name}"
            for i, name in enumerate(
                ("Apache", "Tomcat", "Postgres", "Pgbouncer", "VerboseLogShipper"), 1
            )
        )
        self.assertIs(support_service_status(full, 0), True)
        self.assertIsNone(support_service_status(full.replace(" | 1 |", " | unknown |"), 0))
        self.assertIs(support_service_status(full, 1), False)

    def test_probe_uses_documented_interactive_command_only(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, b"VersionNumber | 12.10.1.1\n", b"")

        probe = SupportToolsProbe(Path("/tmp/qa-support-tools"), runner)
        probe.run("about")
        self.assertEqual(calls[0][0], ["/bin/bash", "/tmp/qa-support-tools/run.sh"])
        self.assertEqual(calls[0][1]["input"], b"about\nexit\n")
        with self.assertRaises(ValueError):
            probe.run("resync-deploylogs")


if __name__ == "__main__":
    unittest.main()
