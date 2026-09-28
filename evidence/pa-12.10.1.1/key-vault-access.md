# JBLAB Key Vault access check

Checked 2026-09-23 with the local Azure CLI user session. No secret values were printed, saved, or added to the repository.

| Check | Result |
| --- | --- |
| Azure CLI account session | Signed in to tenant `1c5fe622-80aa-4a4c-adbd-67a1cb87c6ed` |
| Vault name listing | All seven supplied `JBLAB-*` secret names were returned |
| Data-plane Get Secret for `JBLAB-token` | Succeeded; CLI output was restricted to the secret name |
| Data-plane Get Secret for other six | Not attempted |
| VM Managed Identity Get Secret | Subsequently passed for all seven references; see [VM identity evidence](vm-managed-identity.md) |

This establishes local-user access to the registration token and visibility of all supplied names. A later VM identity test established access to all seven values without displaying them; it did not validate the six registration-field values against the qualified runtime contract.
