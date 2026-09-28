"""RC2 forwarding and policy tests; no live installations."""

import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from azure.integration.consumer import bootstrap_arguments, install_arguments
from jbpa import release_cli
from jbpa.catalogue import load_catalogues
from jbpa.config import ROOT, validate_schema
from jbpa.errors import FrameworkError
from jbpa.release import digest


class OverridePolicyTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = load_catalogues()[0]
        self.host = {
            "os": "ubuntu",
            "version": "22.04",
            "architecture": "x86_64",
            "system": "Linux",
        }

    def guard(self, version="12.10", allow=False, requested=None, package=None):
        return release_cli.qualification_guard(
            requested or version, self.catalogue["versions"][version], self.host, allow, package
        )

    def test_ubuntu22_default_denied(self):
        with self.assertRaises(FrameworkError) as error:
            self.guard()
        self.assertEqual(error.exception.spec.name, "VERSION_NOT_QUALIFIED")

    def test_ubuntu22_explicit_allowed_to_preflight(self):
        self.assertEqual(self.guard(allow=True), "EXPERIMENTAL_VERSION_TEST")

    def test_tested_ubuntu24_normal(self):
        self.host["version"] = "24.04"
        self.assertEqual(self.guard(), "QUALIFIED_VERSION")

    def test_archived_default_denied(self):
        with self.assertRaises(FrameworkError):
            self.guard("12.8")

    def test_archived_explicit_experimental(self):
        self.assertEqual(self.guard("12.8", True), "EXPERIMENTAL_VERSION_TEST")

    def test_latest_unqualified_default_denied(self):
        with self.assertRaises(FrameworkError) as error:
            self.guard(requested="latest")
        self.assertEqual(error.exception.spec.name, "LATEST_VERSION_NOT_QUALIFIED")

    def test_latest_exact_package_cannot_inherit_older_qualification(self):
        self.host["version"] = "24.04"
        with self.assertRaises(FrameworkError):
            self.guard(requested="latest", package="12.10.9.9")
        self.assertEqual(
            self.guard(allow=True, requested="latest", package="12.10.9.9"),
            "EXPERIMENTAL_VERSION_TEST",
        )

    def test_reviewed_tuple_promotion_removes_need_for_override(self):
        self.catalogue["versions"]["12.10"]["qualification"]["platforms"]["ubuntu-22.04-amd64"] = (
            "TESTED_LIVE"
        )
        self.assertEqual(self.guard(), "QUALIFIED_VERSION")
        self.assertNotEqual(
            load_catalogues()[0]["versions"]["12.10"]["qualification"]["platforms"][
                "ubuntu-22.04-amd64"
            ],
            "TESTED_LIVE",
        )

    def test_override_metadata_on_preflight_failure(self):
        entry = self.catalogue["versions"]["12.10"]
        manifest = {
            "logical_version": "12.10",
            "package_version": "12.10.1.1",
            "request_url": entry["artifacts"][0]["url"],
            "sha256": entry["integrity"]["sha256"],
        }

        def next_preflight(argv, stdout, **kwargs):
            stdout.write(json.dumps({"status": "FAILED", "packageVersion": "12.10.1.1"}))
            return 10

        with (
            patch("jbpa.release_cli.detect", return_value=self.host),
            patch("jbpa.artifacts.inspect", return_value=(manifest, Path("/unused"))),
            patch(
                "jbpa.host_readiness.run",
                return_value={
                    "profile": "INSTALL",
                    "status": "PASS",
                    "checks": {},
                    "hostState": "CLEAN_HOST",
                    "platform": {},
                    "mutationPerformed": False,
                },
            ),
            patch("jbpa.bootstrap.execute", side_effect=next_preflight),
        ):
            code, data = release_cli.install(
                [
                    "--config",
                    str(ROOT / "config/examples/azure-qa.example.yaml"),
                    "--controlled-test",
                    "--allow-unqualified",
                ]
            )
        self.assertEqual(code, 10)
        self.assertTrue(data["qualification"]["overrideUsed"])
        self.assertFalse(data["qualification"]["qualified"])
        self.assertEqual(
            data["qualification"]["executionClassification"], "EXPERIMENTAL_VERSION_TEST"
        )
        validate_schema(release_cli.envelope("install", code, data), "rc-result")

    def test_override_does_not_swallow_artifact_validation_failure(self):
        for name in ("ARTIFACT_CHANGED", "UNSUPPORTED_ARCHITECTURE"):
            with (
                self.subTest(name=name),
                patch("jbpa.release_cli.detect", return_value=self.host),
                patch("jbpa.artifacts.inspect", side_effect=FrameworkError(name)),
                patch("jbpa.bootstrap.execute") as mutation,
            ):
                with self.assertRaises(FrameworkError):
                    release_cli.install(
                        [
                            "--config",
                            str(ROOT / "config/examples/azure-qa.example.yaml"),
                            "--controlled-test",
                            "--allow-unqualified",
                        ]
                    )
                mutation.assert_not_called()

    def test_override_does_not_bypass_invalid_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "invalid.yaml"
            config.write_text("schema_version: invalid\n")
            with patch("jbpa.artifacts.inspect") as acquisition, self.assertRaises(FrameworkError):
                release_cli.install(
                    ["--config", str(config), "--controlled-test", "--allow-unqualified"]
                )
            acquisition.assert_not_called()

    def test_azure_false_and_true_and_strict_boolean(self):
        values = (
            "/wrapper.sh",
            "/archive.tar.gz",
            "a" * 64,
            "/config.yaml",
            "/result.json",
            "/opt/jbpa",
        )
        self.assertEqual(bootstrap_arguments(*values)[-1], "false")
        self.assertEqual(
            bootstrap_arguments(*values, controlled_test=True, allowUnqualified=True)[-1], "true"
        )
        for bad in ("false", "true", 1):
            with self.assertRaises(ValueError):
                bootstrap_arguments(*values, controlled_test=True, allowUnqualified=bad)
        self.assertNotIn(
            "--allow-unqualified", install_arguments("/bin/jbpa", "/config", "/result")
        )


