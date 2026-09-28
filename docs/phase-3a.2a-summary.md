# Phase 3A.2A Summary

> Phase 3B scope correction: JBPA does not provision VMs. `azure/provisioning` and `bin/jbpa-azure` are NON_PRODUCTION / DEVELOPMENT_TEST_HARNESS / NOT_PART_OF_JBPA_RUNTIME. Historical evidence below is retained. The canonical production boundary is the [external orchestrator contract](external-orchestrator-contract.md); the external tool owns infrastructure.


## Status

Adapter and deployment contract implemented with fake-backed verification. No live Azure deployment is authorized or performed. Existing external VM provisioning agent: EXTERNAL_PROVISIONING_AGENT_NOT_PRESENT in the current repository. Existing delivery wrappers/caller helpers are reused. Decision: BUILT_ADAPTER.

## Architecture and inputs

`azure/provisioning` is an external callable component, invoked by `bin/jbpa-azure`, maintained in the same repository for convenience. It uses one contained Azure CLI backend with explicit subscription and existing authenticated operator/CI/Managed Identity context. It creates Azure infrastructure and delegates product lifecycle to immutable packaged JBPA. It contains no registration markers, service-name health parsing, dpkg workflow or TranDb logic.

Deployment schema 1.0 and a null-only example specify subscription, RG/region/network creation modes, VM/image/size/disk/public key, identity, Key Vault references, release delivery and organization tags. No environment ID, URL, credential or secret value was added to examples. Approved actual config remains external.

## Operations and safety

PLAN: implemented, offline and no control-plane calls/state mutation. PROVISION: implemented for future explicit execution. DEPLOY_JBPA: implemented using CSE hash checks and canonical bootstrap arguments. EXECUTE: combines provision/dispatch. STATUS: read-only Azure status. DESTROY: explicit ownership-checked VM/NIC/disk/public-IP cleanup; shared infrastructure and authorization assignments retained. Cleanup on failure is disabled; last successful stage is preserved.

AZURE_BLOB private MI delivery and approved anonymous HTTP(S) delivery contracts are supported. LOCAL_TEST is planning/testing only and rejected before live provisioning. Sources are supplied/published externally; storage is not silently created. The adapter does not claim that control-plane role checks prove guest Key Vault access. That proof still belongs to live JBPA execution/evidence.

## Release and qualification

rc2 version 1.0.0-rc2, exact SHA-256 `68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da`, unchanged. rc1 also remains historical/unchanged. No archive rebuild occurred. Source release validation now recognizes the deployment example's separate schema; no lifecycle code changed and no new guest payload was built. Packaging the adapter in a future guest release would require a new identity.

PA 12.10.1.1 / Ubuntu 22.04 qualification remains PENDING LIVE TEST. allowUnqualified is supported and explicit. GATE-10 and GATE-13 remain PENDING.

## Validation and next action

The baseline was 252 tests. Added tests cover deployment schema/completeness, existing/create resource modes, identity modes, vault/delivery/hash requirements, no-mutation plans, strict flags, private state, ownership-safe cleanup, error mapping and generic CSE/result handoff. All Azure operations use fakes in this phase. Final counts/checks are recorded in [validation evidence](../evidence/phase-3a.2a/validation.yaml).

See [architecture/contract](azure-provisioning-contract.md) and [required live inputs](runbooks/phase-3a.2-live-inputs.md). Supply the approved non-secret configuration and execute Phase 3A.2B. Real platform/identity/RBAC/CSE/guest behavior remains unverified; no production sizing or artifact promotion is asserted.

## Final outcome

Phase 3A.2A: COMPLETE for adapter/contract preparation. Baseline 252 plus 27 new tests: 279 passed, zero failures. The final affected adapter suite also passed after ownership/result hardening. Ruff/formatting, YAML/Bash syntax, schemas/catalogue/contracts and bounded credential scan passed. ShellCheck/shfmt were unavailable and skipped by existing policy. rc2 archive, sidecar and manifest match the pre-phase snapshot; 79-file payload verification passes. The null-only example's CLI rejection was observed without an Azure call.

PROVISION/EXECUTE/DEPLOY_JBPA/STATUS/DESTROY are implemented and fake-tested, not live-qualified. An existing externally authored agent is still not present; the newly built adapter provides the callable boundary for Phase 3A.2B. No exact environment is invented and no subscription/resource operation was executed.
