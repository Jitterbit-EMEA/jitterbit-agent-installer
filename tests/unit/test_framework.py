import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from jsonschema import Draft202012Validator

from jbpa.catalogue import load_catalogues, readiness, resolve, support_for
from jbpa.cli import execute
from jbpa.config import ROOT, load_config, load_yaml, validate_schema
from jbpa.errors import ERRORS, FrameworkError
from jbpa.platform import detect, normalize_arch, parse_os_release
from jbpa.preflight import run
from jbpa.providers import require_runtime_provider
from jbpa.results import FUTURE_STATES, State, write_result
from jbpa.security import Logger, Redactor, Secret
from tests.mocks.secret_provider import MockSecretProvider


def host():
    return dict(
        os="ubuntu",
        version="22.04",
        architecture="x86_64",
        kernel="fixture",
        system="Linux",
        hostname="fixture-host",
        packageManager="apt",
        packageType="deb",
        cpuCount=4,
        memoryBytes=8000000000,
        diskTotalBytes=50000000000,
        diskAvailableBytes=40000000000,
    )


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config.yaml"
        self.config = load_yaml(ROOT / "config/agent.example.yaml")

    def load(self, data=None, **kwargs):
        self.path.write_text(yaml.safe_dump(self.config if data is None else data))
        return load_config(self.path, **kwargs)

    def invalid(self, data):
        with self.assertRaises(FrameworkError) as ctx:
            self.load(data)
        self.assertEqual(ctx.exception.spec.name, "CONFIG_INVALID")

    def cli(self, command="install", args=None, detected=None):
        out, err = io.StringIO(), io.StringIO()
        with patch("jbpa.preflight.shutil.which", return_value="/fixture/apt"):
            code = execute(
                command,
                args or [],
                stdout=out,
                stderr=err,
                host_provider=lambda: detected or host(),
                environ={},
                clock=lambda: "2026-09-22T00:00:00+00:00",
                run_id_factory=lambda: "fixture-run",
            )
        data = json.loads(out.getvalue())
        validate_schema(data, "result")
        return code, data, err.getvalue()


class ConfigurationTests(Base):
    def test_valid_example(self):
        self.assertEqual(self.load()[0]["agent"]["version"], "12.10")

    def test_required(self):
        del self.config["agent"]
        self.invalid(self.config)

    def test_enum(self):
        self.config["logging"]["level"] = "TRACE"
        self.invalid(self.config)

    def test_unknown_key(self):
        self.config["harmony"]["password"] = "synthetic-sensitive"
        self.invalid(self.config)

    def test_malformed_yaml(self):
        self.path.write_text("agent: [\n")
        with self.assertRaises(FrameworkError):
            load_yaml(self.path)

    def test_duplicate_keys(self):
        self.path.write_text("agent: a\nagent: b\n")
        with self.assertRaises(FrameworkError):
            load_yaml(self.path)

    def test_alias_rejected(self):
        self.path.write_text("a: &a [*a]\n")
        with self.assertRaises(FrameworkError):
            load_yaml(self.path)

    def test_python_tag_rejected(self):
        self.path.write_text('!!python/object/apply:os.system ["false"]')
        with self.assertRaises(FrameworkError):
            load_yaml(self.path)

    def test_yaml_size_limit(self):
        self.path.write_text("x" * 262145)
        with self.assertRaises(FrameworkError):
            load_yaml(self.path)

    def test_ssl_conditional(self):
        self.config["ssl"]["enabled"] = True
        self.invalid(self.config)

    def test_ssh_conditional(self):
        self.config["ssh"]["enabled"] = True
        self.invalid(self.config)

    def test_proxy_conditional(self):
        self.config["proxy"]["enabled"] = True
        self.invalid(self.config)

    def test_truststore_conditional(self):
        self.config["java_trust"]["enabled"] = True
        self.invalid(self.config)

    def test_timeout(self):
        self.config["health"]["registration_timeout_seconds"] = 0
        self.invalid(self.config)

    def test_interval(self):
        self.config["health"]["registration_timeout_seconds"] = 1
        self.invalid(self.config)

    def test_token_reference(self):
        reg = self.config["harmony"]["registration"]
        reg.update(
            strategy="register-json-token",
            token_secret_ref={"provider": "azure-key-vault", "reference": "example-only"},
        )
        self.assertEqual(
            self.load()[0]["harmony"]["registration"]["token_secret_ref"]["provider"],
            "azure-key-vault",
        )

    def test_insecure_provider(self):
        reg = self.config["harmony"]["registration"]
        reg.update(
            strategy="register-json-token",
            token_secret_ref={"provider": "environment", "reference": "example"},
        )
        self.invalid(self.config)

    def test_exclusive_registration(self):
        reg = self.config["harmony"]["registration"]
        ref = {"provider": "azure-key-vault", "reference": "example"}
        reg.update(strategy="register-json-token", token_secret_ref=ref, password_secret_ref=ref)
        self.invalid(self.config)

    def test_signed_url_rejected(self):
        self.config["harmony"]["cloud_url"] = "https://example.invalid/?sig=synthetic"
        self.invalid(self.config)

    def test_duplicate_identities(self):
        item = {
            "id": "test",
            "private_key_secret_ref": {"provider": "azure-key-vault", "reference": "example"},
            "target_directory": "/opt/test",
        }
        self.config["ssh"] = {"enabled": True, "identities": [item, item]}
        self.invalid(self.config)

    def test_path_traversal(self):
        self.config["output"]["result_path"] = "/tmp/../etc/test"
        self.invalid(self.config)

    def test_override_precedence(self):
        config, source = self.load(version="12.11", environ={"JITTERBIT_AGENT_VERSION": "12.12"})
        self.assertEqual((config["agent"]["version"], source), ("12.11", "cli"))

    def test_environment_override(self):
        self.assertEqual(self.load(environ={"JITTERBIT_AGENT_VERSION": "12.12"})[1], "environment")


