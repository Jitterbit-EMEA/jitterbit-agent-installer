# Customer runbook: install or upgrade a Jitterbit Private Agent

For the current RC8 fresh-VM command sequence, including one-file JSON credentials, interactive and non-interactive installation, and one-command verification, start with [Install a Private Agent on a fresh VM](customer-start-here.md). The detailed commands below preserve the manually tested RC5 path and are useful for review or troubleshooting.

This guide is for an already provisioned Ubuntu VM. Give the customer this runbook alongside the RC5 archive; the archive was built before this guide was written. You need a Linux login with `sudo`, a Harmony registration token, your Harmony cloud URL, the numeric agent group ID, and internet access to the Jitterbit download and Harmony endpoints. JBPA does not create the VM or the Harmony token.

**Current scope:** RC5 and PA 12.10.1.1 are controlled QA releases, not production approved. The complete local-file interactive install passed on Ubuntu 24.04 amd64. Ubuntu 22.04 and a package-changing upgrade remain unqualified live. The commands use `--controlled-test` for this reason. Use them only on a disposable, non-production host until the release and your environment receive approval.

Run the numbered steps in one VM terminal session. Replace the example values in the delivery commands with your own. Each JBPA command prints JSON. A successful operation needs both exit code zero and top-level `"status": "SUCCESS"`.

## 1. Deliver the tool

**Recommended: copy the release archive.** Ask the distributor for `jbpa-1.0.0-rc5.tar.gz` and its SHA-256 through an independent trusted channel. From your administrator computer, after checking the VM's SSH host key, you can use:

```bash
VM_USER='replace-with-vm-user'
VM_HOST='replace-with-vm-host'
scp /path/to/jbpa-1.0.0-rc5.tar.gz "$VM_USER@$VM_HOST:/home/$VM_USER/"
ssh "$VM_USER@$VM_HOST"
```

An approved upload portal works too. The archive can be staged in your VM home directory; the extracted tool will live under `/opt/jbpa/releases`.

**Git alternative:** when your organization publishes an approved repository URL and immutable tag, clone that tag and use its versioned archive from `dist`:

```bash
APPROVED_TAG='replace-with-approved-tag'
REPOSITORY_URL='replace-with-approved-repository-url'
git clone --branch "$APPROVED_TAG" "$REPOSITORY_URL" jbpa-source
cp jbpa-source/dist/jbpa-1.0.0-rc5.tar.gz "$HOME/"
```

Then continue at step 2. This working project has no configured Git remote or published customer tag, so those placeholders cannot yet be replaced with a verified customer URL. The clone must contain the reviewed archive; a development checkout alone is not a verified release.

## 2. Verify, extract, and enter the tool directory

These commands assume the RC5 archive is in your home directory. The digest shown is for this exact RC5 archive; confirm it independently with its distributor.

```bash
cd "$HOME"
printf '%s  %s\n' '099b7d577add54d7b552b97e038b8ce2d299cbb5bd02c3e6872afab166e72aec' jbpa-1.0.0-rc5.tar.gz | sha256sum --check -
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip
sudo install -d -m 0755 /opt/jbpa/releases
sudo tar -xzf jbpa-1.0.0-rc5.tar.gz -C /opt/jbpa/releases
cd /opt/jbpa/releases/jbpa-1.0.0-rc5
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements.txt
./bin/jbpa version
```

The checksum must print `OK`; otherwise stop. Python dependencies need an approved package index or offline wheel mirror. If you reconnect later, return with `cd /opt/jbpa/releases/jbpa-1.0.0-rc5` before using the relative commands below.

## 3. List and select PA versions

```bash
./bin/jbpa versions
./bin/jbpa version resolve latest
```

The first command lists 19 catalogue versions, including their approval and qualification states. A listed release is not automatically approved for installation. The second downloads and inspects the current mutable `latest` package without installing it. The steps below select `latest`; you can replace it with a qualified listed logical version such as `12.10`. Do not use `--allow-unqualified` merely to force a customer install.

## 4. Create the local configuration

JBPA reads `/etc/jbpa/agent.yaml` and protected files under `/etc/jbpa/secrets`. It does **not** read a `.env` file. The YAML contains references, never the token value.

