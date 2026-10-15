# JBPA management learning register

Updated 15 October 2026. This register consolidates the design decisions, QA findings and reusable investigation paths. It distinguishes implemented research tools from the proposed management product. Historical snapshots retain their original platform identity and date.

## Where the knowledge lives

| Subject | Authoritative repository artifact |
| --- | --- |
| Customer journey, components, execution flow and recovery | [Management product specification](jbpa-management-product.md) |
| Required behavior and acceptance criteria | [Requirement records](jbpa-management-requirements.json) and [generated matrix](jbpa-management-requirements-matrix.md) |
| Baseline versus deferred upgrades | [Roadmap](jbpa-management-roadmap.json) |
| Canonical fields and high-volume retrieval | [Data planning contract](jbpa-management-data-contract.json) |
| Database sources, joins, status evidence and unresolved semantics | [Machine-readable catalogue](trandb/knowledge-catalogue.json) |
| Full TranDb inventory and reporting suitability | [Reporting assessment](trandb/reporting-assessment.md) |
| Repeated capture and comparison | [Research workflow](trandb/README.md) |
| Deployment failure, diagnostic evidence and recovery | [Token-invalidation investigation](trandb/token-invalidation-investigation-2026-10-09.md) |
| Documentation layout and version boundaries | [HLA index](hla/README.md) |

## Architecture decisions retained

1. The customer first runs a local bootstrap installer on the initially bare management VM. MCP cannot call APIs that do not yet exist. After management readiness, configure Jitterbit MCP/APIM/Studio and use MCP for target onboarding.
2. Deploy the containerized NGINX, FastAPI, PostgreSQL and worker stack on a dedicated Linux management host. Targets use existing SSH access; add no management web service or listening port on PA hosts.
3. Resolve an explicit target from inventory. A load-balanced PA group is not a mechanism for selecting a particular host. Keep target identity, canonical host identity, group and profile revisions with each job.
4. The accepted baseline uses PostgreSQL as the durable backlog. Commit a validated READY job before returning HTTP 202 and its job ID. A worker executes over SSH and records the outcome. Retrieve it through the same job ID later.
5. JBMQ, outbox IDs, dispatch endpoints and queue acknowledgements belong to the superseded baseline proposal. Reintroduce them only for a separately justified durable intake/routing requirement. Installation duration alone does not require a second queue.
6. AI polling is optional: an installation continues independently of the chat, and a later status call retrieves its retained result. A lost response is recovered with the same idempotency key. An uncertain remote outcome requires reconciliation, not blind replay.
7. A backend schema owns onboarding validation; a versioned Markdown guide explains questions and choices. Discover staged files by safe IDs and allow explicit per-host selection. Store secret references rather than secrets in MCP arguments or job records.
8. A selected group/profile changes future context. It does not move an installed PA or redirect an accepted job. Moving or reinstalling an agent is an explicit lifecycle action.
9. `getVersions` is a synchronous read-only catalogue API/tool. It does not require a job or queue. Listing a version does not qualify or authorize its installation.
10. The canonical business fields stay consistent across MCP, APIM, Studio and management REST; protocol wrappers differ. Metrics and executions need separate resource schemas, bounded queries and pagination rather than one giant result.

These are design decisions. The complete containerized management/MCP product has not been deployed or qualified by the QA research in this repository.

## Operational findings and their limits

| Finding | Evidence and consequence |
| --- | --- |
| Core health is distinct from deployment readiness | Agent registration, Harmony connectivity and Axis HTTP 200 passed while deployment failed because Gmail was unavailable to the connector registry. Check the affected connector separately. |
| HTTP success is not application success | `/axis/v1/token/3lo/invalidate` returned HTTP 200 with `status:false`, null error fields and empty outcome lists. Inspect the logical result and correlated server evidence. |
| Working connector recovery | Customer updated connectors, tested the saved Gmail connection, then could deploy. Gmail loaded at 09:28:25 UTC on 12 October 2026. Deployment success is customer-confirmed; a recovered `status:true` body was not captured. |
| Immediate registry failure versus underlying cause | Entity 37201 mapped to Gmail Endpoint. Axis could not find its adapter. File-lock/retry exceptions occurred in the load window, but are not conclusive proof of the sole underlying cause. |
| Reinstallation is not a generic repair | The error persisted after a v12.10 installation and a fresh PAG/environment. Diagnose transport, handler result and connector availability before proposing another reinstall. |
| Earlier Axis packaging fault was real but separate | A prior v12.11 expansion had 161 of 256 JARs and Axis returned 404. Controlled re-expansion restored the expected library set and HTTP 200, but did not resolve the later deployment error. |
| Proxy account did not match this case | Vendor proxy configuration reported disabled; inspected startup/environment/config fields did not show a proxy server, and actual responses were HTTP 200 rather than 503. Runtime-set JVM properties were not inspected because `jcmd` was unavailable. Shell `no_proxy` alone does not prove Java proxy behavior. |
| Protected registration fields have strict formatting | LocalFileSecretProvider rejected a trailing newline in the PAG field. Validate single-line values without control characters; never log their contents. |
| Registration token renewal can be necessary | The old token failed registration into the newly created PAG; a newly generated token succeeded. Keep token values out of repository artifacts. |
| Transient files are not stable identity sources | Registration files may disappear after successful registration. Check protected configuration references, runtime identity and Harmony records rather than require a transient file to exist. |
| Full uninstall resets local research continuity | Keep captures from previous agent identities as historical evidence. Do not interpret counters across a rebuilt TranDb as one uninterrupted history. |

