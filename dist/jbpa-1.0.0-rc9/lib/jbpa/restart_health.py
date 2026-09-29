"""Version-scoped health profiles for an already registered private agent.

Support Tools commands are diagnostic and interactive. Their launcher exit code
does not imply that an inner check passed; only explicit, bounded observations do.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .bootstrap import SafeParser
from .native_linux import REQUIRED_SERVICES, NativeLinuxWorkflow

SUPPORT_TOOLS = Path("/opt/jitterbit/AgentSupportTools")
SUPPORTED_COMMANDS = frozenset({"about", "connection-check", "service-status"})


class Profile(str, Enum):
    INITIAL_REGISTRATION = "INITIAL_REGISTRATION"
    STEADY_STATE_EXISTING_AGENT = "STEADY_STATE_EXISTING_AGENT"
    EXISTING_AGENT_START = "EXISTING_AGENT_START"
    EXISTING_AGENT_RESTART = "EXISTING_AGENT_RESTART"
    POST_CONFIGURATION_RESTART = "POST_CONFIGURATION_RESTART"
    POST_ROLLBACK_RESTART = "POST_ROLLBACK_RESTART"


def fresh_log_text(raw, since):
    """Keep only UTC-stamped records at or after a host-captured start time."""
    if since.tzinfo is None:
        raise ValueError("since must be timezone-aware")
    result = []
    for line in raw.splitlines():
        match = re.match(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\b", line)
        if not match:
            continue
        stamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        if stamp >= since:
            result.append(line)
    return "\n".join(result)


def runtime_signals(log, group_id, agent_id):
    observed = NativeLinuxWorkflow(None)._observe(log, group_id)
    identity = bool(
        re.search(rf"Agent Logged in: AgentId = {agent_id}; AgentGroupId = {group_id}\b", log)
    )
    return {
        "autoRegistrationCompleted": "AUTO_REGISTRATION_COMPLETED" in observed,
        "harmonyAuthenticated": "HARMONY_AUTHENTICATED" in observed and identity,
        "agentServicesConnected": "AGENT_SERVICES_CONNECTED" in observed,
        "requestFlowStarted": "REQUEST_FLOW_STARTED" in observed,
        "heartbeatObserved": "HEARTBEAT_STARTED" in observed,
        "freshSynchronizationObserved": "AGENT_SYNCHRONIZED" in observed,
    }


def core_services(output, returncode):
    return (
        returncode == 0
        and "All services are running" in output
        and all(f"{name} is running" in output for name in REQUIRED_SERVICES)
    )


def connection_check(output, returncode):
    """Return True, False for an explicit failure, or None for unknown output."""
    if returncode:
        return False
    lower = output.lower()
    if "not reachable" in lower or "unreachable" in lower or "failed" in lower:
        return False
    required = (
        "harmony gateway is reachable",
        "apache is reachable on port",
        "tomcat is reachable on port",
    )
    return True if all(item in lower for item in required) else None


def support_service_status(output, returncode):
    """Require explicit rows for all five documented services; a header is unknown."""
    if returncode:
        return False
    lines = output.splitlines()
    start = next((i for i, line in enumerate(lines) if "Command |" in line), None)
    if start is None:
        return None
    rows = [
        line.lower() for line in lines[start + 1 :] if "|" in line and "JB Agent Tools>" not in line
    ]
    if not rows:
        return None
    if any("not running" in row or "stopped" in row for row in rows):
        return False
    rows = [
        row
        for row in rows
        if len(columns := [value.strip() for value in row.strip().strip("|").split("|")]) >= 2
        and columns[1].isdigit()
        and int(columns[1]) > 0
    ]
    required = ("apache", "tomcat", "postgres", "pgbouncer", "verboselogshipper")
    return True if all(any(name in row for row in rows) for name in required) else None


def service_status_diagnostic(output, returncode):
    lines = output.splitlines()
    start = next((i for i, line in enumerate(lines) if "Command |" in line), None)
    rows = (
        []
        if start is None
        else [line for line in lines[start + 1 :] if "|" in line and "JB Agent Tools>" not in line]
    )
    status = "FAILED" if returncode else "AVAILABLE" if rows else "UNAVAILABLE"
    return {
        "status": status,
        "classification": "SERVICE_STATUS_" + status,
        "launcherExitCode": returncode,
        "rowsReturned": len(rows),
        "sanitizedHeader": "Command | Pid | Start time | %CPU | %MEM | Full command"
        if start is not None
        else None,
    }


def identity_confirmed(about, *, version, agent_name, group_name):
    return bool(about) and all(
        about.get(key) == expected
        for key, expected in (
            ("VersionNumber", version),
            ("Agent_Name", agent_name),
            ("Agent_Group_Name", group_name),
        )
    )


class SupportToolsProbe:
    def __init__(self, root=SUPPORT_TOOLS, runner=subprocess.run):
        self.root = Path(root)
        self.runner = runner

    def run(self, command):
        if command not in SUPPORTED_COMMANDS:
            raise ValueError("Unsupported diagnostic command")
        try:
            result = self.runner(
                ["/bin/bash", str(self.root / "run.sh")],
                cwd=self.root,
                input=f"{command}\nexit\n".encode(),
                capture_output=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return 1, ""
        return result.returncode, result.stdout.decode(errors="replace")

    def connection(self):
        code, output = self.run("connection-check")
        return connection_check(output, code)

    def services(self):
        code, output = self.run("service-status")
        return service_status_diagnostic(output, code)

    def about(self):
        code, output = self.run("about")
        if code:
            return None
        fields = {}
        for line in output.splitlines():
            if "|" not in line:
                continue
            key, value = line.split("|", 1)
            key = key.split(">")[-1].strip()
            if key in {"VersionNumber", "Agent_Name", "Agent_Group_Name"}:
                fields[key] = value.strip()
        return fields if len(fields) == 3 else None


def evaluate(
    profile,
    *,
    log,
    since,
    agent_id,
    group_id,
    credentials_present,
    local_core_services,
    connection,
    support_services,
    rollback_file_verified=None,
    agent_identity_confirmed=None,
):
    profile = Profile(profile)
    steady = profile is Profile.STEADY_STATE_EXISTING_AGENT
    signals = runtime_signals(log if steady else fresh_log_text(log, since), group_id, agent_id)
    if steady:
        signals["historicalSynchronizationObserved"] = signals["freshSynchronizationObserved"]
        signals["freshSynchronizationObserved"] = False
    diagnostic = (
        support_services
        if isinstance(support_services, dict)
        else {
            "status": "AVAILABLE"
            if support_services is True
            else "FAILED"
            if support_services is False
            else "UNAVAILABLE",
            "rowsReturned": None,
            "launcherExitCode": None,
        }
    )
    sync_required = profile is Profile.INITIAL_REGISTRATION
    mandatory = {
        "credentialsPresent": credentials_present,
        "localCoreServices": local_core_services,
        "connectionCheck": connection,
    }
    if steady:
        mandatory["agentIdentityConfirmed"] = agent_identity_confirmed
    else:
        mandatory.update(
            {
                key: signals[key]
                for key in ("harmonyAuthenticated", "agentServicesConnected", "requestFlowStarted")
            }
        )
    if sync_required:
        mandatory["supportToolServices"] = diagnostic["status"] == "AVAILABLE"
        mandatory["autoRegistrationCompleted"] = signals["autoRegistrationCompleted"]
        mandatory["freshSynchronizationObserved"] = signals["freshSynchronizationObserved"]
    if profile is Profile.POST_ROLLBACK_RESTART:
        mandatory["rollbackFileVerified"] = rollback_file_verified
    status = (
        "FAILED"
        if any(value is False for value in mandatory.values())
        else "UNCONFIRMED"
        if any(value is None for value in mandatory.values())
        else "HEALTHY"
    )
    sync_state = (
        "NOT_REQUIRED_STEADY_STATE"
        if steady
        else "FRESH_SYNC_MARKER_OBSERVED"
        if signals["freshSynchronizationObserved"]
        else "SYNC_REQUIRED_AND_UNCONFIRMED"
        if sync_required
        else "FRESH_SYNC_MARKER_NOT_OBSERVED"
    )
    return {
        "profile": profile.value,
        **signals,
        "credentialsPresent": credentials_present,
        "connectionCheck": connection,
        "localCoreServices": local_core_services,
        "serviceStatus": diagnostic,
        "serviceStatusMandatory": sync_required,
        "agentIdentityConfirmed": agent_identity_confirmed,
        "runtimeLogEvidenceScope": "SUPPORTING_HISTORY" if steady else "AFTER_EVENT_T0",
        "logSinceUtc": since.isoformat() if since is not None else None,
        "rollbackFileVerified": rollback_file_verified,
        "synchronizationRequired": sync_required,
        "synchronizationState": sync_state,
        "status": status,
    }


def execute(argv=None, *, stdout=None, probe=None, runner=subprocess.run):
    """Read-only, secret-free health evaluation for a known agent lifecycle event."""
    parser = SafeParser(description="Read-only private-agent lifecycle health")
    parser.add_argument("--profile", required=True, choices=[p.value for p in Profile])
    parser.add_argument("--since-utc")
    parser.add_argument("--expected-agent-name")
    parser.add_argument("--expected-agent-group-name")
    parser.add_argument("--expected-version", default="12.10.1.1")
    parser.add_argument("--expected-agent-id", required=True, type=int)
    parser.add_argument("--expected-agent-group-id", required=True, type=int)
    parser.add_argument("--expected-truststore-sha256")
    args = parser.parse_args(argv)
    stdout = stdout or sys.stdout
    since = None
    if args.since_utc:
        try:
            since = datetime.fromisoformat(args.since_utc.replace("Z", "+00:00"))
            if since.tzinfo is None:
                raise ValueError("UTC timezone required")
        except ValueError:
            parser.error("Invalid UTC timestamp")
    steady = args.profile == Profile.STEADY_STATE_EXISTING_AGENT.value
    if not steady and since is None:
        parser.error("Restart profile requires UTC event boundary")
    if steady and not (args.expected_agent_name and args.expected_agent_group_name):
        parser.error("Steady-state profile requires expected agent and group names")
    root = Path("/opt/jitterbit")
    store = root / "jre/lib/security/cacerts"
    expected_hash = args.expected_truststore_sha256
    if expected_hash and not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
        parser.error("Invalid truststore hash")
    store_verified = (
        store.is_file() and hashlib.sha256(store.read_bytes()).hexdigest() == expected_hash
        if expected_hash
        else None
    )
    try:
        local = runner(
            [str(root / "bin/jitterbit"), "status"],
            capture_output=True,
            timeout=30,
            check=False,
        )
        local_ok = core_services(local.stdout.decode(errors="replace"), local.returncode)
    except (OSError, subprocess.TimeoutExpired):
        local_ok = False
    diagnostics = probe or SupportToolsProbe()
    about = diagnostics.about()
    log = root / "log/jitterbit-agent.log"
    health = evaluate(
        args.profile,
        log=log.read_text(errors="replace") if log.is_file() else "",
        since=since,
        agent_id=args.expected_agent_id,
        group_id=args.expected_agent_group_id,
        credentials_present=(root / "Resources/credentials.txt").is_file(),
        local_core_services=local_ok,
        connection=diagnostics.connection(),
        support_services=diagnostics.services(),
        rollback_file_verified=store_verified,
        agent_identity_confirmed=identity_confirmed(
            about,
            version=args.expected_version,
            agent_name=args.expected_agent_name,
            group_name=args.expected_agent_group_name,
        )
        if steady
        else None,
    )
    result = {
        "schemaVersion": 1,
        "evaluatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "logSinceUtc": since.isoformat() if since else None,
        "health": health,
        "agentSupportToolsAbout": about,
        "truststoreHashMatchedExpected": store_verified,
        "controlPlaneStatus": "NOT_AUTOMATED",
    }
    stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if health["status"] == "HEALTHY" else 61


def main():
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
