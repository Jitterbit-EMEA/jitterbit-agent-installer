# External orchestrator contract

JBPA does not provision VMs. The product boundary is `PRE_PROVISIONED_HOST → JBPA_HANDOFF → JBPA_EXECUTION → JBPA_RESULT`. The external tool creates and prepares the host, supplies access and delivers the release/configuration. JBPA independently manages the Private Agent on that host. This boundary applies to Azure, AWS, VMware, on-premises VMs and physical Linux hosts meeting the supported runtime contract.

## Caller responsibilities

The caller owns OS selection, VM creation, sizing, disks, networking, firewalls, routing, DNS, time synchronization, host access, cloud identity/RBAC, remote execution and release delivery. Subscription, resource group, VNet, subnet, region, NIC, public IP, VM SKU and disk SKU are never mandatory JBPA installation inputs. They may be optional diagnostic metadata.

For Azure Key Vault the caller attaches Managed Identity and grants least-privilege secret access before handoff. JBPA performs IMDS authentication, Key Vault retrieval, validation and redaction. The caller supplies secret references in agent configuration and does not need Harmony token values.

## Host preconditions

See the [pre-provisioned host contract](pre-provisioned-host-contract.md). The caller provides supported Linux/architecture, root or sudo execution, working package manager and repositories, adequate CPU/memory/disk/free space, DNS, sufficiently synchronized time for TLS and outbound connectivity. Bootstrap additionally needs Python 3.10+, venv and an approved Python dependency index. Identity and access to configured secret providers must already exist. JBPA reports observed checks and failure reasons; unobserved checks cannot be treated as PASS.

## Handoff request 1.0

The external request schema is [request.schema.json](../tools/handoff/request.schema.json). This tooling schema is excluded from the on-host release. Agent configuration remains version 1 and runtime results remain schema 1.0; the request references these existing contracts rather than copying agent configuration or infrastructure schemas.

```json
{
  "schemaVersion": "1.0",
  "target": "localhost",
  "operation": "INSTALL",
  "jbpaVersion": "1.0.0-rc3",
  "paVersion": "12.10",
  "allowUnqualified": false,
  "configPath": "/etc/jbpa/agent.yaml",
  "resultPath": "/var/lib/jbpa/new-result.json"
}
```

`target` is a transport execution target, not infrastructure configuration. LOCAL requires `localhost`. Paths are absolute on the executing host. `callerMetadata` optionally carries string-valued diagnostic labels; never credentials. `controlledTest` defaults false. `allowUnqualified` defaults false but must be explicitly serialized; true is permitted only for explicit controlled INSTALL or REINSTALL testing and forwards the flag exactly once. It bypasses qualification policy alone, with audit metadata under `details.qualification`. Archive location and independently approved digest are delivery arguments, separate from lifecycle configuration. The harness accepts rc2 and rc3; capabilities differ by release. REINSTALL requires rc3.

## Operations and runtime invocation

| Request operation | Existing command | Conditions |
| --- | --- | --- |
| INSTALL | `jbpa install --config PATH --version VERSION --non-interactive --result-file RESULT` | Artifact policy and strict initial registration/health apply |
| HEALTH | `jbpa health --config PATH --result-file RESULT` | Config supplies composite profile/expected identity; local-only health is insufficient |
| DIAGNOSTICS | `jbpa diagnostics --result-file RESULT` | Observations may remain unknown |
| ENTERPRISE_CONFIGURE | `jbpa enterprise --config PATH --result-file RESULT` | Request expectedIdentity supplies explicit agent/group IDs and names for live enterprise health |
| UNINSTALL | `jbpa uninstall --config PATH --complete --result-file RESULT` | Explicit local removal; JBPA owns drain and package/residual validation; no VM destruction |
| REINSTALL | `jbpa reinstall --config PATH --version VERSION --non-interactive --result-file RESULT` | RC3 supported; RC2 still rejects OPERATION_UNAVAILABLE_IN_RC2. JBPA owns the complete lifecycle |
| ARTIFACT_VERIFY | `jbpa artifact verify --version VERSION --result-file RESULT` | Governed digest/DEB metadata checks, no PA installation |

