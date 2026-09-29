"""Stable public errors. Never include raw input or exception text."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ErrorSpec:
    name: str
    exitCode: int
    message: str
    phase: str
    retryable: bool = False


ERRORS = {
    e.name: e
    for e in [
        ErrorSpec(
            "REINSTALL_STATE_UNSUPPORTED",
            42,
            "Reinstall starting state is unsupported",
            "PREFLIGHT",
        ),
        ErrorSpec("REINSTALL_DRAIN_FAILED", 60, "Reinstall graceful drain failed", "DRAIN"),
        ErrorSpec(
            "REINSTALL_CLEAN_HOST_FAILED", 61, "Reinstall clean host was not confirmed", "UNINSTALL"
        ),
        ErrorSpec(
            "REINSTALL_FRESH_REGISTRATION_FAILED",
            50,
            "Fresh registration was not confirmed",
            "REGISTRATION",
        ),
        ErrorSpec("SUCCESS", 0, "Requested framework action completed", "FRAMEWORK"),
        ErrorSpec("CONFIG_INVALID", 2, "Configuration or arguments are invalid", "CONFIG"),
        ErrorSpec("INTERACTIVE_TTY_REQUIRED", 2, "Interactive mode requires a terminal", "CONFIG"),
        ErrorSpec("INTERACTIVE_ABORTED", 2, "Interactive action was cancelled", "CONFIG"),
        ErrorSpec(
            "UPGRADE_STATE_UNSUPPORTED",
            42,
            "Upgrade requires a healthy registered agent",
            "PREFLIGHT",
        ),
        ErrorSpec(
            "UPGRADE_BASELINE_UNHEALTHY", 42, "Current agent health is unconfirmed", "HEALTH"
        ),
        ErrorSpec(
            "UPGRADE_MAJOR_REVIEW_REQUIRED",
            12,
            "Major version upgrade requires a reviewed path",
            "VERSION",
        ),
        ErrorSpec(
            "UPGRADE_DOWNGRADE_DENIED",
            12,
            "Target version is older than the installed agent",
            "VERSION",
        ),
        ErrorSpec("UPGRADE_BACKUP_FAILED", 40, "Upgrade configuration backup failed", "INSTALL"),
        ErrorSpec(
            "UPGRADE_CONFIGURATION_FAILED",
            40,
            "Upgrade configuration preservation failed",
            "INSTALL",
        ),
        ErrorSpec(
            "UPGRADE_REGISTRATION_LOST", 50, "Agent registration was not preserved", "REGISTRATION"
        ),
        ErrorSpec(
            "UPGRADE_HEALTH_UNCONFIRMED", 60, "Upgraded agent health was not confirmed", "HEALTH"
        ),
        ErrorSpec(
            "UPGRADE_IDENTITY_UNCONFIRMED",
            60,
            "Upgraded agent identity was not confirmed",
            "HEALTH",
        ),
        ErrorSpec("UNSUPPORTED_OS", 10, "Detected operating system is not supported", "PREFLIGHT"),
        ErrorSpec(
            "UNSUPPORTED_ARCHITECTURE", 10, "Detected architecture is not supported", "PREFLIGHT"
        ),
        ErrorSpec(
            "VERSION_NOT_SUPPORTED",
            10,
            "Version and platform combination is not supported",
            "PREFLIGHT",
        ),
        ErrorSpec("PREFLIGHT_FAILED", 11, "Critical preflight checks failed", "PREFLIGHT"),
        ErrorSpec(
            "VERSION_UNKNOWN", 12, "Version or approved alias is not in the catalogue", "CONFIG"
        ),
        ErrorSpec(
            "INSTALLER_METADATA_MISSING",
            22,
            "Installer metadata is incomplete (DEP-001)",
            "PREFLIGHT",
        ),
        ErrorSpec(
            "NOT_IMPLEMENTED", 23, "Runtime execution is not implemented in Phase 1", "FRAMEWORK"
        ),
        ErrorSpec(
            "BLOCKED_BY_PHASE_0_DEPENDENCY",
            24,
            "Vendor evidence is required before execution",
            "FRAMEWORK",
        ),
        ErrorSpec("DOWNLOAD_FAILED", 20, "Package download failed", "DOWNLOAD", True),
        ErrorSpec(
            "ARTIFACT_NOT_APPROVED", 22, "Approved package metadata is required", "PREFLIGHT"
        ),
        ErrorSpec("CHECKSUM_FAILED", 21, "Artifact integrity verification failed", "DOWNLOAD"),
        ErrorSpec(
            "ARTIFACT_METADATA_MISMATCH", 22, "Artifact package identity does not match", "DOWNLOAD"
        ),
        ErrorSpec("INSTALLATION_FAILED", 30, "Package installation failed", "INSTALL"),
        ErrorSpec("PACKAGE_INSTALL_FAILED", 30, "Native package installation failed", "INSTALL"),
        ErrorSpec("CONFIGURATION_FAILED", 40, "Configuration mutation failed", "CONFIGURE"),
        ErrorSpec(
            "JKS_CONFIGURATION_FAILED", 40, "JKS configuration is not qualified", "CONFIGURE"
        ),
        ErrorSpec("JKS_NOT_FOUND", 40, "Bundled Java truststore is unavailable", "CONFIGURE"),
        ErrorSpec(
            "JKS_BASELINE_UNHEALTHY", 40, "Existing agent health is not confirmed", "CONFIGURE"
        ),
        ErrorSpec("JKS_BACKUP_FAILED", 40, "Truststore backup verification failed", "CONFIGURE"),
        ErrorSpec(
            "JKS_IMPORT_UNCONFIRMED", 40, "Truststore did not change after import", "CONFIGURE"
        ),
        ErrorSpec("JKS_CERT_INVALID", 40, "Certificate preflight failed", "CONFIGURE"),
        ErrorSpec("JKS_ALIAS_CONFLICT", 40, "Alias contains a different certificate", "CONFIGURE"),
        ErrorSpec("JKS_IMPORT_FAILED", 40, "Truststore certificate import failed", "CONFIGURE"),
        ErrorSpec(
            "JKS_VALIDATION_FAILED", 40, "Truststore or agent validation failed", "CONFIGURE"
        ),
        ErrorSpec(
            "JKS_CONFIGURATION_ROLLED_BACK", 40, "Truststore change was rolled back", "CONFIGURE"
        ),
        ErrorSpec("JKS_ROLLBACK_FAILED", 40, "Truststore rollback failed", "CONFIGURE"),
        ErrorSpec(
            "SSH_CONFIGURATION_FAILED", 40, "SSH configuration is not qualified", "CONFIGURE"
        ),
        ErrorSpec(
            "SSL_CONFIGURATION_FAILED", 40, "SSL configuration is not qualified", "CONFIGURE"
        ),
        ErrorSpec(
            "REGISTRATION_MODE_INCOMPATIBLE_WITH_PROXY",
            40,
            "Proxy requires a qualified registration mode",
            "CONFIGURE",
        ),
        ErrorSpec(
            "PROXY_REGISTRATION_BLOCKED",
            40,
            "Proxy registration mode has no qualified secure automation path",
            "CONFIGURE",
        ),
        ErrorSpec(
            "REGISTER_JSON_INVALID", 40, "Registration document input is invalid", "CONFIGURE"
        ),
        ErrorSpec(
            "REGISTRATION_STATE_CONFLICT",
            42,
            "Registration files are in a conflicting state",
            "REGISTRATION",
        ),
        ErrorSpec(
            "SECRET_PROVIDER_FAILED", 41, "Secret provider did not resolve the reference", "SECRETS"
        ),
        ErrorSpec("KEY_VAULT_AUTH_FAILED", 41, "Managed Identity authentication failed", "SECRETS"),
        ErrorSpec("KEY_VAULT_ACCESS_DENIED", 41, "Key Vault secret access was denied", "SECRETS"),
        ErrorSpec("KEY_VAULT_SECRET_NOT_FOUND", 41, "Key Vault secret was not found", "SECRETS"),
        ErrorSpec("KEY_VAULT_SECRET_EMPTY", 41, "Key Vault secret is empty", "SECRETS"),
        ErrorSpec(
            "LOCAL_SECRET_UNSAFE", 41, "Local secret path or permissions are unsafe", "SECRETS"
        ),
        ErrorSpec("LOCAL_SECRET_NOT_FOUND", 41, "Local secret file was not found", "SECRETS"),
        ErrorSpec("LOCAL_SECRET_EMPTY", 41, "Local secret file is empty", "SECRETS"),
        ErrorSpec("LOCAL_SECRET_INVALID", 41, "Local secret encoding is invalid", "SECRETS"),
        ErrorSpec("KEY_VAULT_NETWORK_FAILED", 41, "Key Vault transport failed", "SECRETS", True),
        ErrorSpec("SECRET_PROVIDER_TIMEOUT", 41, "Secret retrieval timed out", "SECRETS", True),
        ErrorSpec(
            "LIFECYCLE_ACTION_REQUIRED", 42, "Explicit lifecycle action is required", "INSTALL"
        ),
        ErrorSpec("HARMONY_AUTH_FAILED", 50, "Harmony authentication was rejected", "REGISTRATION"),
        ErrorSpec(
            "REGISTRATION_AUTH_FAILED",
            50,
            "Harmony registration authentication failed",
            "REGISTRATION",
        ),
        ErrorSpec("REGISTRATION_FAILED", 51, "Registration was not successful", "REGISTRATION"),
        ErrorSpec("AUTO_REGISTRATION_FAILED", 51, "Automatic registration failed", "REGISTRATION"),
        ErrorSpec(
            "REGISTRATION_NETWORK_FAILED",
            51,
            "Registration network connection failed",
            "REGISTRATION",
            True,
        ),
        ErrorSpec(
            "CREDENTIALS_NOT_CREATED", 52, "Agent credentials were not created", "REGISTRATION"
        ),
        ErrorSpec(
            "STALE_CREDENTIALS_REINTRODUCED",
            42,
            "Credentials appeared before fresh registration",
            "REGISTRATION",
        ),
        ErrorSpec(
            "AGENT_SERVICES_CONNECTION_FAILED",
            60,
            "Agent Services connection was not established",
            "HEALTH",
        ),
        ErrorSpec("SYNCHRONIZATION_FAILED", 60, "Agent synchronization failed", "HEALTH"),
        ErrorSpec(
            "LOCAL_SERVICE_FAILURE", 60, "Required local agent services are not healthy", "HEALTH"
        ),
        ErrorSpec(
            "REGISTRATION_TIMEOUT", 52, "Registration confirmation timed out", "REGISTRATION"
        ),
        ErrorSpec("HEALTH_CHECK_FAILED", 60, "Agent health is not confirmed", "HEALTH"),
        ErrorSpec(
            "ACTIVE_OPERATION_QUERY_FAILED",
            70,
            "Active operations could not be checked",
            "UNINSTALL",
            True,
        ),
        ErrorSpec("DRAIN_PAUSE_FAILED", 71, "Agent drain-pause failed", "UNINSTALL", True),
        ErrorSpec(
            "DRAIN_PAUSE_TIMEOUT", 72, "Active operations did not drain in time", "UNINSTALL", True
        ),
        ErrorSpec("DRAIN_STOP_FAILED", 73, "Agent drain-stop failed", "UNINSTALL", True),
        ErrorSpec("DRAIN_STOP_TIMEOUT", 74, "Agent did not stop in time", "UNINSTALL", True),
        ErrorSpec("FORCED_STOP_FAILED", 75, "Explicit forced stop failed", "UNINSTALL", True),
        ErrorSpec("PACKAGE_REMOVE_FAILED", 76, "Agent package removal failed", "UNINSTALL", True),
        ErrorSpec("USER_REMOVE_FAILED", 77, "Agent user removal failed", "UNINSTALL", True),
        ErrorSpec("RESIDUAL_CLEANUP_FAILED", 78, "Product state cleanup failed", "UNINSTALL", True),
        ErrorSpec("REGISTRATION_STATE_REMAINS", 79, "Registration state remains", "UNINSTALL"),
        ErrorSpec("POSTGRES_STATE_REMAINS", 79, "Bundled PostgreSQL state remains", "UNINSTALL"),
        ErrorSpec("PROCESS_STILL_RUNNING", 79, "Agent processes remain", "UNINSTALL", True),
        ErrorSpec("COMMAND_LINK_REMAINS", 79, "Agent command links remain", "UNINSTALL"),
        ErrorSpec(
            "STARTUP_INTEGRATION_REMAINS", 79, "Agent startup integration remains", "UNINSTALL"
        ),
        ErrorSpec(
            "LOCAL_UNINSTALL_INCOMPLETE",
            79,
            "Complete local uninstall is not verified",
            "UNINSTALL",
        ),
        ErrorSpec(
            "RESULT_WRITE_FAILED", 61, "Result destination is unsafe or unavailable", "OUTPUT"
        ),
        ErrorSpec(
            "INTERNAL_ERROR",
            99,
            "Unexpected framework failure; no raw details emitted",
            "FRAMEWORK",
        ),
    ]
}


for _name, _code, _phase, _retry in [
    ("VERSION_NOT_QUALIFIED", 12, "VERSION", False),
    ("LATEST_VERSION_NOT_QUALIFIED", 12, "VERSION", False),
    ("ARTIFACT_CHANGED", 21, "ARTIFACT", False),
    ("ARTIFACT_NOT_DEBIAN_PACKAGE", 22, "ARTIFACT", False),
    ("ARTIFACT_AUTH_REQUIRED", 22, "ARTIFACT", False),
    ("ARTIFACT_URL_REJECTED", 22, "ARTIFACT", False),
    ("ARTIFACT_INSPECTOR_UNAVAILABLE", 22, "DEPENDENCY", False),
    ("LIVE_REGRESSION_NOT_AUTHORIZED", 2, "CONFIG", False),
    ("REGRESSION_FAILED", 80, "RELEASE", False),
    ("CONTRACT_CHANGED", 80, "RELEASE", False),
    ("RELEASE_INVALID", 81, "RELEASE", False),
]:
    ERRORS[_name] = ErrorSpec(_name, _code, _name.replace("_", " ").capitalize(), _phase, _retry)


def category(spec):
    if spec.name == "SUCCESS":
        return "SUCCESS"
    if spec.name.startswith("VERSION") or spec.name.startswith("LATEST_VERSION"):
        return "VERSION_ERROR"
    if spec.name.startswith("DRAIN") or spec.name.startswith("ACTIVE_OPERATION"):
        return "DRAIN_ERROR"
    if spec.name.startswith(("JKS", "SSH", "SSL", "PROXY")):
        return "ENTERPRISE_CONFIGURATION_ERROR"
    if spec.name.startswith(("ARTIFACT", "CHECKSUM", "DOWNLOAD", "INSTALLER_METADATA")):
        return (
            "DEPENDENCY_ERROR"
            if spec.name == "ARTIFACT_INSPECTOR_UNAVAILABLE"
            else "ARTIFACT_ERROR"
        )
    return {
        "CONFIG": "CONFIGURATION_ERROR",
        "CONFIGURE": "ENTERPRISE_CONFIGURATION_ERROR",
        "VERSION": "VERSION_ERROR",
        "PREFLIGHT": "PLATFORM_ERROR",
        "DOWNLOAD": "ARTIFACT_ERROR",
        "INSTALL": "INSTALL_ERROR",
        "REGISTRATION": "REGISTRATION_ERROR",
        "HEALTH": "HEALTH_ERROR",
        "UNINSTALL": "UNINSTALL_ERROR",
        "SECRETS": "SECRET_PROVIDER_ERROR",
        "RELEASE": "RELEASE_ERROR",
        "DEPENDENCY": "DEPENDENCY_ERROR",
    }.get(spec.phase, "RELEASE_ERROR")


class FrameworkError(Exception):
    def __init__(self, name: str):
        self.spec = ERRORS[name]
        super().__init__(self.spec.message)

    def as_dict(self):
        return asdict(self.spec)
