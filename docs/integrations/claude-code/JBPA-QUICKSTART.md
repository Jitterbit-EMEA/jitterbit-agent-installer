# JBPA quickstart

**JBPA DOES NOT CREATE VIRTUAL MACHINES.** Start with `VM_ALREADY_PROVISIONED`; use your infrastructure tool for the VM, network, OS, storage, identity and access. Claude Code belongs on the engineer/orchestrator machine, never on the PA host merely to run JBPA.

1. Provision an appropriate Linux VM with your infrastructure tool. Establish approved remote execution, outbound access and, for Azure Key Vault, a Managed Identity with secret-read permission.
2. Make the immutable RC3 archive available to the host. Verify `sha256sum jbpa-1.0.0-rc3.tar.gz` equals `4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e` **before extraction or execution**. Stop with `JBPA_RELEASE_HASH_MISMATCH` otherwise.
3. Deliver an `agent.yaml` derived from the [actual RC3 schema example](../../../examples/agent.install.example.yaml). Replace example vault/secret references; do not embed secret values.
4. Prepare the verified release's Python environment and private result directory as described in the [operator runbook](JBPA-OPERATOR-RUNBOOK.md#release-verification-and-deployment). The established RC3 installed executable for bootstrap/SSH delivery is `/opt/jbpa/releases/<approved-archive-sha256>/bin/jbpa`, not `/opt/jbpa/bin/jbpa`.
5. Run canonical host readiness: `sudo /opt/jbpa/releases/<sha>/bin/jbpa validate --config /etc/jbpa/agent.yaml --version 12.10 --profile INSTALL --result-file /var/lib/jbpa/results/validate-new.json`. Replace `<sha>` with the full approved digest. Require preflight PASS or PASS_WITH_WARNINGS with no blocking unresolved checks and the expected clean host state.
6. Run INSTALL: `sudo /opt/jbpa/releases/<sha>/bin/jbpa install --config /etc/jbpa/agent.yaml --version 12.10 --non-interactive --result-file /var/lib/jbpa/results/install-new.json`. For an explicitly authorized **controlled Ubuntu 22.04 qualification**, add both `--controlled-test --allow-unqualified`; these flags do not waive artifact or host checks.
7. Wait for completion and retrieve the fresh `result.json`. Validate [schema 1.0](../../../config/schemas/rc-result.schema.json) and require exit `0`, `operation=INSTALL`, `versions.jbpa=1.0.0-rc3`, `status=SUCCESS`, `category=SUCCESS`, and `error=null`.
8. Preserve the result. Do not parse Jitterbit vendor logs, service output or TranDb in the external tool. JBPA owns that interpretation.

For an existing installation, use the [runbook](JBPA-OPERATOR-RUNBOOK.md) for HEALTH, DIAGNOSTICS, first-class REINSTALL and complete local UNINSTALL. A new result path is required for every invocation. The [Phase 3D SSH caller](../../../tools/handoff/README.md) is an optional reference for controlled Ubuntu 22.04 INSTALL/REINSTALL; it is not an all-operation transport.
