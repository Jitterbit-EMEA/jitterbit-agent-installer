import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import yaml

from jbpa.azure_artifact import AzureBlobDownloader
from jbpa.azure_identity import AzureKeyVaultSecretProvider, HttpResponse, ManagedIdentity
from jbpa.bootstrap import execute
from jbpa.config import ROOT
from jbpa.errors import FrameworkError
from jbpa.host_lock import HostLock
from jbpa.native_linux import LocalBackend
from jbpa.security import Secret
from tests.unit.test_native_linux import FakeBackend

TEST_SECRET = "UNIT_TEST_SUPER_SECRET_123"


class FakeTransport:
    def __init__(self, *, imds_status=200, vault_status=200, value=TEST_SECRET):
        self.imds_status = imds_status
        self.vault_status = vault_status
        self.value = value
        self.requests = []

    def __call__(self, request, timeout, bypass_proxy=False):
        self.requests.append((request.full_url, bypass_proxy, request.headers))
        if bypass_proxy:
            return HttpResponse(
                self.imds_status,
                json.dumps({"access_token": "synthetic-identity-token"}).encode(),
            )
        return HttpResponse(self.vault_status, json.dumps({"value": self.value}).encode())


class KeyVaultTests(unittest.TestCase):
    def provider(self, transport):
        identity = ManagedIdentity(transport=transport)
        return AzureKeyVaultSecretProvider(
            "https://example-vault.vault.azure.net", identity, transport=transport
        )

    def test_success_and_clear(self):
        transport = FakeTransport()
        provider = self.provider(transport)
        secret = provider.resolve({"provider": "azure-key-vault", "reference": "agent-token"})
        self.assertEqual(secret.reveal(), TEST_SECRET)
        self.assertEqual(str(secret), "[REDACTED]")
        self.assertTrue(transport.requests[0][1])
        self.assertIn("Metadata", transport.requests[0][2])
        provider.clear()
        self.assertIsNone(secret.reveal())

    def test_auth_failure(self):
        self.assert_error("KEY_VAULT_AUTH_FAILED", FakeTransport(imds_status=400))

    def test_access_denied(self):
        self.assert_error("KEY_VAULT_ACCESS_DENIED", FakeTransport(vault_status=403))

    def test_missing_secret(self):
        self.assert_error("KEY_VAULT_SECRET_NOT_FOUND", FakeTransport(vault_status=404))

    def test_empty_secret(self):
        self.assert_error("KEY_VAULT_SECRET_EMPTY", FakeTransport(value=""))

    def test_network_failure(self):
        def unavailable(request, timeout, bypass_proxy=False):
            raise FrameworkError("KEY_VAULT_NETWORK_FAILED")

        provider = AzureKeyVaultSecretProvider(
            "https://example-vault.vault.azure.net",
            ManagedIdentity(transport=unavailable),
            transport=unavailable,
        )
        with self.assertRaises(FrameworkError) as caught:
            provider.resolve({"provider": "azure-key-vault", "reference": "agent-token"})
        self.assertEqual(caught.exception.spec.name, "KEY_VAULT_NETWORK_FAILED")
        self.assertNotIn(TEST_SECRET, str(caught.exception))

    def test_timeout(self):
        self.assert_error("SECRET_PROVIDER_TIMEOUT", FakeTransport(vault_status=503))

    def assert_error(self, name, transport):
        with self.assertRaises(FrameworkError) as caught:
            self.provider(transport).resolve(
                {"provider": "azure-key-vault", "reference": "agent-token"}
            )
        self.assertEqual(caught.exception.spec.name, name)
        self.assertNotIn(TEST_SECRET, str(caught.exception))


class BlobArtifactTests(unittest.TestCase):
    def test_private_blob_uses_identity_and_private_file(self):
        class Identity:
            def token(self, resource):
                self.resource = resource
                return "synthetic-storage-token"

        class Response(io.BytesIO):
            status = 200

        class Opener:
            def open(self, request, timeout):
                self.request = request
                return Response(b"synthetic-package")

        identity = Identity()
        opener = Opener()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "agent.deb"
            AzureBlobDownloader(identity, opener)(
                "https://example.blob.core.windows.net/agents/agent.deb", str(target)
            )
            self.assertEqual(target.read_bytes(), b"synthetic-package")
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(identity.resource, "https://storage.azure.com/")
        self.assertIn("Authorization", opener.request.headers)

    def test_rejects_unapproved_blob_locator_shape(self):
        with self.assertRaises(FrameworkError) as caught:
            AzureBlobDownloader(identity=None)(
                "https://example.blob.core.windows.net/agents/agent.deb?sig=unsafe", "/tmp/x"
            )
        self.assertEqual(caught.exception.spec.name, "CONFIG_INVALID")


