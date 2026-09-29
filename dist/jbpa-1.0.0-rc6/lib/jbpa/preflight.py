"""Safe local checks. Network, secret and vendor probes are deliberately absent."""

import shutil

from .catalogue import support_for


def check(id_, name, status, message, severity="critical", dependency=None):
    return dict(
        id=id_, name=name, status=status, severity=severity, message=message, dependency=dependency
    )


def run(config, host, version, readiness, support, which=None):
    which = which or shutil.which
    status, entry = support_for(host, version, support)
    expected = config["agent"]["expected_os"]
    expected_matches = (host["os"], host["version"], host["architecture"], host["packageType"]) == (
        expected["id"],
        expected["version"],
        expected["architecture"],
        config["agent"]["package_kind"],
    )
    checks = [
        check("CFG-001", "Configuration schema", "PASS", "Configuration is structurally valid"),
        check(
            "OS-001",
            "Linux host",
            "PASS" if host["system"] == "Linux" else "FAIL",
            "Linux is required for runtime execution",
        ),
        check(
            "OS-002",
            "Platform support",
            "PASS" if status == "SUPPORTED" else "FAIL",
            "Detected platform support: " + status,
        ),
        check(
            "OS-003",
            "Expected target",
            "PASS" if expected_matches else "FAIL",
            "Detected platform must match the configured target",
        ),
        check("VER-001", "Known version", "PASS", "Requested version resolves in the catalogue"),
        check(
            "VER-002",
            "Target compatibility",
            "PASS" if readiness["supportedForTarget"] else "FAIL",
            "Version must be supported for the configured target",
        ),
    ]
    for id_, key, requirement, name in [
        ("RES-001", "cpuCount", "cpu_count", "CPU count"),
        ("RES-002", "memoryBytes", "memory_bytes", "Memory"),
        ("RES-003", "diskTotalBytes", "disk_total_bytes", "Disk capacity"),
    ]:
        value = host[key]
        outcome = (
            "BLOCKED"
            if entry is None or value is None
            else ("PASS" if value >= entry["minimum"][requirement] else "FAIL")
        )
        checks.append(check(id_, name, outcome, "Compare observed capacity to documented minimum"))
    checks.extend(
        [
            check(
                "RES-004",
                "Available disk",
                "WARN",
                "Free space is reported; package-specific free-space requirement is unresolved",
                "warning",
                "DEP-001",
            ),
            check(
                "HOST-001",
                "Hostname",
                "PASS" if host["hostname"] != "unknown" else "FAIL",
                "Hostname observation completed",
            ),
            check(
                "PKG-001",
                "Package manager",
                "PASS" if host["packageManager"] and which(host["packageManager"]) else "FAIL",
                "Package manager availability only; repositories and locks are not tested",
            ),
            check(
                "TOOL-001", "Python runtime", "PASS", "Framework dependencies loaded successfully"
            ),
            check(
                "JB-001",
                "Installer metadata",
                "PASS"
                if readiness["downloadConfigured"] and readiness["integrityConfigured"]
                else "BLOCKED",
                "Exact build, download URL and trusted digest are required",
                dependency="DEP-001",
            ),
            check(
                "JB-002",
                "Installer execution",
                "BLOCKED",
                "No real installer provider exists in Phase 1",
                dependency="DEP-001",
            ),
            check(
                "JB-003",
                "Registration mechanism",
                "BLOCKED",
                "Verified secure registration adapter is required",
                dependency="DEP-002",
            ),
            check(
                "JB-004",
                "Harmony health",
                "SKIPPED",
                "Registration health requires vendor evidence and Phase 2",
                dependency="DEP-003",
            ),
            check(
                "NET-001",
                "DNS and outbound connectivity",
                "SKIPPED",
                "No network probes in Phase 1 dry-run",
                "info",
            ),
            check(
                "SEC-001",
                "Secret resolution",
                "SKIPPED",
                "No secret provider is invoked in Phase 1",
                "info",
            ),
            check(
                "FILE-001",
                "Certificate and key checks",
                "SKIPPED",
                "Only schema checks run; key access and certificate parsing are deferred",
                "info",
            ),
        ]
    )
    return status, checks


PLAN = [
    "Validate the actual host against the approved support matrix",
    "Resolve exact approved package build and trusted integrity evidence (DEP-001)",
    "Inspect existing product state and back up affected configuration before changes",
    "Resolve secret references through a reviewed provider; never print values (DEP-002)",
    "Download and verify the Private Agent artifact (DEP-001)",
    "Install the approved package through the future installer provider",
    "Configure required connection prerequisites and registration (DEP-002)",
    "Start verified product services",
    "Confirm current Harmony registration using verified evidence (DEP-003)",
    "Run post-install health checks and return an independently verified result",
]