class PlatformTests(Base):
    def test_ubuntu_fixture(self):
        h = detect(ROOT / "tests/fixtures/ubuntu-22.04.os-release", system="Linux", machine="amd64")
        self.assertEqual((h["os"], h["version"], h["architecture"]), ("ubuntu", "22.04", "x86_64"))

    def test_missing_release(self):
        self.assertEqual(detect(Path(self.temp.name) / "missing", system="Linux")["os"], "unknown")

    def test_architectures(self):
        for original, expected in [
            ("amd64", "x86_64"),
            ("x86_64", "x86_64"),
            ("arm64", "aarch64"),
            ("aarch64", "aarch64"),
            ("i686", "i686"),
        ]:
            self.assertEqual(normalize_arch(original), expected)

    def test_release_is_data(self):
        parsed = parse_os_release('ID="$(touch /do-not-create)"')
        self.assertEqual(parsed["ID"], "$(touch /do-not-create)")

    def test_unsupported_fixture(self):
        _, matrix = load_catalogues()
        h = detect(ROOT / "tests/fixtures/unsupported.os-release", system="Linux", machine="x86_64")
        self.assertEqual(support_for(h, "12.10", matrix)[0], "UNSUPPORTED")

    def test_platform_states(self):
        _, matrix = load_catalogues()
        self.assertEqual(support_for(host(), "12.10", matrix)[0], "SUPPORTED")
        h = host()
        h["os"] = "unknown"
        self.assertEqual(support_for(h, "12.10", matrix)[0], "UNKNOWN")
        self.assertEqual(support_for(host(), "12.10", {"platforms": []})[0], "NOT_CONFIGURED")


class CatalogueTests(Base):
    def test_exact_version(self):
        versions, _ = load_catalogues()
        self.assertEqual(resolve("12.10", versions)[0], "12.10")

    def test_alias(self):
        versions, _ = load_catalogues()
        versions["aliases"]["recommended"] = "12.10"
        self.assertEqual(resolve("recommended", versions)[0], "12.10")

    def test_unknown(self):
        versions, _ = load_catalogues()
        with self.assertRaises(FrameworkError):
            resolve("99.99", versions)

    def test_readiness_distinct(self):
        versions, matrix = load_catalogues()
        v, entry = resolve("12.10", versions)
        r = readiness(self.config, v, entry, matrix)
        self.assertTrue(r["known"])
        self.assertTrue(r["supportedForTarget"])
        self.assertTrue(r["downloadConfigured"])
        self.assertFalse(r["integrityConfigured"])
        self.assertFalse(r["installable"])

    def test_unsupported_version_combination(self):
        _, matrix = load_catalogues()
        self.assertEqual(support_for(host(), "12.11", matrix)[0], "UNSUPPORTED")

    def test_approved_complete_metadata_enables_qualified_adapter(self):
        versions, matrix = load_catalogues()
        v, entry = resolve("12.10", versions)
        entry["approval"] = "approved"
        entry["artifacts"][0].update(
            url="https://example.invalid/a.deb", sha256="a" * 64, package_version="12.10-fixture"
        )
        r = readiness(self.config, v, entry, matrix)
        self.assertTrue(r["downloadConfigured"])
        self.assertTrue(r["integrityConfigured"])
        self.assertTrue(r["installable"])


