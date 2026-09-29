"""One-file customer credentials are schema-bound and private."""

import json
import tempfile
import unittest
from pathlib import Path

from jbpa.config import ROOT, load_config
from jbpa.errors import FrameworkError
from jbpa.host_readiness import Probe
from jbpa.json_secrets import JsonFileSecretProvider, parse_credentials


class JsonSecretTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "credentials.json"
        self.document = {
            "schemaVersion": 1,
            "harmony": {
                "registrationToken": "synthetic-token",
                "cloudUrl": "https://qa.example.test",
                "agentGroupId": 123,
            },
            "agent": {"namePrefix": "qa-pa"},
            "registration": {
                "deregisterOnDrainstop": False,
                "retryCount": 10,
                "retryIntervalSeconds": 5,
            },
        }

    def write(self, document=None):
        self.path.write_text(json.dumps(document or self.document))
        self.path.chmod(0o600)

    def test_resolves_fields_from_one_file_and_readiness(self):
        self.write()
        provider = JsonFileSecretProvider(str(self.path))
        token = provider.resolve(
            {"provider": "local-json", "reference": "harmony.registrationToken"}
        )
        group = provider.resolve({"provider": "local-json", "reference": "harmony.agentGroupId"})
        self.assertEqual(token.reveal(), "synthetic-token")
        self.assertEqual(group.reveal(), "123")
        provider.clear()
        self.assertIsNone(token.reveal())
        config, _ = load_config(ROOT / "config/examples/local-json-qa.example.yaml")
        config["secrets"]["file"] = str(self.path)
        self.assertEqual(Probe().secrets(config), ("PASS", "SECRET_PROVIDER_READY"))

    def test_rejects_duplicate_keys_unknown_fields_and_bad_settings(self):
        with self.assertRaises(FrameworkError):
            parse_credentials('{"schemaVersion":1,"schemaVersion":1}')
        for changed in (
            {**self.document, "unexpected": "value"},
            {**self.document, "registration": {**self.document["registration"], "retryCount": 11}},
            {**self.document, "harmony": {**self.document["harmony"], "agentGroupId": 0}},
        ):
            with self.assertRaises(FrameworkError):
                parse_credentials(json.dumps(changed))

    def test_rejects_unsafe_file(self):
        self.write()
        self.path.chmod(0o644)
        provider = JsonFileSecretProvider(str(self.path))
        with self.assertRaises(FrameworkError):
            provider.resolve({"provider": "local-json", "reference": "harmony.registrationToken"})


if __name__ == "__main__":
    unittest.main()
