# Azure Key Vault integration

`src/jbpa/azure_identity.py` resolves the registration token from Azure Key Vault with the VM's Managed Identity. The configuration carries a vault URI, optional user-assigned identity client ID, and a secret name/version reference. It carries no token value.

The provider requests a token from the [Azure VM IMDS Managed Identity endpoint](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/how-to-use-vm-token), bypassing HTTP proxies for the link-local request. It then calls the [Key Vault Get Secret API](https://learn.microsoft.com/en-us/rest/api/keyvault/secrets/get-secret/get-secret) over HTTPS. The VM identity needs Key Vault secret read access scoped to the intended vault or secret. No client secret, storage key or Azure username/password is used.

The provider emits only fixed errors: `KEY_VAULT_AUTH_FAILED`, `KEY_VAULT_ACCESS_DENIED`, `KEY_VAULT_SECRET_NOT_FOUND`, `KEY_VAULT_SECRET_EMPTY`, `KEY_VAULT_NETWORK_FAILED`, and `SECRET_PROVIDER_TIMEOUT`. It does not include response bodies or token values in errors. Bootstrap clears its `Secret` wrapper after the attempt. Python strings and HTTP response buffers cannot be guaranteed physically erased from memory; the process is short lived and never persists them except in the native registration input.

The supplied VM's initial read-only IMDS request returned HTTP 400 `invalid_request` because it had no Managed Identity. A later [local Azure CLI access check](../evidence/pa-12.10.1.1/key-vault-access.md) proved local-user access. The VM now has a system-assigned identity with secret-scoped `Key Vault Secrets User` assignments for the seven JBLAB references. A [live VM check](../evidence/pa-12.10.1.1/vm-managed-identity.md) obtained an IMDS token and retrieved all seven nonempty values without printing them. The VM is still Ubuntu 24.04, so this does not satisfy the requested Ubuntu 22.04 regression.

Use this configuration shape:

```yaml
harmony:
  registration:
    strategy: register-json-token
    token_secret_ref: {provider: azure-key-vault, reference: REPLACE_WITH_SECRET_NAME}
secrets:
  provider: azure-key-vault
  vault_uri: https://REPLACE_WITH_VAULT.vault.azure.net
  managed_identity_client_id: null
```

The remaining required fields follow [agent.example.yaml](../config/agent.example.yaml). Place the completed non-secret file at `/etc/jbpa/agent.yaml`, owned by root with restrictive permissions. The token value must remain in Key Vault.

The supplied JBLAB vault is `https://jblab-pa-automated.vault.azure.net/`. Its screenshot shows seven enabled names: `JBLAB-token`, `JBLAB-cloudUrl`, `JBLAB-agentGroupId`, `JBLAB-agentNamePrefix`, `JBLAB-deregisterAgentOnDrainstop`, `JBLAB-retryCount`, and `JBLAB-retryIntervalSeconds`. The [JBLAB reference-only example](../config/agent.jblab.example.yaml) maps these names to bootstrap fields. At runtime, bootstrap retrieves them through Managed Identity, validates their types and config schema, and then follows the existing registration sequence. The qualified path requires `deregisterAgentOnDrainstop=false`, `retryCount=10`, and `retryIntervalSeconds=5`; a different value fails closed until separately qualified. The screenshot establishes names and enabled status only, not values, permissions, reachability, or a working identity.
