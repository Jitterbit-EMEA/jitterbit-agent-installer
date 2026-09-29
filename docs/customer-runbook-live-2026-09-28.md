# RC5 customer runbook live QA report — 2026-09-28

## Scope and outcome

The designated QA VM ran Ubuntu 24.04 amd64 with two CPUs. An existing PA 12.10.1.1 was completely uninstalled through RC4, leaving a clean host. The RC5 customer flow then installed PA 12.10.1.1 using protected local credential files and the guided interactive `latest` choice. The installer returned `SUCCESS` / `COMPLETE`, with service running, Harmony registration confirmed, and the agent synchronized. The installed Debian package remained 12.10.1.1 after the subsequent upgrade no-op test.

The seven registration and policy values were retrieved from `https://jblab-pa-automated.vault.azure.net/` by the VM's managed identity and staged as root-owned `0600` local files in `/etc/jbpa/secrets` (`0700` directory). The values were not printed or copied into the repository. This tested the customer-facing local-file provider even though Azure Key Vault supplied the files. A customer outside Azure can use its own protected secret-delivery process to create the same files.

## Commands and results

Commands below ran on the QA VM as `azureuser` (with `sudo` where shown). SSH used the supplied key and a separately verified, pinned host key. The archive was delivered to `/home/azureuser` and its SHA-256 was checked before extraction.

```bash
printf '%s  %s\n' '099b7d577add54d7b552b97e038b8ce2d299cbb5bd02c3e6872afab166e72aec' jbpa-1.0.0-rc5.tar.gz | sha256sum --check -
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip
sudo install -d -m 0755 /opt/jbpa/releases
sudo tar -xzf jbpa-1.0.0-rc5.tar.gz -C /opt/jbpa/releases
RELEASE=/opt/jbpa/releases/jbpa-1.0.0-rc5
sudo python3 -m venv "$RELEASE/.venv"
sudo "$RELEASE/.venv/bin/python" -m pip install -r "$RELEASE/requirements.txt"
sudo "$RELEASE/bin/jbpa" versions
sudo "$RELEASE/bin/jbpa" validate --config /etc/jbpa/agent.yaml --controlled-test --result-file /var/lib/jbpa/results/customer-rc5-preflight-20260928.json
sudo "$RELEASE/bin/jbpa" install --interactive --config /etc/jbpa/agent.yaml --version latest --controlled-test --result-file /var/lib/jbpa/results/customer-rc5-interactive-install-20260928.json
```

`versions` listed 19 governed catalogue entries. `validate` returned `PASS_WITH_WARNINGS`: all blocking checks passed, including local secret files; the warning was the explicit controlled-test exception for two CPUs against the four-CPU policy. Interactive install displayed PA 12.10.1.1, SHA-256 `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8`, `TESTED_LIVE`, and the config path. The operator typed `INSTALL`. The install result file records `status: SUCCESS`, `state: COMPLETE`, `harmonyRegistered: true`, and `serviceRunning: true`.

```bash
sudo "$RELEASE/bin/jbpa" upgrade --config /etc/jbpa/agent.yaml --version latest --non-interactive --controlled-test --result-file /var/lib/jbpa/results/customer-rc5-upgrade-latest-20260928.json
sudo "$RELEASE/bin/jbpa" health
dpkg-query -W jitterbit-agent
sudo find /etc/jbpa/secrets -maxdepth 1 -type f -printf '%u:%g %m %f\n'
```

The upgrade result returned `ALREADY_CURRENT` and `changed: false` because the latest resolved package was the installed 12.10.1.1. Bare `health` returned `HEALTHY` with `LOCAL_ONLY` scope; the installer result separately confirmed Harmony registration. `dpkg-query` returned `jitterbit-agent 12.10.1.1`. All seven secret files were `root:root 600`.

## Qualification boundary

This is one controlled QA run on Ubuntu 24.04, not a production approval. Ubuntu 22.04 and the package-changing upgrade path have not been live-qualified by this run. The governed PA artifact remains approved for test only. Result files remain on the VM under `/var/lib/jbpa/results`; this report contains no secret values or registration identifiers.
