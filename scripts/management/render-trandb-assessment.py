#!/usr/bin/env python3
"""Build the live TranDb reporting assessment and full table reportability inventory."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
b = json.loads((ROOT / "output/trandb/baseline-2026-10-08.json").read_text())
v = json.loads((ROOT / "output/trandb/reporting-validation-2026-10-08.json").read_text())
support = json.loads((ROOT / "output/trandb/support-tool-crosscheck-2026-10-08.json").read_text())
critical = {
    "operationlogtab": (
        "Execution history",
        "Run GUID and definition ID/name; original status; submitted/start/last-status timestamps; parent/root; historical project/agent identity. Message and trigger-user fields are restricted.",
    ),
    "operationinstancetab": (
        "Execution history",
        "Execution envelope and parent linkage; join by operation_instance_guid without changing run grain.",
    ),
    "operationmessagetab": (
        "Execution history",
        "Ordered message/event records; count and timestamps safely, expose message text only through scoped redacted diagnostics.",
    ),
    "operationprogresstab": (
        "Execution history",
        "Progress percentage, stage and estimated end; empty at baseline, must sample during a running operation.",
    ),
    "operationsummarytab": (
        "Execution history",
        "Source/target files, bytes/records and transformation-time counter; units and availability require populated test evidence.",
    ),
    "operationfilestatustab": (
        "Execution history",
        "Per-file record/byte counts, category and status; paths/messages are restricted and one run can have many files.",
    ),
    "incomingmsgtab": (
        "Queues and synchronization",
        "Local requested work with execution/priority/thread flags; excludes processvariables and subjects/addresses from default APIs.",
    ),
    "logsynctab": (
        "Queues and synchronization",
        "Log shipment rows by table_id, is_synced and priority. Numeric code meaning and Support Tools comparison remain to be qualified.",
    ),
    "verboseloguploadtab": (
        "Queues and synchronization",
        "Verbose-log upload queue metadata; no raw payload upload into AI context.",
    ),
    "locktab": (
        "Queues and synchronization",
        "Runtime lock records; report counts/persistence observations, never mutate or clear locks.",
    ),
    "deploylogtab": (
        "Deployment and identity",
        "Environment/group/entity deployment bookkeeping, raw timestamp, sync/deletion/error flags; epoch units require validation.",
    ),
    "deployhistory": (
        "Deployment and identity",
        "Historical deployment bookkeeping; currently empty.",
    ),
    "projectdeploylog": ("Deployment and identity", "Project deployment linkage; currently empty."),
    "environmentstab": (
        "Deployment and identity",
        "Environment identity/type/active/group settings. Observed agentgroup_id is null; do not invent historical group ownership.",
    ),
    "organizationinfotab": (
        "Deployment and identity",
        "Organization identity and metadata. Default reports need only authorized identity fields.",
    ),
    "organizationsecuritytab": (
        "Restricted security configuration",
        "Security policy/configuration; metadata only in default reports, raw records need separate security review.",
    ),
    "key_values": (
        "Deployment and identity",
        "Whitelisted current agent/group/version identity exists. Other values may be sensitive; no generic property dump.",
    ),
    "projectstab": (
        "Projects and operation definitions",
        "Project ID/GUID/name/environment and version/deletion metadata; no raw description or downloaded configuration needed.",
    ),
    "operationstab": (
        "Projects and operation definitions",
        "Definitions with ID/GUID/name/environment, timeout/history/logging settings and success/failure/SOAP-fault links.",
    ),
    "projectoperationstab": (
        "Projects and operation definitions",
        "Project membership links use item_id -> operationstab.operation_id and project_id -> projectstab.project_id.",
    ),
    "operationpropertiestab": (
        "Projects and operation definitions",
        "Property keys/configuration availability. Whitelist numeric settings; arbitrary keyvalue text can contain sensitive definitions.",
    ),
    "operationpipelineactivitiestab": (
        "Projects and operation definitions",
        "Pipeline/activity membership and sequencing; useful for topology after role-specific joins are qualified.",
    ),
    "operationgraphlayouttab": (
        "Projects and operation definitions",
        "Designer graph layout; not execution performance evidence.",
    ),
    "commonsourceoperationstab": (
        "Projects and operation definitions",
        "Shared-source operation relationships; schema only at baseline.",
    ),
    "schedulestab": (
        "Schedules",
        "Schedule recurrence/timezone definitions; empty until a scheduled workload is deployed.",
    ),
    "schedulepropertiestab": (
        "Schedules",
        "Schedule property keys; raw values require a whitelist.",
    ),
    "endpointauditlog": (
        "Endpoint usage and audit",
        "Endpoint, operation/project/environment/agent identity and login time; URLs are sensitive and must be sanitized.",
    ),
    "unique_endpoint_usage_tab": (
        "Endpoint usage and audit",
        "Usage counts/month/last-used/shipment metadata; unique endpoint strings/hashes are not a generic AI payload.",
    ),
    "unique_endpoint_identifier_tab": (
        "Endpoint usage and audit",
        "Endpoint identity/deduplication structure; report counts or permitted metadata, exclude unrestricted identifiers.",
    ),
    "xferhist": (
        "File transfer",
        "Transfer time/bytes/status/retries; filenames/paths restricted. xferhistorylogsview supplies a definition join.",
    ),
    "filestoretab": (
        "File store",
        "Stored-file metadata and potentially content; report counts/size only by validated projection.",
    ),
    "filestorepropertiestab": (
        "File store",
        "File-store property bags; values may carry content/configuration and are not returned by default.",
    ),
    "clientcertificatestab": (
        "Restricted security configuration",
        "Certificate/identity configuration; never export private certificate/key contents.",
    ),
    "sessionidtab": (
        "Restricted security configuration",
        "Runtime session identifiers; no raw token/session export.",
    ),
    "scriptstab": (
        "Transformations scripts and documents",
        "Script definitions; contents may embed SQL, credentials and business logic. Default output is names/IDs/counts.",
    ),
    "sqlscripttab": (
        "Transformations scripts and documents",
        "Stored SQL/script material; do not execute or expose as arbitrary queries.",
    ),
    "errormsgtab": (
        "Execution history",
        "Error-message definitions/data; metadata/counts only unless sanitized diagnostics are specifically scoped.",
    ),
}


def classification(t):
    n = t["name"]
    if n in critical:
        return critical[n]
    if n.startswith("project"):
        return (
            "Projects and operation definitions",
            "Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication.",
        )
    if n.startswith(
        (
            "connector",
            "http",
            "webservice",
            "salesforce",
            "netsuite",
            "ldap",
            "apientity",
            "callrestriction",
        )
    ):
        return (
            "Connector and endpoint definitions",
            "Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted.",
        )
    if n.startswith(
        (
            "source",
            "target",
            "document",
            "dataelement",
            "dbfield",
            "dbtable",
            "transformation",
            "trans_",
            "tran_",
            "xslt",
            "script",
            "function",
            "edge",
            "error",
            "folder",
            "pipelineplugin",
            "plugin",
        )
    ):
        return (
            "Transformations scripts and documents",
            "Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets.",
        )
    if n.startswith("bulkload"):
        return (
            "Bulk-load runtime",
            "Batch/job/record/status/time metadata for bulk-load processing. Empty at baseline; external job IDs and units need workload evidence.",
        )
    if n.startswith("filestore"):
        return (
            "File store",
            "File-store relationship/folder metadata; do not expose content or unrestricted paths.",
        )
    return (
        "Other runtime configuration",
        "Schema is queryable; semantics and safe field projection require provider-specific validation before an API is exposed.",
    )


def safe(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


cols = defaultdict(list)
for c in b["columns"]:
    cols[(c["schema"], c["name"])].append(c)
reportability = []
for t in b["tables"]:
    area, purpose = classification(t)
    reportability.append(
        {
            "schema": t["schema"],
            "table": t["name"],
            "area": area,
            "rows": t.get("exactRows"),
            "columns": cols[(t["schema"], t["name"])],
            "purposeAndBoundary": purpose,
            "evidence": "OBSERVED_POPULATED" if t.get("exactRows", 0) > 0 else "SCHEMA_ONLY_EMPTY",
            "totalBytes": t["total_bytes"],
            "canSelect": t["can_select"],
        }
    )
counts = Counter(r["area"] for r in reportability)
schemahash = hashlib.sha256(
    json.dumps(
        {
            "tables": [(t["schema"], t["name"], t["kind"]) for t in b["tables"]],
            "columns": b["columns"],
            "keys": b["constraints"],
            "indexes": b["indexes"],
        },
        sort_keys=True,
    ).encode()
).hexdigest()
model = {
    "paVersion": "12.11.3.1",
    "postgresVersion": b["database"][0]["server_version"],
    "observedAtUtc": b["observedAtUtc"],
    "schemaFingerprint": schemahash,
    "tables": reportability,
    "views": b["views"],
    "functions": b["functions"],
    "dataQuality": v["reports"]["run_grain_checks"],
    "relationshipChecks": v["reports"]["logical_relationship_checks"],
    "sourceFiles": [
        "baseline-2026-10-08.json",
        "reporting-validation-2026-10-08.json",
        "support-tool-crosscheck-2026-10-08.json",
    ],
    "boundaries": [
        "Read-only statements; no DB credential values retained",
        "Row counts/profile queries are individually bounded snapshots, not one global atomic snapshot",
        "No source/target payload, property value, script body, security record or raw operation message exported",
        "Only safe run identifiers/names/timestamps sampled",
        "This is scoped QA reporting discovery, not enabling production observability APIs",
    ],
}
(ROOT / "output/trandb/reportability-matrix-2026-10-08.json").write_text(
    json.dumps(model, indent=2) + "\n"
)
latest = {
    "observedDate": "2026-10-08",
    "target": "JBLAB-PA-AUTOMATION",
    "vendorLatestPackage": "12.11.3.1",
    "installedPackage": "12.11.3.1",
    "sha256": "b9b6d6c231005c675fa200e998e4864a4e0b815e6764abe38b2c2ff24e58a561",
    "runtimeQualification": "AVAILABLE_UNQUALIFIED",
    "alreadyLatest": True,
    "installationPerformedThisAssessment": False,
    "reason": "Existing installation matches freshly resolved vendor latest; no unnecessary reinstall or registration performed.",
}
(ROOT / "output/trandb/latest-observation-2026-10-08.json").write_text(
    json.dumps(latest, indent=2) + "\n"
)
lines = [
    "# TranDb reporting assessment",
    "",
    "Live assessment of JBLAB-PA-AUTOMATION on 8 October 2026. The installed PA is **12.11.3.1**, matching the freshly resolved vendor latest package. No reinstall, restart, agent registration, operation execution or database mutation was performed. The existing framework still labels this release AVAILABLE_UNQUALIFIED; this research does not promote production approval.",
    "",
    "## Findings",
    "",
    "| Measure | Observed result |",
    "| --- | --- |",
    f"| PostgreSQL | {b['database'][0]['server_version']}; configured local PgBouncer endpoint 6432 |",
    f"| Database size | {b['database'][0]['database_bytes']:,} bytes ({b['database'][0]['database_bytes'] / 1024 / 1024:.2f} MiB) |",
    f"| Application tables / views | {len(b['tables'])} / {len(b['views'])} |",
    f"| Columns | {len(b['columns'])} total: 1,150 base-table and 223 view columns |",
    f"| Keys / indexes / routines | {len(b['constraints'])} primary/unique constraints; {len(b['indexes'])} indexes; {len(b['functions'])} routines |",
    "| Declared foreign keys | **0**; relationships must be explicitly verified |",
    "| Populated / empty tables | **29 / 101**; 213 retained rows at baseline |",
    "| Operation definitions / execution logs | **3 / 2** |",
    "| Observed execution states | Both retained runs have status **7 (Error)**; active count 0 |",
    "| Discovery / reporting queries | **161 + 21**, all successful in the final read-only runs |",
    "",
    f"Baseline capture: `{b['observedAtUtc']}`. Reporting validation: `{v['observedAtUtc']}`. Queries are bounded, separate snapshots; later counts can change while the agent runs. Database timezone is Etc/UTC.",
    "",
    "## Connection and safety",
    "",
    "Only User, Password and Port are read locally from the [DbInfo] section of `/opt/jitterbit/jitterbit.conf`; the bundled psql/runtime location is resolved from `/etc/sysconfig/jitterbit`. Credential values are never printed or copied into reports. No database listener is exposed.",
    "",
    "The configured endpoint is PgBouncer, not an assumed direct port 5432. An initial startup-options approach was rejected by PgBouncer. The working provider uses **BEGIN READ ONLY**, local 5-second statement / 1-second lock timeouts, quiet psql output and **ROLLBACK** for every query. `transaction_read_only=on` was verified against the live database. No database/agent configuration was changed.",
    "",
    "The analysis excludes raw properties, source/target contents, scripts, certificate/session/security values and full operation messages. The attached inventory covers their structure and reporting potential without exporting their sensitive contents. Cumulative PostgreSQL statistics include the assessment queries themselves; they are not per-integration performance metrics.",
    "",
    "## Required operation fields and actual sources",
    "",
    "| Canonical concept | Verified local source | Interpretation |",
    "| --- | --- | --- |",
    "| Operation definition ID | operationstab.operation_id; operationlogtab.operation_id | Numeric definition identity; qualify by source/customer scope |",
    "| Definition GUID | operationstab.guid; operationlogtab.operation_guid | Definition UUID separate from execution UUID |",
    "| Operation name | operationstab.operation_name; operationlogtab.operation_name | Use log-side value for historical runs; definition can be renamed |",
    "| Execution ID | operationlogtab.operation_instance_guid | Unique index verified; preferred run identity |",
    "| Local log row ID | operationlogtab.operation_log_id | Primary key; qualifies cursor within this local database |",
    "| Parent/root run | parent_operation_instance_guid / root_operation_instance_guid | Parent/child lineage; one observed parent-child pair |",
    "| Submission/start time | entered_ts / started_ts | Timestamp-with-time-zone columns; directly observed |",
    "| Last status time | status_ts | **Not a dedicated finish-time field** |",
    "| Finish time | No dedicated finish column in operationlogtab | Keep canonical finishedAt unverified/null until terminal status_ts semantics are qualified; expose terminalStatusAt/source candidate separately |",
    "| Queue delay | started_ts - entered_ts | Derivable where both exist; not a configured timeout |",
    "| Time to latest status | status_ts - started_ts | Derivable; do not call it definitive execution duration before finish semantics are tested |",
    "| Original status | operationlogtab.status | Retain numeric code; existing JBPA mapping defines 0/1/3/8/10 as active |",
    "| Project/environment/agent | Denormalized operationlogtab fields | Useful historical context; preserve source identifiers/names |",
    "| Agent group | key_values whitelisted Agent_Group_Id/Name | Current host identity only; environmentstab.agentgroup_id was null. Do not assign current group to past executions as historical fact |",
    "",
    "Current agent identity: agent **665400**, group **678370 — 7-Automated Infrastructure**. The local environment is **570050 — 12-Automated Infrastructure**. Group and environment are different identities.",
    "",
    "## Data grain and relationships",
    "",
    "The observed run GUIDs and log primary keys are unique. Both runs have non-null submitted/start/status timestamps, with no start-before-entry or status-before-start violation. The two logs resolve to operation definitions and instance records; the observed child resolves to its parent. Message records resolve to run GUIDs. These checks cover the small current sample, not every future record.",
    "",
    "Validated definition catalogue join: `projectoperationstab.item_id = operationstab.operation_id`, then `projectoperationstab.project_id = projectstab.project_id`. It returns three rows for three definitions. There is no projectoperationstab.operation_id field.",
    "",
    "Runtime joins use operation_instance_guid for instances/messages/progress/summaries/file results. One run can have many message/file/progress rows; aggregate those separately before joining to avoid inflated run counts. All PK/unique/FK metadata is in the baseline JSON; no FK constraints were present.",
    "",
    "## Present operation catalogue",
    "",
    "| Definition ID | Name | Timeout | Retained history |",
    "| --- | --- | --- |",
]
for d in v["reports"]["operation_definitions"]:
    lines.append(
        f"| {d['operation_id']} | {safe(d['operation_name'])} | {d['timeoutseconds']} seconds | ignore_history={d['ignore_history']}; logging coverage requires validation |"
    )
lines += [
    "",
    "All three definitions are in project **Create Workload (minimal) - 02**. The baseline has error runs for Parent Operation and Child Operation 1; no retained run for Child Operation 2. `ignore_history=1` is observed for all three. Do not claim the local log table is a complete ledger of all successful executions until success/logging/retention behavior is tested.",
    "",
    "## Reporting families",
    "",
    "| Family | Tables | Reporting value |",
    "| --- | --- | --- |",
]
for area, count in sorted(counts.items()):
    lines.append(
        f"| {area} | {count} | See per-table inventory below; populated versus schema-only is explicit |"
    )
lines += [
    "",
    "Execution-history APIs can cover active/pending/running/error/terminal lists, definition catalogue, run details, lineage, queue age and status-transition timing. Progress, record/byte throughput, file outcomes, schedules, endpoint usage and bulk-load metrics have schema support but need populated workloads.",
    "",
    "Definition/configuration APIs can cover projects, environments, deployment changes, timeout/logging settings, operation chains, sources/targets/transformation membership and connector inventory using whitelisted fields. Stored definition/property/script/document content is not a default AI response.",
    "",
    "Database diagnostics can cover size, connections/waits, locks, transaction/cache/temp-file/deadlock counters, table/index size, row counts and vacuum/analyze statistics. These are cumulative/instantaneous database observations, not CPU, JVM heap, GC or Apache/Tomcat thread statistics. Those require their separate approved providers.",
    "",
    "## Diagnostic cross checks",
    "",
    "Support Tools `pending-ops -j` returned an empty array; the direct active-run query independently returned zero. Apache `apache-stat -j` returned 1 busy, 255 idle and 256 total workers, with reported free capacity 99%. `pg-connection -m conf -j` returned 5 null-state, 1 active and 15 idle PostgreSQL sessions. The active session can include the probe itself.",
    "",
    "`log-sync` returned a SYNCED count of 0 while the earlier direct snapshot had 12 logsynctab rows with is_synced=1. The captures occur at different times, and numeric queue-state/selection semantics are not yet established. **Do not normalize is_synced=1 into “synced” or “pending” from its name alone.** Compare a controlled workload with contemporaneous reads before shipping a backlog API.",
    "",
    "## Test operations needed next",
    "",
    "| Test | Capture | What it proves |",
    "| --- | --- | --- |",
    "| Successful single operation | Before, during and after; identify definition/run | Status progression and whether successful history is retained |",
    "| Controlled failure | Same sequence and redacted error metadata | Error state, message links and terminal-status timing |",
    "| Long-running operation | Several reads while running, then completion | Pending/Running visibility, elapsed time and progress availability |",
    "| Parent plus two children | Capture every run GUID and parent/root link | Lineage, ordering and roll-up semantics without double counting |",
    "| Transformation with known records/files | Known source/target counts and bytes | operationsummary/file-result units and population |",
    "| Scheduled operation | Schedule definition and pending/delivery captures | scheduledoperationview, incomingmsgtab flags and timing/epoch units |",
    "| Repeated operation and retention | Incremental reads and late finishing run | Stable paging, changed-record collection, cleanup and restart behavior |",
    "",
    "Do not alter agent operation logging or retention automatically to make tests produce data. If a successful run has no log, inspect the operation/agent settings and agree the desired coverage. A null finish time or empty summary table is not zero processing time or zero successful executions.",
    "",
    "## Query library and replay",
    "",
    "The [reporting SQL catalogue](reporting-queries.sql) contains the 21 read-only query shapes used for validation, with transaction/time limits. It includes catalogue, run detail/status, lineage, orphan/grain checks, message metadata, log-sync/deployment summaries, safe numeric configuration, identity whitelist and view metadata.",
    "",
    "Use `scripts/management/capture-trandb.py --inventory <private inventory> --target <named target> --mode profile --output <new snapshot.json>` for another bounded capture; `--mode reporting` performs the reporting/relationship checks. Output files must be new and are private by default. The assessment scripts use the same local credential provider through pinned SSH. Every query records SQL, duration, success/failure and its label. Baseline/reporting JSON artifacts preserve the evidence for comparison after your tests; secret values are excluded.",
    "",
    "## Complete table inventory",
    "",
    "Purposes below are reporting interpretations based on observed names, columns and validated relationships. Empty tables prove schema availability, not population or business metric semantics. The [full data dictionary and reportability JSON](../../output/trandb/reportability-matrix-2026-10-08.json) contains every column and type for all 130 tables; the baseline also includes the 223 view columns.",
    "",
    "| Table | Rows | Columns | Family and reporting boundary |",
    "| --- | --- | --- | --- |",
]
for r in reportability:
    lines.append(
        "| "
        + r["table"]
        + " | "
        + str(r["rows"])
        + " | "
        + str(len(r["columns"]))
        + " | "
        + safe(r["area"] + ": " + r["purposeAndBoundary"])
        + " |"
    )
lines += [
    "",
    "## Views and routines",
    "",
    "All 19 views were inventoried. Validated definitions (with literal values masked) and their column projections are retained in the reporting JSON. `scheduledoperationview`, `bulkload_instance_view` and `xferhistorylogsview` are useful existing join examples; their source tables are empty at baseline, so metric semantics remain to be tested.",
    "",
    ", ".join("`" + x["name"] + "`" for x in b["views"]) + ".",
    "",
    "The 16 routines include log-sync triggers, message/session insertion routines and create/drop helpers. They were **inventoried, never executed**. They are not read-only MCP tools.",
    "",
    "## Evidence and reference files",
    "",
    "- [Schema, counts, columns, keys, indexes and query audit](../../output/trandb/baseline-2026-10-08.json)",
    "- [Reporting queries, records and quality checks](../../output/trandb/reporting-validation-2026-10-08.json)",
    "- [Support Tools diagnostic cross checks](../../output/trandb/support-tool-crosscheck-2026-10-08.json)",
    "- [Latest package observation](../../output/trandb/latest-observation-2026-10-08.json)",
    "- [Jitterbit diagnostic commands](https://docs.jitterbit.com/agent/agent-support-tools/)",
    "- [PostgreSQL cumulative statistics](https://www.postgresql.org/docs/current/monitoring-stats.html)",
    "",
    f"Schema fingerprint: `{schemahash}`.",
    "",
]
(ROOT / "docs/trandb/reporting-assessment.md").write_text("\n".join(lines))
sql = [
    "-- TranDb PA 12.11.3.1 / PostgreSQL 16.13 read-only reporting shapes.",
    "-- Run through the local protected provider; no DB credentials are embedded.",
    "-- Existing data is a small QA sample; query semantics/retention need broader qualification.",
    "",
]
for q in v["queries"]:
    sql += [
        "-- " + q["label"],
        "BEGIN READ ONLY;",
        "SET LOCAL statement_timeout='5s';",
        "SET LOCAL lock_timeout='1s';",
        q["sql"] + ";",
        "ROLLBACK;",
        "",
    ]
(ROOT / "docs/trandb/reporting-queries.sql").write_text("\n".join(sql))
print("Built full table reportability inventory, assessment and read-only SQL catalogue.")
