# Operation assessment for API and MCP

Design updated 12 October 2026. This is the UPG-001 service contract, not a deployed endpoint. The existing SSH collectors and offline assessment script provide QA evidence; runtime API, authorization, central collection, pagination and load qualification remain to be implemented.

## Question to answer

“Did my last 20 files succeed, and were there SFTP problems?” requires separate answers for transfer, validation, transformation, downstream delivery and alerting. A healthy agent or successful root controller does not establish successful business processing. The observed rerun retrieved 20 files successfully, then recorded 20 validation errors. Gmail succeeded and Slack completed with warnings. These are 122 operation executions, not 122 files.

## Public actions and internal providers

| MCP action | Management route | Use |
| --- | --- | --- |
| `pa_assess_operations` | `POST /v1/targets/{targetId}/operation-assessments` | Read-only composite assessment for a root run or bounded time window |
| `pa_list_operation_runs` | `GET /v1/targets/{targetId}/operation-runs` | Resolve candidate runs and disambiguate repeated project executions |
| `pa_get_operation_run` | `GET /v1/targets/{targetId}/operation-runs/{operationRunId}` | Selected run, parent/child relationships, safe diagnostics and provenance |
| `pa_get_transfer_diagnostics` | `GET /v1/targets/{targetId}/transfer-diagnostics` | Bounded redacted curl diagnostic text and match confidence |
| `pa_get_logs` | `GET /v1/targets/{targetId}/logs` | Allowlisted component/log-family excerpts; no arbitrary filesystem path |

The composite request uses POST for structured filters; it performs reads and does not create a lifecycle job or install anything. The Jitterbit MCP tool calls a protected APIM route; Studio forwards the same canonical request to management FastAPI. The management service resolves the authorized target and runs providers over existing SSH. APIM/Studio preserve findings, source errors and partial coverage instead of turning them into HTTP-only success.

Within management, an assessment coordinator queries the TranDb provider, diagnostic classifier and curl-log provider. Optional service/host collectors are selected only when the question requires them. Compose multiple reads in the management layer, not a chain of unbounded AI requests. No listener is added to the PA and no JBMQ layer is needed for synchronous reads.

## Request, selection and bounded execution

The planning request/response contract and MCP input schema are in [operation-assessment-contract.json](operation-assessment-contract.json). Require an authorized target plus a root execution GUID or UTC time window. Optional project/environment filters narrow that scope. `operationId` is a definition, `operationRunId` is an execution, `rootRunId` groups executions and `jobId` is management lifecycle work; never substitute one for another.

If “last run” identifies multiple candidates, list them with start time, environment and agent and resolve the intended root. Do not merge repeated runs. Root selection does not silently widen to the whole project history. An expected file count is customer context, not measured throughput.

Proposed limits: 15-second overall collection budget, 5-second SQL statement timeout, 1-second SQL lock timeout, 500 returned execution rows by default and at most 2000, 100 diagnostic records by default and at most 500, 256 KiB response cap and at most 24 hours for interactive window requests. These are configurable proposed guardrails requiring benchmarks, not measured performance commitments. Cap SQL scanned scope too; a response row limit does not bound an unfiltered aggregate. Allowlisted provider selection and fleet concurrency are server-owned.

Use a read-only repeatable-read transaction for the related TranDb queries where supported by the qualified pooler/provider. Existing QA captures use separate transactions: label that difference explicitly. Files and service observations occur at other instants and cannot share the DB snapshot. Deadline expiry or one provider failure returns partial data with a failed coverage entry; total source failure is unavailable, not healthy. Large history uses paginated drill-down or a separate bounded export job, not a larger chat response.

## Complete query plan

“Complete” means comprehensive within an explicit source/window, not every table or unrestricted log contents.

| Provider stage | Fixed sources | Output and interpretation |
| --- | --- | --- |
| Identity and freshness | Qualified agent identity, selected environment and source version | Current target/group/agent, observedAt and provider compatibility; historical run identity remains historical |
| Definitions | `operationstab`, deduplicated project mappings, environment metadata | Available operation definitions and configured success/failure relationships; names do not prove role |
| Execution scope | `operationlogtab` filtered by root/time and authorized environment | Whole-scope status totals plus bounded ordered run rows; count attempts separately from unique executions |
| Runtime lineage | Parent/root execution GUIDs, `operationinstancetab` | Parent/child tree, depth, missing parents and cross-agent gaps; configured branches are not proof they ran |
| Messages and diagnostics | `operationmessagetab`, log-side message | Message metadata by run; separate redacted error classifier/excerpts; no raw messages by default |
| Records/files/progress | `operationsummarytab`, `operationfilestatustab`, `operationprogresstab` | Aggregate each at its own grain before joining; preserve units and qualification flags |
| Backlog and sync | `incomingmsgtab`, `logsynctab` | Current queue/sync observations with their own capture times; not historical root-run state |
| Transfer | Configured curl directory and qualified connector logs | Logging state, covered interval, redacted diagnostic text, protocol and matching strength |
| Overall interpretation | Evidence-backed rules plus configured operation-role map | Transfer/validation/delivery/alerts outcomes and recommendations, separate from data coverage |