```bash
sudo install -d -m 0700 /etc/jbpa/secrets /var/lib/jbpa/results
sudo install -m 0600 config/examples/local-file-qa.example.yaml /etc/jbpa/agent.yaml
sudoedit /etc/jbpa/agent.yaml
```

In the editor, check `agent.expected_os` against `cat /etc/os-release` and `uname -m`. The example expects Ubuntu 24.04 amd64 and PA 12.10. Keep `secrets.provider: local-file`, `secrets.directory: /etc/jbpa/secrets`, and the seven `registration_field_refs`. The cloud URL, group ID and agent name prefix are supplied by the protected files in the next step; their YAML fields are intentionally `null`. Save and close the editor.

## 5. Enter the Harmony details without displaying the token

Paste the **whole block** below into the VM terminal. It asks for four values; the token is hidden while you type. It writes seven root-owned files with mode `0600`. If any file exists, it stops without overwriting it. Use your organization's credential rotation procedure to change existing files.

```bash
sudo python3 - <<'PY'
from getpass import getpass
from pathlib import Path
import os
import re

directory = Path('/etc/jbpa/secrets')
if directory.is_symlink():
    raise SystemExit('Secret directory must not be a symbolic link.')
directory.mkdir(parents=True, exist_ok=True)
os.chown(directory, 0, 0)
os.chmod(directory, 0o700)
with open('/dev/tty', 'r') as terminal_input, open('/dev/tty', 'w') as terminal_output:
    def ask(label, hidden=False):
        if hidden:
            value = getpass(label + ': ', stream=terminal_output)
        else:
            terminal_output.write(label + ': ')
            terminal_output.flush()
            value = terminal_input.readline().rstrip('\n')
        if not value or '\n' in value or '\r' in value:
            raise SystemExit('Missing or invalid value; no files written.')
        return value
    token = ask('Harmony registration token (hidden)', hidden=True)
    cloud_url = ask('Harmony cloud URL beginning with https://')
    group_id = ask('Numeric agent group ID')
    prefix = ask('Agent name prefix')
if not cloud_url.startswith('https://') or not group_id.isdigit() or int(group_id) < 1:
    raise SystemExit('Invalid URL or group ID; no files written.')
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', prefix):
    raise SystemExit('Invalid agent name prefix; no files written.')
values = {
    'pa-registration-token': token,
    'pa-cloud-url': cloud_url,
    'pa-agent-group-id': group_id,
    'pa-agent-name-prefix': prefix,
    'pa-deregister-on-drainstop': 'false',
    'pa-retry-count': '10',
    'pa-retry-interval-seconds': '5',
}
if any((directory / name).exists() or (directory / name).is_symlink() for name in values):
    raise SystemExit('An existing credential file was found; nothing overwritten.')
for name, value in values.items():
    path = directory / name
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        output.write(value)
    os.chown(path, 0, 0)
    os.chmod(path, 0o600)
print('Seven protected files created; values were not displayed.')
PY
sudo find /etc/jbpa/secrets -maxdepth 1 -type f -printf '%u:%g %m %f\n' | sort
```

The last command must show seven `root:root 600` files. Your secret manager may create the same files instead of using the prompts. Azure Key Vault is one possible delivery source, not a requirement for this local-file installation.

## 6. Preflight the VM and configuration

```bash
sudo ./bin/jbpa validate --config /etc/jbpa/agent.yaml --controlled-test
```

Continue only when the JSON's `details.status` is `PASS` or `PASS_WITH_WARNINGS`, and understand every warning. The QA VM used an explicit two-CPU test exception. `FAIL` or a nonzero exit means stop and correct the issue. Preflight does not install PA.

## 7. Install PA: choose one command

For a person at a terminal, use **interactive** mode. It displays exact package version, SHA-256, qualification and config path, then asks you to type `INSTALL`:

```bash
sudo ./bin/jbpa install --interactive --config /etc/jbpa/agent.yaml --version latest --controlled-test --result-file /var/lib/jbpa/results/customer-install.json
```

