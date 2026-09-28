# Phase 1 implementation matrix

Baseline: all Phase 0 documents reviewed on 2026-09-22. Initial reconciliation before code; statuses will be updated after validation. Source links J01–J16 refer to references.md. No runtime installation is authorized.

| ID | Requirement | Status | Component | Source file | Test coverage | Evidence/source | Unresolved dependency | Phase |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CFG-001 | Strict YAML and schema, safe overrides | IMPLEMENTED | config | src/jbpa/config.py | ConfigurationTests | configuration.md | none | 1 |
| CFG-002 | Conditional proxy/SSH/SSL/trust fields | IMPLEMENTED | schemas | config/schemas/agent.schema.json | ConfigurationTests conditional tests | J07–J10 | runtime verification later | 1/4 |
| VER-001 | Version/alias and readiness distinctions | IMPLEMENTED | catalogue | src/jbpa/catalogue.py | CatalogueTests | configuration.md | DEP-001 | 1 |
| OS-001 | OS detection and explicit compatibility | IMPLEMENTED | platform | src/jbpa/platform.py | PlatformTests fixtures | J02 | VM validation later | 1 |
| PRE-001 | Read-only structured preflight | IMPLEMENTED | preflight | src/jbpa/preflight.py | PreflightCliTests | architecture.md | network tests deferred | 1 |
| SEC-001 | References, opaque secret and redaction | IMPLEMENTED | security | src/jbpa/security.py | SecurityTests / AdditionalBoundaryTests | architecture.md | DEP-002 | 1 |
| STATE-001 | Guarded transitions, correlated results | IMPLEMENTED | state/results | src/jbpa/results.py | StateResultTests | architecture.md | none | 1 |
| CLI-001 | Validation, dry-run, diagnostics | IMPLEMENTED | CLI | src/jbpa/cli.py | PreflightCliTests / AdditionalBoundaryTests | Phase 1 request | none | 1 |
| JB-001 | Package acquisition/integrity/install | BLOCKED | provider | src/jbpa/providers.py | SecurityTests.test_runtime_provider_fail_closed | J01 | DEP-001 | 2 |
| JB-002 | Register and reconcile identity | BLOCKED | provider | src/jbpa/providers.py | SecurityTests.test_runtime_provider_fail_closed | J03–J05 | DEP-002 | 2 |
| JB-003 | Service and registration health/logs | BLOCKED | provider | src/jbpa/providers.py | provider refusal + null-runtime result tests | J11/J12 | DEP-003 | 2 |
| AZ-001 | Azure dispatch/storage/Key Vault | DEFERRED | provider contracts | src/jbpa/providers.py | no calls permitted | azure-integration.md | DEP-004 | 3 |
| MUT-001 | Targeted edit/backup/validate/restore | INTERFACE_ONLY | mutation contract | docs/developer-guide.md | no mutation permitted | architecture.md | selected product files | 2/4 |
| ENT-001 | Proxy/SSH/SSL/Java runtime changes | DEFERRED | future adapters | docs/research-findings.md | schema only in Phase 1 | J07–J10 | M07/M08/P05/P06 | 4 |
| LIFE-001 | Locks, idempotent install, backup/upgrade/uninstall | DEFERRED | future lifecycle | docs/architecture.md | dry-run repeatability only | J01 | real runtime evidence | 2/5 |
| QA-001 | Tests, lint, docs and hygiene | IMPLEMENTED | quality scripts | scripts/ | 76 tests; scripts/lint.sh | Phase 1 acceptance | none | 1 |
| PROD-001 | Fleet, failure injection, production review | DEFERRED | future acceptance | docs/architecture.md | real acceptance deferred | architecture.md | earlier phase gates | 6 |

Progress update: contracts, schemas, catalogue, platform, preflight and CLI implemented. Initial suite ran 64 tests: 60 passed, four failed due to a test-injection seam binding the package-manager probe at import time. Probe injection corrected; subsequent runs passed. No runtime providers implemented.

Final Phase 1 update: IMPLEMENTED denotes the bounded framework contract only, never vendor runtime readiness. The corrected suite and added boundary tests pass (76 tests). Runtime-provider rows remain BLOCKED/DEFERRED.

