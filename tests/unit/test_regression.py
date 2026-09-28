import unittest

from jbpa.regression import REQUIRED_STATES, compare


class RegressionComparisonTests(unittest.TestCase):
    def observation(self):
        return {
            "resultStatus": "COMPLETE",
            "os": "ubuntu",
            "osVersion": "22.04",
            "architecture": "x86_64",
            "packageVersion": "12.10.1.1",
            "packageDependencies": "odbcinst, unixodbc, unzip",
            "paths": {
                "root": True,
                "resources": True,
                "credentials": True,
                "agent_log": True,
                "jre": True,
                "keytool": True,
                "cacerts": True,
                "register": False,
            },
            "markers": {name: True for name in REQUIRED_STATES},
            "localServices": {
                "JitterbitProcessEngine": True,
                "Scheduler": True,
                "FileCleanup": True,
                "VerboseLogShipper": True,
            },
            "allServicesRunning": True,
            "registrationDurationSeconds": 90,
        }

    def test_unchanged_contract(self):
        self.assertEqual(
            compare(self.observation(), {"polling": {"timeout_seconds": 300}})["status"],
            "UNCHANGED",
        )

    def test_detects_os_and_registration_changes(self):
        observation = self.observation()
        observation["osVersion"] = "24.04"
        observation["markers"]["AGENT_SYNCHRONIZED"] = False
        changes = compare(observation, {"polling": {"timeout_seconds": 300}})
        self.assertEqual(changes["status"], "CONTRACT_CHANGED")
        self.assertIn("target_os", changes["changes"])
        self.assertIn("marker:AGENT_SYNCHRONIZED", changes["changes"])


if __name__ == "__main__":
    unittest.main()
