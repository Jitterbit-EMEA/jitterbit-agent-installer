"""Noninteractive Azure-facing entrypoint for the qualified native Linux workflow."""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

from . import __version__
from .azure_artifact import AzureBlobDownloader
from .azure_identity import AzureKeyVaultSecretProvider, ManagedIdentity
from .catalogue import load_catalogues, readiness, resolve, support_for
from .config import load_config, safe_fields, validate_schema
from .errors import FrameworkError
from .host_lock import HostLock
from .json_secrets import JsonFileSecretProvider
from .local_secrets import LocalFileSecretProvider
from .native_linux import CREDENTIALS, REGISTER_JSON, LocalBackend, NativeLinuxWorkflow
from .platform import detect
from .results import write_result
from .security import Secret


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise FrameworkError("CONFIG_INVALID")


def parser():
    command = SafeParser(description="Bootstrap a qualified native Linux Private Agent")
    command.add_argument("--config", required=True)
    command.add_argument("--result-file")
    command.add_argument("--version")
    command.add_argument("--non-interactive", action="store_true")
    command.add_argument("--verbose", action="store_true")
    command.add_argument("--dry-run", action="store_true")
    command.add_argument("--controlled-test", action="store_true")
    command.add_argument("--allow-under-spec", action="store_true")
    return command


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def _plan(config, version, build):
    reference = config["harmony"]["registration"]["token_secret_ref"]
    plan = [
        f"Would retrieve PA {version} build {build or 'unapproved'}",
        "Would install odbcinst, unixodbc and unzip if the exact package is absent",
        f"Would retrieve secret reference {reference['reference']} through {config['secrets']['provider']}",
        "Would create /opt/jitterbit/Resources/register.json if credentials are absent",
        "Would restart Jitterbit once and monitor /opt/jitterbit/log/jitterbit-agent.log",
    ]
    for field, ref in config["secrets"].get("registration_field_refs", {}).items():
        plan.append(f"Would retrieve registration field {field} from {ref['reference']}")
    return plan


def _resolve_registration_fields(config, provider):
    refs = config["secrets"].get("registration_field_refs", {})
    values = {field: provider.resolve(ref).reveal() for field, ref in refs.items()}
    try:
        if "cloud_url" in values:
            config["harmony"]["cloud_url"] = values["cloud_url"]
        if "agent_group_id" in values:
            config["harmony"]["agent_group_id"] = int(values["agent_group_id"])
        if "agent_name_prefix" in values:
            config["agent"]["name"] = values["agent_name_prefix"]
        if "deregister_on_drainstop" in values and values["deregister_on_drainstop"] != "false":
            raise FrameworkError("CONFIG_INVALID")
        # The qualified registration contract uses these exact retry settings.
        if "retry_count" in values and values["retry_count"] != "10":
            raise FrameworkError("CONFIG_INVALID")
        if "retry_interval_seconds" in values and values["retry_interval_seconds"] != "5":
            raise FrameworkError("CONFIG_INVALID")
        validate_schema(config, "agent")
        safe_fields(config)
    except (TypeError, ValueError) as exc:
        raise FrameworkError("CONFIG_INVALID") from exc


