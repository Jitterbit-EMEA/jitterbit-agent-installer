# Azure integration decision

Status: DESIGNED, not deployed. Decision date: 2026-09-22. DEP-004 PARTIALLY_RESOLVED. Sources: [A01–A14](references.md). Initial target: a persistent Ubuntu 22.04 x86_64 VM, PA 12.10.

## Decision and reconciliation

Recommend **Custom Script Extension 2.1+ as the primary bootstrap candidate**, after VM/identity/network readiness. Keep Managed Run Command for controlled diagnostics, recovery and workflows needing longer timeouts or multiple scripts. Use cloud-init for minimal first-boot prerequisites only. This revises the Phase 0 preference for Managed Run Command because the now-specified deployment model prioritizes native private-Blob acquisition through Managed Identity and an extension-managed bootstrap. It is a project design decision, not a product claim that CSE is universally better.

Phase 0's [Azure proposal](azure-integration.md) remains historical. The actual AI VM-provisioning implementation remains unavailable in the inspected checkout (L02). No hook has been wired. The sibling CLI's VNet-only deploy function is not a VM tool and must not be repurposed silently.

## Decision matrix

| Capability | Custom Script Extension | cloud-init | Run Command |
| --- | --- | --- | --- |
| First boot | Attach during/after deployment; depends on guest agent | Native initial-boot customization | Managed variant can be a deployment resource |
| Post-deployment | Explicit extension update/rerun | Not a normal post-provision lifecycle dispatcher | Strong fit for diagnostics and later lifecycle tasks |
| Managed Identity | Native file download with protected managedIdentity, 2.1+ | Guest SDK/IMDS logic needed; bound readiness waits | Guest SDK/IMDS logic possible; native source identity capability must be checked for selected API, do not copy CSE fields |
| Private Blob | Native authenticated fileUris retrieval | Custom retrieval required | Reviewed Linux guide shows source URI/SAS; approved local dispatcher can retrieve with VM identity |
| Azure CLI | az vm extension set | az vm create --custom-data | Managed: az vm run-command create/show; Action: invoke |
| Retry | No general safe application retry contract; wrapper owns bounded retry | Module behavior varies; wrapper owns retry | Caller/wrapper owns retry and reconciliation |
| Rerun | Change timestamp/settings; same sequence is not a fresh execution | Requires deliberate module/recovery handling; never casually clean all cloud-init state | New/update request under correlation and per-VM lock |
| Troubleshooting | Extension status, handler log, guest stdout/stderr | cloud-init logs/status plus explicit installer result | Managed progress, exit code, instanceView and optional append-blob output |
| Cross-cloud | Azure-specific wrapper | Widely portable Linux bootstrap model | Azure-specific wrapper |
| Timeout | 90-minute script ceiling | No equivalent Azure CSE deadline; installer must impose one | Action 90 minutes; Managed configurable |
| Interactive | Unsupported | Unsuitable | Unsuitable for assisted registration |
| Suitable for PA install | Yes, conditional on noninteractive adapter and bounded runtime | Possible but couples installation to first boot | Managed yes; stronger for long/sequenced work; Action reserved for diagnostics |

Facts: A01 explicitly lists Ubuntu 22.04 x64, idempotency, no input prompts, no in-script reboot, one extension version per VM, no native proxy support, and native MI Blob retrieval. A02/A03 distinguish Action from Managed Run Command. A04 documents first-boot behavior and warns that successful provisioning can precede background completion or conceal script failure. Do not treat VM provisioning success as PA health.

## CSE execution and operating limits

Use publisher `Microsoft.Azure.Extensions`, type `CustomScript`, handler version at least 2.1. `managedIdentity` belongs in protected settings: empty object for the assigned system identity, or explicit client/object ID for a user-assigned identity. Do not combine with storage account keys (A01). Set `skipDos2Unix=true` so hash-pinned downloaded bootstrap bytes are not rewritten before verification.

A12 upstream code executes through `/bin/sh -c` and persists stdout/stderr; it reports a bounded 4 KiB tail per stream in status. Full outputs remain on guest disk. A14's default waagent service has no alternate User and A12's subprocess code does not drop identity: **source-based inference is root execution under the standard guest agent**. Verify effective UID on the chosen image; no live verification has occurred. Treat extension-write permission as privileged code execution.

