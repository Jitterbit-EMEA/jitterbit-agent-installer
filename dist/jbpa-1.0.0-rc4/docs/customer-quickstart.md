# Customer VM quickstart: local credential files

JBPA starts on an already provisioned Linux VM. Give the customer a versioned release archive and its SHA-256 digest through a separate trusted channel. They do **not** need the development Git repository. Copying the archive to `/home/azureuser` is fine as a staging step; install the verified framework under `/opt/jbpa/releases` and keep configuration and credentials under `/etc/jbpa`.

This walkthrough uses RC4 on the currently live-tested Ubuntu 24.04 amd64 / PA 12.10.1.1 tuple. RC4's local-file provider is tested offline; a live installation with that provider has not yet been qualified. Ubuntu 22.04 is not yet live-qualified. The PA artifact is QA-only, so use a disposable, non-production host and the explicit `--controlled-test` flag. A production run remains blocked by artifact governance.

## 1. Deliver and set up the framework

Copy `jbpa-1.0.0-rc4.tar.gz` to the VM (for example, `/home/azureuser`). Supply the expected SHA-256 independently of the archive and its adjacent `.sha256` file. On the VM:

```bash
cd /home/azureuser
EXPECTED_SHA256='<digest supplied through trusted channel>'
printf '%s  %s\n' "$EXPECTED_SHA256" jbpa-1.0.0-rc4.tar.gz | sha256sum --check -
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip
sudo install -d -m 0755 /opt/jbpa/releases
sudo tar -xzf jbpa-1.0.0-rc4.tar.gz -C /opt/jbpa/releases
RELEASE=/opt/jbpa/releases/jbpa-1.0.0-rc4
sudo python3 -m venv "$RELEASE/.venv"
sudo "$RELEASE/.venv/bin/python" -m pip install -r "$RELEASE/requirements.txt"
"$RELEASE/bin/jbpa" version
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
sudo chown root:root /etc/jbpa/secrets /etc/jbpa/secrets/*
sudo chmod 0700 /etc/jbpa/secrets
sudo chmod 0600 /etc/jbpa/secrets/*
sudo stat -c '%U:%G %a %n' /etc/jbpa/secrets /etc/jbpa/secrets/*
```

The provider rejects symlinks, hard links, world/group-readable files, unsafe parent directories, empty files, control characters and files over 64 KiB. It never prints file values. Do not put the token in the YAML, shell arguments, Git, or the release archive.

## 3. Preflight and install

```bash
sudo "$RELEASE/bin/jbpa" validate --config /etc/jbpa/agent.yaml --controlled-test
sudo "$RELEASE/bin/jbpa" install --config /etc/jbpa/agent.yaml --version 12.10 --non-interactive --controlled-test
```

Read both the process exit code and the JSON `status`; a successful install reports `SUCCESS`. `validate` is a host and credential preflight, not an agent installation. If a PA is already installed, investigate its state before using `reinstall` or `uninstall`. The tool does not provision the VM or create the Harmony token; those remain the customer's or external orchestrator's responsibility.

For Azure hosts, use the existing Managed Identity / Key Vault example instead of the local-file example. On AWS, on-premises VMs or other clouds, a secret manager can deliver the root-owned files and then invoke the same `jbpa` CLI. The local-file provider makes Azure credentials unnecessary for this path.
