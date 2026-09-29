# Customer VM quickstart: local credential files

For a step-by-step walkthrough with delivery, secure credential prompts, version selection, install, upgrade, and verification, use the [start-to-finish customer runbook](customer-install-runbook.md).

JBPA starts on an already provisioned Linux VM. Give the customer a versioned release archive and its SHA-256 digest through a separate trusted channel. They do **not** need the development Git repository. Copying the archive to `/home/azureuser` is fine as a staging step; install the verified framework under `/opt/jbpa/releases` and keep configuration and credentials under `/etc/jbpa`.

This walkthrough uses RC5 on the live-tested Ubuntu 24.04 amd64 / PA 12.10.1.1 tuple. The local-file and guided interactive installation completed successfully on the QA VM on 2026-09-28; see the live customer runbook report (source repository). Ubuntu 22.04 is not yet live-qualified. The PA artifact is QA-only, so use a disposable, non-production host and the explicit `--controlled-test` flag. A production run remains blocked by artifact governance.

## 1. Deliver and set up the framework

Copy `jbpa-1.0.0-rc5.tar.gz` to the VM (for example, `/home/azureuser`). Supply the expected SHA-256 independently of the archive and its adjacent `.sha256` file. On the VM:

```bash
cd /home/azureuser
EXPECTED_SHA256='<digest supplied through trusted channel>'
printf '%s  %s\n' "$EXPECTED_SHA256" jbpa-1.0.0-rc5.tar.gz | sha256sum --check -
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip
sudo install -d -m 0755 /opt/jbpa/releases
sudo tar -xzf jbpa-1.0.0-rc5.tar.gz -C /opt/jbpa/releases
RELEASE=/opt/jbpa/releases/jbpa-1.0.0-rc5
sudo python3 -m venv "$RELEASE/.venv"
sudo "$RELEASE/.venv/bin/python" -m pip install -r "$RELEASE/requirements.txt"
"$RELEASE/bin/jbpa" version
"$RELEASE/bin/jbpa" versions
```

Use an approved Python package index or offline wheel mirror for the pinned dependencies. The release archive does not include Python or wheels. Verify the release's inner manifest with the build-side verifier before distribution; the independent archive SHA-256 is the customer-side integrity check before extraction.

## 2. Configure the customer VM

```bash
sudo install -d -m 0700 /etc/jbpa/secrets
sudo install -m 0600 "$RELEASE/config/examples/local-file-qa.example.yaml" /etc/jbpa/agent.yaml
sudoedit /etc/jbpa/agent.yaml
```

Review `agent.expected_os`, `agent.version`, the registration strategy, and the output/health policy. The example already points to `/etc/jbpa/secrets`. It contains only references, never secret values. A customer secret-delivery system or administrator must place these seven UTF-8, single-line files in that directory, owned by root with mode `0600`:

| File | Content |
| --- | --- |
| `pa-registration-token` | Harmony PA registration token |
| `pa-cloud-url` | Reviewed Harmony HTTPS cloud URL |
| `pa-agent-group-id` | Numeric target agent group ID |
| `pa-agent-name-prefix` | Desired agent name prefix |
| `pa-deregister-on-drainstop` | `false` |
| `pa-retry-count` | `10` |
| `pa-retry-interval-seconds` | `5` |

For example, transfer protected files using the customer's existing secret-delivery channel, then verify permissions without displaying values:

```bash
sudo chown root:root /etc/jbpa/secrets
sudo chmod 0700 /etc/jbpa/secrets
sudo find /etc/jbpa/secrets -maxdepth 1 -type f -exec chown root:root {} +
sudo find /etc/jbpa/secrets -maxdepth 1 -type f -exec chmod 0600 {} +
sudo find /etc/jbpa/secrets -maxdepth 1 -type f -printf '%u:%g %m %f\n'
```

The provider rejects symlinks, hard links, world/group-readable files, unsafe parent directories, empty files, control characters and files over 64 KiB. It never prints file values. Do not put the token in the YAML, shell arguments, Git, or the release archive.

## 3. Preflight and install

```bash
sudo "$RELEASE/bin/jbpa" validate --config /etc/jbpa/agent.yaml --controlled-test
sudo "$RELEASE/bin/jbpa" install --interactive --config /etc/jbpa/agent.yaml --version latest --controlled-test
```

Interactive mode requires a real terminal. It resolves `latest` once, displays the exact package version, SHA-256, qualification and config path, then waits for the operator to type `INSTALL`. If the observed package is not qualified for this VM, the operator must explicitly choose controlled testing and pass `--allow-unqualified`; the tool does not automatically promote it. For automation, use `--non-interactive` instead of `--interactive`.

Read both the process exit code and the JSON `status`; a successful install reports `SUCCESS`. `validate` is a host and credential preflight, not an agent installation. If a PA is already installed, investigate its state before using `upgrade`, `reinstall` or `uninstall`. The tool does not provision the VM or create the Harmony token; those remain the customer's or external orchestrator's responsibility.

`jbpa versions` (or `jbpa version list`) lists every version in the governed catalogue without downloading packages; it does not claim each historical URL is currently reachable. `jbpa version resolve latest` downloads and inspects the mutable vendor endpoint before reporting its exact package version and hash.

## Upgrade an existing agent

```bash
sudo "$RELEASE/bin/jbpa" upgrade --config /etc/jbpa/agent.yaml --version latest --non-interactive --controlled-test
```

The in-place upgrade requires an already registered, healthy PA, a newer package in the same major series, a clean preflight and a root-private configuration backup. It drains operations before `dpkg --install`, restores changed settings from that backup, restarts and confirms the same agent/group identity and healthy connectivity. If `latest` is the installed version, the result is `ALREADY_CURRENT` with no package change; this no-op path passed on the QA VM on 2026-09-28. A major-version change, downgrade, unknown latest package or unqualified combination stops for review. The actual package-changing upgrade path has offline tests but no live qualification yet. The backup remains under `/var/lib/jbpa/backups` for recovery.

For Azure hosts, use the existing Managed Identity / Key Vault example instead of the local-file example. On AWS, on-premises VMs or other clouds, a secret manager can deliver the root-owned files and then invoke the same `jbpa` CLI. The local-file provider makes Azure credentials unnecessary for this path.
