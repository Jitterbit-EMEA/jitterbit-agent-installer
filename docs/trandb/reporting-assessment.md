# TranDb reporting assessment

> Historical v12.11 baseline. After the user-requested uninstall/reinstall, the current agent is v12.10.1.1, ID 667310, in PAG 679240. See [current capture guidance](README.md#current-agent-in-pag-679240) for the new baseline.

Live assessment of JBLAB-PA-AUTOMATION on 8 October 2026. The installed PA is **12.11.3.1**, matching the freshly resolved vendor latest package. No reinstall, restart, agent registration, operation execution or database mutation was performed. The existing framework still labels this release AVAILABLE_UNQUALIFIED; this research does not promote production approval.

## Findings

| Measure | Observed result |
| --- | --- |
| PostgreSQL | 16.13; configured local PgBouncer endpoint 6432 |
| Database size | 15,285,271 bytes (14.58 MiB) |
| Application tables / views | 130 / 19 |
| Columns | 1373 total: 1,150 base-table and 223 view columns |
| Keys / indexes / routines | 131 primary/unique constraints; 335 indexes; 16 routines |
| Declared foreign keys | **0**; relationships must be explicitly verified |
| Populated / empty tables | **29 / 101**; 213 retained rows at baseline |
| Operation definitions / execution logs | **3 / 2** |
| Observed execution states | Both retained runs have status **7 (Error)**; active count 0 |
| Discovery / reporting queries | **161 + 21**, all successful in the final read-only runs |

Baseline capture: `2026-10-08T15:49:29.745539+00:00`. Reporting validation: `2026-10-08T15:57:38.446314+00:00`. Queries are bounded, separate snapshots; later counts can change while the agent runs. Database timezone is Etc/UTC.

## Connection and safety

Only User, Password and Port are read locally from the [DbInfo] section of `/opt/jitterbit/jitterbit.conf`; the bundled psql/runtime location is resolved from `/etc/sysconfig/jitterbit`. Credential values are never printed or copied into reports. No database listener is exposed.

The configured endpoint is PgBouncer, not an assumed direct port 5432. An initial startup-options approach was rejected by PgBouncer. The working provider uses **BEGIN READ ONLY**, local 5-second statement / 1-second lock timeouts, quiet psql output and **ROLLBACK** for every query. `transaction_read_only=on` was verified against the live database. No database/agent configuration was changed.

The analysis excludes raw properties, source/target contents, scripts, certificate/session/security values and full operation messages. The attached inventory covers their structure and reporting potential without exporting their sensitive contents. Cumulative PostgreSQL statistics include the assessment queries themselves; they are not per-integration performance metrics.

## Required operation fields and actual sources

| Canonical concept | Verified local source | Interpretation |
| --- | --- | --- |
| Operation definition ID | operationstab.operation_id; operationlogtab.operation_id | Numeric definition identity; qualify by source/customer scope |
| Definition GUID | operationstab.guid; operationlogtab.operation_guid | Definition UUID separate from execution UUID |
| Operation name | operationstab.operation_name; operationlogtab.operation_name | Use log-side value for historical runs; definition can be renamed |
| Execution ID | operationlogtab.operation_instance_guid | Unique index verified; preferred run identity |
| Local log row ID | operationlogtab.operation_log_id | Primary key; qualifies cursor within this local database |
| Parent/root run | parent_operation_instance_guid / root_operation_instance_guid | Parent/child lineage; one observed parent-child pair |
| Submission/start time | entered_ts / started_ts | Timestamp-with-time-zone columns; directly observed |
| Last status time | status_ts | **Not a dedicated finish-time field** |
| Finish time | No dedicated finish column in operationlogtab | Keep canonical finishedAt unverified/null until terminal status_ts semantics are qualified; expose terminalStatusAt/source candidate separately |
| Queue delay | started_ts - entered_ts | Derivable where both exist; not a configured timeout |
| Time to latest status | status_ts - started_ts | Derivable; do not call it definitive execution duration before finish semantics are tested |
| Original status | operationlogtab.status | Retain numeric code; existing JBPA mapping defines 0/1/3/8/10 as active |
| Project/environment/agent | Denormalized operationlogtab fields | Useful historical context; preserve source identifiers/names |
| Agent group | key_values whitelisted Agent_Group_Id/Name | Current host identity only; environmentstab.agentgroup_id was null. Do not assign current group to past executions as historical fact |

Current agent identity: agent **665400**, group **678370 — 7-Automated Infrastructure**. The local environment is **570050 — 12-Automated Infrastructure**. Group and environment are different identities.

## Data grain and relationships

The observed run GUIDs and log primary keys are unique. Both runs have non-null submitted/start/status timestamps, with no start-before-entry or status-before-start violation. The two logs resolve to operation definitions and instance records; the observed child resolves to its parent. Message records resolve to run GUIDs. These checks cover the small current sample, not every future record.

Validated definition catalogue join: `projectoperationstab.item_id = operationstab.operation_id`, then `projectoperationstab.project_id = projectstab.project_id`. It returns three rows for three definitions. There is no projectoperationstab.operation_id field.

Runtime joins use operation_instance_guid for instances/messages/progress/summaries/file results. One run can have many message/file/progress rows; aggregate those separately before joining to avoid inflated run counts. All PK/unique/FK metadata is in the baseline JSON; no FK constraints were present.

## Present operation catalogue

| Definition ID | Name | Timeout | Retained history |
| --- | --- | --- |
| 18929120 | Child Operation 1 | 7200 seconds | ignore_history=1; logging coverage requires validation |
| 18929130 | Child Operation 2 | 7200 seconds | ignore_history=1; logging coverage requires validation |
| 18929140 | Parent Operation | 7200 seconds | ignore_history=1; logging coverage requires validation |

All three definitions are in project **Create Workload (minimal) - 02**. The baseline has error runs for Parent Operation and Child Operation 1; no retained run for Child Operation 2. `ignore_history=1` is observed for all three. Do not claim the local log table is a complete ledger of all successful executions until success/logging/retention behavior is tested.

## Reporting families

| Family | Tables | Reporting value |
| --- | --- | --- |
| Bulk-load runtime | 2 | See per-table inventory below; populated versus schema-only is explicit |
| Connector and endpoint definitions | 30 | See per-table inventory below; populated versus schema-only is explicit |
| Deployment and identity | 6 | See per-table inventory below; populated versus schema-only is explicit |
| Endpoint usage and audit | 3 | See per-table inventory below; populated versus schema-only is explicit |
| Execution history | 7 | See per-table inventory below; populated versus schema-only is explicit |
| File store | 4 | See per-table inventory below; populated versus schema-only is explicit |
| File transfer | 1 | See per-table inventory below; populated versus schema-only is explicit |
| Other runtime configuration | 3 | See per-table inventory below; populated versus schema-only is explicit |
| Projects and operation definitions | 28 | See per-table inventory below; populated versus schema-only is explicit |
| Queues and synchronization | 4 | See per-table inventory below; populated versus schema-only is explicit |
| Restricted security configuration | 3 | See per-table inventory below; populated versus schema-only is explicit |
| Schedules | 2 | See per-table inventory below; populated versus schema-only is explicit |
| Transformations scripts and documents | 37 | See per-table inventory below; populated versus schema-only is explicit |

Execution-history APIs can cover active/pending/running/error/terminal lists, definition catalogue, run details, lineage, queue age and status-transition timing. Progress, record/byte throughput, file outcomes, schedules, endpoint usage and bulk-load metrics have schema support but need populated workloads.

Definition/configuration APIs can cover projects, environments, deployment changes, timeout/logging settings, operation chains, sources/targets/transformation membership and connector inventory using whitelisted fields. Stored definition/property/script/document content is not a default AI response.

Database diagnostics can cover size, connections/waits, locks, transaction/cache/temp-file/deadlock counters, table/index size, row counts and vacuum/analyze statistics. These are cumulative/instantaneous database observations, not CPU, JVM heap, GC or Apache/Tomcat thread statistics. Those require their separate approved providers.

## Diagnostic cross checks

Support Tools `pending-ops -j` returned an empty array; the direct active-run query independently returned zero. Apache `apache-stat -j` returned 1 busy, 255 idle and 256 total workers, with reported free capacity 99%. `pg-connection -m conf -j` returned 5 null-state, 1 active and 15 idle PostgreSQL sessions. The active session can include the probe itself.

`log-sync` returned a SYNCED count of 0 while the earlier direct snapshot had 12 logsynctab rows with is_synced=1. The captures occur at different times, and numeric queue-state/selection semantics are not yet established. **Do not normalize is_synced=1 into “synced” or “pending” from its name alone.** Compare a controlled workload with contemporaneous reads before shipping a backlog API.

## Test operations needed next

| Test | Capture | What it proves |
| --- | --- | --- |
| Successful single operation | Before, during and after; identify definition/run | Status progression and whether successful history is retained |
| Controlled failure | Same sequence and redacted error metadata | Error state, message links and terminal-status timing |
| Long-running operation | Several reads while running, then completion | Pending/Running visibility, elapsed time and progress availability |
| Parent plus two children | Capture every run GUID and parent/root link | Lineage, ordering and roll-up semantics without double counting |
| Transformation with known records/files | Known source/target counts and bytes | operationsummary/file-result units and population |
| Scheduled operation | Schedule definition and pending/delivery captures | scheduledoperationview, incomingmsgtab flags and timing/epoch units |
| Repeated operation and retention | Incremental reads and late finishing run | Stable paging, changed-record collection, cleanup and restart behavior |

Do not alter agent operation logging or retention automatically to make tests produce data. If a successful run has no log, inspect the operation/agent settings and agree the desired coverage. A null finish time or empty summary table is not zero processing time or zero successful executions.

## Query library and replay

The initial validation used 21 queries. The extended workload harness now includes 25, with recent bounded execution samples plus transformation summaries, progress, file counters and instance links. All 25 executed successfully in the new baseline at `2026-10-08T17:35:37.301528+00:00`. See [the repeatable workload workflow](README.md) and [machine-readable knowledge catalogue](knowledge-catalogue.json) for capture/comparison commands, evidence limits and unresolved semantics.

The [reporting SQL catalogue](reporting-queries.sql) contains the 25 current read-only query shapes (21 initial checks plus four workload queries), with transaction/time limits. It includes catalogue, run detail/status, lineage, orphan/grain checks, message metadata, log-sync/deployment summaries, safe numeric configuration, identity whitelist and view metadata.

Use `scripts/management/capture-trandb.py --inventory <private inventory> --target <named target> --mode profile --output <new snapshot.json>` for another bounded capture; `--mode reporting` performs the reporting/relationship checks. Output files must be new and are private by default. The assessment scripts use the same local credential provider through pinned SSH. Every query records SQL, duration, success/failure and its label. Baseline/reporting JSON artifacts preserve the evidence for comparison after your tests; secret values are excluded.

## Complete table inventory

Purposes below are reporting interpretations based on observed names, columns and validated relationships. Empty tables prove schema availability, not population or business metric semantics. The [full data dictionary and reportability JSON](../../output/trandb/reportability-matrix-2026-10-08.json) contains every column and type for all 130 tables; the baseline also includes the 223 view columns.

| Table | Rows | Columns | Family and reporting boundary |
| --- | --- | --- | --- |
| apientity | 0 | 13 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| apientityfield | 0 | 11 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| bulkloadbatchtab | 0 | 16 | Bulk-load runtime: Batch/job/record/status/time metadata for bulk-load processing. Empty at baseline; external job IDs and units need workload evidence. |
| bulkloadinstancetab | 0 | 13 | Bulk-load runtime: Batch/job/record/status/time metadata for bulk-load processing. Empty at baseline; external job IDs and units need workload evidence. |
| callrestrictionstab | 0 | 9 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| clientcertificatestab | 0 | 8 | Restricted security configuration: Certificate/identity configuration; never export private certificate/key contents. |
| commonsourceoperationstab | 0 | 4 | Projects and operation definitions: Shared-source operation relationships; schema only at baseline. |
| connectorendpointpropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| connectorendpointstab | 0 | 10 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| connectorfunctionpropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| connectorfunctionstab | 0 | 12 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| dataelementstab | 0 | 7 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| dataelementtab | 0 | 8 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| dataelementtexttab | 0 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| dbfieldstab | 0 | 7 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| dbtablestab | 0 | 7 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| deployhistory | 0 | 6 | Deployment and identity: Historical deployment bookkeeping; currently empty. |
| deploylogtab | 24 | 9 | Deployment and identity: Environment/group/entity deployment bookkeeping, raw timestamp, sync/deletion/error flags; epoch units require validation. |
| document_definitionstab | 1 | 16 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| documentfieldvalidationtab | 0 | 12 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| documentpropertiestab | 4 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| documentstab | 1 | 11 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| edgemartfieldstab | 0 | 12 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| edgemartpropertiestab | 0 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| edgemartstab | 0 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| endpointauditlog | 0 | 17 | Endpoint usage and audit: Endpoint, operation/project/environment/agent identity and login time; URLs are sensitive and must be sanitized. |
| environmentstab | 1 | 15 | Deployment and identity: Environment identity/type/active/group settings. Observed agentgroup_id is null; do not invent historical group ownership. |
| errordataelementtab | 0 | 9 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| errordataelementtexttab | 0 | 6 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| errormsgtab | 0 | 21 | Execution history: Error-message definitions/data; metadata/counts only unless sanitized diagnostics are specifically scoped. |
| explicitagentversion | 0 | 8 | Other runtime configuration: Schema is queryable; semantics and safe field projection require provider-specific validation before an API is exposed. |
| filestoredependenciestab | 0 | 4 | File store: File-store relationship/folder metadata; do not expose content or unrestricted paths. |
| filestorefolderstab | 0 | 7 | File store: File-store relationship/folder metadata; do not expose content or unrestricted paths. |
| filestorepropertiestab | 47 | 5 | File store: File-store property bags; values may carry content/configuration and are not returned by default. |
| filestoretab | 12 | 13 | File store: Stored-file metadata and potentially content; report counts/size only by validated projection. |
| folderitemtab | 0 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| folderpropertiestab | 0 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| folderstab | 0 | 6 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| functionstab | 0 | 4 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| functiontypestab | 1 | 2 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| httpendpointoperationstab | 0 | 8 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| httpendpointpropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| httpendpointstab | 0 | 14 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| httptriggerstab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| incomingmsgtab | 0 | 18 | Queues and synchronization: Local requested work with execution/priority/thread flags; excludes processvariables and subjects/addresses from default APIs. |
| key_values | 12 | 11 | Deployment and identity: Whitelisted current agent/group/version identity exists. Other values may be sensitive; no generic property dump. |
| ldapsearchparameterstab | 0 | 8 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| ldapstructureentriestab | 0 | 7 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| locktab | 0 | 2 | Queues and synchronization: Runtime lock records; report counts/persistence observations, never mutate or clear locks. |
| logsynctab | 12 | 5 | Queues and synchronization: Log shipment rows by table_id, is_synced and priority. Numeric code meaning and Support Tools comparison remain to be qualified. |
| messagestab | 0 | 18 | Other runtime configuration: Schema is queryable; semantics and safe field projection require provider-specific validation before an API is exposed. |
| netsuitessomappingtab | 0 | 10 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| operationdataelementtab | 0 | 6 | Other runtime configuration: Schema is queryable; semantics and safe field projection require provider-specific validation before an API is exposed. |
| operationfilestatustab | 0 | 12 | Execution history: Per-file record/byte counts, category and status; paths/messages are restricted and one run can have many files. |
| operationgraphlayouttab | 0 | 4 | Projects and operation definitions: Designer graph layout; not execution performance evidence. |
| operationinstancetab | 2 | 7 | Execution history: Execution envelope and parent linkage; join by operation_instance_guid without changing run grain. |
| operationlogtab | 2 | 34 | Execution history: Run GUID and definition ID/name; original status; submitted/start/last-status timestamps; parent/root; historical project/agent identity. Message and trigger-user fields are restricted. |
| operationmessagetab | 3 | 7 | Execution history: Ordered message/event records; count and timestamps safely, expose message text only through scoped redacted diagnostics. |
| operationpipelineactivitiestab | 8 | 5 | Projects and operation definitions: Pipeline/activity membership and sequencing; useful for topology after role-specific joins are qualified. |
| operationprogresstab | 0 | 10 | Execution history: Progress percentage, stage and estimated end; empty at baseline, must sample during a running operation. |
| operationpropertiestab | 24 | 5 | Projects and operation definitions: Property keys/configuration availability. Whitelist numeric settings; arbitrary keyvalue text can contain sensitive definitions. |
| operationstab | 3 | 31 | Projects and operation definitions: Definitions with ID/GUID/name/environment, timeout/history/logging settings and success/failure/SOAP-fault links. |
| operationsummarytab | 0 | 11 | Execution history: Source/target files, bytes/records and transformation-time counter; units and availability require populated test evidence. |
| organizationinfotab | 1 | 5 | Deployment and identity: Organization identity and metadata. Default reports need only authorized identity fields. |
| organizationsecuritytab | 1 | 5 | Restricted security configuration: Security policy/configuration; metadata only in default reports, raw records need separate security review. |
| pipelinepluginpositiontab | 0 | 9 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| pluginstab | 0 | 4 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| projectconnectorendpointstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectconnectorfunctionstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectdeploylog | 0 | 3 | Deployment and identity: Project deployment linkage; currently empty. |
| projectdocumentstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectedgemartstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectfolderstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projecthttpendpointstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectmessagestab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectoperationstab | 3 | 3 | Projects and operation definitions: Project membership links use item_id -> operationstab.operation_id and project_id -> projectstab.project_id. |
| projectsalesforcebulkloadstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectsalesforceconnectorstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectsalesforcecreatestab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectsalesforcedeletestab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectsalesforcequeriestab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectsalesforceupdatestab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectsalesforceupsertstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectschedulestab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectscriptstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectsourcestab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectstab | 1 | 22 | Projects and operation definitions: Project ID/GUID/name/environment and version/deletion metadata; no raw description or downloaded configuration needed. |
| projecttargetstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projecttransformationstab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectvariablestab | 0 | 10 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| projectwebservicestab | 0 | 3 | Projects and operation definitions: Project-to-component membership or project configuration. Join item IDs against the qualified component type; avoid row multiplication. |
| salesforcebulkloadpropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforcebulkloadstab | 0 | 17 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforceconnectorpropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforceconnectorstab | 0 | 16 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforcecreatepropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforcecreatestab | 0 | 10 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforcedeletepropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforcedeletestab | 0 | 9 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforcequeriestab | 0 | 8 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforcequerypropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforceupdatepropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforceupdatestab | 0 | 10 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforceupsertpropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| salesforceupsertstab | 0 | 11 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| schedulepropertiestab | 0 | 5 | Schedules: Schedule property keys; raw values require a whitelist. |
| schedulestab | 0 | 34 | Schedules: Schedule recurrence/timezone definitions; empty until a scheduled workload is deployed. |
| scriptpropertiestab | 3 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| scriptstab | 3 | 6 | Transformations scripts and documents: Script definitions; contents may embed SQL, credentials and business logic. Default output is names/IDs/counts. |
| sessionidtab | 0 | 2 | Restricted security configuration: Runtime session identifiers; no raw token/session export. |
| sourcepropertiestab | 8 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| sourcestab | 1 | 38 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| sqlscripttab | 0 | 8 | Transformations scripts and documents: Stored SQL/script material; do not execute or expose as arbitrary queries. |
| targetpropertiestab | 9 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| targetstab | 1 | 36 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| tran_relationstab | 0 | 12 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| trans_filtertab | 0 | 10 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| transformationdatastore | 0 | 4 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| transformationdatastoreinstance | 0 | 11 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| transformationdefinitionstab | 2 | 7 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| transformationfunctiontab | 0 | 3 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| transformationpropertiestab | 0 | 5 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| transformationstab_new | 2 | 24 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |
| unique_endpoint_identifier_tab | 21 | 5 | Endpoint usage and audit: Endpoint identity/deduplication structure; report counts or permitted metadata, exclude unrestricted identifiers. |
| unique_endpoint_usage_tab | 0 | 29 | Endpoint usage and audit: Usage counts/month/last-used/shipment metadata; unique endpoint strings/hashes are not a generic AI payload. |
| verboseloguploadtab | 0 | 17 | Queues and synchronization: Verbose-log upload queue metadata; no raw payload upload into AI context. |
| webservicepropertiestab | 0 | 5 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| webservicestab | 0 | 25 | Connector and endpoint definitions: Endpoint/connector/API definition or property structure. Counts and selected identity/type metadata are reportable; raw properties/URLs/credentials are restricted. |
| xferhist | 0 | 15 | File transfer: Transfer time/bytes/status/retries; filenames/paths restricted. xferhistorylogsview supplies a definition join. |
| xslttransformstab | 0 | 6 | Transformations scripts and documents: Design/configuration/component structure. Report names, IDs, relationships and counts through a qualified whitelist; contents can carry business data or secrets. |

## Views and routines

All 19 views were inventoried. Validated definitions (with literal values masked) and their column projections are retained in the reporting JSON. `scheduledoperationview`, `bulkload_instance_view` and `xferhistorylogsview` are useful existing join examples; their source tables are empty at baseline, so metric semantics remain to be tested.

`archivesourcefiles`, `bulkload_instance_view`, `documentfieldvalidationview`, `fields1`, `fields2`, `fields3`, `functionservicefunctiontransformationview`, `scheduledoperationview`, `sql1`, `sql2`, `tables1`, `tables2`, `transformationstab`, `transformationstab_v`, `transformationtab_appended`, `transformtiontab_nofunction`, `webservicefunctiontransformationview`, `webservicesview`, `xferhistorylogsview`.

The 16 routines include log-sync triggers, message/session insertion routines and create/drop helpers. They were **inventoried, never executed**. They are not read-only MCP tools.

## Evidence and reference files

- [Schema, counts, columns, keys, indexes and query audit](../../output/trandb/baseline-2026-10-08.json)
- [Reporting queries, records and quality checks](../../output/trandb/reporting-validation-2026-10-08.json)
- [Support Tools diagnostic cross checks](../../output/trandb/support-tool-crosscheck-2026-10-08.json)
- [Latest package observation](../../output/trandb/latest-observation-2026-10-08.json)
- [Jitterbit diagnostic commands](https://docs.jitterbit.com/agent/agent-support-tools/)
- [PostgreSQL cumulative statistics](https://www.postgresql.org/docs/current/monitoring-stats.html)

Schema fingerprint: `f859b23a1db1d2eb2a230a37913eb3a5cef3186f90a30ac84b387e2e5fddbf04`.
