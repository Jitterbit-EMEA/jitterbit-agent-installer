# JBPA operator runbook for external AI

**JBPA DOES NOT CREATE VIRTUAL MACHINES.** This runbook begins at `VM_ALREADY_PROVISIONED`. The infrastructure AI owns VM/OS/network/disk/identity/access/release delivery. JBPA owns all Private Agent work and returns exit code plus schema 1.0 result JSON.

## Prerequisites

Use a supported pre-provisioned Linux/architecture with root or approved `sudo`, working package repositories, CPU/memory/disk, DNS, time synchronization and outbound endpoints. The RC3 runtime needs Python 3.10+, venv and an approved dependency index for setup. Azure Key Vault requires Managed Identity already attached and granted secret-read access. Read the [host contract](../../pre-provisioned-host-contract.md). Never infer readiness from VM creation success; run JBPA preflight.

For this development target, logical PA is `12.10`, resolved package `12.10.1.1` amd64. Its hash `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8` is QA_TEST_ONLY / LOCALLY_CALCULATED. It is not a production-approved artifact. Ubuntu 22.04 qualification is pending. Do not treat these instructions as production approval.

## Release verification and deployment

Immutable RC3 is `dist/jbpa-1.0.0-rc3.tar.gz`. Before any extraction or execution on the guest:

```bash
sha256sum jbpa-1.0.0-rc3.tar.gz
```

Require exact SHA-256 `4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e`; otherwise stop `JBPA_RELEASE_HASH_MISMATCH`. Verify the bundled manifest and file hashes using the release tooling. Do not rebuild or alter RC3.

Pattern A: an approved fleet image already has the verified bundle under `/opt/jbpa`; check the actual executable path and installed file hashes, then invoke it. Pattern B: deliver RC3 at runtime to a private stage, verify the archive and manifest, create `.venv` from an approved Python index, and place the config privately. The [Phase 3D SSH reference](../../../tools/handoff/README.md) performs those steps for controlled Ubuntu 22.04 INSTALL/REINSTALL. The [release bootstrap](../../../azure/custom-script/release-bootstrap.sh) is an INSTALL bootstrap that immediately invokes INSTALL; it is not a general all-operation launcher. Neither path provisions infrastructure or installs Claude Code on the guest.

The RC3 archive contains `bin/jbpa`. The established bootstrap/SSH delivery location is:

```text
/opt/jbpa/releases/4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e/bin/jbpa
```

Use that path only when delivery actually used this layout. The examples below set `jbpa` to this verified executable. Create a private `/var/lib/jbpa/results` owned by the execution identity; choose a **new filename for every command** because result creation refuses an existing file.

```bash
jbpa=/opt/jbpa/releases/4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e/bin/jbpa
```

## Config preparation and secrets

Start from [INSTALL template](../../../examples/agent.install.example.yaml) or [REINSTALL template](../../../examples/agent.reinstall.example.yaml), both based on the real `agent.schema.json`. Replace example vault URI and secret reference names with approved references. The YAML is not executable as-is. `agent.yaml` contains references, **never the Harmony token or other secret values**. The existing VM must have the correct Managed Identity and Key Vault access. JBPA retrieves and validates those values. Do not copy credentials into a handoff request or Claude prompt.

The template uses `health.expected_identity` only after the agent has registered. For a later composite HEALTH request, populate that schema field with the observed `agent_id`, `group_id`, `agent_name`, `group_name`, and `package_version`, and set `health.profile: STEADY_STATE_EXISTING_AGENT`. Do not invent an identity. `health --config` fails if this field is absent. The plain `health` command without config is LOCAL_ONLY and does not prove Harmony identity.

## Validate

Run before any mutation on an unknown host. The CLI profile can be INSTALL, REINSTALL, HEALTH or UNINSTALL.

```bash
sudo "$jbpa" validate --config /etc/jbpa/agent.yaml --version 12.10 --profile INSTALL \
  --result-file /var/lib/jbpa/results/validate-install-new.json
```

Inspect `details.preflight`: overall `PASS`, `PASS_WITH_WARNINGS` or `FAIL`; `checks` with statuses `PASS`, `WARN`, `FAIL`, `NOT_APPLICABLE`, `UNCONFIRMED`; `hostState`; and `platform`. Preflight covers OS, architecture, privilege, package manager/repositories, CPU, memory, disk, DNS, time, network, secret provider and existing Jitterbit state. Any blocking FAIL or UNCONFIRMED prevents mutation. Review warnings explicitly. INSTALL expects a clean host; REINSTALL expects an installed/registered agent. `--dry-run` may leave checks UNCONFIRMED and is not live readiness proof.

## Install

```bash
sudo "$jbpa" install --config /etc/jbpa/agent.yaml --version 12.10 --non-interactive \
  --result-file /var/lib/jbpa/results/install-new.json
```

