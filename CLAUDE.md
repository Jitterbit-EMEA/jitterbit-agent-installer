# JBPA project instructions

## JBPA integration boundary

JBPA DOES NOT CREATE VIRTUAL MACHINES. It starts at `VM_ALREADY_PROVISIONED` and owns the Jitterbit Private Agent lifecycle through `JITTERBIT_PRIVATE_AGENT_CONFIGURED_AND_HEALTHY`. External infrastructure AI owns provisioning, OS/network/disk preparation, identity attachment, access and release delivery. Its caller passes an operation and configuration, then consumes the JBPA process exit code and schema-valid result JSON.

External caller tooling must not duplicate PA install, registration, drain, health, uninstall or reinstall logic, and must not parse Jitterbit logs or TranDb. Use first-class `jbpa reinstall` for REINSTALL. Do not expose secret values or bypass release/artifact hashes.

Current immutable JBPA release: `1.0.0-rc3`; archive SHA-256: `4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e`. PA 12.10.1.1 artifact remains QA_TEST_ONLY / LOCALLY_CALCULATED, not production approved. Ubuntu 22.04 live qualification remains pending.

Use `/jbpa <install|reinstall|uninstall|health|diagnostics|validate>` for the operating workflow. Start with the [integration kit](docs/integrations/claude-code/README.md); keep detailed procedures in the skill and runbooks.
