# Estate-wide expert health assessment

Updated 12 October 2026. The read-only QA collector, fleet evaluator, CLI and Prometheus gauge renderer are implemented. HTTP/MCP deployment, Harmony roster discovery, historical Prometheus query integration and production qualification are not implemented. This document defines those interfaces and the complete evidence/qualification boundary.

## Purpose and customer experience

The customer asks: “Assess all agents in this estate, explain performance problems, and tell me whether to add agents or increase VM capacity.” One management action resolves the authorized roster and assessment policy, gathers bounded evidence, explains findings and returns prioritized next actions with source coverage.

An exact interpretation means accurately describing measured facts and their scope. It does not mean inventing a definitive cause or precise VM size from incomplete telemetry. Every unavailable agent/provider remains visible; missing data cannot improve the health result. A successful controller can conceal failed children, and validation errors do not establish insufficient compute capacity.

## Implemented collector coverage

| Domain | Collected today | Interpretation and limits |
| --- | --- | --- |
| CPU/load | Interval CPU busy, iowait/steal, load per logical CPU | Separate compute from hypervisor and I/O waits; short windows are not sizing evidence |
| Memory | MemAvailable/total, swap used and swap-in/out rates, memory PSI | Cache is not automatically pressure; allocated swap alone does not trigger a fault |
| Disk space/inodes | Root, PA data/log/temp paths and backing device identity | Repeated paths may share a device; do not sum them as independent storage |
| Disk I/O | Per-device IOPS, bytes/sec, await, busy time, in-flight I/O and I/O PSI | Devices/layers are not summed; NVMe/cloud IOPS limits need provider/context evidence |
| Network/sockets | Interface rates/errors/drops, socket/kernel FD counters | Link speed, retransmits and cloud egress limits need qualified history/adapters |
| Process resources | PA-account Java/Apache/native process CPU, RSS, threads, FDs/limits and I/O counters | Export no argv/environment; process CPU is percent of one core; RSS is not heap |
| Containers/cgroups | Current root cgroup CPU/memory/pid limits/events and throttle/OOM deltas | Service-specific subgroups and namespace mapping still require qualification |
| PA services/connectivity | Native status plus classified Support Tools connection/service checks | Explicit inner results only; unrecognized output is unknown, not successful |
| Apache | Existing configured loopback mod_status worker/scoreboard/cumulative counters | Absent endpoint is a coverage gap; no module/listener added by the assessment |
| JVM/Tomcat | Existing RATP-compatible JMX metrics and per-PA-JVM jstat when available | Heap/GC/thread pools/requests; unsupported/missing tools remain gaps; one configured exporter does not establish every JVM is instrumented |
| TranDb state | Version/size, identity, connections/waits/limits, locks, maintenance statistics, DB counters/I/O timing setting | Fixed read-only queries via PgBouncer; no raw SQL text or secret config export |
| Operation health | Recent statuses/by-definition, active/pending ages, oldest work and bounded execution details | Raw statuses preserved; status_ts is not a verified completion time; current summary is not full history |
| Queue/sync | Incoming queue and log sync counts, before/after active backlog | Requires source-time/group interpretation; queue growth over seconds is not a capacity model |
| Errors | Recent error/warning message metadata, classified native log tails | Logs may contain historical faults; classification alone does not identify a current cause |
| Clock | NTP synchronization indicator, uptime and observed timestamps | Clock drift magnitude/timezone mappings need additional qualified measurement |

The detailed project/transfer assessment remains available via `pa_assess_operations`. Estate health selects problematic roots for that drill-down; it does not indiscriminately dump every operation message. SFTP authentication or missing-file cleanup messages must not be mistaken for CSV business validation failures.

## Fleet completeness and authorization

The CLI selects explicit inventory targets or all targets in the supplied private inventory. An expected roster can additionally expose missing/unreachable targets. It never uses expected roster names as permission to discover arbitrary hosts.

The production coordinator must reconcile the customer-authorized Harmony organization/PAG agent list with management inventory and observed local agent identities. Report online/offline/draining agents, inaccessible targets, uninstrumented Java processes, stale observations, duplicate host aliases and unsupported agent builds. A single reachable PA does not establish complete PAG/estate coverage. Current CLI deliberately reports `rosterVerifiedAgainstHarmony=false`.

Discovery does not read credentials.txt/register.json into the response. The local `key_values` identity allowlist is metadata, not proof of current Harmony authentication; use qualified connectivity/identity checks. Agent aliases require canonical identity reconciliation before metrics or capacity totals are merged. Group context and operation-specific SLOs are management-owned validated configuration, not AI assertions.

## API and MCP actions

