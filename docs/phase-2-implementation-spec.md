# Phase 2 implementation specification

Status: DESIGNED, awaiting inputs and authorization. Documentation only. Scope: exact-build Ubuntu22.04 x86_64 PA12.10 base lifecycle and selected registration adapter; upgrades, other OSes, ephemeral fleets and enterprise SSH/SSL/trust changes remain deferred unless separately authorized. No Phase 1 runtime code or schema changed.

## Prerequisites and boundaries

Follow [artifact intake](artifact-intake.md), [registration strategy](registration-strategy.md), [health model](health-evidence.md), [schema proposal](schema-change-proposal.md) and [test plan](integration-test-plan.md). No guessed package metadata, credentials-file grammar, support-tool flags or log success patterns. Inspect the actual package first. Retain Python core/Bash entrypoints, provider interfaces, strict config, redaction and new-file atomic results.

A Phase 2 provider may not be enabled until its package/profile/input channel is qualified. Build and test locally against fixtures first; real VM actions require the phase's explicit non-production scope. All dry-run paths remain read-only with no secret resolution.

## State proposal and reconciliation

```text
INITIALIZED -> CONFIG_LOADED -> CONFIG_VALIDATED -> VERSION_RESOLVED
-> PLATFORM_DETECTED -> PLATFORM_VALIDATED -> PREFLIGHT_COMPLETE
-> ARTIFACT_RESOLVED -> ARTIFACT_VERIFIED -> PACKAGE_INSTALLED
-> REGISTRATION_PREPARED -> AGENT_STARTED -> REGISTRATION_PENDING
-> REGISTERED -> LOCAL_HEALTH_VALIDATED
-> HARMONY_CONNECTIVITY_VALIDATED -> COMPLETE
```

Keep VERSION_RESOLVED from Phase 1. New vocabulary replaces reserved INSTALLER_DOWNLOADED/AGENT_INSTALLED/AGENT_CONFIGURED/HEALTH_VALIDATED with more precise stages; these were never legal Phase 1 transitions. A reconciled rerun can advance through verified stages without mutation; event details record verified-existing vs changed. AGENT_STARTED means required startup state achieved, not necessarily a start command issued. REGISTERED requires qualified registration evidence for the intended identity; credentials existence alone cannot grant it. HARMONY_CONNECTIVITY_VALIDATED requires the full [health gate](health-evidence.md), including authoritative current cloud confirmation.

Any active step may end FAILED/BLOCKED; preserve lastCompletedStage and immutable stateHistory, failureStage, nullable observations and cleanup outcome. Do not overwrite lastCompletedStage with FAILED. Current Phase 1 terminal/validation semantics remain unchanged until a versioned runtime contract is introduced.

## Step contract

| Step | Input | Operation | Output | Error condition/category | Rollback / cleanup | State on success |
| --- | --- | --- | --- | --- | --- | --- |
| Load/validate | Non-secret config, overrides, catalogue/profile | Existing strict parser; explicit v2 and cross-field validation | Validated desired state, digest | CONFIG_INVALID2, VERSION_UNKNOWN12 | No secrets/mutation | CONFIG_VALIDATED then VERSION_RESOLVED |
| Platform | OS/arch/package facts | Exact target match, no family inference | Verified Ubuntu22.04/x64 tuple | Unsupported10 | None | PLATFORM_DETECTED then PLATFORM_VALIDATED |
| Preflight | Desired state, target and provider evidence | Resources/free-space policy, root for mutation, package lock availability, dependency/network/TLS/profile/materialization checks; acquire per-host operation lock; inspect existing state | Bounded action plan, readiness | PREFLIGHT_FAILED11; metadata22; evidence24; lifecycle42 | Release own lock; no package changes | PREFLIGHT_COMPLETE |
| Resolve artifact | Approved or explicit lab-qualified digest/locator | Obtain through artifact provider into private owned staging; bound size/time and redirect destinations | Exact local artifact/provenance | DOWNLOAD_FAILED20 / missing metadata22 | Remove partial owned download | ARTIFACT_RESOLVED |
| Verify artifact | Trusted manifest + bytes | SHA-256 match, metadata/build/architecture, qualifier and provenance checks; no install scripts executed here | Verified package handle/profile | CHECKSUM_FAILED21; evidence24 | Quarantine/delete owned invalid download; never install | ARTIFACT_VERIFIED |
| Install package | Verified package, inspected dependencies/scripts | Reconcile exact installed build; execute qualified noninteractive .deb path only if absent; no implicit upgrade/downgrade | Installed package metadata and service behavior | INSTALLATION_FAILED30; existing incompatible42 | Preserve package/db evidence; do not auto-purge or claim package rollback | PACKAGE_INSTALLED |
| Prepare registration/config | Installed profile, identity metadata, mode, secret references | Verify identity lifecycle; reject proxy/auto; resolve approved secret; create approved temporary input safely; apply only scoped validated settings | Prepared adapter context, mutation record | SECRET_PROVIDER_FAILED41; CONFIGURATION_FAILED40; lifecycle42 | Remove only owned temporary input; restore only backed-up owned config when safe | REGISTRATION_PREPARED |
| Start/submit | Prepared context and baseline logs | Start/restart through qualified vendor service interface, or observe already-running healthy identity; invoke selected adapter in its qualified order | Process/service invocation outcome; deadline starts before action | REGISTRATION_FAILED51 / installation30 as appropriate | Stop only newly initiated failed attempt; preserve pre-existing service/identity | AGENT_STARTED |
| Poll registration | Monotonic deadline, identity, log offsets | Bounded qualified probes and classification; no blind re-registration | Current qualified identity evidence | Auth50; registration51; timeout52 | Halt new attempt, remove transient input, retain product credentials for reconciliation | REGISTRATION_PENDING then REGISTERED |
| Local health | Component profile/observations | Qualified status checks for all required components | Individually sourced service verdicts | HEALTH_CHECK_FAILED60 | Preserve installation; do not restart blindly | LOCAL_HEALTH_VALIDATED |
| Cloud/transport health | Intended identity, qualified provider | Current connectivity and authoritative Harmony status; veto known fatal errors | Current cloud evidence tied to run/identity | HEALTH_CHECK_FAILED60, reason HARMONY_STATUS_UNCONFIRMED when unknown | Preserve evidence and identity; no synthetic success | HARMONY_CONNECTIVITY_VALIDATED |
| Cleanup | Owned transient handles/files, outcome | Ensure pending new registration cannot continue on failure; remove temporary material, clear references, release lock, verify residue absence | Cleanup record | CONFIGURATION_FAILED40 reason CLEANUP_FAILED | Preserve primary error plus secondary cleanup error; block success if cleanup failed | Keep last successful stage |
| Result | Observations, state history, changed record, errors | Validate v2 result, write new atomic0600 file; emit sanitized final JSON; propagate category | Correlated terminal result | RESULT_WRITE_FAILED61; INTERNAL_ERROR99 | No uninstall; caller sees missing result as failure; no raw exception output | COMPLETE only after gates and cleanup, otherwise FAILED/BLOCKED |

