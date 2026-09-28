"""The shared external-AI examples must remain compatible with immutable RC3."""

import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from jbpa import bootstrap, uninstall
from jbpa.config import load_config
from tools.handoff.caller import arguments, validate

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "docs/integrations/claude-code"
SHA = "4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e"


class ClaudeIntegrationKitTests(unittest.TestCase):
    def test_agent_templates_use_actual_rc3_schema_and_references(self):
        for name in ("agent.install.example.yaml", "agent.reinstall.example.yaml"):
            config, _ = load_config(ROOT / "examples" / name)
            self.assertEqual(config["agent"]["version"], "12.10")
            self.assertEqual(config["agent"]["expected_os"]["version"], "22.04")
            self.assertEqual(config["secrets"]["provider"], "azure-key-vault")
            self.assertIsNone(config["health"].get("expected_identity"))

    def test_request_examples_validate_and_map_to_one_operation(self):
        paths = [
            KIT / "examples" / f"{name}-request.json"
            for name in ("install", "reinstall", "uninstall", "health")
        ] + [ROOT / "examples/external-handoff.example.json"]
        result_paths = set()
        for path in paths:
            request = validate(json.loads(path.read_text()))
            argv = arguments(request, "/opt/jbpa/releases/" + SHA + "/bin/jbpa")
            self.assertEqual(argv[1], request["operation"].lower())
            self.assertNotIn(request["resultPath"], result_paths)
            result_paths.add(request["resultPath"])
            if request["operation"] in {"INSTALL", "REINSTALL"}:
                self.assertIn("--non-interactive", argv)
                self.assertEqual(argv.count("--allow-unqualified"), 1)
                self.assertEqual(argv.count("--controlled-test"), 1)
            else:
                self.assertNotIn("--allow-unqualified", argv)

    def test_success_result_is_schema_valid_synthetic_shape(self):
        schema = json.loads((ROOT / "config/schemas/rc-result.schema.json").read_text())
        result = json.loads((KIT / "examples/result-success.json").read_text())
        Draft202012Validator(schema).validate(result)
        self.assertEqual(result["versions"]["jbpa"], "1.0.0-rc3")
        self.assertTrue(result["details"]["exampleOnly"])

    def test_documented_install_and_uninstall_flags_parse(self):
        install = bootstrap.parser().parse_args(
            [
                "--config",
                "/etc/jbpa/agent.yaml",
                "--version",
                "12.10",
                "--non-interactive",
                "--controlled-test",
                "--result-file",
                "/var/lib/jbpa/results/install-new.json",
            ]
        )
        self.assertTrue(install.non_interactive)
        self.assertTrue(install.controlled_test)
        remove = uninstall.parser().parse_args(
            ["--complete", "--result-file", "/tmp/uninstall.json"]
        )
        self.assertTrue(remove.complete)

    def test_rc3_archive_is_immutable_approved_digest(self):
        archive = ROOT / "dist/jbpa-1.0.0-rc3.tar.gz"
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), SHA)


if __name__ == "__main__":
    unittest.main()
