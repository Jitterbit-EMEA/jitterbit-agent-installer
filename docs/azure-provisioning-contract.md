# Azure provisioning contract — adapter 1.0

> Phase 3B scope correction: JBPA does not provision VMs. `azure/provisioning` and `bin/jbpa-azure` are NON_PRODUCTION / DEVELOPMENT_TEST_HARNESS / NOT_PART_OF_JBPA_RUNTIME. Historical evidence below is retained. The canonical production boundary is the [external orchestrator contract](external-orchestrator-contract.md); the external tool owns infrastructure.


No external VM provisioning agent implementation was found in this repository. Existing `azure/custom-script` wrappers and `azure/integration/consumer.py` provide delivery and caller helpers, not VM creation. Status: EXTERNAL_PROVISIONING_AGENT_NOT_PRESENT; BUILT_ADAPTER. No external repository or endpoint is fabricated.

The new Python component at `azure/provisioning` is external to the JBPA lifecycle engine, callable through `bin/jbpa-azure`. An Azure AI Agent, CLI operator or pipeline can invoke the same interface. It runs on the orchestrator before the guest exists, using Python and the pinned repository requirements. It is not added to, or dependent on installation of, the immutable rc2 guest payload. The payload's manifest/file hashes are checked locally without extracting or executing it.

## Backend decision

A contained Azure CLI argv adapter is the sole control-plane backend. Every call receives an explicit subscription and bounded timeout; raw Azure error text is not emitted. Use an existing authenticated CLI context. Local operators/CI authenticate separately using approved Azure CLI methods; an Azure-hosted runner can establish its context with `az login --identity`. No client secret/password/credential file is implemented.

Bicep would offer declarative deployments and what-if; Terraform would add state/provider management. Both are appropriate for broader infrastructure ownership, but neither is introduced for this scoped VM-and-installer handoff. Azure SDK is another valid typed backend; the current CLI adapter matches existing repository conventions and avoids adding a second resource engine. There is no general infrastructure platform or inferred enterprise policy.

## Configuration

[Schema](../config/schemas/azure-deployment.schema.json), version 1.0, rejects unknown fields and non-boolean flags. [The example](../config/examples/azure-deployment.example.yaml) contains null environment values only. It is schema-valid documentation and intentionally fails complete planning until approved external inputs are supplied. Null is never interpreted as permission to select infrastructure.

Required fields cover subscription, RG create/use-existing, region, VNet/subnet references and explicit creation/CIDRs, VM name/image/size/disk/admin public key, Managed Identity mode/reference, Key Vault resource/secret references, delivery source and exact release hash. Image is fixed to Canonical Jammy 22.04 Gen2; no Ubuntu 24.04 fallback exists. SSH input is a public key file only. Duplicate YAML keys are rejected.

Existing networking is preferred. Creation requires supplied CIDRs, subnet containment and explicit create flags; no CIDR is inferred. Public IP defaults false; optional NSG is supplied by resource ID, with no invented ingress rule. Public-IP creation requires explicit true. A VM/NIC/OS disk is created fresh; collision checks refuse existing VM names and requested new network resource names. Run tags include ownership nonce, managed-by, purpose, JBPA and PA versions. Organization tags cannot override these reserved fields.

Disk has a 50-GiB technical floor; available SKU capabilities must show x64, at least 4 vCPUs and 8 GiB. `qa_sizing_exception` records the declared QA intent and does not bypass these current Ubuntu 22.04 technical floors. No VM size/disk SKU is selected automatically and production sizing is never certified.

## Interface and mutation boundaries

```bash
bin/jbpa-azure plan --config /path/to/approved-azure.yaml
bin/jbpa-azure provision --config /path/to/approved-azure.yaml --plan
bin/jbpa-azure execute --config /path/to/approved-azure.yaml --state-file /private/state/run.json --execute
```

PLAN is offline: schema/completeness/names/dependencies/public-key/guest-config/immutable release validation plus resource and command-family plans. It never calls Azure or creates a state file. Missing environment inputs fail rather than invent a plan. Control-plane authentication/resolvability are explicitly NOT_RUN in offline plans.

PROVISION with `--execute` performs read-only control-plane checks, then creates configured resources and leaves VM_READY. DEPLOY_JBPA (`deploy-jbpa --execute`) requires that same private state and config digest, and performs delivery/dispatch/result retrieval. EXECUTE (`execute --execute`) combines them. Without --execute all three return a local plan. STATUS reads recorded state and queries VM instance status without changing Azure resources. DESTROY defaults to a deletion plan; --execute is a separate deliberate operation.

Keep state directory private (0700), state file owner-only (0600). A new run refuses an existing state filename. State records last stage, resource ownership, identity IDs, generic installer decisions and failure category. It excludes secret values and raw guest results/logs. It is sensitive environment metadata and belongs outside the repository. Partial failures preserve state/resources; there is no automatic retry, resume-by-reprovision, rollback or automatic cleanup.

## Preflight and permissions