JBPA owns artifact resolution and hash/DEB metadata checks, dependencies, package install, `register.json` handling, secret retrieval, fresh registration, Harmony authentication, Agent Services, initial synchronization and health. Caller code must not invoke `dpkg`, `jitterbit-config` or registration logic. Require exit 0 and schema-valid `operation=INSTALL`, `status=SUCCESS`, `category=SUCCESS`, `error=null`; verify requested/resolved PA versions. Save the fresh result. Do not use stdout prose as the success signal.

## Controlled qualification

Only for an explicitly authorized non-production test of an unqualified tuple, use both flags. Ubuntu 22.04/PA 12.10.1.1 still requires this until source qualification is promoted in a later release.

```bash
sudo "$jbpa" install --config /etc/jbpa/agent.yaml --version 12.10 --non-interactive \
  --controlled-test --allow-unqualified \
  --result-file /var/lib/jbpa/results/install-controlled-new.json
```

`--allow-unqualified` bypasses qualification policy **only**. It does not bypass artifact integrity/approval classification, OS, architecture, preflight, config, secret provider, registration or health. A QA-only artifact still requires controlled-test policy. Do not mark a tuple TESTED_LIVE based on a dry run or synthetic caller test.

## Health and diagnostics

After adding observed `health.expected_identity` to the private config, run composite health:

```bash
sudo "$jbpa" health --config /etc/jbpa/agent.yaml \
  --result-file /var/lib/jbpa/results/health-new.json
```

JBPA interprets product services, connection-check, registration identity and profile-specific synchronization; the caller only reads the result. Diagnostics gathers non-secret observations and may contain unknowns; it is not a health pass:

```bash
sudo "$jbpa" diagnostics --result-file /var/lib/jbpa/results/diagnostics-new.json
```

## Reinstall

Run `validate --profile REINSTALL` first and require `AGENT_INSTALLED_REGISTERED`. Preserve previous INSTALL evidence. Invoke **one first-class command**:

```bash
sudo "$jbpa" reinstall --config /etc/jbpa/agent.yaml --version 12.10 --non-interactive \
  --controlled-test --allow-unqualified \
  --result-file /var/lib/jbpa/results/reinstall-new.json
```

The two qualification flags above are for the explicitly authorized Ubuntu 22.04 controlled run against immutable RC3; omit them for a qualified, approved tuple. JBPA handles active-operation query, drain-pause/poll/drain-stop, local uninstall, clean-host check, fresh install, fresh registration, initial synchronization and health. The caller must not chain UNINSTALL and INSTALL. Do not blindly retry after a timeout; inspect the result and current host state first.

## Uninstall

```bash
sudo "$jbpa" uninstall --config /etc/jbpa/agent.yaml --complete \
  --result-file /var/lib/jbpa/results/uninstall-new.json
```

JBPA performs graceful drain and complete **local** PA removal; it leaves JBPA framework/state available. Harmony-side agent record deletion is separate and not automated. `--force` is a distinct operator decision after graceful failure; never add it implicitly. Do not remove `/opt/jitterbit`, user accounts or packages from caller code.

## Enterprise truststore

Configure the real schema's `java_trust` branch only with an approved public PEM and expected fingerprint/hash. Use the [truststore runbook](../../runbooks/enterprise-truststore.md) for alias collision, private backup, one import/restart, mandatory health and rollback. True custom-CA qualification remains pending; a CA:FALSE endpoint certificate does not prove it. SSH/SFTP, mTLS and proxy enterprise branches remain deferred under their separate test-material requirements. JBPA configuration here is distinct from SSH as a *remote execution transport*.

## Result handling, retries and failures

For each invocation, retain process exit and the newly created result file. Validate [RC3 result schema](../../../config/schemas/rc-result.schema.json), requested operation/release, `status`, `category`, `state`, and `error.retryable`. Success requires exit 0, status SUCCESS, category SUCCESS and null error. On nonzero exit retrieve result if present. Missing result or invalid schema is an integration failure, not PA success. Follow JBPA's error classification; do not blindly retry an interrupted mutation. A package-manager lock may clear; artifact hash mismatch must stop; unsupported architecture needs a different host; registration failures need JBPA result and host-state review. See [troubleshooting](JBPA-TROUBLESHOOTING.md).

## Security and support evidence

Never put secret values in handoff JSON; put registration tokens in Claude prompts; paste `credentials.txt` or token-bearing `register.json`; commit SSH keys or live value-bearing config; disable release/artifact hash checks; or ask the caller to grep vendor logs/TranDb. Use private config/result directories, pinned RC3 digest and pinned SSH host keys. Keep any vendor-log interpretation in JBPA. For support, share only sanitized structured results, non-secret host preflight, delivery digests, operation timing, and JBPA-generated sanitized evidence. Do not send raw credential files.

## Upgrade or new PA version

Review the governed [version qualification matrix](../../version-qualification-matrix.md), exact package metadata and artifact provenance. Qualify a new PA/OS tuple on a controlled host before updating source qualification. Compatible contracts do not require a new lifecycle adapter; incompatible ones require review. RC3 itself remains immutable. Production artifact approval and production sizing are separate gates.
