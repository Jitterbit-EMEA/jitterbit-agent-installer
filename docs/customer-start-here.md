# Install a Private Agent on a fresh VM

This guide uses the **RC9 QA candidate** on **Ubuntu 24.04 amd64**. The VM needs `sudo`, outbound access to Ubuntu packages, the Jitterbit download endpoint and Harmony, and at least 4 vCPUs, 8 GB RAM and 50 GB disk. RC9 has offline validation but has **not** had a live installation test; the earlier RC7 interactive install was live-tested on this QA platform. Neither release is approved for production or qualified on Ubuntu 22.04.

Choose **A** for guided input at a terminal. Choose **B** when your administrator or secret manager supplies one protected JSON document. The bundled `jbpa-install` script prepares Python, checks the JSON, shows or selects a version, runs preflight and installation, then verifies the result. No result filename or Python command is needed.

## 1. Put the release in the VM user's home directory

First, copy **a version of the installer archive and its matching `.sha256` file** to `/home/{user}/` on the VM (for example, `/home/azureuser/`). Your organization may use `scp`, SFTP, a managed file-transfer service, or another approved method. The steps on the VM are the same whichever transfer method you use. Obtain the expected checksum through a trusted release channel.

If you use `scp`, run this example from the repository root on the computer holding RC9. Replace the VM user and host. The destination is explicitly `/home/${VM_USER}/`:

```bash
VM_USER='your-vm-user'
VM_HOST='your-vm-address'
scp dist/jbpa-1.0.0-rc9.tar.gz dist/jbpa-1.0.0-rc9.tar.gz.sha256 "${VM_USER}@${VM_HOST}:/home/${VM_USER}/"
ssh "${VM_USER}@${VM_HOST}"
```

If the files were delivered by another method, SSH into the VM as that user and start here. Run the remaining commands **on the VM**. For a standard Ubuntu account, `$HOME` is `/home/{user}`. Stop if the checksum does not print `OK`. The installer checks OS, architecture and resources during preflight.

```bash
cd "$HOME"
sha256sum --check jbpa-1.0.0-rc9.tar.gz.sha256
sudo install -d -m 0755 /opt/jbpa/releases
sudo tar -xzf jbpa-1.0.0-rc9.tar.gz -C /opt/jbpa/releases
cd /opt/jbpa/releases/jbpa-1.0.0-rc9
```

The archive is the documented delivery route; this development repository has no published customer clone URL. Run each command in order and stop if it fails.

## A. Guided interactive installation

```bash
sudo ./bin/jbpa-install
```

The script asks for the registration token in a **hidden prompt**, then the Harmony cloud URL (`https://...`), numeric agent group ID and agent name prefix. It stores them together in one root-only `/etc/jbpa/credentials.json`. It lists the governed JBPA catalogue and asks you to choose a version; press Enter for `latest` or type `12.10` for the known PA 12.10.1.1 build. The catalogue is not every Jitterbit release, and listing does not grant production approval. At the install prompt, review the exact package version and SHA-256, then type `INSTALL`. The script checks the installed package, connection and services before declaring success.

To preselect a version, run `sudo ./bin/jbpa-install --version 12.10`. To check the agent later, run `sudo ./bin/jbpa-customer status`.

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

Do not commit the populated file or put its token in a command, `.env` file or chat. The example contains placeholders only. The `registration` settings are fixed for this QA contract. Once the file is delivered, run this one command from the extracted RC9 directory. The source must be an absolute path to a private regular file (`0600`), with no symlink. The script validates it and securely imports it to `/etc/jbpa/credentials.json` without printing the token. `sudo -n` requires passwordless sudo; an automation account already running as root can omit it.

```bash
sudo -n ./bin/jbpa-install --non-interactive --credentials-file /run/secrets/jbpa/credentials.json --version 12.10
```

`12.10` resolves to the approved-for-test PA `12.10.1.1` build in this candidate. You may replace it with `latest`, but an unqualified or changed vendor build can be blocked by policy. If the supplied JSON is missing, malformed, too permissive or includes unknown keys, the script stops before installation. If `/etc/jbpa/credentials.json` is already staged, omit `--credentials-file` and the script will validate and use it.

## After installation and before reinstalling

The installer script reports the installed version, Harmony registration, current connection and healthy core services. Check that the agent is **Running** in the intended group in Harmony Management Console too. For a later status check, run `sudo ./bin/jbpa-customer status`; for a repeat evidence check, run `sudo ./bin/jbpa-customer verify`. For an in-place upgrade, use `sudo ./bin/jbpa-customer upgrade --version latest` interactively or `sudo -n ./bin/jbpa-customer upgrade --version latest --yes` under automation; package-changing upgrade is not yet live-qualified.

**Check group capacity before a fresh reinstall.** JBPA's complete uninstall removes the local agent, but the current `deregisterOnDrainstop=false` setting leaves its Harmony record in the group. Reinstalling registers a new agent and can consume another group or organization slot. The installer cannot determine your licensed capacity from the VM. Review the group's agents and the organization's limit in Management Console. If the group is full, have an authorized Harmony administrator delete an unused **Stopped**, **Starting**, **Unregistered** or **Unknown** record before retrying. A detected limit error is reported as `AGENT_CAPACITY_REACHED`; the script also prints the private result path. Prefer an in-place upgrade when the existing identity should be retained. See Jitterbit's [registration behavior](https://docs.jitterbit.com/agent/register/) and [capacity troubleshooting](https://docs.jitterbit.com/getting-started/troubleshooting/).

If installation stops, retain the private result path printed by the launcher and use the [detailed runbook](customer-install-runbook.md) for recovery. Public Java truststore certificates have a separate [enterprise procedure](runbooks/enterprise-truststore.md). SSH/SFTP keys, mTLS client certificates and corporate proxy settings are not applied by this quick path.