Historical 12 October QA observation: PA **12.10.1.1**, agent **667310**, PAG **679240**, environment **571300**, JBPA **1.0.0-rc9**. These identifiers document this case, not customer defaults. The QA VM has a scoped sizing exception; this is not production sizing qualification.

## TranDb and observability findings

- Read the database settings locally from `/opt/jitterbit/jitterbit.conf` through the existing provider. Never return its username/password. The observed endpoint is PgBouncer on port 6432; `PGOPTIONS` startup parameters were rejected. Use explicit read-only transactions and local statement/lock timeouts.
- Definition IDs/GUIDs and execution GUIDs are different identities. Qualify records by customer/source/host/environment. Use execution GUIDs for runs and local row IDs only as local cursors.
- Parent/root execution GUIDs and runtime links allow hierarchy reconstruction. Workload captures showed four nested levels. Missing or cross-agent parents must remain unresolved rather than fabricated.
- `status_ts` is a status-transition timestamp, not an independently verified finish-time column. Preserve raw status codes and timestamps; qualify normalized semantics from known workloads.
- Transformation summaries, progress and file counters have different grains. Avoid multiplying totals through joins; preserve raw units until validated against known inputs/outputs.
- Samples are bounded; absence is not deletion or proof of non-execution. Retention, `ignore_history`, cross-agent routing and short runs can hide executions. Query failures are unavailable data, not zero.
- Query snapshots are taken at different instants. The harness is not a lossless event stream. Full profiling adds load; prefer reporting-only queries during busy execution.
- PostgreSQL statistics are not host CPU, JVM heap/GC or Apache/Tomcat metrics. Host/service collectors remain a separate deferred observability upgrade.

## Executable requery paths

From the repository root, inspect saved knowledge without contacting the VM:

```bash
python3 -m json.tool docs/trandb/knowledge-catalogue.json
rg -n 'gmail|statusMapping|relationships|connectorReadinessRunbook' docs/trandb/knowledge-catalogue.json
python3 scripts/management/trandb-workload.py --help
```

For authorized live research, use a protected inventory and a new output directory:

```bash
python3 scripts/management/trandb-workload.py capture \
  --inventory secrets/qa-troubleshooting-inventory.json \
  --target JBLAB-PA-AUTOMATION \
  --output output/trandb/workloads/next-observation --limit 500
```

The named QA inventory is private and ignored by Git; customers supply their own inventory. Do not commit keys, credentials or private inventory. Compare two existing bundles offline with the `compare` subcommand documented in the research workflow.

The SQL library is `docs/trandb/reporting-queries.sql`. Reusable collectors include `inspect-trandb.py`, `capture-trandb.py`, `validate-trandb-reporting.py`, `inspect-agent-proxy.py` and `inspect-agent-deployment.py` in `scripts/management/`. The specialized `capture-invalidation-response.py` is a bounded passive loopback observer for this diagnosed route/port, not a general management API or automatic remedy. Raw packet data stays in memory and exported structure is filtered. Use it only under the applicable authorized diagnostic workflow.

## Qualification still required

Implement and qualify per-connector readiness reporting and safe, explicit recovery; do not declare automatic remediation complete. Validate install/upgrade/uninstall, worker ownership, idempotency, uncertain-outcome reconciliation, backup/restore and MCP compatibility end to end. Observability remains deferred until the baseline works; finish-time meanings, counter units and retention behavior still require controlled workload evidence. No new infrastructure, connector refresh, project deployment or lifecycle mutation is performed by documenting these findings.

## Skill and composite-query additions

