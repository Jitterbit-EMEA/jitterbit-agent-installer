# Production readiness

The framework release candidate is QA-ready; production approval is not asserted. Maturity and artifact approval are separate.

## Core framework

| Capability | Current evidence |
| --- | --- |
| Native installer, token registration, initial health | TESTED_LIVE for PA 12.10.1.1 / Ubuntu 24.04.5 amd64 / no proxy |
| Graceful drain and TranDb operation polling | TESTED_LIVE zero-active path; timeout/failure/decreasing-count mocks |
| Complete local uninstall and clean reinstall | TESTED_LIVE on the same tuple; no Harmony deletion |
| Managed Identity / Key Vault | TESTED_LIVE on QA VM; caller provisioning and fleet RBAC unqualified |
| Version/artifact resolution and latest pinning | Implemented, mock tested; latest metadata inspected explicitly in Phase 2G |
| Composite existing-agent health | TESTED_LIVE; mandatory identity/connectivity/core and fresh restart markers; sync/service-status supplementary |
| Release packaging and verification | Source/mocks/archive/installed-layout validation; no live CSE deployment claimed |

## Runtime certification

| PA | Platform | Qualification |
| --- | --- | --- |
| 12.10.1.1 | Ubuntu 24.04.5 amd64 | TESTED_LIVE core lifecycle and scoped endpoint trust |
| 12.9.2.2 | Ubuntu 24.04 amd64 | Scoped live install/registration/initial health only |
| 12.10.1.1 | Ubuntu 22.04 amd64 | NOT TESTED |
| Other 17 pinned releases | Ubuntu 24.04 / 22.04 | AVAILABLE_UNQUALIFIED |

## Enterprise extensions

| Branch | Qualification |
| --- | --- |
| Bundled Java truststore / explicit endpoint trust | TESTED_LIVE for supplied CA:FALSE certificate; rollback and no-change behavior scoped to existing evidence |
| True custom CA | NOT_TESTED_WITH_CURRENT_CERTIFICATE |
| SSH/SFTP | DEFERRED_NO_TEST_MATERIAL |
| SSL client certificate | DEFERRED_NO_PRIVATE_KEY_OR_MTLS_ENDPOINT |
| Proxy | DEFERRED_NO_PROXY_TEST_ENVIRONMENT |

## Governance

| Gate | Status |
| --- | --- |
| Independent PA artifact provenance / production promotion | PENDING; local digest and QA approval are insufficient |
| Production sizing | NOT VALIDATED; explicit 2-vCPU functional QA exception only |
| Organizational security approval | PENDING; focused code review and scan are not sign-off |
| Release signing / trusted distribution / dependency supply chain | PENDING; archive/file hashes implemented |
| Azure provisioning-agent integration and live CSE dispatch | PENDING; handoff contract and bootstrap provided |
| Ubuntu 22.04 regression | PENDING |
| Exact historical old/new Harmony ID comparison | UNVERIFIED; previous ID missing |
| Harmony-side record deletion | NOT AUTOMATED / PENDING |

Support-management recommendation: CURRENT_TESTED 12.10, PREVIOUS_TESTED 12.9 with its limited scope, ARCHIVED_AVAILABLE 12.8 through 11.47. This is a release-management policy, not a compatibility promise. Availability never implies supported installability. See the [version matrix](version-qualification-matrix.md) and [security review](security-review.md).