| Action | Proposed route | Behavior |
| --- | --- | --- |
| `estate_assess_health` | `POST /v1/estate/health-assessments` | Select authorized groups/targets/window and basic/deep/capacity mode; return assessment ID |
| `estate_get_health_assessment` | `GET /v1/estate/health-assessments/{assessmentId}` | Retained aggregate/per-agent findings, coverage, measurements and evidence references |
| `pa_get_health` | `GET /v1/targets/{targetId}/health` | Last qualified snapshot and freshness; no hidden synchronous long scan |
| `pa_assess_operations` | Existing proposed operation-assessment route | Drill into failing/slow/pending root executions and connector/log evidence |

AI → Jitterbit MCP → APIM → Studio → management coordinator → bounded SSH/TranDb/existing telemetry providers. Keep filters, identities, finding codes and coverage canonical. Only management hosts the REST layer. No custom web service, daemon or listening port is installed on the PA by the default collector.

A deep fleet scan can outlast HTTP timeouts. Persist the assessment request in the existing management durable work model, return HTTP 202 with assessmentId, and let the worker collect independently. Retrieve results later; AI polling is optional. Do not introduce JBMQ/outbox/dispatch just to perform a deep scan. Cached recent/history assessments can use a short synchronous path. Separate read assessment jobs from lifecycle mutation jobs and expose read-only MCP annotations.

The response includes: selected/expected/observed agents; roster version; source/time/coverage; per-node infrastructure, runtime, database and operation findings; group bottlenecks; measured vs inferred conclusions; policy/SLO revision; ordered remediation options; capacity recommendation confidence and required evidence. A failed HTTP/provider call is unavailable data. One failed agent does not suppress healthy peer evidence. Assessment completion does not mean the estate is healthy.

## Expert interpretation and capacity decisions

Findings are deterministic checks with observed values, threshold/policy, severity, scope, evidence and next action. They are candidates for investigation, not automatic remediation. Thresholds are configurable investigation defaults, not universal vendor limits.

1. Check roster/identity, unavailable services and critical storage/OOM conditions first.
2. Separate application/connector/dependency errors from infrastructure faults. Validation failures should trigger schema/script investigation rather than VM expansion.
3. Identify pressure through multiple signals: CPU plus queue growth; low memory plus swap/PSI/post-GC evidence; disk await plus PSI; Apache/Tomcat occupancy plus request/dependency timing; DB lock/pool pressure plus pending operations.
4. Compare peers within the same qualified PAG/workload. If one host is overloaded while peers are idle, investigate targeting, concurrency, serialization or routing before adding nodes.
5. Consider scale up for a constrained single-operation working set or per-host bottleneck; consider scale out for confirmed distributable work when all qualified peers are saturated. Check DB/dependency headroom, licensing, state/local files, schedule behavior and N-1 failover capacity.
6. Return “insufficient evidence” until representative peak history, workload/SLO context and full source coverage exist. The current CPU candidate rule requires at least five minutes of sustained pressure plus rising pending work; that is a screening minimum, not a production sizing guarantee. Memory/GC/storage findings produce targeted investigations, not an exact SKU or node count.

Production capacity mode needs at least representative peak intervals plus normal/peak baselines and growth expectations. Derive throughput and latency separately from business-record volume; the RATP batching work demonstrates why HTTP request counts cannot stand for telemetry records. Compare arrival/service rates, concurrency, p95/p99 latency, queue age and headroom. Predict disk exhaustion only with a qualified growth trend. Do not claim a VM-size uplift translates linearly to throughput.

Long-running investigation ages are configurable; per-operation SLO overrides are supported. Future duration/latency comparisons require verified terminal timing semantics and history. Current settings such as CPU 85%, memory available 10%, filesystem/inode used 90%, pending 300s and long-running 1800s are conservative configurable screening defaults. Customers must tune them to workload/SLOs.

## Reuse of RATP and Grafana shipping

Reviewed sources: `RATP API Processing Verification/health/scripts/host-health-snapshot.sh`, `docs/private-agent-jvm-apache-tomcat-observability.md`, `docs/observability-plan.md`, `grafana/alloy/alloy-agent-jitterbit-observability.alloy` and `jitterbit/agent/observability/jmx-exporter-private-agent.yaml`.

Reuse metric families, component separation, before/during/after evidence and counter-reset handling. Improve the snapshot behavior: unavailable metrics are null/coverage gaps rather than synthetic zeros. Do not copy its deployment script automatically: it changes Apache/JVM settings, adds scrape ports, restarts services and installs Alloy on each PA. Those changes need a separately selected and qualified instrumentation profile.