The matching Codex/Claude JBPA skills now route operation and SFTP diagnosis through the query/interpretation workflow in [operation-assessment-api.md](trandb/operation-assessment-api.md). The [MCP/API planning contract](trandb/operation-assessment-contract.json) defines one composite read action with scope, findings, source coverage and drill-down. [Root SQL](trandb/operation-assessment.sql) and `scripts/management/assess-trandb.py` make the QA evidence requeryable. Production service implementation remains deferred under UPG-001.

## Estate health workstream

[Estate-wide health](estate-health.md) builds on the RATP metric families while preserving the no-added-PA-listener default. Available telemetry is sampled; missing sources remain gaps; errors and capacity pressure are interpreted separately. A validated QA collector/evaluator exists; roster discovery, APIs, history shipping and production qualification remain pending.

## Vendor-owned upgrades — 14 October 2026

The deployed JBPA upgrade verifier restarted an agent already started by the vendor post-install script. The 12.10.1.1 to 12.11.3.2 upgrade was reported successful despite incomplete Axis expansion (118 missing JARs, one truncated JAR, conversion/OAuth 404s). The double-restart path and false-success record are confirmed; causation of the interrupted extraction is strongly supported, not independently reproduced.

User decision: JBPA triggers and monitors Jitterbit installation/configuration; it does not disable vendor startup, alter scripts, rebuild applications, change deployment permissions or override vendor-restored configuration during normal upgrades. The new observer performs fresh runtime and read-only application readiness checks without restarting. Recovery repairs are separate explicit incident actions. Downgrade requests use qualified uninstall/fresh reinstall, retaining evidence and checking resources before destruction. See [upgrade contract and recovery](vendor-owned-upgrades.md). Unit validation does not establish live upgrade qualification.

Fresh-install learning from the 12.9 reset: do not assume a successfully installed package has started Tomcat. Observe whether vendor startup is actually in progress before waiting for expansion. When the package is installed and services are stopped, use the supported fresh-registration/start path. Preserve initial failures separately from recovery success. This reset registered new agent 667590 in PAG 679240; it does not qualify a later upgrade.

## Fixed upgrade validated — 15 October 2026

The fixed observer successfully upgraded JBLAB-PA-AUTOMATION from 12.9.2.2 to 12.11.3.2 with the normal vendor installer and no verification restart or manual Axis repair. The user explicitly authorized the two-vCPU exception for this exact host/package; it is a separate approval from the earlier 12.9 exception. Pin the exact package and digest before execution; neither a sizing exception nor a successful QA run promotes a release to production qualification.

All 302 Axis files matched the packaged archive and conversion/connector WSDL checks passed. Fresh authentication, login, request flow and heartbeat were observed. Native status reported all services running. Independent final health was HEALTHY. Agent 667590 and PAG 679240 were retained; all 15 operation definitions matched the baseline, all 25 reporting queries passed, and active/pending work and log-sync backlog were empty.

Readiness has explicit limits: an OAuth GET returning 405 with Allow PUT confirms route presence, not successful token invalidation. Valid connector WSDLs do not prove a saved Gmail connection works. Preserved synchronized deployment records do not prove a new cloud deployment occurred. No business/connector canary was executed. The supplementary AgentSupportTools service-status parser remained unavailable; native status and application/runtime evidence supplied service verification. Do not mask an unavailable provider as a passing provider.

After independently confirming retained agent/group and installed version, refresh only JBPA expected-health metadata with a protected backup. Never overwrite vendor-restored configuration to satisfy a health check. Keep initial failures and later recovery/upgrade outcomes separately dated. The exact upgrade outcome and portable, sanitized evidence are in [the validation report](upgrade-12.11.3.2-qa-validation.md) and [evidence summary](../evidence/pa-12.11.3.2/fixed-upgrade-2026-10-15.json). Raw captures, private inventory and generated candidates remain local and ignored by Git.

## Interactive read performance — 15 October 2026

Measured full reporting was dominated by eight SSH/SCP invocations and temporary staging, not SQL. The median of three captures fell from 18.180 to 2.978 seconds after replacing staging with one integrity-checked in-memory SSH execution; all original 25 SQL reports remain unchanged. A focused running query takes a median 2.341 seconds on the same idle QA agent. Route ordinary questions to focused running/active/errors/definitions/backlog/identity modes and reserve full reporting/profile for broader assessment. No services/ports, persistent sessions, cached credentials or database writes were added. Timings exclude AI reasoning/scheduling and do not qualify production peak-load latency. See [read path](read-path-performance.md) and the portable benchmark evidence.