class SecurityTests(Base):
    def test_mock_and_redaction(self):
        redactor = Redactor()
        provider = MockSecretProvider({"example": "synthetic-sensitive-value"}, redactor)
        secret = provider.resolve({"reference": "example"})
        self.assertEqual(secret.reveal(), "synthetic-sensitive-value")
        out = io.StringIO()
        logger = Logger(out, "run", redactor)
        logger.event(
            "INFO",
            "cli",
            "finish",
            description="raw=" + secret.reveal(),
            provider_response=secret.reveal(),
        )
        self.assertNotIn(secret.reveal(), out.getvalue())
        provider.clear()
        self.assertIsNone(secret.reveal())

    def test_private_key_redaction(self):
        material = "-----BEGIN OPENSSH PRIVATE KEY-----\nsynthetic-material\n-----END OPENSSH PRIVATE KEY-----"
        self.assertEqual(Redactor().clean(material), "[REDACTED]")

    def test_nested_secret_response(self):
        self.assertEqual(
            Redactor().clean({"providerResponse": {"value": "synthetic"}})["providerResponse"],
            "[REDACTED]",
        )

    def test_opaque_secret_repr(self):
        self.assertNotIn("synthetic", str(Secret("synthetic")))

    def test_unknown_event_refused(self):
        with self.assertRaises(ValueError):
            Logger(io.StringIO(), "run").event("INFO", "cli", "secret text")

    def test_invalid_cli_does_not_echo_values(self):
        code, result, log = self.cli(args=["--password", "synthetic-sensitive-value"])
        self.assertEqual(code, 2)
        self.assertNotIn("synthetic-sensitive-value", json.dumps(result) + log)

    def test_invalid_yaml_does_not_echo_values(self):
        self.path.write_text("password: [synthetic-sensitive-value\n")
        code, result, log = self.cli(args=["--config", str(self.path)])
        self.assertEqual(code, 2)
        self.assertNotIn("synthetic-sensitive-value", json.dumps(result) + log)

    def test_runtime_provider_fail_closed(self):
        for kind in ["installer", "registration", "health", "secrets", "storage"]:
            with self.assertRaises(FrameworkError):
                require_runtime_provider(kind)


class StateResultTests(Base):
    def test_transitions(self):
        s = State()
        s.advance("CONFIG_LOADED")
        s.advance("CONFIG_VALIDATED")
        self.assertEqual(s.current, "CONFIG_VALIDATED")

    def test_invalid_transition(self):
        with self.assertRaises(FrameworkError):
            State().advance("COMPLETE")

    def test_terminal_state(self):
        s = State()
        s.advance("FAILED")
        with self.assertRaises(FrameworkError):
            s.advance("CONFIG_LOADED")

    def test_schema_definitions_valid(self):
        for path in (ROOT / "config/schemas").glob("*.json"):
            Draft202012Validator.check_schema(json.loads(path.read_text()))

    def test_schema_rejects_fake_runtime_success(self):
        _, result, _ = self.cli("validate")
        result["harmonyRegistered"] = True
        with self.assertRaises(FrameworkError):
            validate_schema(result, "result")

    def test_result_file_permissions(self):
        path = Path(self.temp.name).resolve() / "result.json"
        write_result(path, "{}\n")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FrameworkError):
            write_result(path, "overwrite")
        self.assertEqual(path.read_text(), "{}\n")

    def test_result_symlink_refused(self):
        base = Path(self.temp.name).resolve()
        (base / "target").write_text("unchanged")
        (base / "link").symlink_to(base / "target")
        with self.assertRaises(FrameworkError):
            write_result(base / "link", "bad")
        self.assertEqual((base / "target").read_text(), "unchanged")

    def test_error_catalogue(self):
        self.assertEqual(ERRORS["INSTALLER_METADATA_MISSING"].exitCode, 22)
        self.assertFalse(ERRORS["REGISTRATION_TIMEOUT"].retryable)