Interactive Mode A configures before final service startup; auto mode submits by starting the prepared service; Mode B order comes from qualified package behavior. The common state denotes outcome, not an invented identical command sequence. Package maintainer scripts may auto-start services: qualify how the adapter prevents accidental registration before input is ready. Do not assume DEBIAN_FRONTEND suppresses vendor prompts. Do not run the documented Python2 alternatives step blindly or modify system Python as a shortcut.

## Failure, concurrency and recovery

Hold one owned per-host lock across mutation and final cleanup; distinguish active work from crash residue without killing another process. Package-manager lock waits have deadlines; never delete package-manager locks. Existing different builds need an explicit upgrade/recovery operation, not overwrite. Compare desired digest and approved identity; do not trust a completion marker alone. New request IDs yield new result filenames; the same request cannot replace an earlier result.

Every provider call gets a deadline and sanitized typed error. Preserve changed=true once a mutation occurred, even if later steps fail. Keep a restricted non-secret journal sufficient for recovery; never store secret payloads in it. On cancellation, stop only owned child work, reconcile service state, clean transient material, write failure if possible. On next start inspect crash residue before retrieving secrets. A post-install failure leaves a failed installation to investigate; rollback of package/database/cloud identity is not claimed atomic.

Secret-bearing child output must not pass through directly to logger/stdout/stderr. Validate/adapt before reporting. Immutable evidence identifies executed artifact/config/test profile and timestamps, not secret hashes. Run cleanup before a success verdict; if result writing itself fails, error61 overrides exit success while preserving prior failure details where safe.

## Error compatibility proposal

These are **reason codes** under existing Phase 1 categories, not new numeric exits. No catalogue changes in this phase.

| Proposed reason | Existing error / exit | Retry policy |
| --- | --- | --- |
| ARTIFACT_NOT_FOUND | DOWNLOAD_FAILED /20 | No retry on confirmed missing object; bounded retry only for transient download faults |
| ARTIFACT_HASH_MISMATCH | CHECKSUM_FAILED /21 | Never install/retry as success |
| PACKAGE_INSTALL_FAILED | INSTALLATION_FAILED /30 | Reconcile before any rerun |
| REGISTRATION_CONFIG_FAILED | CONFIGURATION_FAILED /40 | Fix input/profile first |
| SECRET_RESOLUTION_FAILED | SECRET_PROVIDER_FAILED /41 | Only bounded known identity propagation/transport retries |
| EXISTING_IDENTITY_CONFLICT | LIFECYCLE_ACTION_REQUIRED /42 | Explicit owner action |
| REGISTRATION_AUTH_FAILED | HARMONY_AUTH_FAILED /50 | No automatic credential retry |
| REGISTRATION_NETWORK_FAILED | REGISTRATION_FAILED /51 | Bounded polling inside attempt; no outer replay |
| REGISTRATION_TIMEOUT | REGISTRATION_TIMEOUT /52 | No automatic fresh registration |
| CREDENTIALS_FILE_NOT_CREATED | REGISTRATION_TIMEOUT /52 at deadline, or REGISTRATION_FAILED /51 on explicit terminal failure | Do not infer auth failure |
| SERVICE_STATUS_FAILED / CONNECTION_CHECK_FAILED | HEALTH_CHECK_FAILED /60 | Report health failure; no blind restart |
| HARMONY_STATUS_UNCONFIRMED | HEALTH_CHECK_FAILED /60 | Unknown is not false/healthy |
| CLEANUP_FAILED | CONFIGURATION_FAILED /40 | Stop success; controlled remediation |

DOWNLOAD_FAILED currently has retryable=true for the whole category; proposed v2 reason-aware retry policy must narrow permanent 404/denied outcomes and preserve v1 compatibility tests. Existing unknown platform10, preflight11, metadata22, NOT_IMPLEMENTED23, blocked-evidence24, result61 and internal99 remain. Prefer a reason field over renaming stable categories. REGISTRATION_FAILED currently has retryable=false; internal polling is not permission for caller-level replay.

## Phase 2 completion criteria

Implement only qualified adapters and v2 contract after approval; add tests derived from actual package/help and sanitized fixtures; pass all 76 baseline tests plus meaningful new failure/cleanup/idempotency cases. Run IT-001–010 on the approved target. Report automated versus manual evidence separately. Do not claim production readiness from mock tests, local Linux service status or Azure extension success.