For an already-reviewed unattended run, use **non-interactive** mode instead:

```bash
sudo ./bin/jbpa install --non-interactive --config /etc/jbpa/agent.yaml --version latest --controlled-test --result-file /var/lib/jbpa/results/customer-install.json
```

Run only one install command, on a clean host. It downloads, verifies, installs, registers, and checks PA; allow several minutes. Use a **new result filename on every run** because JBPA never overwrites a result file. If PA is already installed, use the upgrade procedure below instead.

## 8. Verify the result

```bash
sudo python3 -c 'import json; d=json.load(open("/var/lib/jbpa/results/customer-install.json")); print("status:", d["status"], "state:", d["state"], "PA:", d["versions"]["resolvedPA"], "Harmony registered:", d["registration"]["harmonyRegistered"]); assert d["status"] == "SUCCESS" and d["registration"]["harmonyRegistered"] is True'
dpkg-query -W jitterbit-agent
sudo ./bin/jbpa health
```

The result must report `SUCCESS` and `Harmony registered: True`. `dpkg-query` shows the installed build. Bare `health` checks local service state only; it does not establish Harmony identity. Confirm the new agent and group in the Harmony Management Console. See the live QA run (source repository) for observed output.

## 9. Upgrade an existing PA later

```bash
cd /opt/jbpa/releases/jbpa-1.0.0-rc5
dpkg-query -W jitterbit-agent
./bin/jbpa version resolve latest
sudo ./bin/jbpa upgrade --config /etc/jbpa/agent.yaml --version latest --non-interactive --controlled-test --result-file /var/lib/jbpa/results/customer-upgrade.json
```

Use a new result filename for each attempt. If latest equals the installed build, the result is `ALREADY_CURRENT` and `changed: false`. For a newer same-major approved build, JBPA checks existing health and identity, makes a private configuration backup, drains operations, installs the inspected package, restores changed settings, and verifies identity/health. Downgrades, major-version changes and unknown or unqualified latest builds stop for review. The no-op upgrade passed on the QA VM; a real package-changing upgrade has offline tests but is **not yet live-qualified**. Inspect its result and confirm the agent in Harmony again.

## 10. Certificates, SFTP, SSL and proxy

Keep `ssh.enabled`, `ssl.enabled`, `java_trust.enabled` and `proxy.enabled` set to `false` for the basic run above. These are YAML settings, not `.env` variables.

| Need | Current procedure |
| --- | --- |
| Public CA or explicitly trusted endpoint certificate for Java connections | Use the separate [enterprise truststore runbook](runbooks/enterprise-truststore.md) **after registration**. Stage the public PEM, set `java_trust.certificates` with absolute path, alias and fingerprint, then dry-run and apply with verified agent identity and a protected truststore password. The existing live test covered an endpoint certificate, not a true custom CA. |
| SFTP/SSH private key | The YAML schema has `ssh.identities`, but the runtime currently blocks this branch. `ssh.enabled: true` does not install keys. Use a separately approved Jitterbit procedure until implemented and tested. |
| SSL/mTLS client certificate and key | The YAML schema has `ssl.identities`, but the runtime currently blocks this branch. `ssl.enabled: true` does not configure mTLS. |
| Corporate proxy | The current token-registration path is incompatible with enabled proxy; JBPA fails closed. A proxy-dependent VM needs a separately reviewed registration path. |

If SFTP keys, mTLS or a proxy are mandatory, RC5 is **not yet an automatic end-to-end installer for that environment**. Never paste private keys or passphrases into YAML or Git. See the [readiness matrix](production-readiness.md).

## When a command fails

Read the JSON `error` and `details`, then inspect state before retrying. `CONFIG_INVALID` points to YAML or local files, `VERSION_NOT_QUALIFIED` to the release/OS qualification, and `RESULT_WRITE_FAILED` to the private result directory or a reused filename. Run `sudo ./bin/jbpa diagnostics` for installed version, identity, connection and service observations without printing the token. A partial install is not a reason to blindly run install again; follow the [uninstall](runbooks/uninstall.md) or [reinstall](runbooks/reinstall.md) procedure only after checking product state and active operations.
