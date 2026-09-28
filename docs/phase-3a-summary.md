# Phase 3A Summary

> Phase 3B scope correction: JBPA does not provision VMs. `azure/provisioning` and `bin/jbpa-azure` are NON_PRODUCTION / DEVELOPMENT_TEST_HARNESS / NOT_PART_OF_JBPA_RUNTIME. Historical evidence below is retained. The canonical production boundary is the [external orchestrator contract](external-orchestrator-contract.md); the external tool owns infrastructure.


## Status

PARTIAL. Following the user's clarification, this repository prepares a comprehensive packaged installer contract for an AI provisioning agent in a separate project. Caller-side helpers and mock tests are supplied here; live dispatch and Ubuntu 22.04 certification remain unexecuted. No Azure resources or existing QA VM were modified.

## JBPA Release

Version 1.0.0-rc1. Archive `dist/jbpa-1.0.0-rc1.tar.gz` verified locally, including 75 manifest files. Expected and actual SHA-256: `5a18ba2bbc87efdb5a9aa671a1fa6d87575f2446981d00814c27b847efc7eacd`. No rebuild, version bump, packaged source change or archive mutation. New caller helpers, tests and documentation live outside the published package.

## Azure Provisioning Agent

The known infra-master repository implements only VNet/subnet orchestration. The user confirmed the VM provisioning tool is a separate project. Its actual implementation has not been inspected or modified. [The handoff](../azure/integration/README.md) defines responsibilities and optional Python helpers for integration through that project's existing guest execution and result transport. No Azure or Jitterbit lifecycle replacement was created. Jitterbit-specific log parsing outside JBPA: NO.

## Azure VM

No new VM provisioned. OS, version, kernel, architecture, vCPU, memory, disk and resource ID: NOT OBSERVED. Approved resource/network/identity/sizing configuration is required for eventual live execution. Production sizing is not certified.

## Ubuntu 22.04

Target is Ubuntu 22.04 amd64. Qualification remains NOT_TESTED. Preflight has not executed on a guest. First experimental QA requires explicit packaged CLI `--allow-unqualified --controlled-test --non-interactive`; the stock rc1 wrapper does not forward the first flag. This source-inspected dispatch limitation must be resolved through an existing staging extension point or a separately versioned wrapper release before using that path. The existing 2-vCPU exception is scoped to Ubuntu 24.04.

## Managed Identity

Assignment and IMDS token acquisition on a new VM: NOT_RUN. The external project owns identity assignment and role permissions; JBPA owns guest token retrieval.

## Key Vault

Existing vault/reference contract retained. New-VM authentication, secret presence, expected types and formats: NOT_RUN. No secret values acquired or retained during this phase.

## JBPA Deployment

Guest release download, guest hash verification, extraction/installation, configuration placement and bootstrap exit code: NOT_RUN. The caller helpers accept private guest paths and an already verified packaged entry point. They do not themselves deploy or install JBPA. Hash mismatch stops before archive execution when the caller honors `verify_archive`'s decision.

## PA Artifact

Catalogue expectation remains logical 12.10 / package 12.10.1.1 / amd64, SHA-256 `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8`, LOCALLY_CALCULATED / QA_TEST_ONLY. No new guest artifact download or metadata verification. Governance was not promoted.

## Installation

NOT_RUN on Ubuntu 22.04. The separate agent should invoke the packaged install operation, not dpkg or lifecycle commands. No installation duration exists for this phase.

## Registration

New register.json, ownership/mode, automatic registration, credentials.txt, agent ID and group: NOT OBSERVED. The intended new identity uses a unique `jbpa-u2204-` prefix; existing Key Vault field resolution can override the local agent name and must be reconciled before execution. Existing Ubuntu 24.04 agent 646830 was not contacted or modified.

## Harmony Authentication

New guest login: NOT_RUN.

## Agent Services

New guest connection: NOT_RUN.

## Initial Synchronization

