# Error catalogue

> Phase 1.5 addendum (2026-09-22): historical Phase 0/1 content below is preserved. Current readiness and reconciled decisions are in the [Phase 1.5 summary](phase-1.5-summary.md), [dependency register](dependencies.md) and [Phase 2 specification](phase-2-implementation-spec.md). Runtime code/schemas remain Phase 1.

Stable process categories; use error.name for precise diagnosis. Retryable means an unchanged request might succeed after a transient external condition; it does not authorize automatic registration/install retries.

| Name | Exit | Meaning | Phase | Retryable |
| --- | --- | --- | --- | --- |
| SUCCESS | 0 | Requested framework action completed | FRAMEWORK | false |
| CONFIG_INVALID | 2 | Configuration or arguments are invalid | CONFIG | false |
| UNSUPPORTED_OS | 10 | Detected operating system is not supported | PREFLIGHT | false |
| UNSUPPORTED_ARCHITECTURE | 10 | Detected architecture is not supported | PREFLIGHT | false |
| VERSION_NOT_SUPPORTED | 10 | Version and platform combination is not supported | PREFLIGHT | false |
| PREFLIGHT_FAILED | 11 | Critical preflight checks failed | PREFLIGHT | false |
| VERSION_UNKNOWN | 12 | Version or approved alias is not in the catalogue | CONFIG | false |
| INSTALLER_METADATA_MISSING | 22 | Installer metadata is incomplete (DEP-001) | PREFLIGHT | false |
| NOT_IMPLEMENTED | 23 | Runtime execution is not implemented in Phase 1 | FRAMEWORK | false |
| BLOCKED_BY_PHASE_0_DEPENDENCY | 24 | Vendor evidence is required before execution | FRAMEWORK | false |
| DOWNLOAD_FAILED | 20 | Package download failed | DOWNLOAD | true |
| CHECKSUM_FAILED | 21 | Artifact integrity verification failed | DOWNLOAD | false |
| INSTALLATION_FAILED | 30 | Package installation failed | INSTALL | false |
| CONFIGURATION_FAILED | 40 | Configuration mutation failed | CONFIGURE | false |
| SECRET_PROVIDER_FAILED | 41 | Secret provider did not resolve the reference | SECRETS | false |
| LIFECYCLE_ACTION_REQUIRED | 42 | Explicit lifecycle action is required | INSTALL | false |
| HARMONY_AUTH_FAILED | 50 | Harmony authentication was rejected | REGISTRATION | false |
| REGISTRATION_FAILED | 51 | Registration was not successful | REGISTRATION | false |
| REGISTRATION_TIMEOUT | 52 | Registration confirmation timed out | REGISTRATION | false |
| HEALTH_CHECK_FAILED | 60 | Agent health is not confirmed | HEALTH | false |
| RESULT_WRITE_FAILED | 61 | Result destination is unsafe or unavailable | OUTPUT | false |
| INTERNAL_ERROR | 99 | Unexpected framework failure; no raw details emitted | FRAMEWORK | false |

## RC error categories

The 1.0 CLI envelope adds stable categories above existing detailed codes: SUCCESS, CONFIGURATION_ERROR, VERSION_ERROR, PLATFORM_ERROR, ARTIFACT_ERROR, DEPENDENCY_ERROR, INSTALL_ERROR, REGISTRATION_ERROR, HEALTH_ERROR, ENTERPRISE_CONFIGURATION_ERROR, DRAIN_ERROR, UNINSTALL_ERROR, SECRET_PROVIDER_ERROR and RELEASE_ERROR. Legacy error dictionaries remain inside details. Each top-level error includes name, exitCode, fixed message, phase, retryable and category.

VERSION_NOT_QUALIFIED / LATEST_VERSION_NOT_QUALIFIED exit 12 without installation. ARTIFACT_CHANGED exits 21; ARTIFACT_NOT_DEBIAN_PACKAGE, ARTIFACT_AUTH_REQUIRED, ARTIFACT_URL_REJECTED and ARTIFACT_INSPECTOR_UNAVAILABLE exit 22. These need policy/input/operator resolution and are not automatically retryable. LIVE_REGRESSION_NOT_AUTHORIZED exits 2. CONTRACT_CHANGED / REGRESSION_FAILED exit 80; RELEASE_INVALID exits 81. Transport download failures retain exit 20 and retryable=true. Existing secret/drain timeout retryability is preserved; a retry must use a new immutable result path and assess existing identity/product state first.
