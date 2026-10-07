import tempfile
import unittest
from pathlib import Path

from jbpa.errors import FrameworkError
from jbpa.native_linux import (
    AGENT_LOG,
    CREDENTIALS,
    JITTERBIT,
    REGISTER_JSON,
    CommandResult,
    LocalBackend,
    NativeLinuxWorkflow,
)
from jbpa.security import Secret

SUCCESS_LOG = """
Auto Registration - Starting...
Auto Registration - Completed!
Read agent credentials file: /opt/jitterbit/Resources/credentials.txt
REST API RESPONSE: Status: true
Agent Logged in: AgentId = 100; AgentGroupId = 200
connection to agent services has been established
Connection established, agent logged in, and request flow has commenced
Agent synchronization for agent group ID 200 completed
Will send heart beats for AgentId 100
"""

HEALTHY = """JitterbitProcessEngine running
Scheduler running
FileCleanup running
VerboseLogShipper running
All services are running
"""


def config():
    return {
        "agent": {"name": "test-agent"},
        "harmony": {
            "cloud_url": "https://emea-west.jitterbit.com",
            "agent_group_id": 200,
            "registration": {
                "strategy": "register-json-token",
                "deregister_on_drainstop": False,
            },
        },
        "proxy": {"enabled": False},
        "ssh": {"enabled": False},
        "ssl": {"enabled": False},
        "java_trust": {"enabled": False},
        "health": {"registration_timeout_seconds": 15, "poll_interval_seconds": 5},
    }


def artifact(**changes):
    value = {
        "url": "https://download.example.invalid/jitterbit-agent.deb",
        "sha256": "a" * 64,
        "package_version": "12.9.2.2",
        "architecture": "x86_64",
    }
    value.update(changes)
    return value


