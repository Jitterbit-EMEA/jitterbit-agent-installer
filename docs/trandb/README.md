# TranDb discovery and workload learning

This directory catalogues the PA database findings and provides executable, read-only captures. It is a research harness for the existing named agent, not a deployed management API or a qualified production monitoring service.

## What is preserved

| Artifact | Purpose |
| --- | --- |
| [Knowledge catalogue](knowledge-catalogue.json) | Machine-readable connection method, identities, joins, status mapping, timing semantics, evidence levels, open questions and executable query catalogue |
| [Reporting assessment](reporting-assessment.md) | Full explanation and classification of all 130 tables |
| `output/trandb/reportability-matrix-2026-10-08.json` | Complete table/column/type dictionary and reporting classifications |
| [SQL catalogue](reporting-queries.sql) | 25 read-only reporting queries; shared source is `trandb_reporting.py`; execution uses `validate-trandb-reporting.py` |
| `output/trandb/parent-child-links-2026-10-08.json` | Verified runtime parent/child GUID linkage |
| `output/trandb/workloads/pre-production-2026-10-08/` | New replayable baseline: schema/profile, reporting data, query audit and evidence digests |

The dictionary and assessment preserve schema-supported reporting opportunities even when their tables are empty. The catalogue separates observed relationships from meanings that still need workload validation. The baseline PA is 12.11.3.1; qualification remains AVAILABLE_UNQUALIFIED.

## Interactive questions

For current running/active/error executions, definitions, backlog or identity, use the focused one-SSH modes in [read-path-performance.md](../read-path-performance.md). Specify the mode explicitly; omit `--output` for a bounded direct JSON result or retain a new private capture. Full `reporting` (all original 25 queries), `profile`, workload comparison and offline assessment remain available. Do not use full schema profiling for a simple running-operation question.

## Capture the next workload

Run from the repository root. Reuse the existing private inventory; do not put passwords or key contents into commands. Each output directory must be new. The protected inventory below is staged for this QA target and ignored by Git; customers use their own protected inventory path.

```bash
python3 scripts/management/trandb-workload.py capture \
  --inventory secrets/qa-troubleshooting-inventory.json \
  --target JBLAB-PA-AUTOMATION \
  --output output/trandb/workloads/during-project-01 --limit 500
```

Run this while a longer operation is running, then again after completion with a different directory, such as `after-project-01`. The customer runs the project through Harmony; this harness does not trigger operations. Deployment may have happened before the baseline—compare the evidence rather than assuming the label proves an empty starting environment.

A full bundle profiles all table populations, timestamp coverage, numeric/string state distributions, keys/indexes/views and database diagnostics, then captures recent operation definitions/runs, runtime links, message metadata, transformation summaries, progress, file counters, deployment/queue summaries and data-quality checks. Credentials, scripts, payloads, raw properties, full messages and file paths are excluded.

For a lighter during-run observation, use reporting only:

```bash
python3 scripts/management/capture-trandb.py \
  --inventory secrets/qa-troubleshooting-inventory.json \
  --target JBLAB-PA-AUTOMATION --mode reporting --limit 500 \
  --output output/trandb/during-project-reporting-01.json
```

This is a bounded research tool: individual queries have a 5-second statement timeout and 1-second lock timeout. Full profiling includes exact counts and can add load; use it before/after, and prefer reporting-only captures during a busy workload. Unavailable queries are recorded, not converted to zero. No schema/configuration changes or new listeners are required.

## Compare and review the new evidence

```bash
python3 scripts/management/trandb-workload.py compare \
  --before output/trandb/workloads/pre-production-2026-10-08 \
  --after output/trandb/workloads/after-project-01 \
  --output output/trandb/workloads/comparison-project-01
```

`comparison.md` shows changed table populations and counts of newly observed/changed records. `comparison.json` preserves new run GUIDs, changes to already observed runs, parent/child links, definition changes, transformation/file/progress records, schema differences, relationship checks and failures. Evidence digests are checked before comparison. Files are private (0600), and bundle directories are created with 0700. A failed capture leaves a partial directory without a completed manifest; choose a new directory after investigating.

Comparison is local and does not contact the VM. A missing row in a later bounded sample is **not** classified as deletion. A newly populated table demonstrates available data, not automatically correct business interpretation.

## What to learn from the production project

