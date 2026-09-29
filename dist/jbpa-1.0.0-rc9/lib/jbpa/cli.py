"""Read-only CLI. No provider calls, downloads, subprocesses or system changes."""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

from . import __version__
from .catalogue import load_catalogues, readiness, resolve
from .config import ROOT, load_config
from .errors import FrameworkError
from .platform import detect
from .preflight import PLAN, run
from .results import State, encode, write_result
from .security import Logger, Redactor


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default includes rejected argument values, potentially secrets.
        raise FrameworkError("CONFIG_INVALID")


def parser(command):
    p = Parser(description="Phase 1 read-only Jitterbit framework; runtime execution unavailable")
    p.add_argument("--config", default=str(ROOT / "config/agent.example.yaml"))
    p.add_argument("--version", help="Exact catalogue version or approved alias")
    p.add_argument("--verbose", action="store_true")
    p.add_argument(
        "--result-file", help="Create a new result file in an existing private directory"
    )
    if command == "install":
        p.add_argument("--dry-run", action="store_true")
        mode = p.add_mutually_exclusive_group()
        mode.add_argument(
            "--non-interactive",
            action="store_true",
            help="Explicitly choose unattended framework evaluation",
        )
        mode.add_argument(
            "--interactive", action="store_true", help="Returns NOT_IMPLEMENTED; no prompts yet"
        )
    return p


def execute(
    command,
    argv=None,
    *,
    stdout=None,
    stderr=None,
    host_provider=detect,
    environ=None,
    clock=None,
    run_id_factory=None,
):
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    now = clock or (lambda: datetime.now(timezone.utc).isoformat())
    run_id = (run_id_factory or (lambda: "jbpa-" + uuid.uuid4().hex))()
    state = State()
    redactor = Redactor()
    logger = Logger(stderr, run_id, redactor, clock=now)
    result = dict(
        schemaVersion=1,
        frameworkVersion=__version__,
        runId=run_id,
        timestamp=now(),
        command=command,
        status="FAILED",
        state=state.current,
        stateHistory=state.history,
        configValid=None,
        host=None,
        agent={"requestedVersion": None, "resolvedVersion": None, "installedVersion": None},
        readiness=None,
        platformStatus="NOT_CONFIGURED",
        checks=[],
        plan=[],
        dependencies=["DEP-001", "DEP-002", "DEP-003", "DEP-004"],
        error=None,
        changed=False,
        serviceRunning=None,
        harmonyRegistered=None,
        versionSource=None,
    )
    args = None
    code = 0
    try:
        args = parser(command).parse_args(argv)
        if getattr(args, "interactive", False):
            raise FrameworkError("NOT_IMPLEMENTED")
        config, source = load_config(
            args.config, args.version, os.environ if environ is None else environ
        )
        state.advance("CONFIG_LOADED")
        state.advance("CONFIG_VALIDATED")
        result["configValid"] = True
        logger.level = "DEBUG" if args.verbose else config["logging"]["level"]
        logger.event("INFO", "cli", "start")
        versions, support = load_catalogues()
        version, entry = resolve(config["agent"]["version"], versions)
        state.advance("VERSION_RESOLVED")
        result["agent"].update(requestedVersion=config["agent"]["version"], resolvedVersion=version)
        result["versionSource"] = source
        result["readiness"] = readiness(config, version, entry, support)
        host = host_provider()
        result["host"] = host
        state.advance("PLATFORM_DETECTED")
        status, checks = run(config, host, version, result["readiness"], support)
        result["platformStatus"], result["checks"] = status, checks
        state.advance("PREFLIGHT_COMPLETE")
        for item in checks:
            level = {
                "PASS": "INFO",
                "WARN": "WARN",
                "FAIL": "ERROR",
                "BLOCKED": "WARN",
                "SKIPPED": "INFO",
            }[item["status"]]
            logger.event(
                level,
                "preflight",
                "check",
                checkId=item["id"],
                status=item["status"],
                description=item["name"],
            )
        if command == "install":
            result["plan"] = PLAN.copy()
            for step in PLAN:
                logger.event("INFO", "plan", "plan", description=step)
        if command == "validate":
            if not result["readiness"]["supportedForTarget"]:
                raise FrameworkError("VERSION_NOT_SUPPORTED")
            result["status"] = "VALIDATED"
        elif command == "diagnostics":
            result["status"] = "DIAGNOSTICS"
        else:
            if any(c["status"] == "FAIL" for c in checks):
                raise FrameworkError(
                    "UNSUPPORTED_OS" if status != "SUPPORTED" else "PREFLIGHT_FAILED"
                )
            if not (args.dry_run or config["execution"]["dry_run"]):
                raise FrameworkError("NOT_IMPLEMENTED")
            if (
                not result["readiness"]["downloadConfigured"]
                or not result["readiness"]["integrityConfigured"]
            ):
                raise FrameworkError("INSTALLER_METADATA_MISSING")
            raise FrameworkError("BLOCKED_BY_PHASE_0_DEPENDENCY")
        state.advance(result["status"])
    except FrameworkError as exc:
        code = exc.spec.exitCode
        result["error"] = exc.as_dict()
        result["status"] = (
            "NOT_IMPLEMENTED"
            if exc.spec.name == "NOT_IMPLEMENTED"
            else "BLOCKED"
            if exc.spec.name in {"INSTALLER_METADATA_MISSING", "BLOCKED_BY_PHASE_0_DEPENDENCY"}
            else "FAILED"
        )
        if exc.spec.name == "CONFIG_INVALID":
            result["configValid"] = False
        state.advance("BLOCKED" if result["status"] == "BLOCKED" else "FAILED")
        logger.event("ERROR", "cli", "failure", errorName=exc.spec.name)
    except Exception:
        exc = FrameworkError("INTERNAL_ERROR")
        code, result["error"] = exc.spec.exitCode, exc.as_dict()
        state.advance("FAILED")
        logger.event("ERROR", "cli", "failure", errorName=exc.spec.name)
    result["state"], result["stateHistory"] = state.current, state.history.copy()
    text = encode(redactor.clean(result))
    if args and args.result_file:
        try:
            write_result(args.result_file, text)
        except FrameworkError as exc:
            code, result["error"], result["status"] = exc.spec.exitCode, exc.as_dict(), "FAILED"
            result["state"] = "FAILED"
            result["stateHistory"] = state.history + ["FAILED"]
            text = encode(redactor.clean(result))
    logger.event("INFO", "cli", "finish", status=result["status"])
    stdout.write(text)
    return code


def main():
    command = sys.argv[1]
    return execute(command, sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