def linux_host(version="22.04"):
    return {
        "system": "Linux",
        "os": "ubuntu",
        "version": version,
        "architecture": "x86_64",
        "packageType": "deb",
        "cpuCount": 4,
        "memoryBytes": 8000000000,
        "diskTotalBytes": 50000000000,
    }


class FakeSecretProvider:
    def __init__(self):
        self.secret = Secret(TEST_SECRET)

    def resolve(self, reference):
        return self.secret

    def clear(self):
        self.secret.clear()


class FakeJblabProvider:
    values = {
        "JBLAB-cloudUrl": "https://emea-west.jitterbit.com",
        "JBLAB-agentGroupId": "200",
        "JBLAB-agentNamePrefix": "test-agent",
        "JBLAB-deregisterAgentOnDrainstop": "false",
        "JBLAB-retryCount": "10",
        "JBLAB-retryIntervalSeconds": "5",
        "JBLAB-token": TEST_SECRET,
    }

    def __init__(self):
        self.resolved = []

    def resolve(self, reference):
        secret = Secret(self.values[reference["reference"]])
        self.resolved.append(secret)
        return secret

    def clear(self):
        for secret in self.resolved:
            secret.clear()


class FreshBackend(FakeBackend):
    def __init__(self):
        super().__init__()
        self.package_installed = False

    def run(self, argv, env=None):
        result = super().run(argv, env)
        if argv[:2] == ["dpkg", "--install"]:
            self.package_installed = True
        return result

    def exists(self, path):
        if path in ("/opt/jitterbit", "/opt/jitterbit/Resources", "/opt/jitterbit/bin/jitterbit"):
            return self.package_installed
        return super().exists(path)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config_path = Path(self.temp.name) / "agent.yaml"
        config = yaml.safe_load((ROOT / "config/agent.example.yaml").read_text())
        config["agent"]["name"] = "test-agent"
        config["harmony"]["cloud_url"] = "https://emea-west.jitterbit.com"
        config["harmony"]["agent_group_id"] = 200
        config["harmony"]["registration"]["strategy"] = "register-json-token"
        config["harmony"]["registration"]["token_secret_ref"] = {
            "provider": "azure-key-vault",
            "reference": "agent-token",
        }
        config["secrets"]["vault_uri"] = "https://example-vault.vault.azure.net"
        self.config_path.write_text(yaml.safe_dump(config))

    def invoke(
        self,
        *,
        host_version="22.04",
        approved=False,
        controlled_test=False,
        dry_run=False,
        allow_under_spec=False,
        under_spec=False,
        provider=None,
        backend=None,
        result_file=None,
    ):
        output = io.StringIO()
        args = ["--config", str(self.config_path), "--non-interactive"]
        if controlled_test:
            args.append("--controlled-test")
        if dry_run:
            args.append("--dry-run")
        if allow_under_spec:
            args.append("--allow-under-spec")
        if result_file:
            args.extend(["--result-file", str(result_file)])
        if approved:
            from jbpa.catalogue import load_catalogues

            versions, support = load_catalogues()
            versions["versions"]["12.10"]["approval"] = "approved"
            versions["versions"]["12.10"]["artifacts"][0]["sha256"] = "a" * 64
            context = patch("jbpa.bootstrap.load_catalogues", return_value=(versions, support))
        else:
            context = nullcontext()
        with context:
            code = execute(
                args,
                stdout=output,
                host_provider=lambda: {
                    **linux_host(host_version),
                    **({"cpuCount": 2, "diskTotalBytes": 31138496000} if under_spec else {}),
                },
                effective_uid=lambda: 0,
                lock_path=str(Path(self.temp.name) / "bootstrap.lock"),
                provider_factory=(lambda vault, identity: provider) if provider else None,
                backend_factory=(lambda: backend) if backend else None,
            )
        return code, json.loads(output.getvalue()), output.getvalue()

    def test_artifact_not_approved_before_secret_resolution(self):
        provider = FakeSecretProvider()
        code, result, output = self.invoke(provider=provider)
        self.assertEqual(code, 22)
        self.assertEqual(result["error"]["name"], "ARTIFACT_NOT_APPROVED")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn(TEST_SECRET, output)
        self.assertEqual(provider.secret.reveal(), TEST_SECRET)

    def test_test_only_artifact_requires_explicit_flag(self):
        self.config_path.write_text(
            (ROOT / "config/agent.jblab.ubuntu-24.04.test.yaml").read_text()
        )
        code, result, _ = self.invoke(host_version="24.04", dry_run=True)
        self.assertEqual(code, 22)
        self.assertEqual(result["error"]["name"], "ARTIFACT_NOT_APPROVED")
        code, result, _ = self.invoke(host_version="24.04", controlled_test=True, dry_run=True)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "PLANNED")
        self.assertEqual(result["executionMode"], "controlled-test")
        self.assertEqual(result["artifactApproval"], "approved_for_test")

    def test_below_minimum_disk_cannot_be_overridden(self):
        self.config_path.write_text(
            (ROOT / "config/agent.jblab.ubuntu-24.04.test.yaml").read_text()
        )
        code, result, _ = self.invoke(
            host_version="24.04", controlled_test=True, dry_run=True, under_spec=True
        )
        self.assertEqual(code, 11)
        self.assertEqual(result["error"]["name"], "PREFLIGHT_FAILED")
        self.assertEqual(result["resourcePolicy"], "BELOW_MINIMUM")
        code, result, _ = self.invoke(
            host_version="24.04",
            controlled_test=True,
            dry_run=True,
            under_spec=True,
            allow_under_spec=True,
        )
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["name"], "CONFIG_INVALID")

    def test_two_cpu_controlled_regression_is_functional_exception(self):
        self.config_path.write_text(
            (ROOT / "config/agent.jblab.ubuntu-24.04.test.yaml").read_text()
        )
        output = io.StringIO()
        code = execute(
            ["--config", str(self.config_path), "--controlled-test", "--dry-run"],
            stdout=output,
            host_provider=lambda: {**linux_host("24.04"), "cpuCount": 2},
        )
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["resourcePolicy"], "PASS_WITH_TEST_EXCEPTION")
        self.assertTrue(result["cpuTestException"])
        self.assertFalse(result["productionSizingValidated"])

    def test_one_cpu_controlled_regression_is_blocked(self):
        self.config_path.write_text(
            (ROOT / "config/agent.jblab.ubuntu-24.04.test.yaml").read_text()
        )
        output = io.StringIO()
        code = execute(
            ["--config", str(self.config_path), "--controlled-test", "--dry-run"],
            stdout=output,
            host_provider=lambda: {**linux_host("24.04"), "cpuCount": 1},
        )
        result = json.loads(output.getvalue())
        self.assertEqual(code, 11)
        self.assertEqual(result["resourcePolicy"], "BELOW_MINIMUM")

    def test_controlled_test_complete_without_production_approval(self):
        self.config_path.write_text(
            (ROOT / "config/agent.jblab.ubuntu-24.04.test.yaml").read_text()
        )
        backend = FreshBackend()
        backend.package_version = "12.10.1.1"
        backend.fields["Version"] = "12.10.1.1"
        backend.sha256 = lambda path: (
            "604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8"
        )
        code, result, output = self.invoke(
            host_version="24.04",
            controlled_test=True,
            provider=FakeJblabProvider(),
            backend=backend,
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertNotIn(TEST_SECRET, output)

    def test_controlled_test_refuses_stale_agent_before_secret_resolution(self):
        self.config_path.write_text(
            (ROOT / "config/agent.jblab.ubuntu-24.04.test.yaml").read_text()
        )
        backend = FakeBackend()
        backend.files.add("/opt/jitterbit/Resources/credentials.txt")
        provider = FakeJblabProvider()
        code, result, output = self.invoke(
            host_version="24.04",
            controlled_test=True,
            provider=provider,
            backend=backend,
        )
        self.assertEqual(code, 42)
        self.assertEqual(result["error"]["name"], "REGISTRATION_STATE_CONFLICT")
        self.assertEqual(provider.resolved, [])
        self.assertNotIn(TEST_SECRET, output)

    def test_os_mismatch_stops_before_artifact(self):
        code, result, _ = self.invoke(host_version="24.04")
        self.assertEqual(code, 10)
        self.assertEqual(result["error"]["name"], "UNSUPPORTED_OS")

    def test_complete_result_does_not_leak_secret(self):
        provider = FakeSecretProvider()
        backend = FakeBackend()
        backend.package_version = "12.10.1.1"
        backend.fields["Version"] = "12.10.1.1"
        code, result, output = self.invoke(approved=True, provider=provider, backend=backend)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertNotIn(TEST_SECRET, output)
        self.assertIsNone(provider.secret.reveal())

    def test_result_file_is_private_and_secret_free(self):
        backend = FakeBackend()
        backend.package_version = "12.10.1.1"
        backend.fields["Version"] = "12.10.1.1"
        destination = Path(self.temp.name).resolve() / "result.json"
        code, result, _ = self.invoke(
            approved=True,
            provider=FakeSecretProvider(),
            backend=backend,
            result_file=destination,
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(TEST_SECRET, destination.read_text())

    def test_jblab_registration_fields_resolve_without_leaking_values(self):
        self.config_path.write_text((ROOT / "config/agent.jblab.example.yaml").read_text())
        backend = FakeBackend()
        backend.package_version = "12.10.1.1"
        backend.fields["Version"] = "12.10.1.1"
        provider = FakeJblabProvider()
        code, result, output = self.invoke(approved=True, provider=provider, backend=backend)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(len(provider.resolved), 7)
        self.assertTrue(all(secret.reveal() is None for secret in provider.resolved))
        self.assertNotIn(TEST_SECRET, output)
        self.assertNotIn("https://emea-west.jitterbit.com", output)

    def test_jblab_unsupported_retry_value_fails_closed(self):
        self.config_path.write_text((ROOT / "config/agent.jblab.example.yaml").read_text())
        backend = FakeBackend()
        provider = FakeJblabProvider()
        provider.values = {**provider.values, "JBLAB-retryCount": "11"}
        code, result, output = self.invoke(approved=True, provider=provider, backend=backend)
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["name"], "CONFIG_INVALID")
        self.assertTrue(all(secret.reveal() is None for secret in provider.resolved))
        self.assertNotIn(TEST_SECRET, output)

    def test_existing_agent_skips_token_resolution(self):
        backend = FakeBackend(
            log=(
                "Read agent credentials file: /opt/jitterbit/Resources/credentials.txt\n"
                "REST API RESPONSE: Status: true\n"
                "Agent Logged in: AgentId = 100; AgentGroupId = 200\n"
                "connection to agent services has been established\n"
                "Connection established, agent logged in, and request flow has commenced\n"
                "Agent synchronization for agent group ID 200 completed\n"
            )
        )
        backend.installed_version = "12.10.1.1"
        backend.files.add("/opt/jitterbit/Resources/credentials.txt")
        provider = FakeSecretProvider()
        code, result, _ = self.invoke(approved=True, provider=provider, backend=backend)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(provider.secret.reveal(), TEST_SECRET)

    def test_host_lock_refuses_parallel_run(self):
        lock_path = str(Path(self.temp.name) / "exclusive.lock")
        with HostLock(lock_path):
            with self.assertRaises(FrameworkError) as caught:
                with HostLock(lock_path):
                    pass
        self.assertEqual(caught.exception.spec.name, "LIFECYCLE_ACTION_REQUIRED")

    def test_hardened_registration_write(self):
        path = Path(self.temp.name) / "register.json"
        backend = LocalBackend()
        with (
            patch("jbpa.native_linux.pwd.getpwnam") as user,
            patch("jbpa.native_linux.grp.getgrnam") as group,
            patch("jbpa.native_linux.os.chown") as chown,
        ):
            user.return_value.pw_uid = 101
            group.return_value.gr_gid = 102
            backend.write_private_json(str(path), {"token": TEST_SECRET})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        chown.assert_called_once()
        self.assertEqual(json.loads(backend.read_text(str(path))), {"token": TEST_SECRET})


class WrapperTests(unittest.TestCase):
    def run_wrapper(self, exit_code):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_root = root / "bundle"
            (bundle_root / "bin").mkdir(parents=True)
            (bundle_root / "wheels").mkdir()
            (bundle_root / "requirements.txt").write_text("")
            binary = bundle_root / "bin/jbpa-bootstrap"
            binary.write_text(f"#!/bin/sh\nexit {exit_code}\n")
            binary.chmod(0o755)
            archive = root / "bundle.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                for item in ("bin", "wheels", "requirements.txt"):
                    tar.add(bundle_root / item, arcname=item)
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            config = root / "agent.yaml"
            config.write_text("nonsecret: true\n")
            wrapper = ROOT / "azure/custom-script/bootstrap.sh"
            outcome = subprocess.run(
                [
                    "bash",
                    str(wrapper),
                    str(archive),
                    digest,
                    str(config),
                    str(root / "result.json"),
                    str(root / "install"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return outcome.returncode, outcome.stdout + outcome.stderr

    def test_success_propagates(self):
        self.assertEqual(self.run_wrapper(0)[0], 0)

    def test_failure_propagates(self):
        self.assertEqual(self.run_wrapper(37)[0], 37)


if __name__ == "__main__":
    unittest.main()