class FakeBackend:
    def __init__(self, *, log=SUCCESS_LOG, log_at=0, credentials_at=0):
        self.now = 0
        self.log = log
        self.log_at = log_at
        self.credentials_at = credentials_at
        self.files = {"/opt/jitterbit", "/opt/jitterbit/Resources", JITTERBIT}
        self.commands = []
        self.writes = []
        self.download_error = False
        self.install_prereq_error = False
        self.installed_version = None
        self.package_version = "12.9.2.2"
        self.status = HEALTHY
        self.json_valid = True
        self.fields = {
            "Package": "jitterbit-agent",
            "Architecture": "amd64",
            "Version": "12.9.2.2",
        }

    def run(self, argv, env=None):
        self.commands.append((argv, env))
        if argv[:5] == ["apt-get", "-o", "DPkg::Lock::Timeout=120", "install", "-y"]:
            if self.install_prereq_error:
                return CommandResult(1, stderr="synthetic")
        if argv == ["dpkg-query", "-W", "-f=${Version}", "jitterbit-agent"]:
            return CommandResult(
                0 if self.installed_version else 1, (self.installed_version or "") + "\n"
            )
        if argv == ["dpkg-query", "-W", "-f=${Status}", "jitterbit-agent"]:
            return CommandResult(0, "install ok installed\n")
        if argv[:3] == ["dpkg-deb", "--field", self.package_path]:
            return CommandResult(0, self.fields[argv[3]] + "\n")
        if argv == [JITTERBIT, "status"]:
            return CommandResult(0 if "All services" in self.status else 1, self.status)
        return CommandResult(0)

    @property
    def package_path(self):
        return f"/var/tmp/jbpa/jitterbit-agent_{self.package_version}_amd64.deb"

    def exists(self, path):
        if path == AGENT_LOG:
            return self.now >= self.log_at
        if path == CREDENTIALS:
            restarted = any(command == [JITTERBIT, "restart"] for command, _ in self.commands)
            return path in self.files or (restarted and self.now >= self.credentials_at)
        return path in self.files

    def read_text(self, path):
        return self.log

    def log_position(self, path):
        return None

    def read_log_since(self, path, position):
        return self.log

    def write_private_json(self, path, value):
        self.writes.append((path, value))
        self.files.add(path)

    def validate_json(self, path):
        return self.json_valid

    def remove_registration_input(self, path):
        self.files.discard(path)

    def download(self, url, destination):
        if self.download_error:
            raise FrameworkError("DOWNLOAD_FAILED")
        self.files.add(destination)

    def sha256(self, path):
        return "a" * 64

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class NativeLinuxWorkflowTests(unittest.TestCase):
    def test_registration_capacity_errors_are_distinct(self):
        workflow = NativeLinuxWorkflow(FakeBackend())
        self.assertEqual(
            workflow._runtime_failure(
                "You have reached the maximum agents limit allowed for your organization. Auto Registration - Failed"
            ),
            "AGENT_CAPACITY_REACHED",
        )
        self.assertEqual(
            workflow._runtime_failure(
                "You've reached the maximum number of agent(s) configured for your Jitterbit organization"
            ),
            "AGENT_CAPACITY_REACHED",
        )

    def test_ten_successful_slots_then_eleventh_capacity_failure(self):
        successful = 0
        for _ in range(10):
            backend = FakeBackend()
            secret = Secret("synthetic-test-token")
            result = NativeLinuxWorkflow(backend).run(config(), artifact(), secret)
            self.assertTrue(result["harmonyRegistered"])
            successful += 1
        self.assertEqual(successful, 10)
        full_group_log = (
            "Auto Registration - Failed: You have reached the maximum agents limit "
            "allowed for your organization. Contact your Jitterbit representative."
        )
        backend = FakeBackend(log=full_group_log, credentials_at=1000)
        self.assert_error("AGENT_CAPACITY_REACHED", backend)
        self.assertIn(REGISTER_JSON, backend.files)

    def run_success(self, backend=None, cfg=None):
        backend = backend or FakeBackend()
        secret = Secret("synthetic-test-token")
        result = NativeLinuxWorkflow(backend).run(cfg or config(), artifact(), secret)
        self.assertIsNone(secret.reveal())
        return backend, result

    def assert_error(self, expected, backend=None, cfg=None, art=None):
        backend = backend or FakeBackend()
        secret = Secret("synthetic-test-token")
        with self.assertRaises(FrameworkError) as caught:
            NativeLinuxWorkflow(backend).run(cfg or config(), art or artifact(), secret)
        self.assertEqual(caught.exception.spec.name, expected)
        self.assertEqual(caught.exception.runtime_result["status"], "FAILED")
        self.assertEqual(caught.exception.runtime_result["error"]["name"], expected)
        self.assertIsNone(secret.reveal())

    def test_complete_lifecycle_and_secure_registration_shape(self):
        backend, result = self.run_success()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["state"], "COMPLETE")
        self.assertTrue(result["serviceRunning"])
        document = backend.writes[0][1]
        self.assertEqual(document["retryCount"], 10)
        self.assertNotIn("retrCount", document)
        self.assertEqual(
            sum(1 for command, _ in backend.commands if command == [JITTERBIT, "restart"]), 1
        )
        for state in (
            "AUTO_REGISTRATION_STARTED",
            "AUTO_REGISTRATION_COMPLETED",
            "CREDENTIALS_CREATED",
            "HARMONY_AUTHENTICATED",
            "AGENT_SERVICES_CONNECTED",
            "AGENT_SYNCHRONIZED",
            "LOCAL_SERVICES_HEALTHY",
        ):
            self.assertIn(state, result["stateHistory"])

    def test_dependency_preflight_failure(self):
        backend = FakeBackend()
        backend.install_prereq_error = True
        self.assert_error("PACKAGE_INSTALL_FAILED", backend)

    def test_missing_package_download(self):
        backend = FakeBackend()
        backend.download_error = True
        self.assert_error("DOWNLOAD_FAILED", backend)

    def test_wrong_package_architecture(self):
        backend = FakeBackend()
        backend.fields["Architecture"] = "arm64"
        self.assert_error("ARTIFACT_METADATA_MISMATCH", backend)

    def test_wrong_package_version(self):
        backend = FakeBackend()
        backend.fields["Version"] = "12.9.2.1"
        self.assert_error("ARTIFACT_METADATA_MISMATCH", backend)

    def test_invalid_registration_input(self):
        cfg = config()
        cfg["harmony"]["agent_group_id"] = None
        self.assert_error("REGISTER_JSON_INVALID", cfg=cfg)

    def test_malformed_written_registration_json(self):
        backend = FakeBackend()
        backend.json_valid = False
        self.assert_error("REGISTER_JSON_INVALID", backend)

    def test_existing_credentials_does_not_create_register_json(self):
        backend = FakeBackend()
        backend.files.add(CREDENTIALS)
        backend.installed_version = "12.9.2.2"
        backend, result = self.run_success(backend)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(backend.writes, [])
        self.assertFalse(
            any(command[:2] == ["dpkg", "--install"] for command, _ in backend.commands)
        )

    def test_existing_credentials_do_not_require_auto_registration_markers(self):
        backend = FakeBackend(
            log=SUCCESS_LOG.replace("Auto Registration - Starting...", "").replace(
                "Auto Registration - Completed!", ""
            )
        )
        backend.files.add(CREDENTIALS)
        backend.installed_version = "12.9.2.2"
        _, result = self.run_success(backend)
        self.assertEqual(result["status"], "COMPLETE")

    def test_registration_file_conflict(self):
        backend = FakeBackend()
        backend.files.update({CREDENTIALS, REGISTER_JSON})
        self.assert_error("REGISTRATION_STATE_CONFLICT", backend)

    def test_existing_agent_restart_succeeds_without_full_sync(self):
        log = "\n".join(
            line
            for line in SUCCESS_LOG.splitlines()
            if not any(
                marker in line
                for marker in (
                    "Auto Registration",
                    "Read agent credentials file",
                    "Agent synchronization",
                )
            )
        )
        backend = FakeBackend(log=log)
        backend.files.add(CREDENTIALS)
        backend.installed_version = "12.9.2.2"
        _, result = self.run_success(backend)
        self.assertEqual(result["verificationProfile"], "EXISTING_AGENT_RESTART")
        self.assertFalse(result["synchronizationRequired"])
        self.assertFalse(result["synchronizationObserved"])
        self.assertEqual(backend.now, 0)

    def test_initial_registration_still_requires_full_sync(self):
        backend = FakeBackend(
            log=SUCCESS_LOG.replace("Agent synchronization for agent group ID 200 completed", "")
        )
        self.assert_error("SYNCHRONIZATION_FAILED", backend)
        self.assertTrue(backend.exists(REGISTER_JSON))

    def test_existing_agent_restart_still_requires_fresh_runtime_signals(self):
        for marker in (
            "REST API RESPONSE: Status: true",
            "Agent Logged in: AgentId = 100; AgentGroupId = 200",
            "connection to agent services has been established",
            "Connection established, agent logged in, and request flow has commenced",
        ):
            with self.subTest(marker=marker):
                backend = FakeBackend(log=SUCCESS_LOG.replace(marker, ""))
                backend.files.add(CREDENTIALS)
                backend.installed_version = "12.9.2.2"
                self.assert_error(
                    "AGENT_SERVICES_CONNECTION_FAILED"
                    if marker == "connection to agent services has been established"
                    else "REGISTRATION_TIMEOUT",
                    backend,
                )

    def test_existing_agent_restart_still_requires_healthy_services(self):
        backend = FakeBackend(
            log=SUCCESS_LOG.replace("Agent synchronization for agent group ID 200 completed", "")
        )
        backend.files.add(CREDENTIALS)
        backend.installed_version = "12.9.2.2"
        backend.status = "Scheduler stopped"
        self.assert_error("LOCAL_SERVICE_FAILURE", backend)

    def test_reinstall_rejects_credentials_created_by_package(self):
        class StaleIdentityBackend(FakeBackend):
            def run(self, argv, env=None):
                result = super().run(argv, env)
                if argv[:2] == ["dpkg", "--install"]:
                    self.files.add(CREDENTIALS)
                return result

        backend = StaleIdentityBackend()
        self.assert_error("STALE_CREDENTIALS_REINTRODUCED", backend)
        self.assertFalse(backend.writes)
        self.assertFalse(any(cmd == [JITTERBIT, "restart"] for cmd, _ in backend.commands))

    def test_log_can_appear_after_restart(self):
        backend = FakeBackend(log_at=10, credentials_at=10)
        _, result = self.run_success(backend)
        self.assertIn("WAITING_FOR_AGENT_RUNTIME", result["stateHistory"])
        self.assertIn("AGENT_LOG_AVAILABLE", result["stateHistory"])

    def test_transient_error_does_not_override_success(self):
        log = (
            SUCCESS_LOG
            + "\nERROR Unable to check if Jitterbit.conf is upto date. Error reason: Agent is not running."
        )
        _, result = self.run_success(FakeBackend(log=log))
        self.assertEqual(result["status"], "COMPLETE")

    def test_registration_timeout_with_existing_credentials(self):
        backend = FakeBackend(log="agent booting", credentials_at=0)
        backend.files.add(CREDENTIALS)
        self.assert_error("REGISTRATION_TIMEOUT", backend)

    def test_credentials_not_created(self):
        backend = FakeBackend(log="agent booting", credentials_at=999)
        self.assert_error("CREDENTIALS_NOT_CREATED", backend)

    def test_auth_failure(self):
        self.assert_error(
            "REGISTRATION_AUTH_FAILED", FakeBackend(log="REST API RESPONSE: Status: false")
        )

    def test_network_failure(self):
        self.assert_error(
            "REGISTRATION_NETWORK_FAILED", FakeBackend(log="java.net.UnknownHostException")
        )

    def test_local_service_failure(self):
        backend = FakeBackend()
        backend.status = "Scheduler stopped"
        self.assert_error("LOCAL_SERVICE_FAILURE", backend)

    def test_optional_branches_fail_closed(self):
        for branch, expected in (
            ("java_trust", "JKS_CONFIGURATION_FAILED"),
            ("ssh", "SSH_CONFIGURATION_FAILED"),
            ("ssl", "SSL_CONFIGURATION_FAILED"),
            ("proxy", "REGISTRATION_MODE_INCOMPATIBLE_WITH_PROXY"),
        ):
            with self.subTest(branch=branch):
                cfg = config()
                cfg[branch]["enabled"] = True
                self.assert_error(expected, cfg=cfg)

    def test_registration_input_is_removed_only_after_success(self):
        backend, result = self.run_success()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertFalse(backend.exists(REGISTER_JSON))
        failing = FakeBackend(log="REST API RESPONSE: Status: false")
        self.assert_error("REGISTRATION_AUTH_FAILED", failing)
        self.assertTrue(failing.exists(REGISTER_JSON))

    def test_stale_log_prefix_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jitterbit-agent.log"
            path.write_text("Auto Registration - Completed!\n")
            backend = LocalBackend()
            position = backend.log_position(str(path))
            with path.open("a") as stream:
                stream.write("Agent booting\n")
            self.assertEqual(backend.read_log_since(str(path), position), "Agent booting\n")

    def test_live_pa_1210_sanitized_milestones(self):
        fixture = (
            Path(__file__).parents[1]
            / "fixtures/runtime/pa-12.10.1.1/ubuntu-24.04/jitterbit-agent.sanitized.log"
        ).read_text()
        observed = NativeLinuxWorkflow(FakeBackend())._observe(fixture, 200)
        self.assertTrue(
            {
                "AUTO_REGISTRATION_STARTED",
                "AUTO_REGISTRATION_COMPLETED",
                "CREDENTIALS_CREATED",
                "HARMONY_AUTHENTICATED",
                "AGENT_LOGGED_IN",
                "AGENT_SERVICES_CONNECTED",
                "REQUEST_FLOW_STARTED",
                "AGENT_SYNCHRONIZED",
                "HEARTBEAT_STARTED",
            }
            <= observed
        )


if __name__ == "__main__":
    unittest.main()