| Question | Evidence to inspect | Promotion criterion |
| --- | --- | --- |
| Can we report all executions? | `ignore_history`, retained runs, expected Harmony run count | Explain missing successful/error runs and retention before claiming completeness |
| Which states appear? | `run_status_counts`, repeated `operation_runs` | Observe progression and retain any unmapped raw code |
| Can we link the full hierarchy? | `child_runs`, `instance_links`, parent/root GUIDs | Validate nested/parallel branches; account for missing/cross-agent parents |
| Are finish time and duration reliable? | Start/status timestamp transitions against known workload completion | Qualify semantics; keep finishedAt null until proven |
| Are record/byte totals useful? | `transformation_summaries`, `file_result_counters` | Compare known input/output counts; confirm units and avoid multiplied joins |
| Is progress meaningful? | `run_progress` during/after execution | Validate percentage range, estimates and persistence |
| Can queues/synchronization be interpreted? | `incoming_queue_summary`, `log_sync_backlog` | Correlate controlled workload and contemporaneous support-tool evidence |
| Did deployment add usable metadata? | New table population, catalogue/deployment changes | Whitelist useful fields; do not expose scripts, connection secrets or payloads |
| Did database structure change? | Column/key/index/view differences and query failures | Review provider compatibility before changing API contracts |

Record qualified findings and their snapshot/query references in the project catalogue; preserve unresolved points when evidence is insufficient. These are project artifacts, not automatic changes to personal Codex memory. No background polling is started by this workflow. Tell the agent when the project starts/is running/completes so a fresh capture can be taken at each point.

## Limits to keep visible

- Reporting samples default to the latest 500 rows where a query is ordered by execution time or local record ID; increase to at most 2000 when needed. Catalogues remain ordered by definition ID. At-bound results are flagged as potentially truncated.
- Whole-table counts/status totals complement bounded samples; they do not recover suppressed or expired execution history.
- Query snapshots occur at different instants. Captures are not a lossless event stream, and short executions may be missed between reads.
- Table sizes and PostgreSQL statistics can include this harness's own queries. They are not host CPU, Java heap, GC, Apache or Tomcat metrics.
- Summary/progress/file values retain their raw units/codes until a known workload establishes their meaning.
- Current local agent/group identity must not be assigned retrospectively to historical runs.

## Workload evidence ledger

- 8 October 2026, Jeld Wen File Persona: `output/trandb/workloads/during-project-2026-10-08-01/` contains the live workload capture. `output/trandb/workloads/comparison-during-project-2026-10-08-01/learned-observations.json` records new status observations, four levels of nested execution lineage, populated transformation summaries and unresolved counter/retention semantics. No active execution was observed by the reporting query; this does not establish customer-confirmed completion.

## Historical agent after version change

The user requested complete uninstall followed by v12.10 installation on 8 October 2026. The current verified build is **12.10.1.1**, newly registered agent **665430**, group **678370**. Core services, Harmony connectivity and Axis HTTP 200 passed; all 256 expected Axis libraries are present. Use `output/trandb/workloads/fresh-1210-2026-10-08/` as the new baseline (157 profiling and 25 reporting queries succeeded). Prior v12.11 captures are historical and must not be treated as continuous local history across the uninstall. The old Harmony agent record was not deleted. Customer deployment retry remains required to validate the original error.

## Current agent in PAG 679240

On 11 October 2026, after the customer deleted the previous PAG/environment, v12.10.1.1 was installed into PAG **679240**. A newly generated registration token was required; it is retained only in protected VM files, not in these artifacts. Current agent ID: **667310**, name `automated-agent_2026-10-11 19:19:38.307`, group name **7-Automated Infrastructure**. Configured steady-state health returned **HEALTHY**, with matching identity, Harmony authentication/heartbeat and local core services. Axis HTTP 200 and all 256 expected library names were verified.

Use `output/trandb/workloads/fresh-1210-pag679240-2026-10-11/` as the current baseline: 148 profiling and 25 reporting queries succeeded, with no unavailable queries. Earlier group 678370/agent 665430 captures are historical. The current environment is **571300**. Deployment recovery was customer-confirmed on 12 October 2026 after updating connectors and testing the saved Gmail connection. Fresh logs show Gmail loaded at **09:28:25 UTC**. This remains the existing controlled QA VM with its prior sizing exception; production sizing qualification is not implied.

## Connector readiness and deployment recovery

The working recovery was **Update connectors → test the saved Gmail connection → deploy**. Before recovery, the agent was healthy but Axis could not find Gmail endpoint entity 37201 in its connector registry; its invalidation response was HTTP 200 with `status:false`. Connector download/load evidence and customer-confirmed deployment success are recorded in `knowledge-catalogue.json` and `token-invalidation-investigation-2026-10-09.md`.

The catalogue contains an ordered `connectorReadinessRunbook` for requerying this finding. Package availability, runtime load and registry availability should be separate deployment-readiness checks. This is a documented product requirement, not an implemented automatic repair.

## Composite operation assessment

See the [API/MCP architecture and interpretation rules](operation-assessment-api.md), [planning contract](operation-assessment-contract.json) and [root assessment SQL](operation-assessment.sql). The offline `scripts/management/assess-trandb.py` assesses a selected root from existing reporting/transfer evidence. This is executable QA research; UPG-001 API/MCP deployment remains deferred until baseline validation.
