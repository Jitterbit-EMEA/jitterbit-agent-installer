# Use JBPA from Codex or Claude Code

The repository includes matching `jbpa` skill instructions for [Codex](../../../.codex/skills/jbpa/SKILL.md) and [Claude Code](../../../.claude/skills/jbpa/SKILL.md). The skill chooses a named target and invokes `bin/jbpa-remote`; it is not the installer itself. The caller runs on the engineer's or AI orchestration machine, and JBPA runs on an already-provisioned Linux VM.

**Current scope:** RC9 controlled QA on Ubuntu 24.04 amd64. The remote caller is new and has offline tests, but has not been live-tested against an SSH target. The package-changing upgrade path has not been live-qualified. Do not treat this as a production deployment path or Ubuntu 22.04 qualification. The older [Claude Code operating kit](../claude-code/README.md) describes historical RC3 handoff behavior; use this page for RC9 skill commands.

## 1. Get the repository on the orchestration machine

```bash
git clone https://github.com/Jitterbit-EMEA/jitterbit-agent-installer.git
cd jitterbit-agent-installer
./bin/jbpa-remote --help
```

Codex started in this checkout can use `$jbpa`. Claude Code started in this checkout can use `/jbpa`. When the infrastructure AI has a separate repository, add JBPA as a pinned Git submodule and install the two project skills:

```bash
cd /path/to/ai-project
git submodule add https://github.com/Jitterbit-EMEA/jitterbit-agent-installer.git integrations/jbpa
./integrations/jbpa/scripts/install-ai-skills.sh .
```

Start Codex or Claude Code in the AI project and invoke `$jbpa` or `/jbpa`. Alternatively, Claude Code can load the submodule skill for one session with `claude --add-dir integrations/jbpa`. Keep the executable and release archive in the JBPA submodule; do not copy lifecycle code into the AI agent. Pin the submodule commit during a rollout and review updates before changing it.

## 2. Prepare access and credentials

On first invocation, the skill gathers SSH access and non-secret Harmony settings, clones JBPA when no checkout exists, creates a private named-target inventory, and prepares the framework on the VM. A setup-only request stops before installing a PA. Subsequent install, upgrade and health requests reuse that target.

For example, start with `Use $jbpa to set up my VM for Private Agent management` in Codex, or use `/jbpa` in Claude Code. Supply the target name, reachable host, SSH username, private-key and pinned host-key paths, Harmony cloud URL, agent group ID and agent name prefix. The skill offers suggestions such as target `qa-vm`, Azure username `azureuser` or AWS username `ubuntu`, agent prefix `qa-agent`, inventory `~/jbpa-vms.json` and checkout `~/.local/share/jbpa/repo`. Host and group ID must be real supplied values; region and key suggestions must be confirmed. On macOS the skill runs the prepared launcher command for you:

```bash
python3 /path/to/jbpa/scripts/onboard-target.py --open-terminal \
  --inventory "$HOME/jbpa-vms.json" --target qa-vm \
  --cloud-url https://emea-west.jitterbit.com --group-id 12345 \
  --name-prefix customer-pa
```

The launcher opens macOS Terminal and starts setup automatically. Enter only the registration token in its hidden prompt. `TERMINAL_STARTED` reports launch, not setup completion; the terminal process must report `SUCCESS`. On other systems, run the same command without `--open-terminal` in a real terminal if automatic terminal control is unavailable. It verifies and delivers the pinned release, prepares its Python environment, imports a root-only credentials JSON and configures JBPA. It cleans up setup-owned temporary credential files and updates the inventory without recording the token. It does not install or restart a PA. Existing configuration is preserved and reported for inspection rather than overwritten. A failed setup may have prepared the release or configuration already; inspect the host before retrying.

After setup reports success, request `Install 12.10 on qa-vm`, `Upgrade qa-vm to latest`, or `Check qa-vm health`. No pre-staged credentials JSON is required with this onboarding helper. The instructions below also support administrator-staged credentials.

The orchestrator needs SSH access with a local private key and a **pinned** `known_hosts` file. Verify the host key fingerprint independently before adding it to that file; do not use `StrictHostKeyChecking=no`. The VM login must have passwordless `sudo -n`, Python 3, outbound access to Ubuntu packages, the Jitterbit download endpoint and Harmony, and enough CPU, memory and disk for [preflight](../../pre-provisioned-host-contract.md).

For first install, an administrator or secret manager must stage one private [credentials JSON](../../../config/examples/customer-credentials.example.json) on the VM, for example `/run/secrets/jbpa/credentials.json`, with mode `0600`. The inventory contains only its **path on the VM**. Do not put the token value in a prompt, inventory, Git, or an SSH command. The customer launcher imports and validates the JSON into `/etc/jbpa/credentials.json` on first install.

Create a private copy of the [inventory example](../../../config/examples/remote-inventory.example.json) outside the repository. Replace the host, login, local SSH paths and remote credentials path; add more named targets under `targets` as needed. Each command targets one VM.

```bash
install -m 0600 config/examples/remote-inventory.example.json "$HOME/jbpa-vms.json"
${EDITOR:-vi} "$HOME/jbpa-vms.json"
```

The inventory shape is checked by [remote-inventory.schema.json](../../../config/schemas/remote-inventory.schema.json). Keep `identityFile` and `knownHostsFile` as absolute paths **on the orchestration machine**. `credentialsFile` is an absolute path **on the VM**. Omit `credentialsFile` only if the root-only `/etc/jbpa/credentials.json` is already present on the VM.

## 3. Run one command per operation

```bash
./bin/jbpa-remote install --inventory "$HOME/jbpa-vms.json" --target qa-vm --version 12.10
./bin/jbpa-remote versions --inventory "$HOME/jbpa-vms.json" --target qa-vm
./bin/jbpa-remote status --inventory "$HOME/jbpa-vms.json" --target qa-vm
./bin/jbpa-remote health --inventory "$HOME/jbpa-vms.json" --target qa-vm
./bin/jbpa-remote upgrade --inventory "$HOME/jbpa-vms.json" --target qa-vm --version 12.10
./bin/jbpa-remote uninstall --inventory "$HOME/jbpa-vms.json" --target qa-vm
```

The caller first confirms Ubuntu 24.04 amd64 and passwordless sudo. `install` verifies the locally pinned RC9 archive. When the release is absent on the VM, it copies and verifies the archive, extracts it under `/opt/jbpa/releases`, and checks the packaged file manifest. When the release is already present, it verifies the installed manifest against the pinned archive and checks every packaged file before reusing it. A modified release fails closed; the caller does not overwrite it. The installer then runs non-interactively. Later commands use that installed release. The remote login needs no Claude or Codex installation. The command prints one JSON summary and exits nonzero on failure. Use its `resultPath` to retrieve the private full result on the VM if further diagnosis is needed. `status` is diagnostics; use `health` only when the agent config contains the observed expected identity.

Uninstall removes the local PA; it does not delete a Harmony agent record. A fresh registration can consume another licensed group or organization slot. Before reinstalling, inspect the group in Harmony Management Console and remove unused records through an authorized administrator. The skill and caller do not automatically retry a failed mutation.

## AI integration boundary

The infrastructure AI supplies the existing VM, access, secret delivery and a named operation. The `jbpa` skill tells the AI when and how to invoke the fixed CLI. The CLI returns a process exit and structured result; the AI should report those fields and leave vendor-log interpretation and PA lifecycle decisions to JBPA. Read the [canonical external orchestrator contract](../../external-orchestrator-contract.md) for the broader boundary. Its legacy RC3 request schema and SSH reference caller are separate from this RC9 customer remote command.