class PreflightCliTests(Base):
    def test_ubuntu_dry_run_blocked(self):
        code, data, _ = self.cli(args=["--dry-run"])
        self.assertEqual(code, 22)
        self.assertEqual(data["status"], "BLOCKED")
        self.assertEqual(data["error"]["name"], "INSTALLER_METADATA_MISSING")
        self.assertTrue(data["plan"])
        self.assertFalse(set(data["stateHistory"]) & set(FUTURE_STATES))

    def test_validation_success_with_pending_metadata(self):
        code, data, _ = self.cli("validate")
        self.assertEqual((code, data["status"]), (0, "VALIDATED"))
        self.assertFalse(data["readiness"]["installable"])

    def test_diagnostics_truthful(self):
        code, data, _ = self.cli("diagnostics")
        self.assertEqual(code, 0)
        self.assertEqual(data["host"]["cpuCount"], 4)
        self.assertIsNone(data["agent"]["installedVersion"])
        self.assertIsNone(data["harmonyRegistered"])

    def test_live_host_incompatibility(self):
        h = host()
        h.update(system="Darwin", os="darwin", version=None, architecture="aarch64")
        code, data, _ = self.cli(args=["--dry-run"], detected=h)
        self.assertEqual(code, 10)
        self.assertEqual(data["status"], "FAILED")
        self.assertTrue(data["plan"])

    def test_interactive_not_implemented(self):
        code, data, _ = self.cli(args=["--interactive"])
        self.assertEqual((code, data["status"]), (23, "NOT_IMPLEMENTED"))

    def test_apply_not_implemented(self):
        code, data, _ = self.cli(args=["--non-interactive"])
        self.assertEqual((code, data["status"]), (23, "NOT_IMPLEMENTED"))

    def test_unknown_version_exit(self):
        code, data, _ = self.cli(args=["--version", "99.99", "--dry-run"])
        self.assertEqual(code, 12)
        self.assertEqual(data["error"]["name"], "VERSION_UNKNOWN")

    def test_low_resources_fail(self):
        h = host()
        h["memoryBytes"] = 1
        code, data, _ = self.cli(args=["--dry-run"], detected=h)
        self.assertEqual(code, 11)
        self.assertIn("FAIL", [c["status"] for c in data["checks"] if c["id"] == "RES-002"])

    def test_missing_package_manager(self):
        versions, support = load_catalogues()
        v, e = resolve("12.10", versions)
        r = readiness(self.config, v, e, support)
        _, checks = run(self.config, host(), v, r, support, which=lambda _: None)
        self.assertEqual(next(c["status"] for c in checks if c["id"] == "PKG-001"), "FAIL")

    def test_no_network_or_provider_calls(self):
        with (
            patch("socket.socket", side_effect=AssertionError("network")),
            patch("subprocess.run", side_effect=AssertionError("execution")),
            patch(
                "jbpa.providers.require_runtime_provider", side_effect=AssertionError("provider")
            ),
        ):
            code, data, _ = self.cli(args=["--dry-run"])
        self.assertEqual(code, 22)
        self.assertFalse(data["changed"])

    def test_repeatable_dry_run(self):
        first = self.cli(args=["--dry-run"])
        self.assertEqual(first, self.cli(args=["--dry-run"]))

    def test_no_result_write_without_opt_in(self):
        with patch("jbpa.cli.write_result", side_effect=AssertionError("write")):
            self.assertEqual(self.cli(args=["--dry-run"])[0], 22)

    def test_subprocess_entrypoint(self):
        env = dict(os.environ, JBPA_PYTHON=sys.executable)
        p = subprocess.run(
            [str(ROOT / "bin/jitterbit-agent-validate")], capture_output=True, text=True, env=env
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["status"], "VALIDATED")


