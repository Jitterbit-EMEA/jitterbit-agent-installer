---
name: jbpa
description: Set up or manage Jitterbit Private Agents on named, already-provisioned Ubuntu QA VMs. Gather SSH and Harmony settings, clone JBPA, prepare protected credentials, then handle install, upgrade, uninstall, health, status or versions.
---

# Jitterbit Private Agent setup and management

Use this skill for conversational onboarding and subsequent PA lifecycle requests. The engineer's computer runs the SSH caller; the VM runs JBPA. This skill does not provision infrastructure. Handle one named target and operation at a time.

The pinned remote caller supports RC9 controlled QA on Ubuntu 24.04 amd64. Read `docs/customer-start-here.md` in the checkout for release limitations. Installing the skill does not transfer another engineer's hosts, keys, credentials or QA approvals.

## First-run setup

A request such as “Set up JBPA on my VM” authorizes preparing the framework and protected credentials. It does not itself authorize installing a PA. If setup accompanies an explicit install request, continue that installation after setup succeeds.

1. Gather missing non-secret information before cloning. Reuse the conversation, a user-selected private inventory, or `$HOME/jbpa-vms.json`. Ask in one concise message for:
   - Target name, reachable public hostname/IP or private address, SSH username.
   - Absolute local SSH private-key path and pinned `known_hosts` path.
   - Harmony cloud URL, numeric agent group ID, and desired agent name prefix.
   - PA version only if installation or upgrade was requested and no version was given.

   Offer defaults and examples in the initial question, and let the user accept them together or override individual fields:

   | Setting | Suggested default or example |
   |---|---|
   | Target name | `qa-vm` (choose another if already used) |
   | Host | User's actual hostname/IP; example `203.0.113.10` is illustrative only |
   | SSH username | `azureuser` for Azure Ubuntu, `ubuntu` for AWS Ubuntu; ask for other images |
   | SSH key | An existing user-selected key; suggest `~/.ssh/id_ed25519` only if it exists |
   | Known hosts | `~/.ssh/known_hosts`; verify this target is pinned |
   | Harmony URL | Offer `https://emea-west.jitterbit.com` for EMEA; request their actual cloud URL for other regions |
   | Group ID | Required actual ID from Harmony; `12345` is an example, never an automatic default |
   | Agent prefix | `qa-agent` |
   | Inventory | `~/jbpa-vms.json` |
   | Local checkout | `~/.local/share/jbpa/repo` |

   Do not silently use an example address, group ID, region or missing key. Ask the user to accept applicable suggestions; already-established values take priority. No token default is allowed.

   Tell the user that the registration token will be entered later in a hidden terminal prompt. Never request private-key contents, registration tokens or passwords in chat. If they already have a protected credentials JSON on the VM, ask for its absolute path instead of asking them to re-enter Harmony settings.
