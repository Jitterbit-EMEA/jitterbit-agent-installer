---
name: jbpa
description: Operate Jitterbit Private Agent through JBPA on a pre-provisioned Linux VM for install, reinstall, uninstall, health, diagnostics or validate.
argument-hint: <install|reinstall|uninstall|health|diagnostics|validate> [target]
disable-model-invocation: true
---

# JBPA operator workflow

Interpret `$ARGUMENTS[0]` as the operation (`install`, `reinstall`, `uninstall`, `health`, `diagnostics`, or `validate`) and any following arguments as target context. If missing, ask which operation and already-provisioned host the user means. Read [the quickstart](../../../docs/integrations/claude-code/JBPA-QUICKSTART.md), [handoff](../../../docs/integrations/claude-code/JBPA-EXTERNAL-HANDOFF.md), and the relevant section of [the operator runbook](../../../docs/integrations/claude-code/JBPA-OPERATOR-RUNBOOK.md) before executing.

JBPA DOES NOT CREATE VIRTUAL MACHINES. Start at `VM_ALREADY_PROVISIONED`. If the user says “the VM I just created,” identify that existing host; do not recreate it. The infrastructure AI owns VM, OS, network, identity, access and release delivery. JBPA owns all Jitterbit Private Agent lifecycle decisions and work.

1. Confirm target host, operation, approved transport, RC3 release and configuration source. RC3 SHA-256 is `4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e`. Verify this independently on the executing host before invoking the release. Stop on mismatch.
2. Confirm the configuration uses secret references, not values. Azure Key Vault use requires a pre-attached Managed Identity with least-privilege access. Never put a token into a prompt, request, log or evidence file.
3. Run JBPA `validate --config PATH --version VERSION --profile OPERATION` on an unknown host; check `details.preflight.status` and actual host state. The [runbook](../../../docs/integrations/claude-code/JBPA-OPERATOR-RUNBOOK.md) gives exact RC3 commands.
4. Invoke exactly one JBPA operation. For REINSTALL use first-class `jbpa reinstall`; never compose uninstall and install. `--allow-unqualified` is permitted only when the user explicitly authorized a controlled test, paired with `--controlled-test`. It bypasses qualification policy alone.
5. Wait for completion. Retrieve the fresh private `result.json`. Validate against `config/schemas/rc-result.schema.json`, check matching operation and release, and require process exit `0`, `status=SUCCESS`, `category=SUCCESS`, and `error=null` for success. For a failure, report `category`, `state`, and `error.retryable`; do not blindly retry.
6. Return the generic JBPA result to the parent infrastructure workflow. Preserve failure evidence without credentials or vendor-log interpretation.

Never create a VM as part of JBPA, duplicate Jitterbit lifecycle code, parse Jitterbit vendor logs in the caller, query TranDb, read `credentials.txt`, print `register.json`, expose secret-provider values, bypass artifact SHA validation, assume preflight success, or use `--dangerously-skip-permissions`. Ask for confirmation before separately requested destructive *infrastructure* actions; ordinary JBPA lifecycle commands follow their explicit operation semantics.

`/jbpa install` uses INSTALL, `/jbpa reinstall` uses first-class REINSTALL, `/jbpa uninstall` performs complete local removal only, `/jbpa health` uses structured health with expected identity, `/jbpa diagnostics` gathers non-secret observations, and `/jbpa validate` performs read-only host readiness. The Phase 3D SSH reference caller supports controlled Ubuntu 22.04 INSTALL/REINSTALL only; use an approved preinstalled/remote adapter for other operations. This SSH transport is unrelated to JBPA's `[SSH]`/SFTP enterprise configuration.
