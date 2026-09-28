# Azure bootstrap contract

The Azure VM provisioning agent supplies an Ubuntu target VM, a non-secret config path, approved framework and PA artifact digests, a Key Vault reference, and a unique result filename. It invokes `jbpa-bootstrap` through the [Linux Custom Script Extension](https://learn.microsoft.com/en-us/azure/virtual-machines/extensions/custom-script-linux) 2.1 or later. The extension needs `managedIdentity` in protected settings for private Blob `fileUris` and `skipDos2Unix: true` to preserve hashed bytes.

The reviewed [wrapper](../azure/custom-script/bootstrap.sh) verifies its framework bundle SHA-256 before extraction, installs bundled Python wheels offline, and calls [jbpa-bootstrap](../bin/jbpa-bootstrap). The extension command must verify the downloaded wrapper hash before running it, as shown in [settings.example.json](../azure/custom-script/settings.example.json). The framework and PA package have separate versions and separate approved hashes. The [release builder](../scripts/build-release.sh) must run on an approved Linux x86_64 build runner; its output and SHA-256 are reviewed before upload.

Recommended guest layout:

| Path | Owner/mode | Purpose |
| --- | --- | --- |
| `/etc/jbpa/agent.yaml` | root, 0600 | Non-secret config and secret references |
| `/opt/jbpa/releases/<sha256>/` | root, private | Immutable framework release and offline wheels |
| `/var/lib/jbpa/results/<run-id>.json` | root, 0600 | New result per run |
| `/var/log/jbpa/` | root, private | Optional sanitized wrapper diagnostics |
| `/opt/jitterbit/` | product managed | Native Private Agent files |

The bootstrap process validates config, actual OS, support tuple, artifact approval and root privileges before package mutation. It retrieves the token through Managed Identity, executes the native workflow, writes a schema-validated JSON result, and returns its error code. The provisioning agent decides success from the result JSON and process exit code together. It must not parse Jitterbit logs or use the extension's truncated stdout tail as the full result. A separate [Managed Run Command](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command-managed) can retrieve the private result file for diagnostics or recovery after the extension has finished.

The current checkout contains the wrapper and contract, but no callable source for the separately authored VM-provisioning Azure AI Agent. No extension was deployed in this phase. The supplied VM is Ubuntu 24.04 with PA 12.9.2.2 already installed. Its original [preflight](../evidence/pa-12.10.1.1/vm-preflight.json) found no Managed Identity; this was subsequently corrected and [Key Vault access passed](../evidence/pa-12.10.1.1/vm-managed-identity.md).

## RC2 packaged release bootstrap

Canonical positional interface:

```text
release-bootstrap.sh ARCHIVE_OR_HTTPS_URL SHA256 CONFIG RESULT [INSTALL_ROOT] [production|controlled-test] [false|true]
```

`allowUnqualified` maps to the final boolean, defaults false, and accepts only the literal strings `false` and `true`. True requires controlled-test and appends the existing `--allow-unqualified` CLI flag exactly once using a Bash array. No environment toggle or alternate override mechanism was added.

Normal production call (requires existing production approval):

```bash
bash release-bootstrap.sh jbpa-1.0.0-rc2.tar.gz EXPECTED_RC2_SHA256 \
  /etc/jbpa/agent.yaml /var/lib/jbpa/results/UNIQUE_RUN_ID.json /opt/jbpa production false
```

First Ubuntu 22.04 QA qualification:

```bash
bash release-bootstrap.sh jbpa-1.0.0-rc2.tar.gz EXPECTED_RC2_SHA256 \
  /etc/jbpa/agent.yaml /var/lib/jbpa/results/UNIQUE_RUN_ID.json /opt/jbpa controlled-test true
```

Replace the hash placeholder with the independently approved RC2 archive digest. Verify the wrapper hash before executing it. Configure expected OS Ubuntu 22.04, architecture x86_64, unique Phase 3A naming and disabled enterprise branches using the existing schema. This release correction does not supply a VM or approve its sizing/RBAC. Hash verification occurs before extraction; override does not bypass any artifact/security/runtime gates. No default automatic Ubuntu 22.04 qualification or catalogue promotion occurs.

The release now includes `azure/custom-script/release-bootstrap.sh` and the CSE settings example. Extracting the wrapper from an archive requires prior archive integrity verification by the caller; alternatively distribute the independently hash-approved wrapper alongside it.
