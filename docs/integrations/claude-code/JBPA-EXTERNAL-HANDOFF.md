# External AI → JBPA handoff

**JBPA DOES NOT CREATE VIRTUAL MACHINES.** Boundary: `VM_ALREADY_PROVISIONED → JBPA → JITTERBIT_PRIVATE_AGENT_CONFIGURED_AND_HEALTHY → exit code + result.json`.

The infrastructure AI owns VM provisioning, OS image, sizing, disks, networking, firewalls, identity attachment, remote execution and release/config delivery. JBPA owns host readiness, PA version/artifact validation, dependency preparation, Private Agent install and configuration, secret resolution, registration, Harmony authentication, Agent Services, synchronization, health, drain, local uninstall and first-class reinstall. This boundary is independent of Azure subscription/resource-group/VNet details. The [canonical repository contract](../../external-orchestrator-contract.md) is authoritative.

```text
JBPA(host, operation, config, pa_version, qualification_policy)
  -> { process_exit_code, result_json }

install_private_agent(host, config, pa_version="12.10", allow_unqualified=false)
reinstall_private_agent(host, config, pa_version)
get_private_agent_health(host, config)
uninstall_private_agent(host, config)
```

Infrastructure provisioning is not an argument to JBPA. These signatures describe the integration; the concrete contract is the [handoff request schema](../../../tools/handoff/request.schema.json) and the [RC3 result schema](../../../config/schemas/rc-result.schema.json).

## Request and operation mapping

The request supplies `target`, `operation`, `jbpaVersion`, `paVersion`, absolute on-host `configPath` and fresh `resultPath`, `allowUnqualified`, and optional `controlledTest`. Release location and pinned digest are delivery arguments. See [INSTALL](examples/install-request.json), [REINSTALL](examples/reinstall-request.json), [UNINSTALL](examples/uninstall-request.json), [HEALTH](examples/health-request.json) and the [generic example](../../../examples/external-handoff.example.json). The HEALTH example requires `health.expected_identity` to be populated in `agent.yaml` from the observed registered agent before execution; the example identity is deliberately not fabricated.

| Request | One RC3 command | Meaning |
| --- | --- | --- |
| INSTALL | `jbpa install --config PATH --version VERSION --non-interactive --result-file FILE` | Clean-host install, registration, initial sync, health |
| REINSTALL | `jbpa reinstall --config PATH --version VERSION --non-interactive --result-file FILE` | JBPA handles drain, uninstall, clean host, fresh install and registration |
| UNINSTALL | `jbpa uninstall --config PATH --complete --result-file FILE` | Graceful complete *local* removal; Harmony-side deletion is separate |
| HEALTH | `jbpa health --config PATH --result-file FILE` | Composite health when config has `health.expected_identity` |
| DIAGNOSTICS | `jbpa diagnostics --result-file FILE` | Non-secret observations; not a health pass |
| Validate | `jbpa validate --config PATH --version VERSION --profile INSTALL --result-file FILE` | Read-only canonical preflight; profile also accepts REINSTALL, HEALTH or UNINSTALL |

The packaged CLI is `bin/jbpa` inside RC3. With the established bootstrap/SSH delivery layout the actual executable is `/opt/jbpa/releases/4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e/bin/jbpa`; a managed fleet may place the verified bundle elsewhere. Check the installed path and manifest rather than assuming `/opt/jbpa/bin/jbpa`. RC3 `--help` prints the command list, while operation flags are defined by its packaged parsers and documented in the [runbook](JBPA-OPERATOR-RUNBOOK.md).

## Delivery patterns

**A — preinstalled release:** The host already has a verified RC3 under `/opt/jbpa`. The external tool verifies the installed release/archive and invokes the actual executable. Use this for managed fleets.

