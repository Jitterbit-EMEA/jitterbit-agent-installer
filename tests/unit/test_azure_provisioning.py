"""Synthetic Azure environment and fake control plane only; no live calls."""

import base64
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from azure.provisioning.adapter import (
    RC2_HASH,
    ROOT,
    AzureCLI,
    DeploymentError,
    Provisioner,
    plan,
    validate,
)
from azure.provisioning.cli import main


class FakeAzure:
    def __init__(self, config):
        self.config = config
        self.calls = []
        self.fail = None
        self.tags = {}
        self.extension = None
        self.guest = {}

    def call(self, args, subscription, **kwargs):
        self.calls.append(args)
        if self.fail and args[: len(self.fail)] == self.fail:
            raise DeploymentError(kwargs.get("category", "AZURE_VM_FAILED"))
        a = self.config["azure"]
        prefix = (
            f"/subscriptions/{subscription}/resourceGroups/{a['resource_group']['name']}/providers/"
        )
        if args[:2] == ["account", "show"]:
            return {"id": subscription}
        if args[:2] == ["account", "list-locations"]:
            return [{"name": a["region"]}]
        if args[:2] == ["vm", "list-skus"]:
            return [
                {
                    "name": a["vm"]["size"],
                    "resourceType": "virtualMachines",
                    "capabilities": [
                        {"name": "vCPUs", "value": "4"},
                        {"name": "MemoryGB", "value": "8"},
                        {"name": "CpuArchitectureType", "value": "x64"},
                    ],
                }
            ]
        if args[:2] == ["resource", "show"]:
            if args[-1] == a["key_vault"]["resource_id"]:
                return {
                    "type": "Microsoft.KeyVault/vaults",
                    "properties": {"enableRbacAuthorization": True},
                }
            return {"tags": self.tags}
        if args[:2] == ["group", "exists"]:
            return not a["resource_group"]["create"]
        if args[-1:] == ["--include-inherited"]:
            return [
                {"roleDefinitionName": "Key Vault Secrets User"},
                {"roleDefinitionName": "Storage Blob Data Reader"},
            ]
        if args[:3] == ["storage", "blob", "exists"]:
            return {"exists": True}
        if args[:2] == ["identity", "show"]:
            return {
                "principalId": "synthetic-principal",
                "clientId": "00000000-0000-0000-0000-000000000002",
            }
        if args[:2] == ["vm", "list"] or "list" in args:
            return []
        if args[:3] == ["network", "nic", "create"]:
            return {"NewNIC": {"id": prefix + "Microsoft.Network/networkInterfaces/test-nic"}}
        if args[:2] == ["vm", "show"]:
            return {
                "identity": {"principalId": "synthetic-principal"},
                "storageProfile": {
                    "osDisk": {"managedDisk": {"id": prefix + "Microsoft.Compute/disks/test-disk"}}
                },
            }
        if args[:3] == ["vm", "extension", "set"]:
            self.extension = json.loads(
                Path(args[args.index("--protected-settings") + 1][1:]).read_text()
            )
            return {}
        if args[:3] == ["vm", "run-command", "invoke"]:
            # Test backend transport is isolated from actual shell/Azure execution.
            script = args[-1]
            import re

            offset, end = [int(v) for v in re.search(r"\[(\d+):(\d+)\]", script).groups()]
            key = "exit" if "/exit-code" in script else "result"
            data = self.guest[key][offset:end]
            return {
                "value": [
                    {
                        "message": "[stdout]\nJBPA_TRANSPORT:"
                        + base64.b64encode(data).decode()
                        + ":END\n[stderr]"
                    }
                ]
            }
        if "show" in args:
            return {
                "id": prefix + "Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
            }
        if "--tags" in args:
            tag_values = args[args.index("--tags") + 1 :]
            self.tags.update(dict(v.split("=", 1) for v in tag_values if "=" in v))
        return {}


class AzureProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.folder.chmod(0o700)
        c = yaml.safe_load((ROOT / "config/examples/azure-deployment.example.yaml").read_text())
        a = c["azure"]
        a["subscription_id"] = "00000000-0000-0000-0000-000000000001"
        a["region"] = "syntheticregion"
        a["resource_group"]["name"] = "test-rg"
        a["network"]["resource_group"] = "test-rg"
        a["network"]["vnet"]["name"] = "test-vnet"
        a["network"]["subnet"]["name"] = "test-subnet"
        a["vm"].update({"name": "test-vm", "size": "Synthetic_Test_Size"})
        a["vm"]["os_disk"].update({"size_gb": 50, "sku": "StandardSSD_LRS"})
        key = self.folder / "public.pub"
        key.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI_SYNTHETIC_TEST_ONLY")
        a["vm"]["admin"].update({"username": "testuser", "ssh_public_key_file": str(key)})
        a["identity"]["type"] = "SYSTEM_ASSIGNED"
        a["key_vault"].update(
            {
                "resource_id": f"/subscriptions/{a['subscription_id']}/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-vault",
                "secret_references": ["JBLAB-token"],
            }
        )
        a["release_delivery"].update(
            {
                "type": "AZURE_BLOB",
                "storage_account": "synthetictest",
                "container": "test",
                "blob": "jbpa.tar.gz",
                "wrapper_blob": "bootstrap.sh",
                "config_blob": "agent.yaml",
                "storage_scope_resource_id": f"/subscriptions/{a['subscription_id']}/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/synthetictest",
                "jbpa_sha256": RC2_HASH,
                "local_archive": str(ROOT / "dist/jbpa-1.0.0-rc2.tar.gz"),
            }
        )
        agent = yaml.safe_load((ROOT / "config/agent.jblab.ubuntu-24.04.test.yaml").read_text())
        agent["agent"]["expected_os"]["version"] = "22.04"
        agent["agent"]["name"] = "jbpa-u2204-test"
        agent["secrets"]["vault_uri"] = "https://test-vault.vault.azure.net/"
        agent["secrets"]["registration_field_refs"] = {}
        path = self.folder / "agent.yaml"
        path.write_text(yaml.safe_dump(agent))
        a["release_delivery"]["local_agent_config"] = str(path)
        self.config = c
        self.fake = FakeAzure(c)
        self.adapter = Provisioner(c, self.fake)
        self.state = self.folder / "state.json"

    def assert_error(self, function, expected):
        with self.assertRaises(DeploymentError) as error:
            function()
        self.assertEqual(error.exception.code, expected)

    def test_placeholder_schema_valid_but_not_executable(self):
        example = yaml.safe_load(
            (ROOT / "config/examples/azure-deployment.example.yaml").read_text()
        )
        validate(example, complete=False)
        self.assert_error(lambda: validate(example), "AZURE_CONFIG_INCOMPLETE")

    def test_missing_required_environment_fields(self):
        for path in [("subscription_id",), ("region",), ("network", "vnet", "name")]:
            c = copy.deepcopy(self.config)
            item = c["azure"]
            for key in path[:-1]:
                item = item[key]
            item[path[-1]] = None
            self.assert_error(lambda c=c: validate(c), "AZURE_CONFIG_INCOMPLETE")

    def test_plan_zero_control_plane_calls(self):
        result = self.adapter.provision(self.state)
        self.assertFalse(result["mutation"])
        self.assertEqual(result["releaseHash"], RC2_HASH)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.fake.calls, [])

    def test_rc2_wrong_hash(self):
        self.config["azure"]["release_delivery"]["jbpa_sha256"] = "a" * 64
        self.assert_error(lambda: plan(self.config), "JBPA_RELEASE_HASH_FAILED")

    def test_secret_fields_rejected_by_schema(self):
        self.config["azure"]["client_secret"] = "synthetic-value"
        self.assert_error(lambda: validate(self.config), "AZURE_CONFIG_INVALID")

    def test_network_creation_requires_cidrs(self):
        self.config["azure"]["network"]["vnet"]["create"] = True
        self.assert_error(lambda: validate(self.config), "AZURE_NETWORK_CONFIGURATION_INCOMPLETE")

    def test_existing_resource_ownership(self):
        result = self.adapter.provision(self.state, execute=True)
        self.assertEqual(result["state"], "VM_READY")
        self.assertTrue(
            all(
                v["ownership"] == "PRE_EXISTING"
                for v in result["resources"]
                if v["kind"] in {"resourceGroup", "vnet", "subnet"}
            )
        )
        self.assertFalse(any(v[:3] == ["network", "public-ip", "create"] for v in self.fake.calls))

    def test_explicit_create_modes(self):
        a = self.config["azure"]
        a["resource_group"]["create"] = True
        a["network"]["vnet"].update({"create": True, "cidr": "192.0.2.0/24"})
        a["network"]["subnet"].update({"create": True, "cidr": "192.0.2.0/25"})
        result = self.adapter.provision(self.state, execute=True)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertTrue(
            all(
                v["ownership"] == "CREATED_BY_RUN"
                for v in result["resources"]
                if v["kind"] not in {"keyVault", "releaseStorage"}
            )
        )

    def test_user_assigned_identity_requires_id(self):
        self.config["azure"]["identity"]["type"] = "USER_ASSIGNED"
        self.assert_error(lambda: validate(self.config), "AZURE_IDENTITY_CONFIGURATION_INCOMPLETE")

    def test_user_assigned_identity(self):
        a = self.config["azure"]
        a["identity"].update(
            {
                "type": "USER_ASSIGNED",
                "user_assigned_identity_resource_id": f"/subscriptions/{a['subscription_id']}/resourceGroups/test-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/test-identity",
            }
        )
        guest_path = Path(a["release_delivery"]["local_agent_config"])
        guest = yaml.safe_load(guest_path.read_text())
        guest["secrets"]["managed_identity_client_id"] = "00000000-0000-0000-0000-000000000002"
        guest_path.write_text(yaml.safe_dump(guest))
        result = self.adapter.provision(self.state, execute=True)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["identity"]["clientId"], "00000000-0000-0000-0000-000000000002")

    def test_keyvault_reference_required(self):
        self.config["azure"]["key_vault"]["resource_id"] = None
        self.assert_error(lambda: validate(self.config), "AZURE_CONFIG_INCOMPLETE")

    def test_delivery_no_credentials_or_sas(self):
        d = self.config["azure"]["release_delivery"]
        d.update(
            {
                "type": "HTTP",
                "archive_url": "https://example.invalid/rc2.tar.gz",
                "wrapper_url": "https://example.invalid/boot.sh",
                "config_url": "https://example.invalid/config.yaml",
            }
        )
        self.assertEqual(len(plan(self.config)["fileUris"]), 3)
        d["archive_url"] += "?sig=synthetic"
        self.assert_error(lambda: plan(self.config), "JBPA_RELEASE_DELIVERY_FAILED")

    def test_failure_keeps_vm_and_last_stage(self):
        self.fake.fail = ["vm", "create"]
        result = self.adapter.provision(self.state, execute=True)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error"]["lastSuccessfulStage"], "VM_PROVISIONING")
        self.assertFalse(any("delete" in v for v in self.fake.calls))

    def test_cli_default_plan(self):
        path = self.folder / "config.yaml"
        path.write_text(yaml.safe_dump(self.config))
        with patch("sys.stdout", io.StringIO()) as output, patch("subprocess.run") as commands:
            self.assertEqual(main(["execute", "--config", str(path)]), 0)
        self.assertFalse(json.loads(output.getvalue())["mutation"])
        commands.assert_not_called()

    def fixture_result(self):
        return {
            "schemaVersion": "1.0",
            "runId": "mock",
            "operation": "INSTALL",
            "status": "SUCCESS",
            "state": "COMPLETE",
            "category": "SUCCESS",
            "versions": {"jbpa": "1.0.0-rc2", "requestedPA": "12.10", "resolvedPA": "12.10.1.1"},
            "platform": {"os": "ubuntu", "version": "22.04", "architecture": "x86_64"},
            "artifact": {},
            "registration": {},
            "health": {},
            "enterpriseConfiguration": {},
            "error": None,
            "details": {
                "status": "COMPLETE",
                "serviceRunning": True,
                "harmonyRegistered": True,
                "qualification": {
                    "overrideRequested": True,
                    "overrideUsed": True,
                    "executionClassification": "EXPERIMENTAL_VERSION_TEST",
                },
            },
        }

    def test_generic_handoff_and_safe_argv(self):
        self.adapter.provision(self.state, execute=True)
        self.fake.guest = {"exit": b"0", "result": json.dumps(self.fixture_result()).encode()}
        result = self.adapter.deploy(self.state, execute=True)
        self.assertEqual(result["state"], "PROVISIONING_COMPLETE")
        protected = self.fake.extension
        self.assertEqual(protected["managedIdentity"], {})
        self.assertIn("controlled-test true", protected["commandToExecute"])
        self.assertNotIn("Auto Registration", protected["commandToExecute"])
        self.assertNotIn(
            "dpkg", protected["commandToExecute"].split("bash /etc/jbpa")[0].replace("DPkg", "")
        )
        self.assertEqual(result["jbpa"]["exitCode"], 0)

    def test_missing_json_transport(self):
        self.adapter.provision(self.state, execute=True)
        self.fake.fail = ["vm", "run-command", "invoke"]
        result = self.adapter.deploy(self.state, execute=True)
        self.assertEqual(result["error"]["category"], "JBPA_RESULT_MISSING")

    def test_invalid_schema_result(self):
        self.adapter.provision(self.state, execute=True)
        value = self.fixture_result()
        value["schemaVersion"] = "2.0"
        self.fake.guest = {"exit": b"0", "result": json.dumps(value).encode()}
        self.assertEqual(self.adapter.deploy(self.state, execute=True)["status"], "FAILED")

    def test_destroy_retains_shared_resources(self):
        self.adapter.provision(self.state, execute=True)
        before = len(self.fake.calls)
        result = self.adapter.destroy(self.state)
        self.assertEqual(len(self.fake.calls), before)
        self.assertTrue(
            all(v["kind"] in {"vm", "nic", "disk", "publicIP"} for v in result["resources"])
        )
        self.fake.tags = {}
        self.assert_error(
            lambda: self.adapter.destroy(self.state, execute=True),
            "AZURE_DESTROY_OWNERSHIP_UNPROVEN",
        )
        self.assertFalse(any("delete" in v for v in self.fake.calls))

    def test_azure_backend_error_sanitized(self):
        with patch("subprocess.run", side_effect=OSError("synthetic sensitive text")):
            self.assert_error(
                lambda: AzureCLI().call(["vm", "show"], "synthetic", category="AZURE_VM_FAILED"),
                "AZURE_VM_FAILED",
            )

    def test_cli_backend_uses_argv_without_shell(self):
        import subprocess

        value = "label=synthetic;touch /tmp/never-run"
        with patch(
            "subprocess.run", return_value=subprocess.CompletedProcess([], 0, "{}", "")
        ) as runner:
            AzureCLI().call(["vm", "create", "--tags", value], "synthetic")
        self.assertIn(value, runner.call_args.args[0])
        self.assertNotIn("shell", runner.call_args.kwargs)

    def test_boolean_override_strict(self):
        self.config["jbpa"]["allow_unqualified"] = "true"
        self.assert_error(lambda: validate(self.config), "AZURE_CONFIG_INVALID")

    def test_state_wrong_config_denied(self):
        self.adapter.provision(self.state, execute=True)
        self.config["azure"]["region"] = "anotherregion"
        self.assert_error(lambda: self.adapter.destroy(self.state), "AZURE_STATE_CONFIG_MISMATCH")

    def test_no_default_privilege_escalation(self):
        with patch.object(self.fake, "call", return_value=[]):
            self.assert_error(
                lambda: self.adapter.require_role(
                    "principal", "scope", "Key Vault Secrets User", False
                ),
                "AZURE_IDENTITY_PERMISSION_MISSING",
            )

    def test_explicit_permission_grant(self):
        with patch.object(self.fake, "call", side_effect=[[], {}]) as calls:
            self.adapter.require_role("principal", "scope", "Key Vault Secrets User", True)
        self.assertEqual(calls.call_args_list[1].args[0][:3], ["role", "assignment", "create"])

    def test_verified_owned_destroy_only(self):
        self.adapter.provision(self.state, execute=True)
        result = self.adapter.destroy(self.state, execute=True)
        self.assertTrue(result["mutation"])
        self.assertEqual(sum(v[:2] == ["resource", "delete"] for v in self.fake.calls), 3)

    def test_duplicate_yaml_keys_rejected(self):
        from azure.provisioning.adapter import load_yaml

        self.assert_error(lambda: load_yaml("key: true\nkey: false\n"), "AZURE_CONFIG_INVALID")

    def test_no_automatic_cleanup_config(self):
        self.config["cleanup"]["on_failure"] = True
        self.assert_error(lambda: validate(self.config), "AZURE_CONFIG_INVALID")