Before creation where possible, the adapter checks CLI authentication/subscription, region, VM availability/capabilities, image, existing network/NSG references, Key Vault RBAC mode, user identity, source existence and name collisions. Blob existence uses operator login, not account keys. HTTP HEAD checks availability; HTTPS URLs reject credentials/query strings/fragments, including SAS. LOCAL_TEST is an offline planning/test delivery abstraction and is rejected before live provisioning.

System-assigned principal ID is captured after VM creation. User-assigned principal/client IDs are resolved from the supplied identity. Required roles are checked; missing assignments fail unless the corresponding `grant_permissions` boolean explicitly authorizes `Key Vault Secrets User` at the supplied vault scope or `Storage Blob Data Reader` at the supplied storage/container scope. No broad owner/contributor rights are granted to the VM. Existing equivalent/custom roles and access-policy vaults are conservatively unsupported in this first adapter. RBAC propagation/custom policies must be assessed in the live phase.

Control-plane role evidence does **not** prove guest secret access. The guest uses its identity and Key Vault through packaged JBPA; only completed JBPA execution can confirm configured reference resolution/registration. IMDS and field-specific guest evidence remain required during live qualification. The supplied agent YAML must use the same vault, match the selected identity client ID, target 22.04/x86_64, disable enterprise branches, and use a `jbpa-u2204-` name. A Key Vault name-prefix override is rejected to prevent silently replacing the qualification name.

## Release delivery and invocation

AZURE_BLOB supports pre-existing private storage and CSE Managed Identity downloads. HTTP supports approved anonymous HTTPS endpoints; no SAS is supported. The environment owner publishes exactly three non-secret, approved artifacts: packaged wrapper, rc2 archive, and agent YAML. The adapter verifies the local rc2 archive, bundled wrapper and local guest-config digests; guest CSE checks all three downloaded hashes before execution. It creates private config/run directories, supplies only Python/venv/curl runtime prerequisites with bounded apt lock waits, and invokes the packaged bootstrap. It does not reproduce PA dependencies, dpkg, registration, service checks, log markers or TranDb queries.

`allow_unqualified` is a strict boolean mapped through the existing caller helper to canonical bootstrap argument seven. Controlled-test is explicit for this QA workflow. Results must retain the experimental audit classification when true. JBPA owns PA resolution and all lifecycle/initial-sync health gates. Archive, wrapper/config and PA hash validations remain active.

CSE uses protected settings and skipDos2Unix=true so file hashes remain valid. Private settings are supplied through a temporary 0600 file. The script records the actual bootstrap exit code and private result path even when installation fails. Azure extension success is not treated as JBPA success. A generic chunked Run Command transport retrieves private exit/result files in bounded base64 chunks, avoiding CSE's truncated stdout. Missing/malformed/schema-mismatched/nonzero/incomplete or incorrectly classified results fail; product logs are never parsed by the provisioning layer. Full raw results should be captured through a separate approved evidence workflow during the live run, not committed blindly.

Microsoft documents [CSE Managed Identity and protected settings](https://learn.microsoft.com/en-us/azure/virtual-machines/extensions/custom-script-linux) and [VM Run Command](https://learn.microsoft.com/en-us/cli/azure/vm/run-command). Local Azure CLI help confirmed the implemented CSE/VM/network argument families; no account/resource command was executed in this phase.

## State and errors

States: INITIALIZED, CONFIG_VALIDATED, AZURE_AUTHENTICATED, RESOURCE_GROUP_READY, NETWORK_READY, IDENTITY_READY, VM_PROVISIONING, VM_READY, JBPA_RELEASE_READY, BOOTSTRAP_DISPATCHED, JBPA_RUNNING, JBPA_COMPLETE, PROVISIONING_COMPLETE. IDENTITY_READY records selection; system principal creation is confirmed at VM_READY. Stages describe observed orchestration milestones, not independent proof of product health. Failures preserve `lastSuccessfulStage` and keep resources for inspection.

Stable error categories cover invalid/incomplete config, authentication/subscription, resource group/network/identity/VM/extension, release delivery/hash, execution, missing/invalid result, unsafe/mismatched state, sizing and ownership. The generic result contains schemaVersion 1.0, operation/status/state/history/runId, non-secret Azure references, resource ownership and jbpa exit/decision fields. JBPA status is consumed from its schema 1.0 envelope, not inferred by Azure.

DESTROY verifies all eligible resource ownership tags against the private run nonce before the first deletion, then deletes only run-created VM/NIC/OS disk/public IP resources. Pre-existing resources are never deleted. RGs, VNets/subnets, Key Vault, identities/storage, role assignments and external artifacts are retained even if the run created some infrastructure; their shared status can change later. Partial deletion/timeouts require operator inspection; destroy is not claimed idempotent recovery. Qualifying an agent defaults to leaving it online, with cleanup.on_failure=false.

## Certification boundary

Implementation and unit/fake tests are complete. Authentication, Azure availability/RBAC, network behavior, CSE, result transport and guest installation are NOT_TESTED_LIVE. The next phase must supply [approved live inputs](runbooks/phase-3a.2-live-inputs.md). GATE-10 and GATE-13 remain PENDING. rc2 remains unchanged; shipping the adapter inside a guest release would require a new release identity.
