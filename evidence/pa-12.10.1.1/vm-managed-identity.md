# VM Managed Identity and Key Vault access

Verified 2026-09-23 on the user-supplied test VM. Secret values and Azure bearer tokens were never printed or saved.

| Item | Observation |
| --- | --- |
| VM | `JBLAB-PA-AUTOMATION`, public IP `52.155.252.81`, subscription `11ce6636-2d4f-4a48-858c-65e7bae48562`, resource group `EMEA` |
| Identity | System-assigned; principal ID `82976168-6d45-4374-8924-7a72759d3d98`; tenant `1c5fe622-80aa-4a4c-adbd-67a1cb87c6ed` |
| Vault | `JBLAB-PA-AUTOMATED`, subscription `6a43fd6b-38d4-403c-9aae-3cb2ff724405`, resource group `PS-LAB`; Azure RBAC enabled |
| Permission | `Key Vault Secrets User` at the individual scope of each of the seven `JBLAB-*` secrets in `config/agent.jblab.example.yaml` |
| Assignment audit | Seven assignments for this principal at the seven intended secret scopes; no vault-scope assignment was created |
| VM IMDS request | HTTP 200; Managed Identity token obtained for `https://vault.azure.net` |
| VM Key Vault Get Secret | All seven names returned nonempty values; only per-name `OK` status was printed |

This verifies that the current Ubuntu 24.04 VM can access the required Key Vault secrets through its own identity. It does not validate the secret values against the qualified registration contract, establish PA 12.10 behavior, or establish Ubuntu 22.04 readiness. The earlier IMDS HTTP 400 preflight occurred before the VM identity was enabled.
