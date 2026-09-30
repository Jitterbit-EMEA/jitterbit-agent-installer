# JBPA project instructions

## JBPA integration boundary

JBPA DOES NOT CREATE VIRTUAL MACHINES. It starts at `VM_ALREADY_PROVISIONED` and owns the Jitterbit Private Agent lifecycle through `JITTERBIT_PRIVATE_AGENT_CONFIGURED_AND_HEALTHY`. External infrastructure AI owns provisioning, OS/network/disk preparation, identity attachment, access and release delivery. Its caller passes an operation and configuration, then consumes the JBPA process exit code and schema-valid result JSON.

External caller tooling must not duplicate PA install, registration, drain, health, uninstall or reinstall logic, and must not parse Jitterbit logs or TranDb. Use first-class `jbpa reinstall` for REINSTALL. Do not expose secret values or bypass release/artifact hashes.

Current immutable QA candidate: JBPA `1.0.0-rc9`; archive SHA-256: `596cba1ee7c6c4ce2468aa3c1d6955a238a0bd63e4a60c27866c22b2587f9231`. The remote caller supports controlled Ubuntu 24.04 amd64 QA only and has offline tests, but no live SSH qualification. PA 12.10.1.1 remains QA_TEST_ONLY / LOCALLY_CALCULATED, not production approved. Ubuntu 22.04 live qualification remains pending. RC3 materials are historical.

Use `/jbpa` for the current `install`, `upgrade`, `uninstall`, `status`, `health`, and `versions` workflow on an already-provisioned named VM. Start with the [current skill and remote caller guide](docs/integrations/skills/README.md); the [RC3 integration kit](docs/integrations/claude-code/README.md) is retained for historical integrations.