| ID | Requirement | Status | Component | Source file | Test coverage | Evidence/source | Unresolved dependency | Phase |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CFG-003 | Non-sensitive override precedence; no shell evaluation | IMPLEMENTED | loader | src/jbpa/config.py | override/tag/alias tests | configuration.md | .env parser deferred | 1 |
| OUT-001 | Atomic restricted explicit result artifact | IMPLEMENTED | writer | src/jbpa/results.py | permissions/symlink/overwrite tests | architecture.md | automatic system storage deferred | 1 |
| ERR-001 | Central errors and deterministic exits | IMPLEMENTED | error catalogue | src/jbpa/errors.py | negative CLI/exit tests | Phase 1 request | none | 1 |
| OBS-001 | Correlated logs and honest diagnostics | IMPLEMENTED | CLI/logger | src/jbpa/cli.py | levels/diagnostics/subprocess tests | Phase 1 request | runtime health DEP-003 | 1 |
| DRY-001 | Read-only planning and repeated-run stability | IMPLEMENTED | plan | src/jbpa/preflight.py | write/network/provider guards; repeatability | architecture.md | actual installation deferred | 1 |
| PRE-002 | Network/clock/ports/repositories/product state/key readability | DEFERRED | preflight extension | docs/developer-guide.md | explicit skipped/blocked checks | architecture.md | target VM and runtime evidence | 2/4 |
| INT-001 | Native assisted installer and credential prompts | DEFERRED | future adapter | src/jbpa/cli.py | --interactive returns NOT_IMPLEMENTED | J01/J03 | DEP-002 | 2 |

## Phase 1.5 evidence and design matrix

Reviewed 2026-09-22. The Phase 1 implemented rows above remain unchanged. IMPLEMENTED means code exists; TESTED_MOCK means local synthetic tests; DOCUMENTED means vendor documentation; DESIGNED means this project's proposal; INTERFACE_ONLY means no provider implementation; TESTED_LIVE and PRODUCTION_VALIDATED require their own evidence. No feature below is TESTED_LIVE or PRODUCTION_VALIDATED.

| Capability | Evidence maturity | Project maturity | Validation | Dependency / document |
| --- | --- | --- | --- | --- |
| Phase 1 config, catalogue, preflight, results/redaction | Locally inspected | IMPLEMENTED | TESTED_MOCK plus actual macOS CLI; 76 existing cases rerun | phase-1.5-validation.md |
| Debian package acquisition/type | DOCUMENTED J01/J17 | DESIGNED intake, INTERFACE_ONLY installer | BLOCKED exact artifact | DEP-001 / artifact-intake.md |
| Internal Blob catalogue/provenance approval | DOCUMENTED Azure primitives | DESIGNED | BLOCKED entitlement/storage/test | DEP-001 / schema-change-proposal.md |
| Interactive registration | DOCUMENTED J01/J03/J04 | DESIGNED; CLI still NOT_IMPLEMENTED | BLOCKED live baseline | DEP-002 / registration-strategy.md |
| Parameterized jitterbit-config | DOCUMENTED flags | DESIGNED, INTERFACE_ONLY | BLOCKED secure input grammar and prompts | DEP-002 |
| Native register.json/token | DOCUMENTED native path/shared token | DESIGNED preferred no-proxy candidate | REQUIRES_TEST; no provider | DEP-002 |
| Proxy routing constraint | DOCUMENTED J04/J08 | DESIGNED cross-field guard | Not implemented in schema/runtime | DEP-002 |
| Persistent identity lifecycle | DOCUMENTED J04/J12 | DESIGNED | BLOCKED exact-build restart/recovery evidence | DEP-002 |
| Support Tools/local health | DOCUMENTED J03/J18 | DESIGNED, INTERFACE_ONLY | BLOCKED command/exit contract | DEP-003 / health-evidence.md |
| Authoritative cloud gate | Console status DOCUMENTED | DESIGNED | BLOCKED supported machine API/evidence profile | DEP-003 |
| CSE/cloud-init/Run Command comparison | DOCUMENTED A01–A04 | DESIGNED handoff | BLOCKED actual caller and Azure validation | DEP-004 / azure-integration-decision.md |
| Runtime state/error changes | Phase 1 inspected | DESIGNED only | No v2 schema/code changes | phase-2-implementation-spec.md |
| IT-001–010 | Test plan complete | DESIGNED | NOT RUN | integration-test-plan.md |

