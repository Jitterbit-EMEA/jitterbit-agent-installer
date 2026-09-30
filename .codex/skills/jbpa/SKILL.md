---
name: jbpa
description: Install or manage a Jitterbit Private Agent on a named, already-provisioned Ubuntu QA VM through the JBPA SSH caller. Use for PA installation, upgrade, uninstall, health, status, or version listing on a VM.
---

# Jitterbit Private Agent on a provisioned VM

Locate the JBPA checkout containing `bin/jbpa-remote`, often `integrations/jbpa` in the AI project. Use that command for one named VM and one operation at a time. The caller runs on the engineer's or orchestration host; Codex or Claude Code does not need to run on the PA VM. JBPA owns PA package, registration, upgrade, health, and uninstall work. This skill does not provision infrastructure.

The remote caller currently supports the **RC9 controlled QA workflow on Ubuntu 24.04 amd64**. It is not a production or Ubuntu 22.04 qualification. In the JBPA checkout, read `docs/integrations/skills/README.md` when preparing an inventory or VM, and `docs/customer-start-here.md` for release limitations.

1. Identify the named target and requested operation: `install`, `upgrade`, `uninstall`, `status`, `health`, or `versions`. Mutations require the user's authorization for that operation. Do not turn a failed install into an automatic reinstall or delete Harmony records.
2. Obtain a local SSH identity-file path, a pinned `known_hosts` file, the VM's host and user, and for first install an **absolute path on the VM** to a private JSON credentials file. The VM or its secret manager must stage that file. Never ask for a Harmony token value, put one in inventory, or echo a credentials file. The inventory holds paths only.
3. Create a private inventory outside Git using `config/examples/remote-inventory.example.json` and `config/schemas/remote-inventory.schema.json` from the JBPA checkout. Check the named target and release before execution. Do not auto-accept an SSH host key.
4. Run from the JBPA checkout root:

   ```bash
   ./bin/jbpa-remote install --inventory /private/path/vms.json --target qa-vm --version 12.10
   ./bin/jbpa-remote status --inventory /private/path/vms.json --target qa-vm
   ```

   Use the same command shape for `versions`, `health`, `upgrade --version 12.10`, or `uninstall`. The caller pins and delivers RC9 on first install, then invokes the installed CLI for management. `latest` is mutable; use a governed exact version unless the user explicitly selects latest.
5. Consume the caller's JSON and exit code. Success needs exit 0 and `status=SUCCESS`; installation additionally requires Harmony registration and running service in the JBPA result. Preserve the private on-VM `resultPath` and report the selected target, operation, resolved version, outcome and any JBPA reason. `status` is diagnostic and does not by itself prove Harmony health; use `health` when expected agent identity is configured.

If the caller reports release mismatch, missing result, host-access failure, or a partial install, stop and inspect the host state before any retry. Uninstall is local; Harmony record deletion is a separate administrator action and agent-group capacity can be consumed by fresh registrations.