class AdditionalBoundaryTests(Base):
    def test_schema_failure_result(self):
        _, result, _ = self.cli(args=["--version", "bad-value"])
        self.assertEqual(result["status"], "FAILED")
        self.assertFalse(result["configValid"])

    def test_all_log_levels(self):
        stream = io.StringIO()
        log = Logger(stream, "run", level="DEBUG")
        for level in ["DEBUG", "INFO", "WARN", "ERROR"]:
            log.event(level, "cli", "finish")
        self.assertEqual(len(stream.getvalue().splitlines()), 4)

    def test_mock_failure_is_sanitized(self):
        provider = MockSecretProvider({}, Redactor())
        with self.assertRaises(FrameworkError) as exc:
            provider.resolve({"reference": "synthetic-sensitive-reference"})
        self.assertNotIn("synthetic-sensitive-reference", str(exc.exception))

    def test_provider_payload_cannot_be_logged_as_object(self):
        class Payload:
            def __str__(self):
                return "synthetic-hidden-response"

        stream = io.StringIO()
        Logger(stream, "run").event("ERROR", "cli", "failure", description=Payload())
        self.assertNotIn("synthetic-hidden-response", stream.getvalue())

    def test_multiline_secret_in_logs(self):
        secret = Secret("synthetic-line-one\nsynthetic-line-two")
        redactor = Redactor()
        redactor.register(secret)
        stream = io.StringIO()
        Logger(stream, "run", redactor).event("INFO", "cli", "finish", description=secret.reveal())
        self.assertNotIn("synthetic-line", stream.getvalue())

    def test_error_output_does_not_leak_exception(self):
        out, err = io.StringIO(), io.StringIO()

        def bad_host():
            raise RuntimeError("synthetic-provider-response")

        code = execute("diagnostics", [], stdout=out, stderr=err, host_provider=bad_host)
        self.assertEqual(code, 99)
        self.assertNotIn("synthetic-provider-response", out.getvalue() + err.getvalue())

    def test_explicit_result_write(self):
        destination = Path(self.temp.name).resolve() / "output.json"
        code, data, _ = self.cli("diagnostics", ["--result-file", str(destination)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(destination.read_text()), data)

    def test_result_write_failure_is_structured(self):
        destination = Path(self.temp.name).resolve() / "existing.json"
        destination.write_text("unchanged")
        code, data, _ = self.cli("diagnostics", ["--result-file", str(destination)])
        self.assertEqual(code, 61)
        self.assertEqual(data["status"], "FAILED")
        self.assertEqual(destination.read_text(), "unchanged")

    def test_no_filesystem_mutation_in_dry_run(self):
        import builtins

        original_open = builtins.open
        original_path_open = Path.open

        def guarded_open(file, mode="r", *args, **kwargs):
            if any(c in mode for c in "wax+"):
                raise AssertionError("write attempted")
            return original_open(file, mode, *args, **kwargs)

        def guarded_path_open(path, mode="r", *args, **kwargs):
            if any(c in mode for c in "wax+"):
                raise AssertionError("write attempted")
            return original_path_open(path, mode, *args, **kwargs)

        with (
            patch("builtins.open", guarded_open),
            patch.object(Path, "open", guarded_path_open),
            patch("os.open", side_effect=AssertionError("write attempted")),
        ):
            code, data, _ = self.cli(args=["--dry-run"])
        self.assertEqual(code, 22)
        self.assertFalse(data["changed"])

    def test_help(self):
        env = dict(os.environ, JBPA_PYTHON=sys.executable)
        p = subprocess.run(
            [str(ROOT / "bin/jitterbit-agent-install"), "--help"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(p.returncode, 0)
        self.assertIn("--dry-run", p.stdout)

    def test_alias_to_unqualified_entry_rejected(self):
        versions, support = load_catalogues()
        versions["aliases"]["recommended"] = "12.8"
        with (
            patch("jbpa.catalogue.validated_yaml", side_effect=[versions, support]),
            self.assertRaises(FrameworkError),
        ):
            load_catalogues()


class ResultPathBoundaryTests(Base):
    def test_invalid_result_filename_is_sanitized(self):
        code, data, log = self.cli(
            "diagnostics",
            ["--result-file", str(Path(self.temp.name).resolve() / "invalid") + chr(0)],
        )
        self.assertEqual(code, 61)
        self.assertEqual(data["error"]["name"], "RESULT_WRITE_FAILED")
        self.assertNotIn("embedded null", log)
