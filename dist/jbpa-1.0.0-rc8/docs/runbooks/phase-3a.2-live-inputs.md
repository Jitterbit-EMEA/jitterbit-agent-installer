# Phase 3A.2B approved live inputs

Supply one external non-secret deployment YAML conforming to the schema (source repository). Start from the null-only example (source repository). Do not send secret values, private keys, access tokens, account keys or SAS URLs.

Required inputs:

- Subscription ID and approved provisioning identity with an existing Azure CLI context (operator/CI or Azure Managed Identity).
- Resource-group name and explicit create/use-existing choice; region.
- Network resource-group, VNet/subnet names and create/use-existing flags. Creation requires approved VNet/subnet CIDRs; existing VNet with new subnet requires the approved subnet CIDR.
- New VM name, approved VM size, explicit OS disk size (minimum 50 GiB) and SKU. VM capability minimum is 4 vCPUs/8 GiB/x64. QA intent is separate from production sizing.
- Admin username and a local public SSH key file. No private key/password is accepted. Access can use Azure Run Command without a public IP.
- Identity type SYSTEM_ASSIGNED or USER_ASSIGNED; existing resource ID for user-assigned identity.
- RBAC-enabled Key Vault resource ID and required secret names/references. Confirm the correct vault and selected identity are reflected in the guest agent YAML.
- Existing private storage account/container and archive/wrapper/config blob names, plus role scope; or approved anonymous HTTPS URLs for all three. Publish the exact rc2 wrapper/archive and non-secret guest YAML before execution. No storage account/container is automatically created.
- Local path to immutable rc2 archive and local non-secret agent YAML. Expected digest: `68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da`.
- Provisioner permissions to query/create configured resources and invoke CSE/Run Command. If role grants are requested, explicit booleans and rights to create the two narrowly scoped reader assignments; otherwise preassign them, including storage access needed before CSE download.

Guest YAML must follow the existing agent schema: PA 12.10, Ubuntu 22.04/x86_64, unique `jbpa-u2204-` name, token and other registration references from Key Vault, no Key Vault name-prefix override, and proxy/truststore/SSH/SSL disabled. No relaxed existing-agent profile replaces initial-registration health. This qualification run uses jbpa.allow_unqualified=true.

Optional supported inputs: existing NSG resource ID, explicit public_ip (default false), availability zone, organization tags and QA-sizing declaration. Private static IP, diagnostic storage and Log Analytics are future extension points, not implemented or mandatory. Preserve existing enterprise connectivity policies; the adapter does not invent NSG rules or firewall allowances.

Connectivity prerequisites: Azure control-plane APIs from the runner; guest Azure VM Agent/CSE and Run Command; IMDS link-local endpoint; Key Vault HTTPS and correct DNS/private-endpoint routes; private release Blob HTTPS; Ubuntu package repositories and approved Python dependency index; Jitterbit artifact HTTPS; Harmony/Agent Services HTTPS destinations for the selected cloud. Confirm precise cloud-specific endpoints and proxy/firewall policies with the environment owner rather than guessing them.

```bash
bin/jbpa-azure provision --config /path/to/approved-azure.yaml --plan
# Only in Phase 3A.2B, after the environment is approved:
bin/jbpa-azure execute --config /path/to/approved-azure.yaml \
  --state-file /path/to/private-state/new-run.json --execute
bin/jbpa-azure status --config /path/to/approved-azure.yaml \
  --state-file /path/to/private-state/new-run.json
```

Create the state directory with mode 0700 outside the repository. Preserve state on failure, review the last stage and capture actual live evidence. Do not blindly reprovision/restart. Never reuse the existing Ubuntu 24.04 QA VM/agent 646830. Leave a successful new agent online for review. GATE-13 needs real provisioning, packaged dispatch and generic result consumption; GATE-10 additionally needs the complete Ubuntu 22.04 initial-registration runtime evidence. Source promotion requires success/review, and the promoted catalogue must ship in a new release identity; rc2 stays immutable.
