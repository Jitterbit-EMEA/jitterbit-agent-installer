# Azure reference handoff helpers

The canonical transport-independent boundary is the [external orchestrator contract](../../docs/external-orchestrator-contract.md). JBPA does not provision VMs; infrastructure is external. These Azure-specific helpers are reference tooling, not part of the product runtime.

These optional caller-side Python helpers are maintained separately from the immutable JBPA release. They do not provision resources or implement PA lifecycle logic. The external project can import them, or implement the same documented contract in its own language. Python dependencies are the existing pinned `requirements.txt`; `consumer.py` does not import JBPA source.

1. Provision an approved fresh Ubuntu 22.04 amd64 VM, assign Managed Identity and grant the required Key Vault secret-read and private Blob-read permissions. Prepare Python 3.10+ with venv and approved dependency-index access.
2. Deliver the approved wrapper, immutable archive and non-secret agent YAML. Use CSE Managed Identity artifact references where supported; `delivery_references` returns reference fields only, not a complete extension deployment. The separate project owns resource IDs, file placement, wrapper hash, command quoting, guest execution, timeout handling and result transport.
3. Verify the guest archive hash **before** extracting or executing anything: `68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da`. `verify_archive` returns `JBPA_RELEASE_HASH_MISMATCH` on mismatch; the caller must stop. Local verification does not establish guest verification.
4. Use the packaged JBPA entry point with private, unique config/result paths. `install_arguments` constructs an argv list for an already verified installed release. The caller must transport the process exit code and result file, not infer success from CSE provisioning status alone. Never blindly retry a timed-out installation: remote mutation may still be running.
5. Pass the exact packaged `config/schemas/rc-result.schema.json`, exit code, result text and expected platform into `consume_install`. It accepts only schema 1.0 INSTALL completion for JBPA rc2 / PA logical 12.10 / package 12.10.1.1, with complete service and registration flags. Its output excludes raw result text. It does not parse Jitterbit logs or claim independent proof of synchronization; JBPA's initial registration operation owns those checks.

```python
from azure.integration.consumer import consume_install, install_arguments

argv = install_arguments(
    "/opt/jbpa/releases/<verified-release-hash>/bin/jbpa",
    "/etc/jbpa/agent.yaml",
    "/var/lib/jbpa/results/<unique-run-id>.json",
    controlled_test=True,
    allow_unqualified=True,
)
# The external project's existing guest execution and transport methods run argv.
# decision = consume_install(exit_code, transported_json, packaged_schema,
#     expected_platform={"os": "ubuntu", "version": "22.04", "architecture": "x86_64"})
```

## First Ubuntu 22.04 qualification constraint

Ubuntu 22.04 is currently unqualified. RC2 supports one canonical bootstrap interface: seventh positional argument `false|true`, default false. The external request field is `allowUnqualified` (strict boolean). Call `bootstrap_arguments(..., controlled_test=True, allowUnqualified=True)` for the first QA run. It maps to `/opt/jbpa controlled-test true` after the archive/hash/config/result arguments. The wrapper appends the existing `--allow-unqualified` flag exactly once. False and absence omit it. True never bypasses hashes, metadata, architecture, OS/config/security or lifecycle gates. Immutable rc1 keeps its historical limitation; resume Phase 3A using rc2.

Use the existing YAML/schema and catalogue rather than the conceptual YAML in the phase brief. Set `agent.expected_os.version` to `22.04`, architecture to `x86_64`, and all optional enterprise features disabled. Registration field references can override the configured agent name: ensure the existing naming policy actually resolves to a unique `jbpa-u2204-` identity, rather than reusing the current Key Vault prefix. Keep all token values inside the VM's Managed Identity/Key Vault flow. The approved VM sizing is still required; the existing 2-vCPU QA exception is scoped to Ubuntu 24.04 and does not apply to Ubuntu 22.04.

## Validation status

The caller helpers have unit/mock coverage only. They are not included in rc1's 75-file bundle, are not wired to the separate agent, and do not establish `LIVE_AZURE_INTEGRATION`. Normal tests create no Azure resources. Real dispatch, guest release verification, exact agent identity, mandatory initial sync and runtime capture remain required before GATE-10 or GATE-13 passes.
