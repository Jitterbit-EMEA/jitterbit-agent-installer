# Proposed configuration contract

> Phase 1.5 addendum (2026-09-22): historical Phase 0/1 content below is preserved. Current readiness and reconciled decisions are in the [Phase 1.5 summary](phase-1.5-summary.md), [dependency register](dependencies.md) and [Phase 2 specification](phase-2-implementation-spec.md). Runtime code/schemas remain Phase 1.
> The v2 registration/artifact/result contract is a [proposal](schema-change-proposal.md), not a change to implemented v1. No invented package or approval data was added.

**REASONABLE ENGINEERING DESIGN. Not an implemented schema or runnable configuration.** Initial user-selected test target: Ubuntu 22.04 / PA 12.10. Unresolved values remain null so future validation fails closed.

```yaml
schema_version: 1
agent:
  version: "12.10"
  package_kind: deb
  expected_os: {id: ubuntu, version: "22.04", architecture: x86_64}
  name: null
harmony:
  cloud_url: null
  organization: null
  environment: null
  agent_group_id: null
  agent_group_name: null
  registration:
    strategy: null
    token_secret_ref: null
    username_secret_ref: null
    password_secret_ref: null
    deregister_on_drainstop: false
secrets:
  provider: azure-key-vault
  vault_uri: null
  managed_identity_client_id: null
network:
  endpoint_profile: null
  download_proxy_profile: null
  package_proxy_profile: null
proxy:
  enabled: false
  host: null
  port: null
  username_secret_ref: null
  password_secret_ref: null
  ntlm_domain: null
  exceptions: []
ssh: {enabled: false, identities: []}
ssl: {enabled: false, identities: []}
java_trust: {enabled: false, certificates: []}
health:
  registration_timeout_seconds: 300
  poll_interval_seconds: 5
  evidence_profile: null
  require_cloud_confirmation: true
output:
  result_path: /var/lib/jitterbit-bootstrap/result.json
  log_path: /var/log/jitterbit-bootstrap.log
```

## Field semantics

| Field(s) | Contract |
| --- | --- |
| schema_version | Required supported integer; reject unknown versions/keys. |
| agent.version | Exact catalogue release or explicitly mapped approved alias. Never internet-latest. |
| package_kind / expected_os | Must match the detected machine and catalogue build. Only deb is the initial target. |
| agent.name | Desired stable identity; actual vendor naming/prefix behavior must be validated. |
| cloud_url | Explicit reviewed Harmony regional HTTPS origin, not inferred from Azure geography. |
| organization / environment | Non-secret context; validate the selected group belongs to the intended environment/organization. |
| agent_group_id / agent_group_name | Use ID for auto-registration; use verified vendor group-name representation for the config utility. Do not concatenate guessed names. |
| registration.strategy | Reviewed adapter ID selected after discovery, e.g. register-json-token only when proven for this build. No arbitrary command. |
| *_secret_ref | Opaque provider reference with secret name and optional pinned version; never inline secret values. Token and credential-pair strategies are exclusive. |
| deregister_on_drainstop | Proposed false for persistent VMs, preserving identity; still validate actual restart behavior. |
| secrets.provider / vault_uri | Provider selector and approved HTTPS vault; local assisted provider is a distinct Phase 2 adapter. |
| managed_identity_client_id | Null selects the configured system-assigned identity; explicit ID selects an assigned user identity. |
| endpoint_profile | Reviewed region/feature endpoint list including bootstrap/dependency repositories and vendor endpoints. |
| download_proxy_profile / package_proxy_profile | Separate non-secret profiles; do not map automatically into application/JVM proxy settings. |
| proxy.* | Conditional host/port and secret references; port 1–65535. Exceptions translated only through documented semantics. |
| ssh.identities | Unique id suffix, private_key_secret_ref, optional public_key_source and passphrase_secret_ref, absolute target directory. Secret-bearing passphrase persistence remains blocked. |
| ssl.identities | Unique id suffix, certificate_source, private_key_secret_ref, optional passphrase_secret_ref and absolute target directory. PEM-only for J07 adapter; validate certificate/key match and expiry. |
| java_trust.certificates | Unique alias, public certificate source, expected SHA-256 fingerprint. Discover effective runtime/store; password is a secret reference if required. |
| health.* | Positive bounded timing values, versioned reviewed evidence profile and mandatory authoritative confirmation. 300/5 are proposal defaults, not vendor promises. |
| output.* | Absolute approved locations, no symlinks or writable parents; root-restricted results/logs with no secret payloads. |

## Version catalogue proposal

```yaml
schema_version: 1
aliases: {} # Set recommended/latest-approved only after approval and validation.
versions:
  "12.10":
    approval: pending
    artifacts:
      - os_id: ubuntu
        os_version: "22.04"
        architecture: x86_64
        package_kind: deb
        package_version: null
        url: null
        sha256: null
        adapter_profile: null
        evidence_refs: [J01, J02, J14]
        runtime_validation: not_run
```

