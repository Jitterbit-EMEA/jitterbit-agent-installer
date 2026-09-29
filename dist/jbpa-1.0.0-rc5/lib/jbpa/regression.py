"""Sanitized contract observation and comparison for disposable test VMs."""

import json
import subprocess
from pathlib import Path

import yaml

from .native_linux import AGENT_LOG, CREDENTIALS, JITTERBIT, REGISTER_JSON, REQUIRED_SERVICES
from .platform import detect

PATHS = {
    "root": "/opt/jitterbit",
    "resources": "/opt/jitterbit/Resources",
    "register": REGISTER_JSON,
    "credentials": CREDENTIALS,
    "agent_log": AGENT_LOG,
    "installer_log": "/opt/jitterbit/log/Installer.log",
    "jre": "/opt/jitterbit/jre",
    "keytool": "/opt/jitterbit/jre/bin/keytool",
    "cacerts": "/opt/jitterbit/jre/lib/security/cacerts",
}

REQUIRED_STATES = (
    "AUTO_REGISTRATION_STARTED",
    "AUTO_REGISTRATION_COMPLETED",
    "CREDENTIALS_CREATED",
    "HARMONY_AUTHENTICATED",
    "AGENT_LOGGED_IN",
    "AGENT_SERVICES_CONNECTED",
    "AGENT_SYNCHRONIZED",
    "LOCAL_SERVICES_HEALTHY",
)


def _command(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=15)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def capture(result_file, host_provider=detect, exists=None, command=_command):
    """Capture booleans and metadata only; never read register or credentials contents."""
    result = json.loads(Path(result_file).read_text())
    exists = exists or (lambda path: Path(path).exists())
    host = host_provider()
    status = command([JITTERBIT, "status"]) if exists(JITTERBIT) else None
    installed = command(["dpkg-query", "-W", "-f=${Version}", "jitterbit-agent"])
    dependencies = command(["dpkg-query", "-W", "-f=${Depends}", "jitterbit-agent"])
    states = set(result.get("stateHistory", []))
    return {
        "schemaVersion": 1,
        "runId": result.get("runId"),
        "resultStatus": result.get("status"),
        "os": host["os"],
        "osVersion": host["version"],
        "architecture": host["architecture"],
        "packageVersion": installed,
        "packageDependencies": dependencies,
        "paths": {name: bool(exists(path)) for name, path in PATHS.items()},
        "markers": {name: name in states for name in REQUIRED_STATES},
        "localServices": {name: bool(status and name in status) for name in REQUIRED_SERVICES},
        "allServicesRunning": bool(status and "All services are running" in status),
        "logAvailableAfterSeconds": result.get("logAvailableAfterSeconds"),
        "registrationDurationSeconds": result.get("registrationDurationSeconds"),
    }


def compare(observation, contract):
    changes = []
    if observation["resultStatus"] != "COMPLETE":
        changes.append("bootstrap_result")
    if observation["os"] != "ubuntu" or observation["osVersion"] != "22.04":
        changes.append("target_os")
    if observation["architecture"] != "x86_64":
        changes.append("architecture")
    if observation["packageVersion"] != "12.10.1.1":
        changes.append("package_version")
    for name in ("root", "resources", "credentials", "agent_log", "jre", "keytool", "cacerts"):
        if not observation["paths"].get(name):
            changes.append("path:" + name)
    if observation["paths"].get("register"):
        changes.append("registration_input_not_removed")
    for name in REQUIRED_STATES:
        if not observation["markers"].get(name):
            changes.append("marker:" + name)
    for name in REQUIRED_SERVICES:
        if not observation["localServices"].get(name):
            changes.append("service:" + name)
    if not observation["allServicesRunning"]:
        changes.append("local_health")
    timeout = contract["polling"]["timeout_seconds"]
    duration = observation.get("registrationDurationSeconds")
    if duration is None or duration > timeout:
        changes.append("startup_timing")
    if not observation.get("packageDependencies"):
        changes.append("package_dependencies_unobserved")
    return {"status": "CONTRACT_CHANGED" if changes else "UNCHANGED", "changes": changes}


def load_contract(path):
    return yaml.safe_load(Path(path).read_text())