**B — runtime delivery:** The external tool copies or downloads RC3 to a private host stage, checks the independently supplied archive hash *before* extraction, checks manifest/version/file hashes, creates the Python environment from an approved index, delivers private `agent.yaml`, then invokes JBPA. The archive is immutable. Claude Code itself is not installed on the target VM.

The [Phase 3D SSH adapter](../../../tools/handoff/README.md) illustrates pattern B for controlled Ubuntu 22.04 INSTALL and REINSTALL only. It requires a pinned SSH host key, does not use automatic host-key trust, verifies the release again on the guest, bounds result retrieval to 1 MiB, and invokes one lifecycle operation per request. This SSH execution transport is unrelated to Jitterbit `[SSH]`/SFTP enterprise configuration. Its synthetic tests do not prove a live external handoff; GATE-13 is still pending.

## Secrets and qualification

`agent.yaml` holds secret **references**, not values. For Azure Key Vault, the existing VM must already have Managed Identity and required vault access. JBPA validates IMDS, fetches the referenced values and redacts its outputs. The caller never passes a Harmony token directly or stores it in request JSON.

For a currently unqualified tuple, `allowUnqualified=true` is allowed only with `controlledTest=true` and explicit controlled-test authorization. The CLI forwards `--controlled-test --allow-unqualified` once. This bypasses qualification policy only; it does not waive OS, architecture, readiness, artifact hash, configuration, secret-provider, registration or health checks. PA 12.10.1.1 on Ubuntu 22.04 remains unqualified pending live proof. Its artifact hash `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8` remains QA_TEST_ONLY / LOCALLY_CALCULATED.

## Result consumption

The external caller uses the process exit code and a **fresh result file**. It validates [schema 1.0](../../../config/schemas/rc-result.schema.json), verifies operation and release match the request, and then consumes generic fields. `status=SUCCESS` alone is insufficient if the exit is nonzero, category is not SUCCESS or `error` is present. `details` carries JBPA-owned lifecycle observations; the external caller must not reinterpret vendor logs to supplement it. The [success example](examples/result-success.json) is synthetic shape-only data, not evidence of a live run.

```python
exit_code = execute_jbpa_once(request)
raw = retrieve_fresh_result(request["resultPath"], max_bytes=1_048_576)
payload = validate_json_schema(raw, "config/schemas/rc-result.schema.json")
assert payload["operation"] == request["operation"]
assert payload["versions"]["jbpa"] == request["jbpaVersion"]
success = (exit_code == 0 and payload["status"] == "SUCCESS"
           and payload["category"] == "SUCCESS" and payload["error"] is None)
if not success:
    return {"status": "FAILED", "category": payload["category"],
            "state": payload["state"],
            "retryable": bool(payload["error"] and payload["error"]["retryable"])}
return {"status": "SUCCESS", "result": payload}
```

On nonzero exit, still retrieve the result if present. A missing result is a handoff/integration failure; invalid schema is a release-compatibility failure. `status=FAILED` means report JBPA's `category`, `state` and `error.retryable`. Host unreachable and release delivery failure belong to the external orchestrator. Do not blindly retry a mutation: an interrupted INSTALL or registration can leave partial state. Recheck preflight/host state and use JBPA's retryability classification. An artifact hash mismatch is a stop, not a retry-as-success; unsupported architecture requires infrastructure change. A temporary package-manager lock may become retryable only after the lock clears and JBPA revalidates.

## Claude Code modes

Use `claude` then `/jbpa install` for interactive development on the engineer's machine. If Claude Code itself runs non-interactively, [print mode](https://code.claude.com/docs/en/headless) supports `claude -p "<instruction>" --output-format json`. That JSON is Claude Code's response wrapper, **not** the JBPA result contract. Production orchestration should consume JBPA exit and result JSON directly, not natural-language Claude output. [Claude Code project instructions](https://code.claude.com/docs/en/memory) load from `CLAUDE.md`; [skills](https://code.claude.com/docs/en/skills) load on demand. No Claude Code installation is needed on the PA VM.
