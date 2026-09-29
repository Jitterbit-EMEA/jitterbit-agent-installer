"""One locked on-host lifecycle, reusing proven removal and fresh installation."""

import os
import tempfile
from contextlib import nullcontext

from . import artifacts, bootstrap, host_readiness, restart_health, uninstall
from .catalogue import load_catalogues, resolve
from .config import load_config
from .errors import FrameworkError
from .host_lock import HostLock


def execute(
    argv,
    *,
    backend=None,
    provider=None,
    probe=None,
    install_fn=None,
    identity_probe=None,
    lock_factory=HostLock,
):
    from .release_cli import install, invoke, qualification_guard

    parser = bootstrap.SafeParser(add_help=False)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-unqualified", action="store_true")
    args, install_argv = parser.parse_known_args(argv)
    parsed = bootstrap.parser().parse_args(install_argv)
    config, _ = load_config(parsed.config, parsed.version)
    catalogue, support = load_catalogues()
    requested = config["agent"]["version"]
    logical, entry = (
        resolve(requested, catalogue)
        if requested != "latest"
        else (
            catalogue["aliases"]["recommended"],
            catalogue["versions"][catalogue["aliases"]["recommended"]],
        )
    )
    backend = backend or uninstall.LocalUninstallBackend()
    identity_probe = identity_probe or restart_health.SupportToolsProbe()
    result = {
        "operation": "REINSTALL",
        "status": "FAILED",
        "state": "REINSTALL_INITIALIZED",
        "stateHistory": ["REINSTALL_INITIALIZED"],
        "error": None,
        "requestedVersion": requested,
        "reinstall": {
            "drain": "NOT_RUN",
            "uninstall": "NOT_RUN",
            "cleanHost": "NOT_RUN",
            "install": "NOT_RUN",
            "registration": "NOT_RUN",
            "health": "NOT_RUN",
            "previousIdentityKnown": False,
            "previousIdentity": None,
            "newIdentity": None,
            "freshLocalRegistrationProved": False,
            "numericallyDistinctIdentityProved": False,
        },
    }
    section = result["reinstall"]
    advance = result["stateHistory"].append
    code = 0
    try:
        # Reject denied/unqualified policy before removal, including clean-start requests.
        host = host_readiness.detect()
        classification = qualification_guard(requested, entry, host, args.allow_unqualified)
        result["qualification"] = {
            "required": True,
            "qualified": classification == "QUALIFIED_VERSION",
            "overrideRequested": args.allow_unqualified,
            "overrideUsed": classification == "EXPERIMENTAL_VERSION_TEST",
            "executionClassification": classification,
        }
        if classification == "EXPERIMENTAL_VERSION_TEST" and not parsed.controlled_test:
            raise FrameworkError("ARTIFACT_NOT_APPROVED")
        dry = parsed.dry_run or config["execution"]["dry_run"]
        result["preflight"] = host_readiness.run(
            config,
            profile="REINSTALL",
            controlled_test=parsed.controlled_test,
            dry_run=dry,
            probe=probe,
            host=host,
        )
        initial = backend.snapshot()
        starting = host_readiness.classify(initial)
        result["startingState"] = starting
        advance("EXISTING_AGENT_DISCOVERED")
        if starting not in {
            "CLEAN_HOST",
            "AGENT_INSTALLED_REGISTERED",
            "AGENT_INSTALLED_UNREGISTERED",
        }:
            raise FrameworkError("REINSTALL_STATE_UNSUPPORTED")
        if dry:
            result["status"] = "PLANNED"
            result["plan"] = {
                "currentState": starting,
                "drain": starting != "CLEAN_HOST",
                "completeLocalUninstall": starting != "CLEAN_HOST",
                "targetPA": requested,
                "packageVersion": entry["package_version"],
                "artifactSHA256": entry["integrity"]["sha256"],
                "registrationProfile": "INITIAL_REGISTRATION",
                "qualification": classification,
                "preflightReady": result["preflight"]["status"] != "FAIL",
            }
            advance("REINSTALL_PLANNED")
            result["state"] = result["stateHistory"][-1]
            return 0, result
        if result["preflight"]["status"] == "FAIL":
            raise FrameworkError("PREFLIGHT_FAILED")
        if not parsed.non_interactive:
            raise FrameworkError("CONFIG_INVALID")
        # Acquire/validate the exact target before destruction and keep those bytes pinned.
        with tempfile.TemporaryDirectory(prefix="jbpa-reinstall-") as folder:
            prepared = artifacts.inspect(requested, folder, catalogue=catalogue)
            manifest, _ = prepared
            result["resolvedArtifact"] = manifest
            result["packageVersion"] = manifest["package_version"]
            classification = qualification_guard(
                requested, entry, host, args.allow_unqualified, manifest["package_version"]
            )
            result["qualification"].update(
                qualified=classification == "QUALIFIED_VERSION",
                overrideUsed=classification == "EXPERIMENTAL_VERSION_TEST",
                executionClassification=classification,
            )
            # Exercise normal install approval/config policy as a non-mutating plan before uninstall.
            check_argv = (
                install_argv
                + ["--dry-run"]
                + (["--allow-unqualified"] if args.allow_unqualified else [])
            )
            target_code, target = (install_fn or install)(
                check_argv, prepared=prepared, readiness_profile="REINSTALL", readiness_probe=probe
            )
            if target.get("preflight", {}).get("status") == "FAIL":
                result["targetValidation"] = target
                raise FrameworkError("PREFLIGHT_FAILED")
            if target_code:
                result["targetValidation"] = target
                raise FrameworkError(target.get("error", {}).get("name", "ARTIFACT_NOT_APPROVED"))
            with lock_factory():
                if backend.snapshot() != initial:
                    raise FrameworkError("REINSTALL_STATE_UNSUPPORTED")
                if starting != "CLEAN_HOST":
                    if starting == "AGENT_INSTALLED_REGISTERED":
                        about = identity_probe.about()
                        section["previousIdentity"] = about
                        section["previousIdentityKnown"] = bool(about)
                        if backend.agent_running():
                            result["baseline"] = {
                                "connectionCheck": identity_probe.connection(),
                                "agentRunning": True,
                            }
                    advance("DRAIN_STARTED")
                    removal_args = ["--complete"] + (["--force"] if args.force else [])
                    for key, value in config.get("uninstall_policy", {}).items():
                        removal_args += ["--" + key.replace("_", "-"), str(value)]
                    removal_code, removed = invoke(
                        uninstall.execute,
                        removal_args,
                        backend=backend,
                        provider=provider,
                        lock_factory=lambda path: nullcontext(),
                        effective_uid=os.geteuid,
                    )
                    result["uninstallResult"] = removed
                    result["stateHistory"].extend(removed["stateHistory"])
                    if removal_code:
                        name = removed.get("error", {}).get("name", "INTERNAL_ERROR")
                        if name.startswith(("DRAIN", "ACTIVE_OPERATION", "FORCED_STOP")):
                            section["drain"] = "FAILED"
                            raise FrameworkError("REINSTALL_DRAIN_FAILED")
                        section["uninstall"] = "FAILED"
                        raise FrameworkError(name)
                    section.update(drain="SUCCESS", uninstall="SUCCESS")
                    advance("DRAIN_COMPLETE")
                    advance("UNINSTALL_COMPLETE")
                else:
                    section.update(drain="NOT_APPLICABLE", uninstall="NOT_APPLICABLE")
                if host_readiness.classify(backend.snapshot()) != "CLEAN_HOST":
                    section["cleanHost"] = "FAIL"
                    raise FrameworkError("REINSTALL_CLEAN_HOST_FAILED")
                section["cleanHost"] = "PASS"
                advance("CLEAN_HOST_CONFIRMED")
                advance("INSTALL_STARTED")
                execution_args = install_argv + (
                    ["--allow-unqualified"] if args.allow_unqualified else []
                )
                install_code, installed = (install_fn or install)(
                    execution_args,
                    prepared=prepared,
                    lock_held=True,
                    readiness_profile="INSTALL",
                    readiness_probe=probe,
                )
                result["installResult"] = installed
                result["stateHistory"].extend(installed.get("stateHistory", []))
                section["install"] = "FAILED" if install_code else "SUCCESS"
                if install_code:
                    raise FrameworkError(
                        installed.get("error", {}).get("name", "INSTALLATION_FAILED")
                    )
                history = installed.get("stateHistory", [])
                required = {
                    "REGISTER_JSON_CREATED",
                    "AUTO_REGISTRATION_COMPLETED",
                    "CREDENTIALS_CREATED",
                    "HARMONY_AUTHENTICATED",
                    "AGENT_SERVICES_CONNECTED",
                    "AGENT_SYNCHRONIZED",
                    "COMPLETE",
                }
                if (
                    installed.get("status") != "COMPLETE"
                    or not required <= set(history)
                    or installed.get("serviceRunning") is not True
                    or installed.get("harmonyRegistered") is not True
                ):
                    raise FrameworkError("REINSTALL_FRESH_REGISTRATION_FAILED")
                section.update(
                    registration="SUCCESS",
                    health="HEALTHY",
                    freshLocalRegistrationProved=True,
                    newIdentity=identity_probe.about(),
                )
                result.update(serviceRunning=True, harmonyRegistered=True, status="COMPLETE")
                advance("REGISTRATION_COMPLETE")
                advance("INITIAL_SYNCHRONIZATION_COMPLETE")
                advance("HEALTHY")
                advance("REINSTALL_COMPLETE")
    except FrameworkError as exc:
        code, result["error"] = exc.spec.exitCode, exc.as_dict()
        result["lastSuccessfulState"] = next(
            state
            for state in reversed(result["stateHistory"])
            if not state.endswith(("TIMEOUT", "FAILED"))
        )
    except Exception:
        exc = FrameworkError("INTERNAL_ERROR")
        code, result["error"] = exc.spec.exitCode, exc.as_dict()
        result["lastSuccessfulState"] = next(
            state
            for state in reversed(result["stateHistory"])
            if not state.endswith(("TIMEOUT", "FAILED"))
        )
    result["state"] = result["stateHistory"][-1]
    return code, result
