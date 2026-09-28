"""Explicit disposable-host regression using existing install and uninstall flows."""

import json
import os
import tempfile
from pathlib import Path

from .artifacts import inspect
from .config import ROOT, load_yaml, validate_schema
from .errors import FrameworkError
from .platform import detect
from .regression import REQUIRED_STATES, capture
from .results import write_result
from .uninstall import LocalUninstallBackend
from .uninstall import execute as uninstall_execute


def compare_runtime(observation, contract):
    """Version identity is verified separately; compare observed runtime semantics."""
    dimensions = contract["dimensions"]
    changes = []
    if observation.get("resultStatus") != "COMPLETE":
        return {"status": "REGRESSION_FAILED", "changes": ["lifecycle_result"]}
    if observation.get("architecture") != "x86_64":
        changes.append("architecture")
    expected_os = contract["platform"]
    if observation.get("os") != expected_os["os"] or observation.get("osVersion") != ".".join(
        expected_os["version"].split(".")[:2]
    ):
        changes.append("platform")
    for name in ("root", "resources", "credentials", "agent_log", "jre", "keytool", "cacerts"):
        if not observation["paths"].get(name):
            changes.append("path:" + name)
    if observation["paths"].get("register"):
        changes.append("registration_input_not_removed")
    dependencies = {
        d.strip().split()[0]
        for d in (observation.get("packageDependencies") or "").split(",")
        if d.strip()
    }
    if dependencies != set(dimensions["dependencies"]):
        changes.append("dependencies")
    for marker in REQUIRED_STATES:
        if not observation["markers"].get(marker):
            changes.append("marker:" + marker)
    for service in dimensions["service_contract"]:
        if not observation["localServices"].get(service):
            changes.append("service:" + service)
    if not observation.get("allServicesRunning"):
        changes.append("local_health")
    return {
        "status": "CONTRACT_CHANGED"
        if changes
        else "CONTRACT_COMPATIBLE_MINOR_CHANGES"
        if observation.get("registrationDurationSeconds") is not None
        and contract.get("startup_observation_seconds") is not None
        and observation["registrationDurationSeconds"] != contract["startup_observation_seconds"]
        else "CONTRACT_UNCHANGED",
        "changes": changes,
        "scope": "OBSERVED_INITIAL_RUNTIME",
        "unobservedDimensions": ["existing-agent-restart", "truststore", "drain", "uninstall"],
    }


def run_steps(
    args,
    *,
    inspect_fn=inspect,
    install_fn=None,
    uninstall_fn=None,
    snapshot=None,
    capture_fn=capture,
    host_provider=detect,
):
    from .release_cli import install, invoke

    install_fn = install_fn or install
    uninstall_fn = uninstall_fn or (lambda argv: invoke(uninstall_execute, argv))
    snapshot = snapshot or LocalUninstallBackend().snapshot
    host = host_provider()
    if (
        args.target != f"{host['os']}-{host['version']}"
        or host["system"] != "Linux"
        or host["architecture"] != "x86_64"
    ):
        raise FrameworkError("UNSUPPORTED_OS")
    steps = []
    with tempfile.TemporaryDirectory(prefix="jbpa-regression-") as directory:
        manifest, package = inspect_fn(args.version, directory)
        steps.append({"step": "ARTIFACT_VALIDATION", "status": "SUCCESS", "artifact": manifest})
        clean = snapshot()
        if any(clean.values()):
            raise FrameworkError("REGISTRATION_STATE_CONFLICT")
        steps.append({"step": "CLEAN_BASELINE", "status": "SUCCESS", "snapshot": clean})
        argv = [
            "--config",
            args.config,
            "--version",
            args.version,
            "--non-interactive",
            "--controlled-test",
        ]
        if args.allow_unqualified:
            argv.append("--allow-unqualified")
        code, result = install_fn(argv, prepared=(manifest, package))
        steps.append(
            {"step": "INSTALL_REGISTER_HEALTH", "status": result.get("status"), "result": result}
        )
        if (
            code
            or result.get("status") != "COMPLETE"
            or not result.get("harmonyRegistered")
            or not result.get("serviceRunning")
        ):
            return code or 80, {"status": "REGRESSION_FAILED", "mode": args.mode, "steps": steps}
        result_path = Path(directory).resolve() / "install.json"
        write_result(result_path, json.dumps(result))
        observation = capture_fn(result_path)
        if observation["packageVersion"] != manifest["package_version"]:
            raise FrameworkError("ARTIFACT_METADATA_MISMATCH")
        contract = load_yaml(args.contract)
        validate_schema(contract, "runtime-contract")
        comparison = compare_runtime(observation, contract)
        steps.append(
            {
                "step": "RUNTIME_CONTRACT_CAPTURE",
                "observation": observation,
                "comparison": comparison,
            }
        )
        if comparison["status"] not in {"CONTRACT_UNCHANGED", "CONTRACT_COMPATIBLE_MINOR_CHANGES"}:
            return 80, {"status": comparison["status"], "steps": steps, "mode": args.mode}
        if args.mode == "full-lifecycle":
            code, removal = uninstall_fn(["--complete"])
            steps.append(
                {"step": "DRAIN_UNINSTALL", "status": removal.get("status"), "result": removal}
            )
            if code or any(snapshot().values()):
                return code or 80, {
                    "status": "REGRESSION_FAILED",
                    "steps": steps,
                    "mode": args.mode,
                }
            code, reinstall = install_fn(argv, prepared=(manifest, package))
            steps.append(
                {
                    "step": "REINSTALL_REGISTER_HEALTH",
                    "status": reinstall.get("status"),
                    "result": reinstall,
                }
            )
            if (
                code
                or reinstall.get("status") != "COMPLETE"
                or not reinstall.get("harmonyRegistered")
                or not reinstall.get("serviceRunning")
            ):
                return code or 80, {
                    "status": "REGRESSION_FAILED",
                    "steps": steps,
                    "mode": args.mode,
                }
        return 0, {
            "status": comparison["status"],
            "mode": args.mode,
            "steps": steps,
            "qualificationPromotion": "MANUAL_REVIEW_REQUIRED",
            "historicalHarmonyDeletion": "NOT_AUTOMATED",
        }


def regression(argv):
    from .release_cli import Parser

    p = Parser()
    p.add_argument("action", choices=["run"])
    p.add_argument("--version", required=True)
    p.add_argument("--target", default="ubuntu-24.04")
    p.add_argument("--mode", choices=["basic", "full-lifecycle"], default="basic")
    p.add_argument("--config")
    p.add_argument("--live", action="store_true")
    p.add_argument("--allow-unqualified", action="store_true")
    p.add_argument("--contract", default=str(ROOT / "contracts/12.10.1.1.yaml"))
    args = p.parse_args(argv)
    if not args.live or not args.config:
        raise FrameworkError("LIVE_REGRESSION_NOT_AUTHORIZED")
    if os.geteuid() != 0:
        raise FrameworkError("PREFLIGHT_FAILED")
    return run_steps(args)