class BootstrapForwardingTests(unittest.TestCase):
    def run_bootstrap(self, override=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            config = root / "config;$(touch injected).yaml"
            config.write_text("{}")
            archive = root / "fixture.tar.gz"
            # A recorder stops at the invocation boundary; it never simulates install success.
            script = b"#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\nsys.exit(51)\n"
            with tarfile.open(archive, "w:gz") as tar:
                member = tarfile.TarInfo("jbpa-fixture/bin/jbpa")
                member.mode = 0o755
                member.size = len(script)
                tar.addfile(member, io.BytesIO(script))
            tools = root / "tools"
            tools.mkdir()
            shim = tools / "python3"
            shim.write_text(f"""#!{sys.executable}
import os,pathlib,sys
if sys.argv[1:3] == ['-m','venv']:
    target=pathlib.Path(sys.argv[3])/'bin'
    target.mkdir(parents=True)
    runtime=target/'python'
    runtime.write_text('#!/bin/sh\\nexit 0\\n')
    runtime.chmod(0o755)
else:
    os.execv({sys.executable!r}, [{sys.executable!r}]+sys.argv[1:])
""")
            shim.chmod(0o755)
            args = [
                "bash",
                str(ROOT / "azure/custom-script/release-bootstrap.sh"),
                str(archive),
                digest(archive),
                str(config),
                str(root / "result.json"),
                str(root / "framework"),
                "controlled-test",
            ]
            if override is not None:
                args.append(override)
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=15,
                env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
            )
            self.assertFalse((root / "injected").exists())
            return result, str(config)

    def test_bootstrap_default_omits_override(self):
        result, config = self.run_bootstrap()
        self.assertEqual(result.returncode, 51, result.stderr)
        args = json.loads(result.stdout)
        self.assertNotIn("--allow-unqualified", args)
        self.assertEqual(args[args.index("--config") + 1], config)

    def test_bootstrap_explicit_false_omits_override(self):
        result, _ = self.run_bootstrap("false")
        self.assertEqual(result.returncode, 51, result.stderr)
        self.assertNotIn("--allow-unqualified", json.loads(result.stdout))

    def test_bootstrap_explicit_true_matches_direct_cli(self):
        result, _ = self.run_bootstrap("true")
        self.assertEqual(result.returncode, 51, result.stderr)
        args = json.loads(result.stdout)
        self.assertEqual(args.count("--allow-unqualified"), 1)
        self.assertEqual(args.count("--controlled-test"), 1)
        self.assertIn(
            "--allow-unqualified",
            install_arguments(
                "/bin/jbpa", "/config", "/result", controlled_test=True, allow_unqualified=True
            ),
        )

    def test_bootstrap_invalid_override_rejected_without_execution(self):
        result, _ = self.run_bootstrap("true;touch injected")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["error"], "INVALID_QUALIFICATION_OVERRIDE")
