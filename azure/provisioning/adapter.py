# NON_PRODUCTION: DEVELOPMENT_TEST_HARNESS; NOT_PART_OF_JBPA_RUNTIME.
"""Separate Azure control-plane adapter. No Jitterbit lifecycle implementation."""

import base64
import hashlib
import ipaddress
import json
import os
import re
import shlex
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import yaml
from jsonschema import Draft202012Validator

from azure.integration.consumer import bootstrap_arguments, consume_install


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise DeploymentError("AZURE_CONFIG_INVALID")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_yaml(text):
    return yaml.load(text, Loader=UniqueLoader)


ROOT = Path(__file__).resolve().parents[2]
RC2_HASH = "68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da"
VERSION = "1.0.0-rc2"


class DeploymentError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class AzureCLI:
    """Only argv execution, explicit subscription, bounded timeout, no raw error output."""

    def call(self, args, subscription, *, category="AZURE_VM_FAILED", timeout=600):
        argv = [
            "az",
            *args,
            "--subscription",
            subscription,
            "--only-show-errors",
            "--output",
            "json",
        ]
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout, check=False
            )
            if result.returncode:
                raise DeploymentError(category)
            return json.loads(result.stdout or "null")
        except (OSError, subprocess.TimeoutExpired, ValueError):
            raise DeploymentError(category) from None


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def release_files(archive):
    """Verify immutable payload and every manifest file without extracting or executing it."""
    if file_hash(archive) != RC2_HASH:
        raise DeploymentError("JBPA_RELEASE_HASH_FAILED")
    with tarfile.open(archive, "r:gz") as tar:
        files = {}
        total = 0
        for member in tar.getmembers():
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or path.parts[0] != "jbpa-" + VERSION
                or not (member.isfile() or member.isdir())
                or member.uid
                or member.gid
                or member.mode & 0o022
            ):
                raise DeploymentError("JBPA_RELEASE_HASH_FAILED")
            if member.isfile():
                key = str(PurePosixPath(*path.parts[1:]))
                total += member.size
                if key in files or member.size > 2097152 or total > 33554432:
                    raise DeploymentError("JBPA_RELEASE_HASH_FAILED")
                files[key] = tar.extractfile(member).read()
        manifest = json.loads(files["release-manifest.json"])
        if manifest["jbpaVersion"] != VERSION or set(files) != set(manifest["files"]) | {
            "release-manifest.json",
            "SHA256SUMS",
        }:
            raise DeploymentError("JBPA_RELEASE_HASH_FAILED")
        for name, expected in manifest["files"].items():
            if hashlib.sha256(files[name]).hexdigest() != expected:
                raise DeploymentError("JBPA_RELEASE_HASH_FAILED")
        return files


def validate(config, *, complete=True):
    schema = json.loads((ROOT / "config/schemas/azure-deployment.schema.json").read_text())
    if not Draft202012Validator(schema).is_valid(config):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    if not complete:
        return
    a = config["azure"]
    required = [
        a["subscription_id"],
        a["resource_group"]["name"],
        a["region"],
        a["network"]["resource_group"],
        a["network"]["vnet"]["name"],
        a["network"]["subnet"]["name"],
        a["vm"]["name"],
        a["vm"]["size"],
        a["vm"]["os_disk"]["size_gb"],
        a["vm"]["os_disk"]["sku"],
        a["vm"]["admin"]["username"],
        a["vm"]["admin"]["ssh_public_key_file"],
        a["identity"]["type"],
        a["key_vault"]["resource_id"],
        a["release_delivery"]["type"],
        a["release_delivery"]["local_archive"],
        a["release_delivery"]["local_agent_config"],
    ]
    if any(value is None or value == "" for value in required):
        raise DeploymentError("AZURE_CONFIG_INCOMPLETE")
    if not a["key_vault"]["secret_references"]:
        raise DeploymentError("AZURE_CONFIG_INCOMPLETE")
    if (
        a["identity"]["type"] == "USER_ASSIGNED"
        and not a["identity"]["user_assigned_identity_resource_id"]
    ):
        raise DeploymentError("AZURE_IDENTITY_CONFIGURATION_INCOMPLETE")
    if (
        a["identity"]["type"] == "SYSTEM_ASSIGNED"
        and a["identity"]["user_assigned_identity_resource_id"]
    ):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    vnet, subnet = a["network"]["vnet"], a["network"]["subnet"]
    for resource in (vnet, subnet):
        if resource["create"] and not resource["cidr"]:
            raise DeploymentError("AZURE_NETWORK_CONFIGURATION_INCOMPLETE")
    try:
        if vnet["create"] and not ipaddress.ip_network(subnet["cidr"]).subnet_of(
            ipaddress.ip_network(vnet["cidr"])
        ):
            raise ValueError()
        if subnet["create"]:
            ipaddress.ip_network(subnet["cidr"], strict=True)
    except ValueError:
        raise DeploymentError("AZURE_NETWORK_CONFIGURATION_INCOMPLETE") from None
    if vnet["create"] and not subnet["create"]:
        raise DeploymentError("AZURE_NETWORK_CONFIGURATION_INCOMPLETE")
    if vnet["create"] and a["network"]["resource_group"] != a["resource_group"]["name"]:
        raise DeploymentError("AZURE_CONFIG_INVALID")
    if len(a["vm"]["name"]) > 64 or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9]|[A-Za-z0-9]", a["vm"]["name"]
    ):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", a["vm"]["admin"]["username"]):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    delivery = a["release_delivery"]
    if delivery["jbpa_sha256"] != RC2_HASH:
        raise DeploymentError("JBPA_RELEASE_HASH_FAILED")
    if delivery["type"] == "AZURE_BLOB" and any(
        not delivery[k]
        for k in (
            "storage_account",
            "container",
            "blob",
            "wrapper_blob",
            "config_blob",
            "storage_scope_resource_id",
        )
    ):
        raise DeploymentError("JBPA_RELEASE_DELIVERY_FAILED")
    if delivery["type"] == "HTTP" and any(
        not delivery[k] for k in ("archive_url", "wrapper_url", "config_url")
    ):
        raise DeploymentError("JBPA_RELEASE_DELIVERY_FAILED")
    if any(
        k in a["tags"]
        for k in ("managed-by", "jbpa-run-id", "purpose", "jbpa-version", "pa-version")
    ):
        raise DeploymentError("AZURE_CONFIG_INVALID")