No guaranteed retry count for a failed user script was established. Upstream sequence checking suppresses already processed settings; changing the rerun token creates another attempt, not rollback. Download retry internals are not treated as an application-level guarantee (the attempted downloader source retrieval was unavailable). Qualify installed handler behavior. Use bounded readiness/download retries; never blindly replay package/registration mutations.

Do not reboot, update or stop waagent inside CSE. Return a reboot-required failure/recovery request; reboot is a separate authorized operation after completion. No background detached installer. Coordinate with cloud-init/package locks and other extensions. CSE's proxy limitation is independent of the Jitterbit registration proxy constraint: a proxy-only bootstrap network needs a qualified alternative acquisition path before deployment.

## Typed integration contract (proposal, not an existing tool)

| Input | Contract |
| --- | --- |
| request/run identity | Schema version, unique runId, target VM resource ID, idempotency key |
| target | Approved image/version and Ubuntu22.04 x64 expectation; guest readiness evidence |
| installer release | Immutable bootstrap/framework artifact locator and independently approved SHA-256 |
| package | Approved catalogue revision, exact build/platform locator and digest |
| configuration | Non-secret configuration locator/digest; explicit selected registration profile |
| secrets | Vault URI, secret names/versions and assigned identity selector only |
| execution policy | Noninteractive mode, bounded deadline/retry, new private result path, request digest/approval reference |
| output transport | Non-secret evidence destination and scoped writer identity, or authorized read-only retrieval path |

Caller obligations: validate target allowlist and fresh authorized plan; provision/verify VM, MI, DNS/egress and required RBAC; wait for guest readiness; serialize bootstrap per VM; dispatch only a reviewed fixed command. Preserve the external repository's fresh deployment-hash approval boundary. Authenticated access does not authorize new deployment.

Guest obligations: verify bootstrap digest **before executing downloaded code**, then verify framework/config/catalogue/package digests and target; reject changed request under the same idempotency key; invoke the portable installer; generate one sanitized result and propagate its exit category. A trusted small verification stub is part of the reviewed dispatch/image boundary. A digest supplied by the downloaded script itself is not that trust boundary.

Output contract: runId, target identity, request/config/artifact digests, framework/schema version, status, stage, lastCompletedStage, installed build, changed, service and registration observations, reason code, start/end timestamps, cleanup status and safe evidence references. Validate result schema and request correlation. Missing/truncated/stale JSON or mismatched exit status fails orchestration. CSE extension status is not the full result: store an atomic private guest result, then transport only sanitized JSON via a separate scoped result sink or read-only retrieval. The 4 KiB status tail is not a reliable full-result transport. No implementation for this transport exists yet.

## Boundary and roles

Azure adapter owns VM identity, Blob retrieval, Key Vault, CSE/cloud-init/Run Command and result transport. The portable Python core owns validation, OS/preflight, package integrity/install, registration selection, configuration, lifecycle and health. Retain Phase 1 provider protocols; add no Azure imports to core lifecycle logic.

Recommend system-assigned MI for the initial single persistent test VM unless the provisioning owner requires a preassigned identity. Give it Storage Blob Data Reader on the approved artifact container (A11), Key Vault Secrets User on a dedicated environment vault (A05), and only a separately scoped result-write permission if that transport is chosen. No publishing, approval or role-assignment rights. Artifact publisher, secret administrator and orchestration caller are separate roles. Restrict arbitrary guest execution because code on the VM can use its identity.

Private endpoints require valid DNS/routes; MI/RBAC propagation is a readiness check with a deadline. Keep secret values out of both public and protected extension settings, custom data, CLI, stdout/stderr and AI requests. Fetch in process. Managed Run Command protected parameters may become guest environment/argv (A03), so they are not the selected Harmony-secret delivery channel either.

## Integration acceptance

Require the actual provisioning source/tool schema and owner review, an existing approved test environment, MI/private Blob/Key Vault access tests, handler UID/version/output checks, repeat-run and timeout evidence, plus a correlated result round trip. No Azure resource was inspected live or modified in Phase 1.5. If the bootstrap cannot reliably fit CSE's bound or needs richer sequencing, revisit Managed Run Command without changing portable installer semantics.