The executable [root assessment SQL](operation-assessment.sql) summarizes execution/lineage/message counts for one explicit root without multiplying message joins. The existing [25-query library](reporting-queries.sql) supplies definitions, progress, summaries, files and quality checks. The aggregator must run multiple fixed queries; one giant join is not a complete assessment.

## Interpretation rules learned from QA

- Preserve original status and qualified normalization. Running/pending is not failure; warning is not clean success; terminal is not necessarily successful. Unknown codes remain unknown. Mark root controller outcome and worst observed descendant outcome separately.
- Report business stages through an explicit maintained operation-role map. Do not infer roles from an operation name as a production rule. The QA case uses a reviewed map for file retrieval, CSV validation, Gmail and Slack.
- File totals require a file identity and defined grain. Operation attempts, trace files, upload events and business files are different counts. Retries can retrieve one file more than once.
- Preserve `status_ts` as statusChangedAt. Until finish semantics are qualified, finishedAt/durationMs are null; use separately named active elapsed time. Do not substitute capture time for finish time.
- The sampled validation failures had `Header detected: false` and unsupported operationType values `[]` or `["QCXE"]`. Header/column selection is a hypothesis needing script/schema evidence, not a proven root cause.
- Curl authentication/connection reuse confirms protocol activity. `rm command failed: No such file or directory` may be cleanup before upload; command order and operation outcome matter. It alone does not establish a failed file transfer.
- Curl files may contain multiple request/reuse entries. A curl filename GUID is not proven to be an execution GUID. Exact recorded run IDs yield exact correlation; timestamp/endpoint matching yields inferred correlation; unmatched events stay unmatched. Do not fabricate mappings.
- `CurlDebugDir` empty means diagnostics were not configured; it does not mean no transfer occurred. Configuration present does not prove generated traces. Report loggingConfigured, tracesAvailable, inspected interval, truncated files and redaction separately.
- Only approved diagnostic records leave the VM. Curl DATA blocks and headers can contain credentials/payloads. Extract safe TEXT events, redact authentication/secret fields, cap text and store raw logs only in restricted on-host storage. Do not enable logging, restart, deploy or change credentials merely because an assessment finds a problem.

## Response to the AI

Return an overall outcome, stage outcomes, status totals, root/child summary, findings with evidence references, suggested next actions and explicit coverage. Default output is a compact structured summary with selected errors. The model explains it and can call a detail action using returned run IDs/cursors. Evidence records carry source, observedAt, confidence and whether the conclusion is observed or inferred.

Outcomes: `HEALTHY`, `DEGRADED`, `FAILED`, `IN_PROGRESS`, `UNKNOWN`; coverage: `COMPLETE`, `PARTIAL`, `UNAVAILABLE`. Any observed relevant execution failure yields FAILED even when the root reports SuccessWithInfo. A completed snapshot with missing sources cannot become HEALTHY by default. A no-run result is UNKNOWN. Findings can include a failed business stage, warning-only alerts, active work, unknown status, missing parents, unverified timestamps and absent transfer diagnostics.

The coordinator persists a short-lived assessment/evidence reference on management storage where configured; SQL credentials and raw payloads never enter its response. Each drill-down rechecks customer/target/environment permission. File references use opaque evidence IDs, not management or target filesystem paths. Assessment actions require read scopes; remediation remains a separate explicitly authorized action.

## Executable QA assessment today

```bash
python3 scripts/management/assess-trandb.py \
  --reporting output/trandb/mixed-logs-rerun-2026-10-12.json \
  --root-run-id 6f1cf181-1712-4021-924b-03d41d755ad7 \
  --transfer output/trandb/sftp-curl-rerun-2026-10-12.json \
  --output output/trandb/rerun-assessment-2026-10-12.json
```

This script assesses already filtered local evidence and opens no network connection. It groups the selected run, preserves original status, counts descendants and findings, and reports transfer traces as uncorrelated evidence. It does not expose an API, verify raw-log redaction or implement a production role mapper. Live collection uses the existing bounded SSH workflow. Qualification still requires source authorization, paging, source failures/deadlines, schema/version drift, repeated runs, retries, cross-agent lineage and PA load tests.
