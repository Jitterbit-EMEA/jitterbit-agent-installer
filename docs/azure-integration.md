# Azure integration proposal

> Phase 3B scope correction: JBPA does not provision VMs. `azure/provisioning` and `bin/jbpa-azure` are NON_PRODUCTION / DEVELOPMENT_TEST_HARNESS / NOT_PART_OF_JBPA_RUNTIME. Historical evidence below is retained. The canonical production boundary is the [external orchestrator contract](external-orchestrator-contract.md); the external tool owns infrastructure.


> Phase 1.5 addendum (2026-09-22): historical Phase 0/1 content below is preserved. Current readiness and reconciled decisions are in the [Phase 1.5 summary](phase-1.5-summary.md), [dependency register](dependencies.md) and [Phase 2 specification](phase-2-implementation-spec.md). Runtime code/schemas remain Phase 1.
> The current primary bootstrap candidate is CSE2.1+; see the [Azure integration decision](azure-integration-decision.md) for why this revises the earlier Managed Run Command preference.

## Existing implementation: verified boundary

**VERIFIED — local evidence L01/L02:** this project began empty. The adjacent `AI Engineer - MS Azure` checkout contains the infrastructure design and the nested `infra-master` CLI. Its only Bicep template creates a VNet/subnet; `scripts/azure-ai-hello-world.sh` uses `az deployment group create` in `deploy()` after validating a plan hash, and `verify()` checks the VNet. No VM, identity, Key Vault, bootstrap or hosted agent code was found in the checkout's file inventory. Source inspection is not a claim about what may exist in deployed Azure or another branch.

The user confirms this is the same repository and another person built the actual agent. **REQUIRES CONFIRMATION:** obtain that person's implementation path/branch or deployed tool contract. The wider `azure-ai-engineer-solution.md` proposes typed Foundry tools backed by Functions/Durable Functions, but is a design document. Do not treat it as implemented code.

**DESIGN:** integrate after the real VM provisioning tool has independently verified VM identity, OS image, power state, guest-agent readiness, networking and identity assignment. Do not insert Jitterbit installation into the existing VNet-only `deploy()` function. If that demo is extended later, its cost model, resource allowlist, Bicep, typed plan and approval digest must all be extended together. Preserve the existing fresh-plan approval requirement; historical approval hashes cannot authorize new resources.

## Execution mechanism decision

| Mechanism | Verified behavior | Proposed role |
| --- | --- | --- |
| Managed Run Command | ARM resource, configurable timeout, progress and exit status, output Blob support; Linux Guest Agent >=2.4.0.2 (A02/A03). | Preferred explicit post-provision execution and later diagnostics. |
| Custom Script Extension v2 | Managed Identity artifact downloads, 90-minute execution limit, noninteractive/idempotent scripts required, no native proxy support (A01). | Alternative when installation must participate directly in VM extension provisioning. |
| Action Run Command | 90-minute limit and limited output; less progress support than managed commands (A02). | Bounded operational recovery, not the primary bootstrap workflow. |
| cloud-init | Initial Linux customization on supported images (A04). | Prepare minimal dependencies/trust/runner; defer secret-bearing registration until identity/network readiness. |
| Deployment scripts / other extensions | No product-specific integration validated in this phase. | May orchestrate Azure operations, but do not themselves establish guest installation or Harmony readiness. |

**REASONABLE ENGINEERING DESIGN:** Managed Run Command fits an AI-driven workflow with explicit retry, timeout and result inspection. Azure invocation success is not installer success: inspect instanceView execution state and guest exit code, then validate the result schema and run correlation. If the guest returns no result, report an orchestration failure. Do not detach a background installation and immediately return success.

Use a fixed guest entry point with a non-secret request manifest containing runId, VM resource ID, artifact URI/digest, configuration URI/digest and selected version. The published runner retrieves the immutable release from private Blob Storage using the VM identity, validates it, then invokes the portable installer. Script acquisition for Managed Run Command is a separate design decision from in-script Blob access; do not assume Custom Script Extension's managedIdentity property exists on another API. Avoid SAS where a supported identity flow works; if unavoidable, use short-lived scoped SAS handled as a secret.

## Git, Blob and Key Vault

**DESIGN:** Git owns reviewed code, schemas, references, approved catalogues and non-secret examples. CI builds a versioned release archive and trusted digest. Private Blob Storage distributes it to VMs. Pin both release and config; never execute a mutable branch download or `curl | bash`. Direct pinned Git retrieval is acceptable for assisted development only after provenance checks, but private Git auth adds another credential boundary.

Blob versioning and private endpoints are recommended controls, subject to the actual storage design. Private endpoint DNS/routing and package/Harmony egress must be tested from the guest; a private Storage endpoint does not create private connectivity to Harmony.

**VERIFIED — A05/A06:** Managed Identity permits VM access to Azure resources. Key Vault's control and data planes are separate; Key Vault Secrets User reads secret contents. **DESIGN:** use a dedicated application/environment vault and grant only required secret access. The VM reads approved artifacts; publishing uses a separate identity. The Azure orchestration identity can dispatch the approved command but should not retrieve Harmony secrets. Because guest code can use VM identity, restrict who can modify scripts or invoke arbitrary commands. Do not give the VM role-assignment rights.

Resolve tokens in process; do not pass them in CLI arguments, shell debug output or extension parameters. The Phase 3 provider can use an SDK/HTTP client so Authorization headers stay out of process arguments. No Key Vault secret payloads or signed URLs go to AI tool transcripts. Bound retries for identity/RBAC propagation and network failures; repeated authentication rejection is not a transient retry policy.

## Handoff and outcome

1. Infrastructure tool verifies the intended VM and allowed Ubuntu 22.04 x86_64 image, not just a user-supplied hostname.
2. Check identity, approved dependencies and outbound routes; serialize bootstrap per VM.
3. Dispatch approved artifact/config digests and correlation ID through a typed tool.
4. Guest validates and reconciles desired state; all vendor-specific actions remain portable.
5. Collect sanitized JSON and process exit code. Keep larger restricted evidence outside the short status output.
6. Report COMPLETE only after package/config, component health and current Harmony registration are verified; otherwise retain the VM and failure evidence for controlled recovery.

No Application Gateway, public IP or inbound SSH is proposed solely for bootstrap. Add workload/API ingress only when its requirements are supplied. Fleet orchestration should limit concurrency and preserve one identity per VM; no cloning of registered images.

**Not tested:** Azure dispatch, private Blob download, Key Vault retrieval, registration-token compatibility, network policies and result collection. No deployment template or execution script is supplied in Phase 0.