def delivery_urls(config):
    d = config["azure"]["release_delivery"]
    if d["type"] == "AZURE_BLOB" and (
        not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", d["container"])
        or "--" in d["container"]
    ):
        raise DeploymentError("JBPA_RELEASE_DELIVERY_FAILED")
    if d["type"] == "LOCAL_TEST":
        return []
    if d["type"] == "AZURE_BLOB":
        prefix = f"https://{d['storage_account']}.blob.core.windows.net/{d['container']}/"
        urls = [prefix + d[k] for k in ("wrapper_blob", "blob", "config_blob")]
    else:
        urls = [d[k] for k in ("wrapper_url", "archive_url", "config_url")]
    names = []
    for url in urls:
        parsed = urlsplit(url)
        name = PurePosixPath(parsed.path).name
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", name)
        ):
            raise DeploymentError("JBPA_RELEASE_DELIVERY_FAILED")
        names.append(name)
    if len(set(names)) != 3:
        raise DeploymentError("JBPA_RELEASE_DELIVERY_FAILED")
    return urls


def plan(config):
    validate(config)
    a = config["azure"]
    files = release_files(a["release_delivery"]["local_archive"])
    config_path = Path(a["release_delivery"]["local_agent_config"])
    if config_path.is_symlink():
        raise DeploymentError("AZURE_CONFIG_INVALID")
    agent = load_yaml(config_path.read_text())
    if not Draft202012Validator(json.loads(files["config/schemas/agent.schema.json"])).is_valid(
        agent
    ):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    if (
        agent["agent"]["expected_os"]
        != {"id": "ubuntu", "version": "22.04", "architecture": "x86_64"}
        or agent["agent"]["version"] != "12.10"
    ):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    if any(agent.get(k, {}).get("enabled") for k in ("proxy", "java_trust", "ssh", "ssl")):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    if not (agent["agent"].get("name") or "").startswith(
        "jbpa-u2204-"
    ) or "agent_name_prefix" in agent["secrets"].get("registration_field_refs", {}):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    registration = agent["harmony"]["registration"]
    if (
        registration["strategy"] != "register-json-token"
        or not registration["token_secret_ref"]
        or registration["token_secret_ref"]["provider"] != "azure-key-vault"
    ):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    references = {registration["token_secret_ref"]["reference"]}
    references.update(
        ref["reference"] for ref in agent["secrets"].get("registration_field_refs", {}).values()
    )
    if (
        not references.issubset(set(a["key_vault"]["secret_references"]))
        or agent["secrets"]["provider"] != "azure-key-vault"
    ):
        raise DeploymentError("AZURE_CONFIG_INVALID")
    vault_name = a["key_vault"]["resource_id"].rsplit("/", 1)[-1]
    if agent["secrets"]["vault_uri"].rstrip("/") != f"https://{vault_name}.vault.azure.net":
        raise DeploymentError("AZURE_CONFIG_INVALID")
    key = Path(a["vm"]["admin"]["ssh_public_key_file"]).read_text().strip()
    if not key.startswith(("ssh-rsa ", "ssh-ed25519 ", "ecdsa-sha2-")) or "PRIVATE KEY" in key:
        raise DeploymentError("AZURE_CONFIG_INVALID")
    urls = delivery_urls(config)
    return {
        "schemaVersion": "1.0",
        "operation": "PLAN",
        "status": "SUCCESS",
        "state": "CONFIG_VALIDATED",
        "mutation": False,
        "releaseVersion": VERSION,
        "releaseHash": RC2_HASH,
        "configHash": file_hash(config_path),
        "wrapperHash": hashlib.sha256(
            files["azure/custom-script/release-bootstrap.sh"]
        ).hexdigest(),
        "fileUris": urls,
        "allowUnqualified": config["jbpa"]["allow_unqualified"],
        "resourcePlan": [
            {
                "kind": "resourceGroup",
                "mode": "CREATE_IF_REQUESTED" if a["resource_group"]["create"] else "USE_EXISTING",
            },
            {
                "kind": "vnet",
                "mode": "CREATE_IF_REQUESTED" if a["network"]["vnet"]["create"] else "USE_EXISTING",
            },
            {
                "kind": "subnet",
                "mode": "CREATE_IF_REQUESTED"
                if a["network"]["subnet"]["create"]
                else "USE_EXISTING",
            },
            {"kind": "nic/vm/disk", "mode": "CREATE_NEW"},
            {"kind": "publicIP", "mode": "CREATE_NEW" if a["network"]["public_ip"] else "NONE"},
        ],
        "commandPlan": [
            ["az", "account", "show", "--subscription", a["subscription_id"]],
            [
                "az",
                "vm",
                "create",
                "--subscription",
                a["subscription_id"],
                "--resource-group",
                a["resource_group"]["name"],
                "--name",
                a["vm"]["name"],
                "--size",
                a["vm"]["size"],
                "--image",
                ":".join(a["vm"]["image"][k] for k in ("publisher", "offer", "sku", "version")),
            ],
            [
                "az",
                "vm",
                "extension",
                "set",
                "--name",
                "CustomScript",
                "--publisher",
                "Microsoft.Azure.Extensions",
                "--version",
                "2.1",
            ],
        ],
        "commandPlanScope": "COMMAND_FAMILIES_ONLY_RUNTIME_RESOURCE_IDS_RESOLVED_BEFORE_EXECUTION",
        "controlPlaneValidation": "NOT_RUN_OFFLINE_PLAN",
        "productionSizing": "NOT_CERTIFIED",
    }


