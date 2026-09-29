# Install a Private Agent: the short path

This RC7 launcher is for a **disposable Ubuntu 24.04 amd64 QA VM**. It has not been approved for production, Ubuntu 22.04, or a live package-changing upgrade. You need `sudo`, your Harmony registration token, cloud URL and numeric agent group ID. The token is entered into a hidden prompt and stored in a root-only file; it is never placed in a command or `.env` file.

## 1. Copy and extract the release

Have your administrator copy `jbpa-1.0.0-rc7.tar.gz` to your VM home directory and give you its SHA-256 through a separate trusted channel. SSH into the VM, then run:

```bash
cd "$HOME"
EXPECTED_SHA256='paste-independent-sha256-here'
printf '%s  %s\n' "$EXPECTED_SHA256" jbpa-1.0.0-rc7.tar.gz | sha256sum --check -
sudo install -d -m 0755 /opt/jbpa/releases
sudo tar -xzf jbpa-1.0.0-rc7.tar.gz -C /opt/jbpa/releases
cd /opt/jbpa/releases/jbpa-1.0.0-rc7
```

Stop if the checksum does not say `OK`. A reviewed Git tag may also deliver this same archive; the development repository currently has no published customer clone URL.

## 2. Run the guided launcher

```bash
sudo ./bin/jbpa-customer
```

Choose **1** to prepare Python and enter Harmony details. The launcher creates `/etc/jbpa/agent.yaml` and private files under `/etc/jbpa/secrets`, then runs preflight. Choose **2** to see the PA versions. Choose **3** to install; press Enter for `latest` or type a qualified catalogue version, then type `INSTALL` when JBPA shows the exact package and SHA-256. Choose **5** to check status. Confirm the new agent and group in Harmony Management Console.

The setup uses the current QA registration defaults (`deregister=false`, retry count `10`, retry interval `5`). It retains existing credentials unless you choose menu item **6** to replace them. It uses the same governed JBPA CLI and `--controlled-test` policy as the detailed procedure; it cannot override platform, artifact, secret or health checks.

## Named commands for an operator or automation

You can also call the launcher directly from the extracted RC7 directory:

```bash
sudo ./bin/jbpa-customer setup
sudo ./bin/jbpa-customer versions
sudo ./bin/jbpa-customer install --version latest
sudo ./bin/jbpa-customer status
sudo ./bin/jbpa-customer upgrade --version latest
```

`setup` prompts for the token, cloud URL, group ID and name prefix if they are not already present. The install command calls interactive JBPA and requires a terminal. For an unattended run after protected files are staged, use `install --version latest --non-interactive`. For an unattended upgrade, add `--yes`. The launcher saves a unique private JSON result under `/var/lib/jbpa/results` and prints a short outcome. It does not reinstall an existing agent silently; JBPA checks the host state.

The full [customer runbook](customer-install-runbook.md) explains archive delivery, credentials, preflight and recovery in detail. Public Java truststore certificates use a separate [enterprise procedure](runbooks/enterprise-truststore.md). SSH/SFTP keys, mTLS client certificates and corporate proxy settings are not yet applied by RC7; those branches remain blocked rather than silently ignored.
