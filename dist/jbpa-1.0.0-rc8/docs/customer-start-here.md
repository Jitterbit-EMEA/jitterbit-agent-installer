# Install a Private Agent on a fresh VM

This guide uses the **RC8 QA candidate** on **Ubuntu 24.04 amd64**. The VM needs `sudo`, outbound access to Ubuntu packages, the Jitterbit download endpoint and Harmony, and at least 4 vCPUs, 8 GB RAM and 50 GB disk. RC8 has offline validation but has **not** had a live installation test; the earlier RC7 interactive install was live-tested on this QA platform. Neither release is approved for production or qualified on Ubuntu 22.04.

Choose **A** for guided input at a terminal. Choose **B** when your administrator or secret manager supplies one protected JSON document. The launcher prepares Python, creates `/etc/jbpa/agent.yaml`, runs preflight, and manages the installer. `verify` reads the private result and checks the current package, connection and services; no result filename or Python command is needed.

## 1. Copy and extract the release

On the computer holding the release, run these commands from the repository root. Replace the VM user and host. Your release administrator should provide the checksum through a trusted channel as well as the archive files.

```bash
VM_USER='your-vm-user'
VM_HOST='your-vm-address'
scp dist/jbpa-1.0.0-rc8.tar.gz dist/jbpa-1.0.0-rc8.tar.gz.sha256 "${VM_USER}@${VM_HOST}:~/"
ssh "${VM_USER}@${VM_HOST}"
```

Run the remaining commands **on the VM**. Stop if the OS, architecture or resources do not meet the requirements, or if the checksum does not print `OK`.

```bash
cat /etc/os-release
uname -m
nproc
free -h
df -h /
cd "$HOME"
sha256sum --check jbpa-1.0.0-rc8.tar.gz.sha256
sudo install -d -m 0755 /opt/jbpa/releases
sudo tar -xzf jbpa-1.0.0-rc8.tar.gz -C /opt/jbpa/releases
cd /opt/jbpa/releases/jbpa-1.0.0-rc8
```

The expected OS is `VERSION_ID="24.04"` and architecture `x86_64`. The archive is the documented delivery route; this development repository has no published customer clone URL. Run each install command in order and stop if it fails.

## A. Guided interactive installation

```bash
sudo ./bin/jbpa-customer setup
sudo ./bin/jbpa-customer versions
sudo ./bin/jbpa-customer install --version latest
sudo ./bin/jbpa-customer verify
```

`setup` asks for the registration token in a **hidden prompt**, then the Harmony cloud URL (`https://...`), numeric agent group ID and agent name prefix. It stores them together in one root-only `/etc/jbpa/credentials.json` and validates the JSON schema. It also checks the VM before installation. `versions` shows the governed JBPA catalogue, with qualification and approval; it is not a claim to list every Jitterbit release. `latest` resolves the vendor endpoint when chosen. At the install prompt, review the exact package version and SHA-256, then type `INSTALL`. To pin the known PA 12.10 build, use `sudo ./bin/jbpa-customer install --version 12.10` instead.

For a numbered menu, run `sudo ./bin/jbpa-customer` and choose **1 → 2 → 3 → 7 → 0**. The equivalent named commands above are easier to copy and audit.

## B. Non-interactive installation with one JSON file

Ask your administrator or secret manager to deliver **one** `credentials.json` file to the VM, for example `/run/secrets/jbpa/credentials.json`. The file must be private and must match the bundled [example](../config/examples/customer-credentials.example.json) and [JSON Schema](../config/schemas/customer-credentials.schema.json):

```json
{
  "schemaVersion": 1,
  "harmony": {
    "registrationToken": "REPLACE_WITH_TOKEN",
    "cloudUrl": "https://your-harmony-cloud.example",
    "agentGroupId": 12345
  },
  "agent": {"namePrefix": "customer-pa"},
  "registration": {
    "deregisterOnDrainstop": false,
    "retryCount": 10,
    "retryIntervalSeconds": 5
  }
}
```

Do not commit the populated file or put its token in a command, `.env` file or chat. The example contains placeholders only. The `registration` settings are fixed for this QA contract. Once the file is delivered, run these commands from the extracted RC8 directory. `sudo -n` requires passwordless sudo; an automation account with root privileges can run the commands directly without `sudo`.

```bash
cd /opt/jbpa/releases/jbpa-1.0.0-rc8
sudo -n install -d -o root -g root -m 0700 /etc/jbpa
sudo -n install -o root -g root -m 0600 /run/secrets/jbpa/credentials.json /etc/jbpa/credentials.json
sudo -n ./bin/jbpa-customer setup
sudo -n ./bin/jbpa-customer versions
sudo -n ./bin/jbpa-customer install --version 12.10 --non-interactive
sudo -n ./bin/jbpa-customer verify
```

`setup` checks permissions and schema without displaying the token. `12.10` resolves to the approved-for-test PA `12.10.1.1` build in this candidate. You may replace it with `latest`, but an unqualified or changed vendor build can be blocked by policy. If the supplied JSON is missing, malformed, too permissive or includes unknown keys, setup stops before installation.

## After installation and before reinstalling

`verify` should report the installed version, Harmony registration, current connection and healthy core services. Check that the agent is **Running** in the intended group in Harmony Management Console too. For a later status check, run `sudo ./bin/jbpa-customer status`. For an in-place upgrade, use `sudo ./bin/jbpa-customer upgrade --version latest` interactively or `sudo -n ./bin/jbpa-customer upgrade --version latest --yes` under automation; package-changing upgrade is not yet live-qualified.

**Check group capacity before a fresh reinstall.** JBPA's complete uninstall removes the local agent, but the current `deregisterOnDrainstop=false` setting leaves its Harmony record in the group. Reinstalling registers a new agent and can consume another group or organization slot. The installer cannot determine your licensed capacity from the VM. Review the group's agents and the organization's limit in Management Console. If the group is full, have an authorized Harmony administrator delete an unused **Stopped**, **Starting**, **Unregistered** or **Unknown** record before retrying. Prefer an in-place upgrade when the existing identity should be retained. See Jitterbit's [registration behavior](https://docs.jitterbit.com/agent/register/) and [capacity troubleshooting](https://docs.jitterbit.com/getting-started/troubleshooting/).

If installation stops, retain the private result path printed by the launcher and use the [detailed runbook](customer-install-runbook.md) for recovery. Public Java truststore certificates have a separate [enterprise procedure](runbooks/enterprise-truststore.md). SSH/SFTP keys, mTLS client certificates and corporate proxy settings are not applied by this quick path.