def execute(
    argv=None,
    *,
    stdout=None,
    host_provider=detect,
    provider_factory=None,
    backend_factory=None,
    effective_uid=os.geteuid,
    lock_path="/var/lib/jbpa/bootstrap.lock",
    lock_factory=HostLock,
    clock=_timestamp,
    catalogues_provider=None,
    experimental=False,
):
    stdout = stdout or sys.stdout
    run_id = "jbpa-" + uuid.uuid4().hex
    result = {
        "schemaVersion": 2,
        "frameworkVersion": __version__,
        "runId": run_id,
        "timestamp": clock(),
        "status": "FAILED",
        "executionMode": "production",
        "artifactApproval": None,
        "resourcePolicy": None,
        "cpuTestException": False,
        "productionSizingValidated": False,
        "state": "INITIALIZED",
        "stateHistory": [],
        "requestedVersion": None,
        "packageVersion": None,
        "platform": None,
        "changed": False,
        "serviceRunning": None,
        "harmonyRegistered": None,
        "logAvailableAfterSeconds": None,
        "registrationDurationSeconds": None,
        "plan": [],
        "error": None,
    }
    code = 0
    arguments = None
    provider = None
    try:
        arguments = parser().parse_args(argv)
        if arguments.allow_under_spec:
            raise FrameworkError("CONFIG_INVALID")
        result["executionMode"] = "controlled-test" if arguments.controlled_test else "production"
        config, _ = load_config(arguments.config, arguments.version, os.environ)
        result["requestedVersion"] = config["agent"]["version"]
        result["state"] = "CONFIG_VALIDATED"
        result["stateHistory"].append("CONFIG_VALIDATED")
        versions, support = (catalogues_provider or load_catalogues)()
        version, entry = resolve(config["agent"]["version"], versions)
        result["artifactApproval"] = entry["approval"]
        host = host_provider()
        result["platform"] = {
            "os": host["os"],
            "version": host["version"],
            "architecture": host["architecture"],
        }
        expected = config["agent"]["expected_os"]
        support_status, support_entry = support_for(host, version, support)
        if (
            host["system"] != "Linux"
            or host["os"] != expected["id"]
            or host["version"] != expected["version"]
            or host["architecture"] != expected["architecture"]
            or host["packageType"] != config["agent"]["package_kind"]
            or support_status != "SUPPORTED"
        ):
            raise FrameworkError("UNSUPPORTED_OS")
        result["state"] = "PLATFORM_VALIDATED"
        result["stateHistory"].append("PLATFORM_VALIDATED")
        requirements = support_entry["minimum"]
        cpu = host.get("cpuCount")
        memory = host.get("memoryBytes")
        disk = host.get("diskTotalBytes")
        if any(value is None for value in (cpu, memory, disk)):
            result["resourcePolicy"] = "UNKNOWN"
            raise FrameworkError("PREFLIGHT_FAILED")
        cpu_test_exception = (
            arguments.controlled_test
            and version == "12.10"
            and host["os"] == "ubuntu"
            and host["version"] == "24.04"
            and cpu == 2
        )
        if memory < requirements["memory_bytes"] or disk < requirements["disk_total_bytes"]:
            result["resourcePolicy"] = "BELOW_MINIMUM"
            raise FrameworkError("PREFLIGHT_FAILED")
        if cpu < requirements["cpu_count"] and not cpu_test_exception:
            result["resourcePolicy"] = "BELOW_MINIMUM"
            raise FrameworkError("PREFLIGHT_FAILED")
        elif cpu_test_exception:
            result["resourcePolicy"] = "PASS_WITH_TEST_EXCEPTION"
            result["cpuTestException"] = True
        else:
            result["resourcePolicy"] = "MINIMUM_MET"
        metadata = next(
            (
                item
                for item in entry["artifacts"]
                if (
                    item["os_id"],
                    item["os_version"],
                    item["architecture"],
                    item["package_kind"],
                )
                == (host["os"], host["version"], host["architecture"], host["packageType"])
            ),
            None,
        )
        result["packageVersion"] = metadata["package_version"] if metadata else None
        registration = config["harmony"]["registration"]
        reference = registration["token_secret_ref"]
        if (
            registration["strategy"] != "register-json-token"
            or reference is None
            or (
                config["secrets"]["provider"] == "azure-key-vault"
                and not config["secrets"]["vault_uri"]
            )
            or (
                config["secrets"]["provider"] == "local-file"
                and not config["secrets"].get("directory")
            )
            or (config["secrets"]["provider"] == "local-json" and not config["secrets"].get("file"))
        ):
            raise FrameworkError("CONFIG_INVALID")
        result["plan"] = _plan(config, version, result["packageVersion"])
        production_approved = readiness(config, version, entry, support)["installable"]
        test_approved = bool(
            arguments.controlled_test
            and entry["approval"] == "approved_for_test"
            and (
                experimental
                or (version == "12.10" and host["os"] == "ubuntu" and host["version"] == "24.04")
            )
            and metadata
            and (experimental or metadata["package_version"] == "12.10.1.1")
            and metadata["sha256"]
            and metadata["url"]
            and metadata["adapter_profile"] == "native-deb-register-json"
        )
        if not (production_approved or test_approved):
            raise FrameworkError("ARTIFACT_NOT_APPROVED")
        approval_state = "ARTIFACT_APPROVED_FOR_TEST" if test_approved else "ARTIFACT_APPROVED"
        result["state"] = approval_state
        result["stateHistory"].append(approval_state)
        if arguments.dry_run or config["execution"]["dry_run"]:
            result["status"] = "PLANNED"
        else:
            if not arguments.non_interactive:
                raise FrameworkError("CONFIG_INVALID")
            if effective_uid() != 0:
                raise FrameworkError("PREFLIGHT_FAILED")
            with lock_factory(lock_path):
                identity = (
                    ManagedIdentity(config["secrets"]["managed_identity_client_id"])
                    if config["secrets"]["provider"] == "azure-key-vault"
                    else None
                )
                backend = (
                    backend_factory()
                    if backend_factory
                    else LocalBackend(
                        blob_downloader=AzureBlobDownloader(identity) if identity else None
                    )
                )
                if arguments.controlled_test and any(
                    backend.exists(path) for path in ("/opt/jitterbit", CREDENTIALS, REGISTER_JSON)
                ):
                    raise FrameworkError("REGISTRATION_STATE_CONFLICT")
                credentials_exist = backend.exists(CREDENTIALS)
                field_refs = config["secrets"].get("registration_field_refs", {})
                if field_refs or not credentials_exist:
                    if config["secrets"]["provider"] == "local-file":
                        provider = LocalFileSecretProvider(config["secrets"]["directory"])
                    elif config["secrets"]["provider"] == "local-json":
                        provider = JsonFileSecretProvider(config["secrets"]["file"])
                    else:
                        provider = (
                            provider_factory(config["secrets"]["vault_uri"], identity)
                            if provider_factory
                            else AzureKeyVaultSecretProvider(
                                config["secrets"]["vault_uri"], identity
                            )
                        )
                if field_refs:
                    _resolve_registration_fields(config, provider)
                if credentials_exist:
                    secret = Secret(None)
                else:
                    secret = provider.resolve(reference)
                if provider is not None:
                    result["state"] = "SECRET_RESOLVED"
                    result["stateHistory"].append("SECRET_RESOLVED")
                workflow = NativeLinuxWorkflow(backend)
                try:
                    runtime = workflow.run(config, metadata, secret)
                except FrameworkError as exc:
                    if hasattr(exc, "runtime_result"):
                        result.update(
                            {
                                key: exc.runtime_result[key]
                                for key in (
                                    "state",
                                    "stateHistory",
                                    "changed",
                                    "serviceRunning",
                                    "harmonyRegistered",
                                )
                            }
                        )
                    raise
                result.update(runtime)
    except FrameworkError as exc:
        code = exc.spec.exitCode
        result["error"] = exc.as_dict()
        result["status"] = "BLOCKED" if exc.spec.name == "ARTIFACT_NOT_APPROVED" else "FAILED"
    except Exception:
        exc = FrameworkError("INTERNAL_ERROR")
        code = exc.spec.exitCode
        result["error"] = exc.as_dict()
        result["status"] = "FAILED"
    finally:
        if provider is not None:
            provider.clear()
    validate_schema(result, "bootstrap-result")
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments and arguments.result_file:
        try:
            write_result(arguments.result_file, output)
        except FrameworkError as exc:
            code = exc.spec.exitCode
            result["status"] = "FAILED"
            result["error"] = exc.as_dict()
            output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    stdout.write(output)
    return code


def main():
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