NOT_RUN. Initial synchronization remains mandatory under INITIAL_REGISTRATION; no existing-agent relaxed health profile was substituted.

## Local Health

Connection-check, ProcessEngine, Scheduler, FileCleanup, VerboseLogShipper and overall health: NOT_RUN on a new guest. Existing baseline evidence is not new Phase 3A evidence.

## Azure Result Consumption

MOCK-VALIDATED only. `azure/integration/consumer.py` checks process exit plus result schema 1.0, INSTALL operation, exact version tuple, optional expected platform and COMPLETE/service/registration flags. It rejects dry-run/incomplete results, malformed/missing JSON, nonzero exit and timeout. Its returned decision excludes raw transported result data and disables automatic retry. Schema validation alone cannot independently prove health or synchronization; JBPA supplies the composite initial-registration verdict. The external caller has not consumed a live result.

## Runtime Contract

No Ubuntu 22.04 runtime contract created. Actual dependencies, paths, JRE/PostgreSQL, logs, health signatures, services and timings must be captured from a successful new guest. Existing Ubuntu 24.04 files were not copied and relabeled.

## Ubuntu 22.04 vs Ubuntu 24.04

Comparison pending. Ubuntu 24.04 qualification remains the previously recorded baseline, not reverified in this phase. No OS_CONTRACT classification is assigned without Ubuntu 22.04 observations; the comparison document remains absent until supported by actual runtime evidence.

## Production Readiness Gates

GATE-10: PENDING, no Ubuntu 22.04 live regression. GATE-13: PARTIAL, handoff and mock consumer coverage exist; actual external dispatch and result consumption are unverified. Production artifact approval, sizing, organizational approval, release distribution and dependency supply-chain governance remain separate.

## Tests

Previous baseline: 223 passing tests. Added 13 caller unit/mock tests covering success, nonzero exit, missing result, malformed JSON, schema mismatch, timeout, release hash failure, target OS mismatch, dispatch arguments, credential-free delivery references, dry-run rejection, version mismatch and result redaction. See [validation evidence](../evidence/phase-3a/ubuntu-22.04/validation.yaml) for the final current count and checks. Normal tests do not provision Azure resources.

## Remaining Work

Wire the handoff into the separate project's existing provisioning/execution API. Resolve the first-qualification wrapper flag limitation without altering published rc1. Supply approved guest environment and naming configuration, deliver and verify the release on a new Ubuntu 22.04 VM, execute packaged initial install, transport exit code/result and capture the required live evidence and runtime comparison. Mark the run LIVE_AZURE_INTEGRATION explicitly. Leave a successful new agent online for review by default. The current final state is no new agent installed, online, synchronized or healthy; these outcomes remain unobserved.

## Phase 3A.1 resolution

RC2 corrects the bootstrap forwarding limitation with explicit/default-false `allowUnqualified`. Resume the live run using the verified immutable rc2 release in controlled-test mode with the override explicitly true. Earlier rc1 observations above remain historical. GATE-10 and GATE-13 remain PENDING until live evidence exists. See [Phase 3A.1](phase-3a.1-summary.md).

## Phase 3A.2 and 3A.2A progression

Phase 3A.2 stopped before live provisioning because the actual separate agent and approved environment were absent. Phase 3A.2A now supplies an external callable Azure CLI adapter, deployment schema and [live input contract](runbooks/phase-3a.2-live-inputs.md). [Adapter summary](phase-3a.2a-summary.md) documents unit/fake status; Phase 3A.2B is the future live execution. GATE-10 and GATE-13 remain PENDING, with no source promotion or rc2 mutation.

## Phase 3A.2B live-input gate

[Phase 3A.2B](phase-3a.2b-summary.md) remains PARTIAL: no approved environment configuration was supplied. Immutable rc2 verification passed locally; the placeholder example is correctly rejected as incomplete. No Azure mutation or qualification promotion occurred. GATE-10 and GATE-13 remain PENDING.