Framework catalogue installable remains false; runtime fields remain null. Documentation status updates do not remove runtime guards.

## Phase 2 native Linux update

Updated 2026-09-23. `TESTED_LIVE_PARTIAL` is restricted to PA 12.9.2.2 on Ubuntu 24.04 amd64, native `.deb`, `register.json`, no proxy, Harmony EMEA West. PA 12.10 on Ubuntu 22.04 remains `REQUIRES_TEST`. No trusted digest was supplied, so CLI installation remains fail-closed.

| Capability | Project maturity | Validation | Source |
| --- | --- | --- | --- |
| Native package validation/install | IMPLEMENTED_ADAPTER | TESTED_MOCK; live sequence evidenced, integrity approval blocked | `src/jbpa/native_linux.py`, LIVE-PA-1292-U2404 |
| register.json token registration | IMPLEMENTED_ADAPTER | TESTED_MOCK and TESTED_LIVE_PARTIAL for qualified tuple | runtime contract |
| Delayed log polling and composite health | IMPLEMENTED_ADAPTER | TESTED_MOCK and TESTED_LIVE_PARTIAL for qualified tuple | sanitized success log |
| Existing identity reconciliation | IMPLEMENTED_ADAPTER | TESTED_MOCK | `tests/unit/test_native_linux.py` |
| Proxy, SSH, SSL and Java trust mutation | FAIL_CLOSED | REQUIRES_TEST | adapter rejects unqualified branches |
| PA 12.10 / Ubuntu 22.04 | CATALOGUED_PENDING | REQUIRES_TEST | no supplied live evidence |

## Phase 2B production integration update

Updated 2026-09-23. The PA 12.10.1.1 URL is known, but approval is still pending a trusted digest. The supplied VM is Ubuntu 24.04 with PA 12.9.2.2 already registered and IMDS returned HTTP 400.

| Capability | Project maturity | Validation | Source |
| --- | --- | --- | --- |
| Managed Identity and Key Vault secret resolution | IMPLEMENTED | TESTED_MOCK; VM identity gate FAIL | `src/jbpa/azure_identity.py` |
| Private Blob PA artifact retrieval | IMPLEMENTED | TESTED_MOCK; live Blob access PENDING | `src/jbpa/azure_artifact.py` |
| Azure-facing bootstrap/result | IMPLEMENTED | TESTED_MOCK; deployment PENDING | `src/jbpa/bootstrap.py`, v2 result schema |
| CSE wrapper and release bundle | IMPLEMENTED | wrapper success/failure tests; Azure dispatch PENDING | `azure/custom-script/`, `scripts/build-release.sh` |
| PA 12.10 artifact gate | IMPLEMENTED | pending digest blocks before secret resolution | `config/versions.yaml`, bootstrap tests |
| Secret cleanup and registration hardening | IMPLEMENTED | TESTED_MOCK; live ownership PENDING | native workflow tests |
| PA 12.10/Ubuntu 22.04 regression harness | IMPLEMENTED | comparison tests; live run PENDING | `src/jbpa/regression.py` |

## Phase 2D native Linux decommission

Updated 2026-09-25. Scoped to PA 12.10.1.1 on Ubuntu 24.04.5 amd64. The live QA VM was completely uninstalled without a hard stop. The first attempt stopped safely after treating bundled support processes as running core agent services; the corrected completion run verified all local product state absent.

| Capability | Project maturity | Validation | Source |
| --- | --- | --- | --- |
| TranDb active-operation provider, status 0-11, count/quiet/summary/debug | IMPLEMENTED | TESTED_LIVE on QA VM; current count 0; user supplied prior live count 2 | `src/jbpa/pending_operations.py`, provider evidence |
| Graceful drain-pause and active-operation polling | IMPLEMENTED | TESTED_LIVE zero-active path; decreasing-count and timeout paths tested with fakes | `src/jbpa/uninstall.py`, drain timeline |
| Drain-stop and core-agent stopped validation | IMPLEMENTED | TESTED_LIVE; four agent services stopped, bundled support processes removed during package removal | drain timeline |
| Force-only hard stop | IMPLEMENTED | TESTED_MOCK; not invoked live | uninstall tests |
| Package/account/residual removal and final clean-host check | IMPLEMENTED | TESTED_LIVE; no product package, root, user, processes, links or startup files remain | live uninstall result, post-uninstall evidence |
| Idempotent complete uninstall | IMPLEMENTED | TESTED_LIVE; second run returned `ALREADY_UNINSTALLED` exit 0 | idempotent result |
| Harmony agent record deletion | NOT_IMPLEMENTED | NOT_REQUESTED; unsupported API not invoked | lifecycle guide |