def config_digest(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def persist(path, state, *, new=False):
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink() or path.parent.stat().st_mode & 0o022:
        raise DeploymentError("AZURE_STATE_UNSAFE")
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_EXCL if new else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(state, stream, indent=2)


class Provisioner:
    def __init__(self, config, backend=None):
        self.config = config
        self.backend = backend or AzureCLI()
        self.state = None
        self.state_path = None

    def call(self, args, category="AZURE_VM_FAILED", timeout=600):
        return self.backend.call(
            args, self.config["azure"]["subscription_id"], category=category, timeout=timeout
        )

    def advance(self, stage):
        self.state["state"] = stage
        self.state["history"].append(stage)
        persist(self.state_path, self.state)

    def owned(self, resource_id, kind, mode="CREATED_BY_RUN"):
        self.state["resources"].append({"id": resource_id, "kind": kind, "ownership": mode})
        persist(self.state_path, self.state)

    def preflight(self):
        a = self.config["azure"]
        account = self.call(["account", "show"], "AZURE_AUTH_FAILED")
        if account["id"].lower() != a["subscription_id"].lower():
            raise DeploymentError("AZURE_SUBSCRIPTION_NOT_FOUND")
        locations = self.call(["account", "list-locations"], "AZURE_CONFIG_INVALID")
        if a["region"] not in {v["name"] for v in locations}:
            raise DeploymentError("AZURE_CONFIG_INVALID")
        skus = self.call(
            ["vm", "list-skus", "--location", a["region"], "--size", a["vm"]["size"], "--all"],
            "AZURE_VM_FAILED",
        )
        found = next(
            (
                v
                for v in skus
                if v["name"] == a["vm"]["size"]
                and v.get("resourceType") == "virtualMachines"
                and not v.get("restrictions")
            ),
            None,
        )
        if not found:
            raise DeploymentError("AZURE_VM_SIZE_UNAVAILABLE")
        caps = {v["name"]: v["value"] for v in found["capabilities"]}
        if (
            caps.get("CpuArchitectureType", "x64") != "x64"
            or float(caps.get("vCPUs", 0)) < 4
            or float(caps.get("MemoryGB", 0)) < 8
        ):
            raise DeploymentError("AZURE_TECHNICAL_SIZING_INVALID")
        image = a["vm"]["image"]
        self.call(
            [
                "vm",
                "image",
                "show",
                "--location",
                a["region"],
                "--urn",
                ":".join(image[k] for k in ("publisher", "offer", "sku", "version")),
            ],
            "AZURE_VM_FAILED",
        )
        vault = self.call(
            ["resource", "show", "--ids", a["key_vault"]["resource_id"]], "AZURE_IDENTITY_FAILED"
        )
        self.owned(a["key_vault"]["resource_id"], "keyVault", "PRE_EXISTING")
        if vault["type"].lower() != "microsoft.keyvault/vaults" or not vault["properties"].get(
            "enableRbacAuthorization"
        ):
            raise DeploymentError("AZURE_KEY_VAULT_RBAC_REQUIRED")
        d = a["release_delivery"]
        if d["type"] == "LOCAL_TEST":
            raise DeploymentError("JBPA_RELEASE_DELIVERY_FAILED")
        if d["type"] == "AZURE_BLOB":
            self.owned(d["storage_scope_resource_id"], "releaseStorage", "PRE_EXISTING")
            for blob in (d["blob"], d["wrapper_blob"], d["config_blob"]):
                exists = self.call(
                    [
                        "storage",
                        "blob",
                        "exists",
                        "--auth-mode",
                        "login",
                        "--account-name",
                        d["storage_account"],
                        "--container-name",
                        d["container"],
                        "--name",
                        blob,
                    ],
                    "JBPA_RELEASE_DELIVERY_FAILED",
                )
                if not exists.get("exists"):
                    raise DeploymentError("JBPA_RELEASE_DELIVERY_FAILED")
        if d["type"] == "HTTP":
            for url in delivery_urls(self.config):
                try:
                    with urlopen(Request(url, method="HEAD"), timeout=15) as response:
                        if not response.geturl().startswith("https://"):
                            raise DeploymentError("JBPA_RELEASE_DELIVERY_FAILED")
                except OSError:
                    raise DeploymentError("JBPA_RELEASE_DELIVERY_FAILED") from None
        group_exists = self.call(
            ["group", "exists", "--name", a["resource_group"]["name"]],
            "AZURE_RESOURCE_GROUP_FAILED",
        )
        if not group_exists and not a["resource_group"]["create"]:
            raise DeploymentError("AZURE_RESOURCE_GROUP_FAILED")
        if group_exists and any(
            v["name"] == a["vm"]["name"]
            for v in self.call(["vm", "list", "--resource-group", a["resource_group"]["name"]])
        ):
            raise DeploymentError("AZURE_RESOURCE_COLLISION")
        net = a["network"]
        if not net["vnet"]["create"]:
            self.call(
                [
                    "network",
                    "vnet",
                    "show",
                    "--resource-group",
                    net["resource_group"],
                    "--name",
                    net["vnet"]["name"],
                ],
                "AZURE_NETWORK_FAILED",
            )
        if not net["subnet"]["create"]:
            self.call(
                [
                    "network",
                    "vnet",
                    "subnet",
                    "show",
                    "--resource-group",
                    net["resource_group"],
                    "--vnet-name",
                    net["vnet"]["name"],
                    "--name",
                    net["subnet"]["name"],
                ],
                "AZURE_NETWORK_FAILED",
            )
        if net["nsg_resource_id"]:
            self.call(["resource", "show", "--ids", net["nsg_resource_id"]], "AZURE_NETWORK_FAILED")
        if a["identity"]["type"] == "USER_ASSIGNED":
            identity = self.call(
                ["identity", "show", "--ids", a["identity"]["user_assigned_identity_resource_id"]],
                "AZURE_IDENTITY_FAILED",
            )
            self.owned(
                a["identity"]["user_assigned_identity_resource_id"], "userIdentity", "PRE_EXISTING"
            )
            self.state["identity"] = {
                "principalId": identity["principalId"],
                "clientId": identity["clientId"],
            }
            guest = load_yaml(Path(d["local_agent_config"]).read_text())
            if guest["secrets"].get("managed_identity_client_id") != identity["clientId"]:
                raise DeploymentError("AZURE_IDENTITY_FAILED")
            if not a["key_vault"]["grant_permissions"]:
                self.require_role(
                    identity["principalId"],
                    a["key_vault"]["resource_id"],
                    "Key Vault Secrets User",
                    False,
                )
            if d["type"] == "AZURE_BLOB" and not d["grant_permissions"]:
                self.require_role(
                    identity["principalId"],
                    d["storage_scope_resource_id"],
                    "Storage Blob Data Reader",
                    False,
                )
        self.advance("AZURE_AUTHENTICATED")
        return vault

    def require_role(self, principal, scope, role, grant):
        assignments = self.call(
            [
                "role",
                "assignment",
                "list",
                "--assignee-object-id",
                principal,
                "--scope",
                scope,
                "--include-inherited",
            ],
            "AZURE_IDENTITY_FAILED",
        )
        if not any(v["roleDefinitionName"] == role for v in assignments):
            if not grant:
                raise DeploymentError("AZURE_IDENTITY_PERMISSION_MISSING")
            self.call(
                [
                    "role",
                    "assignment",
                    "create",
                    "--assignee-object-id",
                    principal,
                    "--assignee-principal-type",
                    "ServicePrincipal",
                    "--role",
                    role,
                    "--scope",
                    scope,
                ],
                "AZURE_IDENTITY_FAILED",
            )

    def provision(self, state_path, *, execute=False):
        prepared = plan(self.config)
        if not execute:
            return prepared
        self.state_path = Path(state_path)
        self.state = {
            "schemaVersion": "1.0",
            "operation": "PROVISION",
            "status": "RUNNING",
            "state": "CONFIG_VALIDATED",
            "history": ["INITIALIZED", "CONFIG_VALIDATED"],
            "runId": uuid.uuid4().hex,
            "configHash": config_digest(self.config),
            "resources": [],
            "jbpa": {},
            "identity": {},
        }
        persist(self.state_path, self.state, new=True)
        a = self.config["azure"]
        group = a["resource_group"]["name"]
        net = a["network"]
        prefix = f"/subscriptions/{a['subscription_id']}/resourceGroups/{group}/providers/"
        tags = {
            **a["tags"],
            "managed-by": "jbpa",
            "purpose": "qualification",
            "jbpa-run-id": self.state["runId"],
            "jbpa-version": VERSION,
            "pa-version": "12.10.1.1",
        }
        tag_args = [f"{k}={v}" for k, v in tags.items()]
        try:
            self.preflight()
            exists = self.call(["group", "exists", "--name", group], "AZURE_RESOURCE_GROUP_FAILED")
            if not exists and not a["resource_group"]["create"]:
                raise DeploymentError("AZURE_RESOURCE_GROUP_FAILED")
            if not exists:
                self.call(
                    [
                        "group",
                        "create",
                        "--name",
                        group,
                        "--location",
                        a["region"],
                        "--tags",
                        *tag_args,
                    ],
                    "AZURE_RESOURCE_GROUP_FAILED",
                )
            self.owned(
                f"/subscriptions/{a['subscription_id']}/resourceGroups/{group}",
                "resourceGroup",
                "PRE_EXISTING" if exists else "CREATED_BY_RUN",
            )
            self.advance("RESOURCE_GROUP_READY")
            for kind in ("vnet", "subnet"):
                resource = net[kind]
                args = ["network", "vnet", *(["subnet"] if kind == "subnet" else [])]
                common = ["--resource-group", net["resource_group"], "--name", resource["name"]]
                if kind == "subnet":
                    common += ["--vnet-name", net["vnet"]["name"]]
                if resource["create"]:
                    # Refuse collisions rather than adopt/overwrite an existing resource.
                    listing = self.call(
                        [
                            *args,
                            "list",
                            "--resource-group",
                            net["resource_group"],
                            *(["--vnet-name", net["vnet"]["name"]] if kind == "subnet" else []),
                        ],
                        "AZURE_NETWORK_FAILED",
                    )
                    if any(v["name"] == resource["name"] for v in listing):
                        raise DeploymentError("AZURE_RESOURCE_COLLISION")
                    cidr_arg = "--address-prefixes" if kind == "subnet" else "--address-prefixes"
                    self.call(
                        [
                            *args,
                            "create",
                            *common,
                            cidr_arg,
                            resource["cidr"],
                            *(
                                ["--location", a["region"], "--tags", *tag_args]
                                if kind == "vnet"
                                else []
                            ),
                        ],
                        "AZURE_NETWORK_FAILED",
                    )
                observed = self.call([*args, "show", *common], "AZURE_NETWORK_FAILED")
                self.owned(
                    observed["id"], kind, "CREATED_BY_RUN" if resource["create"] else "PRE_EXISTING"
                )
                if kind == "subnet":
                    subnet_id = observed["id"]
            self.advance("NETWORK_READY")
            if any(
                v["name"] == a["vm"]["name"]
                for v in self.call(["vm", "list", "--resource-group", group])
            ):
                raise DeploymentError("AZURE_RESOURCE_COLLISION")
            nic_name = a["vm"]["name"] + "-" + self.state["runId"][:8] + "-nic"
            pip_id = None
            if net["public_ip"]:
                pip = self.call(
                    [
                        "network",
                        "public-ip",
                        "create",
                        "--resource-group",
                        group,
                        "--name",
                        nic_name + "-pip",
                        "--location",
                        a["region"],
                        "--sku",
                        "Standard",
                        "--tags",
                        *tag_args,
                    ],
                    "AZURE_NETWORK_FAILED",
                )
                pip_id = pip["publicIp"]["id"]
                self.owned(pip_id, "publicIP")
            nic = self.call(
                [
                    "network",
                    "nic",
                    "create",
                    "--resource-group",
                    group,
                    "--name",
                    nic_name,
                    "--location",
                    a["region"],
                    "--subnet",
                    subnet_id,
                    "--tags",
                    *tag_args,
                    *(
                        ["--network-security-group", net["nsg_resource_id"]]
                        if net["nsg_resource_id"]
                        else []
                    ),
                    *(["--public-ip-address", pip_id] if pip_id else []),
                ],
                "AZURE_NETWORK_FAILED",
            )
            nic_id = nic["NewNIC"]["id"]
            self.owned(nic_id, "nic")
            identity_arg = a["identity"]["user_assigned_identity_resource_id"] or "[system]"
            self.advance("IDENTITY_READY")
            self.advance("VM_PROVISIONING")
            image = a["vm"]["image"]
            self.call(
                [
                    "vm",
                    "create",
                    "--resource-group",
                    group,
                    "--name",
                    a["vm"]["name"],
                    "--location",
                    a["region"],
                    "--image",
                    ":".join(image[k] for k in ("publisher", "offer", "sku", "version")),
                    "--size",
                    a["vm"]["size"],
                    "--nics",
                    nic_id,
                    "--admin-username",
                    a["vm"]["admin"]["username"],
                    "--ssh-key-values",
                    a["vm"]["admin"]["ssh_public_key_file"],
                    "--os-disk-size-gb",
                    str(a["vm"]["os_disk"]["size_gb"]),
                    "--storage-sku",
                    a["vm"]["os_disk"]["sku"],
                    "--assign-identity",
                    identity_arg,
                    "--tags",
                    *tag_args,
                    *(["--zone", a["vm"]["zone"]] if a["vm"]["zone"] else []),
                ],
                timeout=1800,
            )
            vm_id = prefix + "Microsoft.Compute/virtualMachines/" + a["vm"]["name"]
            self.owned(vm_id, "vm")
            vm = self.call(["vm", "show", "--ids", vm_id])
            if not self.state["identity"]:
                self.state["identity"] = {
                    "principalId": vm["identity"]["principalId"],
                    "clientId": None,
                }
            disk_id = vm["storageProfile"]["osDisk"]["managedDisk"]["id"]
            self.call(
                [
                    "tag",
                    "update",
                    "--resource-id",
                    disk_id,
                    "--operation",
                    "Merge",
                    "--tags",
                    *tag_args,
                ]
            )
            self.owned(disk_id, "disk")
            self.state["azure"] = {
                "vmResourceId": vm_id,
                "vmName": a["vm"]["name"],
                "resourceGroup": group,
                "region": a["region"],
                "identityType": a["identity"]["type"],
            }
            principal = self.state["identity"]["principalId"]
            self.require_role(
                principal,
                a["key_vault"]["resource_id"],
                "Key Vault Secrets User",
                a["key_vault"]["grant_permissions"],
            )
            d = a["release_delivery"]
            if d["type"] == "AZURE_BLOB":
                self.require_role(
                    principal,
                    d["storage_scope_resource_id"],
                    "Storage Blob Data Reader",
                    d["grant_permissions"],
                )
            self.advance("VM_READY")
            self.state["status"] = "SUCCESS"
            persist(self.state_path, self.state)
        except DeploymentError as error:
            self.fail(error)
        return self.state

    def fail(self, error):
        self.state["status"] = "FAILED"
        self.state["error"] = {"category": error.code, "lastSuccessfulStage": self.state["state"]}
        persist(self.state_path, self.state)

    def load_state(self, path):
        validate(self.config)
        self.state_path = Path(path)
        metadata = self.state_path.lstat()
        if (
            self.state_path.is_symlink()
            or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o077
        ):
            raise DeploymentError("AZURE_STATE_UNSAFE")
        self.state = json.loads(self.state_path.read_text())
        if self.state.get("configHash") != config_digest(self.config):
            raise DeploymentError("AZURE_STATE_CONFIG_MISMATCH")

    def deploy(self, state_path, *, execute=False):
        prepared = plan(self.config)
        if not execute:
            return prepared
        self.load_state(state_path)
        if self.state["state"] != "VM_READY":
            raise DeploymentError("AZURE_STATE_NOT_DISPATCHABLE")
        try:
            a = self.config["azure"]
            agent_config = load_yaml(Path(a["release_delivery"]["local_agent_config"]).read_text())
            if agent_config["secrets"].get("managed_identity_client_id") != self.state[
                "identity"
            ].get("clientId"):
                raise DeploymentError("AZURE_IDENTITY_FAILED")
            urls = prepared["fileUris"]
            names = [PurePosixPath(urlsplit(u).path).name for u in urls]
            run_dir = "/var/lib/jbpa/azure/" + self.state["runId"]
            result = run_dir + "/result.json"
            argv = bootstrap_arguments(
                "/etc/jbpa/release-bootstrap.sh",
                names[1],
                RC2_HASH,
                "/etc/jbpa/agent.yaml",
                result,
                "/opt/jbpa",
                controlled_test=True,
                allowUnqualified=self.config["jbpa"]["allow_unqualified"],
            )
            # Guest script contains only framework delivery/exit transport, never PA lifecycle logic.
            command = (
                "set -eu; umask 077; "
                + shlex.join(["sha256sum", "-c", "-"])
                + " <<'HASHES'\n"
                + prepared["wrapperHash"]
                + "  "
                + names[0]
                + "\n"
                + RC2_HASH
                + "  "
                + names[1]
                + "\n"
                + prepared["configHash"]
                + "  "
                + names[2]
                + "\nHASHES\n"
            )
            command += shlex.join(["install", "-d", "-m", "0700", run_dir, "/etc/jbpa"]) + "; "
            command += (
                shlex.join(["install", "-m", "0600", names[2], "/etc/jbpa/agent.yaml"]) + "; "
            )
            command += (
                shlex.join(["install", "-m", "0600", names[0], "/etc/jbpa/release-bootstrap.sh"])
                + "; "
            )
            command += "apt-get -o DPkg::Lock::Timeout=120 update > /dev/null 2>&1; apt-get -o DPkg::Lock::Timeout=120 install -y python3 python3-venv curl > /dev/null 2>&1; "
            command += (
                "set +e; "
                + shlex.join(argv)
                + " > "
                + shlex.quote(run_dir + "/bootstrap.log")
                + " 2>&1; code=$?; printf '%s' \"$code\" > "
                + shlex.quote(run_dir + "/exit-code")
                + '; exit "$code"'
            )
            protected = {"fileUris": urls, "commandToExecute": command}
            if a["release_delivery"]["type"] == "AZURE_BLOB":
                protected["managedIdentity"] = (
                    {"clientId": self.state["identity"]["clientId"]}
                    if self.state["identity"]["clientId"]
                    else {}
                )
            self.state["jbpa"] = {
                "resultPath": result,
                "exitPath": run_dir + "/exit-code",
                "allowUnqualified": self.config["jbpa"]["allow_unqualified"],
            }
            self.advance("JBPA_RELEASE_READY")
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "protected.json"
                path.write_text(json.dumps(protected))
                path.chmod(0o600)
                self.advance("BOOTSTRAP_DISPATCHED")
                try:
                    self.call(
                        [
                            "vm",
                            "extension",
                            "set",
                            "--ids",
                            self.state["azure"]["vmResourceId"],
                            "--name",
                            "CustomScript",
                            "--publisher",
                            "Microsoft.Azure.Extensions",
                            "--version",
                            "2.1",
                            "--settings",
                            '{"skipDos2Unix":true}',
                            "--protected-settings",
                            "@" + str(path),
                        ],
                        "AZURE_EXTENSION_FAILED",
                        timeout=5500,
                    )
                except DeploymentError:
                    # An extension error can still contain a completed JBPA failure envelope.
                    self.state["extensionFailure"] = True
            self.advance("JBPA_RUNNING")
            raw_exit = self.read_guest(self.state["jbpa"]["exitPath"]).decode()
            if not re.fullmatch(r"[0-9]{1,3}", raw_exit):
                raise DeploymentError("JBPA_RESULT_INVALID")
            text = self.read_guest(result).decode()
            schema = json.loads(
                release_files(a["release_delivery"]["local_archive"])[
                    "config/schemas/rc-result.schema.json"
                ]
            )
            decision = consume_install(
                int(raw_exit),
                text,
                schema,
                expected_platform={"os": "ubuntu", "version": "22.04", "architecture": "x86_64"},
            )
            self.state["jbpa"].update(
                {
                    "exitCode": int(raw_exit),
                    "decision": decision,
                    "status": "SUCCESS" if decision["success"] else "FAILED",
                }
            )
            if not decision["success"]:
                invalid = decision["reason"] in {
                    "RESULT_SCHEMA_MISMATCH",
                    "MALFORMED_RESULT_JSON",
                    "RESULT_TOO_LARGE",
                    "INVALID_PROCESS_EXIT",
                    "AZURE_RESULT_CONTRACT_FAILURE",
                    "UNEXPECTED_OPERATION",
                    "UNEXPECTED_VERSION",
                    "TARGET_OS_MISMATCH",
                }
                raise DeploymentError("JBPA_RESULT_INVALID" if invalid else "JBPA_EXECUTION_FAILED")
            envelope = json.loads(text)
            audit = envelope["details"].get("qualification", {})
            if self.config["jbpa"]["allow_unqualified"] and not (
                audit.get("overrideRequested") is True
                and audit.get("overrideUsed") is True
                and audit.get("executionClassification") == "EXPERIMENTAL_VERSION_TEST"
            ):
                raise DeploymentError("JBPA_RESULT_INVALID")
            self.advance("JBPA_COMPLETE")
            self.advance("PROVISIONING_COMPLETE")
            self.state["operation"] = "PROVISION_AND_INSTALL"
            self.state["status"] = "SUCCESS"
            persist(self.state_path, self.state)
        except DeploymentError as error:
            self.fail(error)
        return self.state

    def read_guest(self, path):
        """Bounded chunked file transport avoids relying on CSE's truncated stdout."""
        content = bytearray()
        for offset in range(0, 1048576, 1024):
            code = (
                "import base64,pathlib; p=pathlib.Path("
                + repr(path)
                + "); print('JBPA_TRANSPORT:'+base64.b64encode(p.read_bytes()["
                + str(offset)
                + ":"
                + str(offset + 1024)
                + "]).decode()+':END')"
            )
            result = self.call(
                [
                    "vm",
                    "run-command",
                    "invoke",
                    "--ids",
                    self.state["azure"]["vmResourceId"],
                    "--command-id",
                    "RunShellScript",
                    "--scripts",
                    shlex.join(["python3", "-c", code]),
                ],
                "JBPA_RESULT_MISSING",
            )
            message = "\n".join(v.get("message", "") for v in result.get("value", []))
            match = re.search(r"JBPA_TRANSPORT:([A-Za-z0-9+/=]*):END", message)
            if not match:
                raise DeploymentError("JBPA_RESULT_MISSING")
            try:
                block = base64.b64decode(match[1], validate=True)
            except ValueError:
                raise DeploymentError("JBPA_RESULT_INVALID") from None
            if len(block) > 1024:
                raise DeploymentError("JBPA_RESULT_INVALID")
            content.extend(block)
            if len(block) < 1024:
                return bytes(content)
        raise DeploymentError("JBPA_RESULT_INVALID")

    def status(self, state_path):
        self.load_state(state_path)
        vm = self.call(["vm", "get-instance-view", "--ids", self.state["azure"]["vmResourceId"]])
        return {
            "schemaVersion": "1.0",
            "operation": "STATUS",
            "status": "SUCCESS",
            "state": self.state["state"],
            "instanceStatuses": vm.get("instanceView", {}).get("statuses", []),
        }

    def destroy(self, state_path, *, execute=False):
        self.load_state(state_path)
        # Shared infrastructure is retained even if originally created by the run.
        resources = [
            v
            for v in self.state["resources"]
            if v["ownership"] == "CREATED_BY_RUN" and v["kind"] in {"vm", "nic", "disk", "publicIP"}
        ]
        expected_prefix = f"/subscriptions/{self.config['azure']['subscription_id']}/resourceGroups/{self.config['azure']['resource_group']['name']}/providers/"
        for resource in resources:
            if not resource["id"].lower().startswith(expected_prefix.lower()):
                raise DeploymentError("AZURE_DESTROY_OWNERSHIP_UNPROVEN")
        resources.sort(key=lambda v: {"vm": 0, "nic": 1, "disk": 2, "publicIP": 3}[v["kind"]])
        if execute:
            # Check ALL ownership evidence before the first deletion.
            for resource in resources:
                observed = self.call(["resource", "show", "--ids", resource["id"]])
                tags = observed.get("tags", {})
                if (
                    tags.get("managed-by") != "jbpa"
                    or tags.get("jbpa-run-id") != self.state["runId"]
                ):
                    raise DeploymentError("AZURE_DESTROY_OWNERSHIP_UNPROVEN")
            for resource in resources:
                self.call(["resource", "delete", "--ids", resource["id"]])
        return {
            "schemaVersion": "1.0",
            "operation": "DESTROY",
            "status": "SUCCESS",
            "mutation": execute,
            "resources": resources,
            "retainedSharedResources": True,
        }