Qualification INSTALL adds `--controlled-test --allow-unqualified`. No operation accepts arbitrary shell text or unvalidated extra argv. RC3 implements standalone REINSTALL; optional result details preserve schema 1.0. See the [reinstall runbook](runbooks/reinstall.md).

## Bootstrap and delivery

A caller may preinstall the verified release, place the archive on the host or supply an approved retrievable location. Verify the independently supplied exact archive SHA before extraction/execution and verify manifest file hashes/version. The existing [bootstrap](azure-bootstrap.md) is an INSTALL bootstrap: archive verification, safe extraction, Python runtime setup, configuration validation, invocation, exit propagation and result creation only. It creates no infrastructure. Other operations use the installed CLI; do not claim bootstrap operation selection that RC2 lacks.

RC2 remains immutable: version `1.0.0-rc2`, SHA-256 `68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da`. New runtime behavior must ship with a new release identity such as rc3. Documentation and external tooling changes do not alter these bytes.

## Transport and result handling

SSH, Azure Run Command, Custom Script Extension, cloud-init or another remote execution service may deliver/invoke this contract. The canonical contract is transport-independent. SSH here means host execution transport, not qualification of Jitterbit SSH/SFTP.

The [external harness](../tools/handoff/README.md) implements LOCAL and a CI mock remote adapter. Release/configuration must already be delivered. LOCAL verifies the archive and installed files before invocation. A real remote transport must perform the same verification on the target and collect its process exit and fresh result file; no real SSH/Azure transport is implemented in this harness.

The caller consumes exit code plus schema-valid RC JSON, never product logs, TranDb or service names. Normal command success requires exit 0, `status=SUCCESS`, `category=SUCCESS`, error null and matching release/operation. Inspect `state` and `details.status` to distinguish plans, no-change, observations and completed work. GATE-13 install acceptance additionally requires JBPA's strict complete initial-registration evidence; generic transport success alone does not close it. Results contain state, category and error retryability; never blindly retry mutation or registration. Caller output excludes raw vendor messages and secret values.

Generic integration failures include HOST_UNREACHABLE, RELEASE_DELIVERY_FAILED, REMOTE_EXECUTION_FAILED, RESULT_FILE_MISSING, RESULT_SCHEMA_INVALID and JBPA_FAILED. REQUEST_INVALID, RESULT_DESTINATION_EXISTS and OPERATION_UNAVAILABLE_IN_RC2 additionally reject invalid/stale/unsupported dispatch. JBPA's internal error categories are preserved rather than reimplemented by the caller.

## Gates and next live test

GATE-13 is **External AI Orchestrator → JBPA Handoff**, replacing the historical Azure provisioning-agent gate. PASS requires a separately controlled tool to invoke JBPA on an already provisioned host, collect deterministic exit/schema-valid result, and leave all PA lifecycle/log interpretation inside JBPA. Provisioning itself is outside the gate.

GATE-10 remains PA 12.10.1.1 + Ubuntu 22.04 amd64. Both gates remain PENDING LIVE TEST. Next inputs are execution target/mechanism, Ubuntu 22.04 amd64/root access, deliverable immutable RC2, agent configuration/secret references and working outbound connectivity. No Azure deployment specification is requested. First run explicitly uses allowUnqualified=true with controlledTest=true; PA SHA is `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8`. QA_TEST_ONLY / LOCALLY_CALCULATED classification remains unchanged. Preserve the existing Ubuntu 24.04 agent.

## Phase 3C release update

Next live qualification uses immutable RC3, with RC2 retained as historical evidence. RC3 adds shared structured validate/INSTALL/REINSTALL readiness and first-class REINSTALL. Required host inputs and external infrastructure ownership are unchanged. GATE-10/GATE-13 remain pending.