## Phase 2E clean reinstall

Updated 2026-09-25. PA 12.10.1.1 on Ubuntu 24.04.5 amd64, controlled 2-vCPU QA exception.

| Capability | Project maturity | Validation | Source |
| --- | --- | --- | --- |
| Clean post-uninstall baseline | IMPLEMENTED | TESTED_LIVE; no package, root, account, credentials, runtime or startup integration | Phase 2E clean baseline |
| Fresh package reinstall | IMPLEMENTED | TESTED_LIVE; exact artifact hash and package metadata, healthy runtime | Phase 2E result and runtime facts |
| Post-install stale-credential guard | IMPLEMENTED | TESTED_MOCK negative test and TESTED_LIVE passing path | `src/jbpa/native_linux.py`, 143-test suite |
| Fresh registration, Agent Services, synchronization and health | IMPLEMENTED | TESTED_LIVE on scoped tuple | Phase 2E lifecycle evidence |
| Exact old/new Harmony ID distinctness | EVIDENCE_GAP | Previous ID unavailable; new ID 646830 captured | Phase 2E identity comparison |
| Harmony-side old agent deletion | NOT_IMPLEMENTED | NOT_REQUESTED | lifecycle guide |

## Phase 2F enterprise branches

Updated 2026-09-26. The local lifecycle and reinstall are `TESTED_LIVE`; the historical Harmony ID comparison is `UNVERIFIED`.

| Capability | Project maturity | Validation | Source |
| --- | --- | --- | --- |
| Bundled PKCS12 truststore explicit endpoint import / JKS branch | IMPLEMENTED, TESTED_LIVE (scoped) | New verified backup, real import/fingerprint/hash change, one restart, mandatory health and matching-alias NO_CHANGE with stable hash and zero restarts passed; true CA not tested | `src/jbpa/enterprise.py`, [Phase 2F JKS evidence](../evidence/pa-12.10.1.1/ubuntu-24.04/enterprise/jks/) |
| Lifecycle-specific health and read-only Support Tools provider | IMPLEMENTED, TESTED_LIVE (scoped) | Initial-registration sync remains mandatory and unchanged; existing sync/service-status supplementary; current identity/connectivity/core health and post-T0 mandatory restart health passed | `src/jbpa/restart_health.py`, [health contract](health-contract.md) |
| SSH/SFTP keys and targeted PA config | SCHEMA_AND_FAIL_CLOSED_GATE_AVAILABLE | DEFERRED_NO_TEST_MATERIAL; no QA keys or SFTP endpoint | Phase 2F SSH pre-state |
| SSL client cert and targeted PA config | SCHEMA_AND_FAIL_CLOSED_GATE_AVAILABLE | DEFERRED_NO_PRIVATE_KEY_OR_MTLS_ENDPOINT | Phase 2F SSL pre-state |
| Proxy and alternate registration | FAIL_CLOSED_POLICY | DEFERRED_NO_PROXY_TEST_ENVIRONMENT; no-proxy token path remains qualified | Phase 2F proxy pre-state |

## Phase 2G release hardening

| Capability | Implementation | Qualification boundary |
| --- | --- | --- |
| Governed 19-release catalogue plus dynamic latest | Implemented; exact identity/count/schema checks | Two scoped live versions; 17 available unqualified |
| Artifact inspect/verify/intake/cache | Implemented; dpkg fields, bounds, immutable hashes and serial cleanup | Latest metadata inspected live; no historical batch executed |
| Version/latest install guard and one-file pinning | Implemented; mocked handoff and negative guards | Existing runtime qualification unchanged |
| BASIC / FULL_LIFECYCLE regression orchestration | Implemented; explicit live flag, clean-host gate, mocked composition | No new live lifecycle regression in this phase |
| RC result / errors / CLI | Implemented; versioned envelope, compatibility details, stable categories | No external Azure controller deployment claimed |
| Release build / verify | Implemented; fail-fast validation, manifest/file/archive hashes, bounded tar verification | QA release candidate; production signing/approval pending |
