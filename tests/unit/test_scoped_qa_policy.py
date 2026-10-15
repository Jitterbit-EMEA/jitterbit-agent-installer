import unittest

from jbpa.qa_policy import cpu_exception


class ScopedQA(unittest.TestCase):
    def setUp(self):
        self.host = {
            "hostname": "authorized-qa",
            "os": "ubuntu",
            "version": "24.04",
            "architecture": "x86_64",
            "cpuCount": 2,
        }
        self.config = {
            "qa_policy": {
                "scoped_cpu_exception": {
                    "hostname": "authorized-qa",
                    "logical_version": "12.9",
                    "package_version": "12.9.2.2",
                    "cpu_count": 2,
                    "authorization": "EXPLICIT_USER_APPROVAL",
                }
            }
        }

    def test_exact_approved_scope(self):
        self.assertTrue(cpu_exception(self.config, self.host, "12.9", "12.9.2.2", True))

    def test_explicit_1211_scope_does_not_extend_129_approval(self):
        self.assertFalse(cpu_exception(self.config, self.host, "12.11", "12.11.3.2", True))
        self.host["hostname"] = "JBLAB-PA-AUTOMATION"
        scope = self.config["qa_policy"]["scoped_cpu_exception"]
        scope.update(
            hostname=self.host["hostname"], logical_version="12.11", package_version="12.11.3.2"
        )
        self.assertTrue(cpu_exception(self.config, self.host, "12.11", "12.11.3.2", True))
        self.assertFalse(cpu_exception(self.config, self.host, "12.11", "12.11.3.2", False))
        self.assertFalse(cpu_exception(self.config, self.host, "12.11", "12.11.3.3", True))
        self.host["hostname"] = scope["hostname"] = "other-qa"
        self.assertFalse(cpu_exception(self.config, self.host, "12.11", "12.11.3.2", True))

    def test_production_cannot_use_exception(self):
        self.assertFalse(cpu_exception(self.config, self.host, "12.9", "12.9.2.2", False))

    def test_other_host_cannot_use_exception(self):
        self.host["hostname"] = "another-host"
        self.assertFalse(cpu_exception(self.config, self.host, "12.9", "12.9.2.2", True))

    def test_other_package_cannot_use_exception(self):
        self.assertFalse(cpu_exception(self.config, self.host, "12.9", "12.9.2.3", True))

    def test_missing_approval_cannot_use_exception(self):
        self.config["qa_policy"]["scoped_cpu_exception"].pop("authorization")
        self.assertFalse(cpu_exception(self.config, self.host, "12.9", "12.9.2.2", True))

    def test_other_platform_cannot_use_exception(self):
        self.host["version"] = "22.04"
        self.assertFalse(cpu_exception(self.config, self.host, "12.9", "12.9.2.2", True))


if __name__ == "__main__":
    unittest.main()
