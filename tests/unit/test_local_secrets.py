"""Local-file credentials are resolved only from private, regular files."""

import copy
import os
import tempfile
import unittest
from pathlib import Path

from jbpa.config import ROOT, load_config
from jbpa.errors import FrameworkError
from jbpa.host_readiness import Probe
from jbpa.local_secrets import LocalFileSecretProvider


class LocalSecretTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "secrets"
        self.directory.mkdir(mode=0o700)
        self.provider = LocalFileSecretProvider(str(self.directory))

    def write(self, name="credential", value=b"sample-value", mode=0o600):
        path = self.directory / name
        path.write_bytes(value)
        path.chmod(mode)
        return path

    def resolve(self, name="credential"):
        return self.provider.resolve({"provider": "local-file", "reference": name})

    def assert_error(self, code, name="credential"):
        with self.assertRaises(FrameworkError) as caught:
            self.resolve(name)
        self.assertEqual(caught.exception.spec.name, code)

    def test_private_file_is_resolved_and_cleared(self):
        self.write()
        secret = self.resolve()
        self.assertEqual(secret.reveal(), "sample-value")
        self.assertEqual(str(secret), "[REDACTED]")
        self.provider.clear()
        self.assertIsNone(secret.reveal())

    def test_missing_empty_and_invalid_content(self):
        self.assert_error("LOCAL_SECRET_NOT_FOUND")
        self.write(value=b"")
        self.assert_error("LOCAL_SECRET_EMPTY")
        self.write(value=b"line\n")
        self.assert_error("LOCAL_SECRET_INVALID")
        self.write(value=b"\xff")
        self.assert_error("LOCAL_SECRET_INVALID")

    def test_unsafe_permissions_and_links(self):
        path = self.write(mode=0o644)
        self.assert_error("LOCAL_SECRET_UNSAFE")
        path.chmod(0o600)
        (self.directory / "alias").symlink_to(path)
        self.assert_error("LOCAL_SECRET_UNSAFE", "alias")
        os.link(path, self.directory / "hardlink")
        self.assert_error("LOCAL_SECRET_UNSAFE")

    def test_directory_must_be_private(self):
        self.write()
        self.directory.chmod(0o755)
        self.assert_error("LOCAL_SECRET_UNSAFE")

    def test_size_and_reference_boundaries(self):
        self.write(value=b"a" * 65537)
        self.assert_error("LOCAL_SECRET_UNSAFE")
        with self.assertRaises(FrameworkError):
            self.resolve("../credential")
        with self.assertRaises(FrameworkError):
            self.provider.resolve({"provider": "azure-key-vault", "reference": "credential"})

    def test_template_secrets_work_in_readiness(self):
        config = copy.deepcopy(load_config(ROOT / "config/examples/local-file-qa.example.yaml")[0])
        config["secrets"]["directory"] = str(self.directory)
        values = {
            "pa-registration-token": "example-token",
            "pa-cloud-url": "https://na-east.jitterbit.com",
            "pa-agent-group-id": "123",
            "pa-agent-name-prefix": "qa-agent",
            "pa-deregister-on-drainstop": "false",
            "pa-retry-count": "10",
            "pa-retry-interval-seconds": "5",
        }
        for name, value in values.items():
            self.write(name, value.encode())
        status, reason = Probe().secrets(config)
        self.assertEqual((status, reason), ("PASS", "SECRET_PROVIDER_READY"))
        (self.directory / "pa-registration-token").chmod(0o644)
        self.assertEqual(Probe().secrets(config)[0], "FAIL")


if __name__ == "__main__":
    unittest.main()
