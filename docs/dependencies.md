# Dependency register

Current assessment: 2026-09-23, Phase 2. Live qualification is tuple-specific.

| ID | Dependency | Previous State | Current State | Evidence | Remaining Work |
| --- | --- | --- | --- | --- | --- |
| DEP-001 | PA 12.10 artifact and integrity | BLOCKED for execution; null metadata | PARTIALLY_RESOLVED | User supplied PA 12.10.1.1 URL; vendor header and downloaded bytes agree on SHA-256; Debian fields inspected in artifact intake | Approve independently trusted digest and test package on Ubuntu 22.04 |
| DEP-002 | Secure unattended registration | BLOCKED; provider interface only | TESTED_LIVE_PARTIAL | LIVE-PA-1292-U2404 proves native register.json token registration with no proxy for PA 12.9.2.2 on Ubuntu 24.04; adapter tests cover conflicts and secret clearing | Regress PA 12.10 on Ubuntu 22.04; validate production secret provider, ownership, lifecycle and revocation |
| DEP-003 | Registration and health evidence | BLOCKED; runtime fields null | TESTED_LIVE_PARTIAL | LIVE-PA-1292-U2404 captures auto-registration, credentials, Harmony auth, Agent Services, sync, heartbeat and local service markers | Regress PA 12.10/Ubuntu 22.04 and capture negative live fixtures; no current control-plane API is claimed |
| DEP-004 | Azure VM provisioning integration hook | BLOCKED; actual agent absent from inspected checkout | PARTIALLY_RESOLVED | Custom Script wrapper, release builder, settings example and bootstrap result contract implemented | Connect the separately authored provisioning agent; validate CSE dispatch, result retrieval, guest identity/RBAC/network on approved VM |

DEP-001 remains execution-blocking because no trusted package digest was supplied. The supplied VM is Ubuntu 24.04 with PA 12.9.2.2 and returned an IMDS identity error, so it cannot establish the PA 12.10/Ubuntu 22.04 or live Key Vault gates. `TESTED_LIVE_PARTIAL` applies only to PA 12.9.2.2 on Ubuntu 24.04 amd64 with native token registration and no proxy.

Owner/input map: Dharish supplies artifact provenance, non-production target, approved test VM, network policy and provisioning-author contact/source. Implementation owner qualifies adapters and captures evidence under the [integration test plan](integration-test-plan.md). Storage/security owners confirm mirror rights, retention and secret lifecycle. See [summary](phase-1.5-summary.md) for the authorization gate.

## Phase 2C and 2D live resolution

Updated 2026-09-25. The earlier assessment above is historical. PA 12.10.1.1 installed, registered and passed composite health on Ubuntu 24.04.5 using VM Managed Identity and seven Key Vault values. Its artifact remains approved only for QA because the SHA-256 was locally calculated. Ubuntu 22.04 and production sizing remain unvalidated. The native Linux TranDb active-operation provider and complete local uninstall then passed on the same disposable QA VM; the first overstrict stop check failed safely, and the corrected completion removed all local product state. The Harmony record was not deleted or independently checked. See the [Phase 2C summary](phase-2c-summary.md), [Phase 2D summary](phase-2d-summary.md), and [live uninstall result](../evidence/pa-12.10.1.1/ubuntu-24.04/uninstall/uninstall-result.json).

## Phase 2E clean-reinstall update

Updated 2026-09-25. A clean Ubuntu 24.04.5 QA host successfully reinstalled PA 12.10.1.1 from the same locally hashed QA artifact, re-registered using VM Managed Identity and Key Vault, synchronized, and restored all four local services. This resolves the local reinstallability question for that exact tuple. The previous Harmony agent ID was absent from saved sanitized evidence, so distinctness of numerical IDs remains an evidence gap even though fresh local registration was confirmed. The old Harmony record was not deleted or observed. See the [Phase 2E summary](phase-2e-summary.md). Ubuntu 22.04, production sizing and production artifact approval remain open.

## Phase 2F enterprise qualification dependencies

Phase 2F.1B resolved the Java truststore qualification dependency: the supplied public PEM (CA:FALSE) passed real explicit endpoint import, new backup, fingerprint, one restart, mandatory fresh health and no-change idempotency on PA 12.10.1.1 / Ubuntu 24.04.5 amd64. Empty service-status output is a supplementary diagnostic limitation and no longer blocks existing-agent health. Connection-check and core status remain mandatory; restart profiles additionally require fresh Harmony/Agent Services/request-flow markers. Initial registration is unchanged and retains mandatory synchronization. A true CA remains NOT_TESTED_WITH_THIS_CERTIFICATE. SSH is DEFERRED_NO_TEST_MATERIAL; SSL is DEFERRED_NO_PRIVATE_KEY_OR_MTLS_ENDPOINT; proxy is DEFERRED_NO_PROXY_TEST_ENVIRONMENT. The no-proxy token-registration path remains qualified. See the [Phase 2F summary](phase-2f-summary.md).

## Phase 2G release dependencies

The release candidate packages framework source and pinned Python requirements, not interpreter/wheels or PA installers. Python 3.10+ / venv and an approved dependency index are bootstrap prerequisites; dpkg-deb is required for artifact inspection. The explicit latest endpoint inspection resolved 12.10.1.1 and matched the locally calculated QA digest. Historical versions remain unqualified and were not bulk-downloaded or installed. Production artifact provenance, Ubuntu 22.04 qualification, sizing, security approval, release signing, dependency supply-chain approval and actual Azure controller/CSE handoff remain open. Current scope supersedes dated historical dependency statements without deleting them.
