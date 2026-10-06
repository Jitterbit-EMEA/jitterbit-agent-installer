---
name: jbpa
description: Install or manage a Jitterbit Private Agent on a named, already-provisioned Ubuntu QA VM through the JBPA SSH caller. Use for PA installation, upgrade, uninstall, health, status, or version listing on a VM.
---

# Jitterbit Private Agent on a provisioned VM

Locate the JBPA checkout containing `bin/jbpa-remote`, often `integrations/jbpa` in the AI project. Use that command for one named VM and one operation at a time. The caller runs on the engineer's or orchestration host; Codex or Claude Code does not need to run on the PA VM. JBPA owns PA package, registration, upgrade, health, and uninstall work. This skill does not provision infrastructure.

The remote caller currently supports the **RC9 controlled QA workflow on Ubuntu 24.04 amd64**. It is not a production or Ubuntu 22.04 qualification. In the JBPA checkout, read `docs/integrations/skills/README.md` when preparing an inventory or VM, and `docs/customer-start-here.md` for release limitations.

## First-run connection setup

Run this conversational setup when the requested target has no usable local inventory. Installing the skill does not transfer another engineer's VM details, keys, credentials or QA approvals.

1. Reuse details explicitly supplied in this conversation or a user-selected inventory. Otherwise check `$HOME/jbpa-vms.json`. If several targets exist and the request does not identify one, ask which target to use. Do not infer a target from example files or another engineer's history. If the JBPA checkout cannot be located in the current project, ask for its local path; the skill alone does not include the caller or release archive.
2. Ask for only the missing fields in one concise message:

   > To connect to your VM, please provide a target name, public hostname/IP (or a private address reachable from this computer), SSH username, absolute local SSH private-key path, and pinned `known_hosts` file path. Provide file paths only, not key contents or passwords.

   For `install`, also ask for the requested PA version if unspecified and the absolute path to the protected credentials JSON **on the VM**. This path is unnecessary if `/etc/jbpa/credentials.json` is already staged and verified by the installer. Do not require registration credentials for status, health, versions or uninstall.
3. Check that local key and host-key files exist without displaying private-key contents. Expand local `~` paths before storing them. If the colleague has no pinned host key, help obtain the expected fingerprint through their VM administrator or authenticated cloud console. A key collected with `ssh-keyscan` is only a candidate: compare its fingerprint with that independent source before pinning it. Never auto-accept a new or changed host key. If verification is unavailable, explain the missing evidence and pause before connecting.
4. Save the completed inventory to `$HOME/jbpa-vms.json`, or the user's chosen private location outside Git, with mode `0600`. Follow the checkout's inventory example and schema. Store host, username and file paths only; never store key contents, tokens, passwords or QA approvals. Preserve other targets. Ask which entry to use or update if the chosen name conflicts with a different host or user; do not silently replace it. Tell the colleague the inventory path and target name so they can reuse them.
5. Test SSH with `BatchMode=yes`, `IdentitiesOnly=yes`, `StrictHostKeyChecking=yes`, the selected identity and pinned host-key files, and a bounded connection timeout. Read the hostname and check `sudo -n true`; do not install or restart anything during connection setup. Quote user-supplied values safely or pass them as subprocess arguments. This SSH probe also works on a fresh VM where JBPA has not been installed. For a failed probe, report whether the issue is reachability, host-key verification, authentication or sudo; ask only for the correction needed.
6. Continue the already-requested operation after successful setup. If the user requested setup only, stop after reporting connection readiness. Reuse the saved inventory on subsequent invocations and prompt again only for missing, ambiguous or invalid details. A saved target establishes access details, not authorization for a new mutation or an inherited exception.

## Agent operation

1. Identify the named target and requested operation: `install`, `upgrade`, `uninstall`, `status`, `health`, or `versions`. Mutations require the user's authorization for that operation. Do not turn a failed install into an automatic reinstall or delete Harmony records.
2. Obtain a local SSH identity-file path, a pinned `known_hosts` file, the VM's host and user, and for first install an **absolute path on the VM** to a private JSON credentials file. The VM or its secret manager must stage that file. Never ask for a Harmony token value, put one in inventory, or echo a credentials file. The inventory holds paths only.
3. Use the private inventory prepared above, following `config/examples/remote-inventory.example.json` and `config/schemas/remote-inventory.schema.json` from the JBPA checkout. Check the named target and release before execution. Do not auto-accept an SSH host key.
4. Run from the JBPA checkout root:

   ```bash
   ./bin/jbpa-remote install --inventory /private/path/vms.json --target qa-vm --version 12.10
   ./bin/jbpa-remote status --inventory /private/path/vms.json --target qa-vm
   ```

   Use the same command shape for `versions`, `health`, `upgrade --version 12.10`, or `uninstall`. The caller pins and delivers RC9 on first install, then invokes the installed CLI for management. `latest` is mutable; use a governed exact version unless the user explicitly selects latest.
5. Consume the caller's JSON and exit code. Success needs exit 0 and `status=SUCCESS`; installation additionally requires Harmony registration and running service in the JBPA result. Preserve the private on-VM `resultPath` and report the selected target, operation, resolved version, outcome and any JBPA reason. `status` is diagnostic and does not by itself prove Harmony health; use `health` when expected agent identity is configured.

If the caller reports release mismatch, missing result, host-access failure, or a partial install, stop and inspect the host state before any retry. Uninstall is local; Harmony record deletion is a separate administrator action and agent-group capacity can be consumed by fresh registrations.
