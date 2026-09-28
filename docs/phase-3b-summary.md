# Phase 3B Summary

## Status

PARTIAL. Architecture correction, canonical contract, external request schema and LOCAL/mock handoff harness are implemented. Standalone REINSTALL and complete structured host preflight remain open; they are documented rather than advertised as working RC2 capabilities. No live host execution, provisioning or qualification occurred.

## Corrected Product Scope

VM provisioning: OUTSIDE_JBPA_SCOPE. PA lifecycle: JBPA. Infrastructure ownership: EXTERNAL_ORCHESTRATOR. JBPA does not provision VMs. It starts from VM_ALREADY_PROVISIONED and the successful install target is JITTERBIT_PRIVATE_AGENT_CONFIGURED_AND_HEALTHY.

## External AI Orchestrator Boundary

PRE_PROVISIONED_HOST → JBPA_HANDOFF → JBPA_EXECUTION → JBPA_RESULT. Caller creates/prepares host, identity, access, egress and delivery; JBPA owns all PA lifecycle/log interpretation. See [canonical contract](external-orchestrator-contract.md).

## Pre-Provisioned Host Contract

[Host contract](pre-provisioned-host-contract.md) defines Linux/architecture, capacity, privilege, package manager, DNS/time/egress, secret-provider access and existing-state requirements. Existing actual OS/architecture/resource and native lifecycle gates remain unchanged. Dedicated package-lock/repository, DNS/time and package-specific free-space preflight coverage remains incomplete; no unknown check is promoted to PASS.

## Handoff Request

External schema 1.0 at `tools/handoff/request.schema.json`, excluded from runtime. Target, operation, JBPA release, PA version, guest config/result paths and explicit allowUnqualified are required. Optional controlledTest and callerMetadata carry no secret values. Subscription/resource group/network/region/SKU/disk infrastructure fields are not required. Secret references live in existing agent config.

## JBPA Invocation

Existing commands retained for INSTALL, HEALTH, DIAGNOSTICS, ENTERPRISE_CONFIGURE, UNINSTALL and ARTIFACT_VERIFY. REINSTALL is declared but explicitly rejected before dispatch because RC2 lacks that standalone command. The caller does not compose a new product lifecycle. Enterprise mapping includes required expectedIdentity agent/group IDs and names.

Qualification INSTALL forwards --controlled-test and --allow-unqualified exactly once. Default override is false; true must be explicit and controlled. No qualification promotion occurs.

## Structured Result Contract

RC schema 1.0 preserved byte-for-byte. Generic caller consumes exit code, schema, matching operation/release, status, category, state and retryability. Safe decisions omit raw results/error text. Caller never parses vendor logs or TranDb. Integration failures are separated from JBPA failure categories. A transport-level success is not evidence of completed install qualification by itself.

## Transport Model

LOCAL implemented against an already delivered/installed release. CI remote mock uses the same execute/retrieve contract. SSH and Azure-specific handoff transports are NOT_IMPLEMENTED; the contract supports external implementations without cloud-specific install inputs. Caller verifies immutable archive and installed file hashes before local invocation, rejects existing result destinations and retrieves bounded JSON. No delivery agent is claimed.

## Azure Reference Adapter

`azure/provisioning` / `bin/jbpa-azure`: DEVELOPMENT_TEST_HARNESS, NON_PRODUCTION, NOT_PART_OF_JBPA_RUNTIME. Paths retained to avoid disruption to existing tests and historical evidence. README, architecture, Azure integration/contracts, release notes, production readiness and Phase 3A summaries now state the corrected boundary.

## Release Packaging Impact

RC2 already excludes `azure/provisioning`, `azure/integration`, `bin/jbpa-azure`, tests and historical evidence. It includes only the minimal acquisition/install bootstrap under Azure paths. New external tools/schema/launcher are likewise outside the runtime packaging allowlist. No runtime module, result schema, bootstrap or RC2 file is changed. Existing immutable RC2 remains valid for the next INSTALL qualification; its older documentation does not supersede the current canonical contract.

RC2: 1.0.0-rc2, SHA-256 `68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da`. Archive, sidecar and manifest are preserved. No rebuild and no rc3 produced. Closing standalone REINSTALL and full preflight gaps would require runtime changes and a new release, not an RC2 overwrite. Future packaging of revised docs/config must also use a new release identity.

## GATE-13 Reclassification

Old Azure provisioning-agent gate RENAMED to External AI Orchestrator → JBPA Handoff. PENDING LIVE TEST. A separately controlled caller must execute JBPA on a provisioned host, receive deterministic exit/schema-valid result and leave all product lifecycle interpretation to JBPA. Infrastructure creation is outside scope.

## Ubuntu 22.04 Qualification Plan

Target PA 12.10.1.1 + Ubuntu 22.04 amd64; requested logical 12.10. External workflow supplies one host with root/sudo, sufficient resources, identity/secrets/egress and RC2/config delivery. Only target and execution mechanism plus agent inputs are needed, not an Azure deployment specification. First run uses explicit allowUnqualified=true/controlledTest=true. Expected PA SHA `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8` remains QA_TEST_ONLY / LOCALLY_CALCULATED. GATE-10 remains PENDING. Existing Ubuntu 24.04 agent untouched.

## Tests

Previous baseline 279; current 307 passed, 0 failed (28 new). Lint, schemas, Markdown links, bounded credential scan and source validation PASS; optional ShellCheck/shfmt skipped because unavailable. Added focused handoff tests for request/target/cloud independence, argv and override policy, operation capability rejection, process exits, missing/malformed/mismatched results, LOCAL retrieval, mock remote boundary and RC2 digest/installed-file verification. Final counts and scans are recorded in [validation evidence](../evidence/phase-3b/validation.json).

## Remaining Work

Implement and verify standalone on-host REINSTALL. Add comprehensive structured host readiness probes without weakening existing lifecycle gates; ship any runtime changes as rc3. These are implementation work, not missing user approvals.

Then use a supplied pre-provisioned Ubuntu 22.04 amd64 host and separately controlled external execution tool for actual RC2 INSTALL qualification. No host was supplied in this brief; no live test is claimed. Complete GATE-10/GATE-13 from real evidence only.

SSH/SFTP remains DEFERRED_NO_TEST_MATERIAL; SSL CLIENT CERT remains DEFERRED_NO_PRIVATE_KEY_OR_MTLS_ENDPOINT; PROXY remains DEFERRED_NO_PROXY_TEST_ENVIRONMENT; true custom CA remains not live tested; Harmony deletion remains PENDING. No production approval is asserted.