The default produces `health.prom` gauges on management, with stable target labels and no run/file IDs. The management-only [Alloy example](../config/examples/estate-health-management.alloy) can read a textfile publication directory and remote-write to a customer Prometheus/Mimir/Grafana backend. Deploy/validate that separately; nothing has been shipped to Grafana by this task. Exported gauges represent sampled/window values, not lifetime counters. Include observed_timestamp_seconds and collection/coverage indicators so stale data cannot appear fresh. Do not put every dated evidence bundle in a textfile scrape directory: atomically publish only latest-per-scope series to avoid duplicate/stale samples. Group-readable permissions and private secret provisioning must be configured for the collector/Alloy service identities.

Historical ingestion is a management background task, independent of AI requests. Use customer/estate/group/canonical-host/agent/component identity, provider/schema revision, UTC sample time and units. Define scrape cadence, retention/rollups, freshness deadlines, counter resets, label/cardinality caps, tenant isolation and raw-log redaction. Grafana is a presentation/query client; Prometheus/Mimir is the time-series backend. The historical query adapter and scheduled publication are not yet implemented.

## Run and replay today

```bash
python3 scripts/management/estate-health.py collect \
  --inventory /private/path/customer-inventory.json \
  --profile /private/path/estate-health-profile.json \
  --seconds 30 --interval 5 --concurrency 2 \
  --output output/estate-health/customer-assessment-01

python3 scripts/management/estate-health.py assess \
  --bundle output/estate-health/customer-assessment-01 \
  --output output/estate-health/customer-assessment-replay.json
```

Omit `--profile` to collect available default sources; `--target` can be repeated to limit scope. Only use loopback URLs for existing Apache/JMX endpoints. The [profile example](../config/examples/estate-health-profile.example.json) contains illustrative IDs/addresses; do not treat these as configured endpoints or a verified roster.

Outputs are restricted bundle.json, assessment.json, assessment.md and health.prom. Capture/replay does not modify PA configuration, terminate work, restart services, install exporters, invoke business APIs or alter the database. Python-side and SQL deadlines plus bounded concurrency control collection load. The RC9 TranDb/Support Tools provider is version-scoped; alternative releases/images require qualification.

## Qualification before customer production use

Required tests: representative load; multiple hosts/PAGs; Harmony roster reconciliation; aliases/missing/offline nodes; tenant authorization; deadline/partial source behavior; API/MCP async retrieval; timestamp/history consistency; process/counter resets; cloud storage limits; all JVMs; supported Apache/JMX versions; native metrics compatibility; failed DNS/TLS/dependencies; unbounded log growth and retention; duplicate pagination; backup/restore; secrets/redaction; collector overhead and N-1 capacity. The current CLI/QA validation is a research implementation, not proof of this full production qualification.

Primary references: [Linux pressure stall information](https://www.kernel.org/doc/html/latest/accounting/psi.html), [Jitterbit native observability](https://docs.jitterbit.com/agent/observability/), [Jitterbit metric/capability definitions](https://docs.jitterbit.com/agent/dashboards/), [Grafana Alloy unix/textfile exporter](https://grafana.com/docs/alloy/latest/reference/components/prometheus/prometheus.exporter.unix/).

## QA validation record

Validated on the established JBLAB-PA-AUTOMATION QA host on 12 October 2026. The initial 30-second sample measured mean CPU busy about 1.1%, minimum available memory about 65.6%, and zero running/pending operations; 40 retained validation errors were reported separately. Apache/JMX and per-JVM GC internals remained coverage gaps. A final short smoke capture passed all 15 before and 15 after database queries, rendered health.prom and replayed the result offline. Eleven behavioral tests and lint/skill checks passed. These captures cover one QA host, not a production estate or peak-load capacity study. Evidence: `output/estate-health/qa-2026-10-12` and `output/estate-health/qa-final-2026-10-12`.

## No-port runtime visibility update

The existing Apache status endpoint on port 46908 and an opt-in bounded local attach helper now provide Apache worker, per-JVM heap/GC/thread and Tomcat MBean counters on the qualified QA runtime. No additional PA listener/service or restart is needed. See [method, integrity, cleanup and interpretation](noport-runtime-visibility.md). The earlier 8099/9404 gaps describe the previous exporter-only collector; those scrape ports remain absent.

## Loaded no-port validation

The restarted-load capture (18:51–18:56 SAST, 12 October) closed Apache/JVM/Tomcat gaps with no new services/ports or restart. It observed active parent/child work, CPU mean 48.4%, available memory at least 64.6%, sustained I/O wait and growing log synchronization records. STORAGE_PRESSURE and LOG_SYNC_BACKLOG_GROWING rules now preserve these findings instead of relying only on a fixed device-latency threshold. Sixteen behavioral checks passed. See `output/estate-health/noport-restarted-load-2026-10-12-01/interpretation.md`.