Approval and vendor support are distinct. Store exact package build, immutable URL and checksum provenance. A checksum calculated only after an untrusted download is not independent integrity evidence. Prefer an approved private mirror and trusted digest; if vendor checksums are absent, require a documented artifact-approval policy. Signed/expiring URLs are secret runtime references, not catalogue literals. Reject plain HTTP, URL userinfo and unreviewed redirect hosts. Historical/EOL entries never become approved merely because a URL is supplied.

`os-support.yaml` describes reviewed distro/version/package/release combinations and source dates. Unknown combinations stop; distro-family equivalence is insufficient. Catalogue and evidence profiles are reviewed code-adjacent policy, not free-form user input.

## Precedence and validation

Proposed precedence: explicit non-secret CLI overrides > allowlisted environment variables > parsed development `.env` > config > documented defaults. Record which source supplied each non-secret field. Permit `--version` and `JITTERBIT_AGENT_VERSION`. Never source `.env` as shell; reject expansion, commands, unknown keys and secret keys. No secret CLI overrides.

Validate structure before any secret fetch or server mutation: strict types, duplicate YAML keys, unknown keys, required conditional fields, alias resolution, compatibility, approved artifact and adapter, URL policy, unique suffixes/aliases, path safety and bounded timing. File readability/permissions and certificate parsing belong to preflight, not JSON Schema alone. Dry-run should explain unresolved references without resolving secrets.

Assisted mode should collect safe choices through a TTY and secret inputs through an approved hidden-input/provider channel, then use the same schema. Preserve the native interactive installer/configuration interface where verified. Reject interactive requests under Azure unattended dispatch.

## Result and exit-code proposal

```json
{
  "schemaVersion": 1,
  "runId": "example-only",
  "status": "FAILED",
  "stage": "HARMONY_REGISTRATION_PENDING",
  "lastCompletedStage": "AGENT_STARTED",
  "errorCode": 52,
  "message": "Registration was not confirmed before the deadline",
  "privateAgentVersion": "12.10",
  "agentInstalled": true,
  "serviceRunning": true,
  "harmonyRegistered": null,
  "retryable": false,
  "durationSeconds": 300
}
```

This is illustrative, not an execution result. Null means unknown, not false. Include hostname, OS, exact installed build, feature states (disabled/applied/failed/not_checked), changed flag, config digest and sanitized evidence references. Never hash secret values into public results. Write JSON atomically and send only sanitized progress to stderr; retain one final JSON object for the caller. PLANNED may exit 0 but is never COMPLETE/SUCCESS. The caller checks both process code and result status.

| Code | Meaning |
| --- | --- |
| 0 | Successful requested action (including explicitly labelled dry-run) |
| 2 | Invalid configuration/arguments |
| 10 / 11 | Unsupported OS/architecture / preflight failure |
| 12 / 13 | Unknown or unapproved version/profile / concurrent run |
| 20 / 21 | Download failure / integrity mismatch |
| 30 / 40 | Installation / configuration failure |
| 41 / 42 | Secret-provider failure / lifecycle action required |
| 50 / 51 / 52 | Proven Harmony authentication rejection / registration failure / confirmation timeout |
| 60 | Service failure |
| 70 / 80 / 90 | Certificate or truststore / SSH / proxy configuration failure |
| 99 | Unexpected internal failure, sanitized evidence retained |

Do not emit a precise authentication diagnosis from an ambiguous timeout or database error. On SIGTERM/interruption, preserve a failed/incomplete result where possible; orchestration must detect a missing result after SIGKILL.

## Phase 2G governed configuration

[Production](../config/examples/azure-production.example.yaml) and [QA](../config/examples/azure-qa.example.yaml) examples contain references only. The agent config remains schema version 1 with additive policy fields. `artifact_policy.require_production_approval=true` refuses the controlled-test exception; false still requires the explicit flag and does not approve production. Only the governed vendor catalogue is selected by these examples. Private Blob artifact retrieval remains the existing Managed Identity runtime provider and requires separately approved catalogue metadata.

`uninstall_policy` timeouts are consumed by `jbpa uninstall --config PATH --complete`; explicit timeout flags override config. There is no implicit force permission. `qa_policy` records sizing intent; only the existing exact controlled-test flag/tuple exception changes preflight. Setting policy text cannot bypass resource checks.

Composite `jbpa health --config PATH` accepts optional `health.profile` and requires `health.expected_identity` containing agent_id, group_id, agent_name, group_name and package_version. These are non-secret approved identity expectations. CLI identity arguments override them. Restart profiles still require an actual --since-utc boundary; rollback requires the expected original file hash. Bare health remains explicitly local-only.

The catalogue is schema version 2 with one dynamic latest source, governed static aliases, separate logical/package identity and separate artifact/runtime status. `expected_pinned_count` is governed catalogue data: initially 19. Future onboarding increments it along with the new entry, so compatible releases require no core source change. Exact package filenames, URL suffixes and legacy runtime artifact projections must agree. Intake never overwrites a governed hash, alias or qualification.

The RC production facade requires all three governed signals: approval=approved, artifact_status=PRODUCTION_APPROVED and integrity.classification=INDEPENDENTLY_VERIFIED, plus exact tested runtime/platform qualification. Editing only a legacy approval flag cannot promote the locally calculated QA digest. These catalogue changes require governance review; no intake or latest observation performs them.
