# Phase 3A.2B Summary

## Status

PARTIAL. BLOCKED_MISSING_APPROVED_CONFIG. The live brief supplied no approved non-secret environment YAML or path. Only the null-only repository example exists among the deployment configuration files inspected. No Azure authentication, resource query, provisioning, extension/guest command, SSH substitution or destruction occurred. Missing input is classified AZURE_CONFIG_INVALID for this phase; the existing adapter reports AZURE_CONFIG_INCOMPLETE for the placeholder example. No runtime provisioning failure is inferred.

## Live Environment

Not supplied. Required missing fields:

- azure.subscription_id
- azure.resource_group.name
- azure.region
- azure.network.resource_group
- azure.network.vnet.name
- azure.network.subnet.name
- azure.vm.name
- azure.vm.size
- azure.vm.os_disk.size_gb
- azure.vm.os_disk.sku
- azure.vm.admin.username
- azure.vm.admin.ssh_public_key_file
- azure.identity.type
- azure.key_vault.resource_id
- azure.key_vault.secret_references
- azure.release_delivery.type
- azure.release_delivery.jbpa_sha256
- azure.release_delivery.local_archive
- azure.release_delivery.local_agent_config

Conditional inputs: user identity resource ID for USER_ASSIGNED; approved CIDRs for requested network creation; storage account/container/archive/wrapper/config blobs and reader role scope for AZURE_BLOB; three approved anonymous HTTPS URLs for HTTP. Existing example booleans/tags are documentation defaults and are not approved live choices. Public-IP policy, create/use-existing flags, tags and permission-grant policy must be confirmed in the actual config. No secret values are requested.

## Plan

CLI syntax confirmed with `bin/jbpa-azure --help`. The implemented operations are lowercase. Example schema validation passes, but example completeness fails; its offline plan returns exit 1 / AZURE_CONFIG_INCOMPLETE. This is not PLAN=PASS for a live environment. The current adapter's PLAN is offline; authenticated Azure preflight normally runs at the beginning of explicit execution. Before any live mutation, this brief additionally requires read-only Azure preflight of the approved environment and ownership review. Neither can occur without that environment.

## Azure Provisioning

NOT_RUN. No subscription, resource group, region, VNet/subnet, NIC, public IP, VM or extension was selected or created.

## Resource Ownership

No live resource ownership observation exists. Intended PRE_EXISTING/TO_BE_CREATED ownership must come from an approved plan and Azure queries. No ownership file is fabricated from placeholder values.

## Ubuntu 22.04 VM

NOT_CREATED. Name, resource ID, image actually used, OS/version/kernel/architecture, SKU, vCPU/memory and disk facts: NOT_OBSERVED.

## Managed Identity

Type/assignment/IMDS: NOT_RUN. No token acquisition attempted or captured.

## Key Vault

Authentication and required reference presence/type/shape validation on a new guest: NOT_RUN. No secret values retrieved.

## RC2 Delivery

NOT_RUN on a guest. Archive remains the qualification payload, not rebuilt from current source.

## RC2 Verification

Local archive, sidecar and manifest preserve the pre-phase digests. RC2_IMMUTABILITY=PASS, version 1.0.0-rc2; expected/actual archive SHA-256 `68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da`. Release verification passed for 79 files. Guest hash, guest manifest and guest CLI version: NOT_RUN. Historical rc1 remains untouched.

## Qualification Override

Intended live request: explicit allowUnqualified=true for PA 12.10.1.1 / Ubuntu 22.04 amd64. It has not been dispatched, so forwarding count, override usage and actual execution classification are NOT_OBSERVED. Local/mock forwarding tests are not live evidence. No tuple qualification is promoted.

## PA Artifact

Catalogue expectation: request 12.10, package 12.10.1.1, jitterbit-agent/amd64, SHA-256 `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8`. Guest resolution/download/actual hash/DEB metadata/dependencies: NOT_RUN. Artifact classification stays QA_TEST_ONLY / LOCALLY_CALCULATED.

## Installation

NOT_RUN. No new PA installed and no install duration observed.

## Registration

Credentials-before/after, register.json ownership/group/mode, restart count, auto-registration, new Agent ID/group/display name: NOT_OBSERVED. No credential/register contents inspected. Existing Ubuntu 24.04 agent 646830 was not contacted or mutated.

## Harmony Authentication

NOT_RUN.

## Agent Services

Connection/request flow/heartbeat: NOT_RUN.

## Initial Synchronization

NOT_RUN. INITIAL_REGISTRATION still requires fresh initial synchronization; no relaxed profile was substituted.

## Health

ProcessEngine/Scheduler/FileCleanup/VerboseLogShipper/all-services, connection-check Harmony/Apache/Tomcat, supplementary service-status and overall health: NOT_RUN on a new guest.

## Azure Result Consumption

JBPA exit code/result/schema/adapter consumption: NOT_OBSERVED. No raw vendor log parsing or manual guest execution occurred. Unit/mock coverage does not close GATE-13.

## Runtime Contract

No Ubuntu 22.04 contract generated because no runtime observations exist.

## Ubuntu 22.04 vs Ubuntu 24.04

Comparison and OS contract classification remain pending. A missing run is not labelled OS_REGRESSION_FAILED. The existing Ubuntu 24.04 baseline is retained without a new live check.

## Qualification Promotion

NOT_PROMOTED. Source and immutable rc2 catalogue remain unchanged. If future live qualification passes, source promotion must be restricted to the exact tuple and shipped in a new release identity, such as rc3. No next release was built here.

## Production Gates

GATE-10: PENDING. GATE-13: PENDING. Local preparation does not satisfy live acceptance criteria.

## Tests

Previous baseline: 279. Final local validation results are recorded in [validation evidence](../evidence/phase-3a.2b/ubuntu-22.04/validation.yaml). No new runtime contract behavior was observed, so no speculative promotion tests or unrelated features were added.

## Final Azure State

No new VM/agent exists from this phase. Installed/online/synchronized/healthy/preserved target: NOT_APPLICABLE / NOT_OBSERVED. No manual recovery or DESTROY occurred.

## Remaining Production Work

Supply the approved external YAML and complete read-only environment/ownership planning before explicit execution. Use the existing [live-input runbook](runbooks/phase-3a.2-live-inputs.md) and adapter. Then capture the actual Azure/guest evidence, strict initial health and OS comparison. Separate production work remains artifact approval, production sizing/governance, true custom CA, SSH/SFTP, SSL client certificate, proxy, Harmony-side deletion and next release identity. No production status is promoted by this preparation.