2. Check local SSH files without displaying private-key contents. Expand `~` to absolute paths. If the host key is not pinned, help obtain the expected fingerprint from an authenticated cloud console or VM administrator. `ssh-keyscan` produces only a candidate; compare it with that independent fingerprint before pinning. Never auto-accept a new or changed host key. Test SSH with BatchMode, IdentitiesOnly and StrictHostKeyChecking enabled, a bounded connection timeout, the chosen key and known-hosts file; read the hostname and check `sudo -n true`.
3. Find an existing JBPA checkout containing `bin/jbpa-remote`. If absent, clone `https://github.com/Jitterbit-EMEA/jitterbit-agent-installer.git` into the user's chosen directory, defaulting to `$HOME/.local/share/jbpa/repo`. Clone only into an absent directory. Reuse an existing checkout without resetting files or silently pulling over local work. Record its commit and pinned release. Use subprocess arguments or properly quoted values. Read `docs/integrations/skills/README.md` for the SSH inventory schema and setup helper.
4. Save a mode-`0600` private inventory outside Git, default `$HOME/jbpa-vms.json`, following `config/examples/remote-inventory.example.json` and `config/schemas/remote-inventory.schema.json`. Store named targets with host, user, identityFile and knownHostsFile. Preserve other targets; resolve a conflicting target name before replacing it. Do not store token values, key contents or QA approvals. Include credentialsFile only when a protected source JSON is already staged on the VM.
5. Prepare JBPA and Harmony credentials. For a new target without staged credentials, run the prepared command for the user. On macOS, execute the helper with `--open-terminal`: it launches the actual setup in Terminal and brings the window forward. The user only enters the token in its hidden prompt. The agent may launch this command from a captured session because the launcher itself never asks for or receives the token. Never supply hidden token input through chat or a tool call. On other systems use an available user-controlled terminal launcher; if unavailable, provide the exact command without `--open-terminal` and explain that terminal launching is unavailable.

   ```bash
   python3 /path/to/jbpa/scripts/onboard-target.py --open-terminal \
     --inventory /private/path/jbpa-vms.json --target qa-vm \
     --cloud-url https://emea-west.jitterbit.com --group-id 12345 \
     --name-prefix customer-pa
   ```

   The helper prompts for the token with echo disabled, verifies and delivers the pinned release, installs JBPA's Python dependencies, imports credentials into root-only `/etc/jbpa/credentials.json`, creates `/etc/jbpa/agent.yaml`, cleans temporary credential files and preserves the inventory's other hosts. It installs the framework, not the PA. A non-terminal invocation fails before asking for a token. Existing configuration is never overwritten: inspect and reuse a configured target, or obtain explicit reconfiguration instructions. If the user supplies a staged JSON instead, use the checkout's verified delivery and customer configure/import path with that remote file; never retrieve its contents into chat. Keep credential staging private and clean up only setup-owned files.
6. `TERMINAL_STARTED` means the window was launched, not that setup succeeded. Confirm the terminal helper returned `status=SUCCESS`, or independently verify setup when the user reports completion: check release integrity, runtime dependencies and protected credential/configuration metadata without printing secrets. Do not call an uncompleted hidden prompt successful. Report the checkout, inventory and target names. For setup-only requests stop at “Ready for install, upgrade and health requests.” Resume an already-authorized PA operation; never invent an initial version or auto-install during setup.

The hidden-token step is the user's only secret entry; the skill collects the remaining settings conversationally. No pre-created credentials file is required for this setup route. If an installed copy of the skill predates the setup helper, update the checkout before invoking it, with attention to local work.

## Subsequent operations

Reuse the saved checkout and inventory. Ask which target when ambiguous; prompt only for missing or invalid details. Natural requests include “Install 12.10 on qa-vm”, “Upgrade qa-vm to latest”, and “Check qa-vm health”. The user's requested mutation is its authorization; carry forward explicit approvals in this conversation, but never infer approvals from a saved inventory.

Run from the checkout:

```bash
./bin/jbpa-remote install --inventory /private/path/jbpa-vms.json --target qa-vm --version 12.10
./bin/jbpa-remote upgrade --inventory /private/path/jbpa-vms.json --target qa-vm --version latest
./bin/jbpa-remote status --inventory /private/path/jbpa-vms.json --target qa-vm
./bin/jbpa-remote health --inventory /private/path/jbpa-vms.json --target qa-vm
```

Use the same command shape for versions or uninstall. Setup saves imported credentials on the VM; omit credentialsFile after a successful import to avoid trying to import it again. `latest` is mutable: select it only when requested, then record its resolved version and digest. A catalogue entry does not establish production qualification.

For full health, the VM configuration must contain an independently checked expected identity. After initial installation, capture the observed agent ID/name/group/version through diagnostics and sanitized runtime identity evidence, compare the group and name prefix with the supplied Harmony settings, and configure the health expected identity without exposing credentials. Do not claim full health from the status command alone. If expected identity cannot be established, report diagnostic results and the precise evidence gap.

Success requires exit 0 and status=SUCCESS; installation additionally requires registration and running services. Preserve the private on-VM resultPath and report target, operation, resolved version, outcome and any reason. On release mismatch, missing result, host-access failure or partial installation, inspect host state before retrying. Do not turn a failed install into automatic reinstall or delete Harmony records. Uninstall is local; fresh registration can consume another Harmony group slot.
