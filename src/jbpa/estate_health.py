"""Evidence-backed fleet assessment; no collection, mutation, or automatic sizing."""

from datetime import datetime
from statistics import mean

DEFAULT_POLICY = {
    "cpuBusyPercent": 85,
    "cpuStealPercent": 5,
    "memoryAvailablePercent": 10,
    "filesystemUsedPercent": 90,
    "inodeUsedPercent": 90,
    "fdUsedPercent": 85,
    "longRunningSeconds": 1800,
    "pendingSeconds": 300,
    "connectionUsedPercent": 85,
    "ioAwaitMs": 20,
    "ioPressureAvg10": 10,
    "ioWaitPercent": 10,
    "logSyncBacklogRecords": 1000,
    "heapUsedPercent": 85,
    "gcTimePercent": 10,
    "tomcatBusyPercent": 85,
    "minimumCapacityWindowSeconds": 300,
    "sustainedFraction": 0.8,
}


DB_QUERIES = [
    "identity",
    "agentIdentity",
    "connections",
    "limits",
    "locks",
    "tableMaintenance",
    "databaseStats",
    "ioTimingEnabled",
    "recentStates",
    "recentOperations",
    "activeSummary",
    "activeRuns",
    "incomingQueue",
    "logSync",
    "errorMessageCounts",
]


def provider(capture, name):
    p = capture.get("providers", {}).get(name, {})
    return p.get("data") if p.get("status") == "AVAILABLE" else None


def query(capture, label, source="trandbAfter"):
    p = provider(capture, source) or {}
    q = p.get("queries", {}).get(label, {})
    return q.get("data") if q.get("status") == "AVAILABLE" else None


def assess_node(target, capture, policy=None, context=None):
    thresholds = {**DEFAULT_POLICY, **(policy or {})}
    context = context or {}
    findings = []

    def add(code, severity, category, message, evidence, next_action):
        findings.append(
            {
                "code": code,
                "severity": severity,
                "category": category,
                "message": message,
                "evidence": evidence,
                "interpretation": "OBSERVED_CONDITION",
                "nextAction": next_action,
            }
        )

    expected_providers = [
        "host",
        "filesystems",
        "services",
        "trandbBefore",
        "trandbAfter",
        "apache",
        "jvmBefore",
        "jvmAfter",
        "clock",
        "logs",
        "cgroup",
        "sockets",
        "supportTools",
        "jvmProcessesBefore",
        "jvmProcessesAfter",
    ]
    gaps = [
        name
        for name in expected_providers
        if capture.get("providers", {}).get(name, {}).get("status") != "AVAILABLE"
    ]
    agent_identity = {r["key_name"]: r["key_value"] for r in query(capture, "agentIdentity") or []}
    if (
        context.get("agentGroupId")
        and agent_identity.get("Agent_Group_Id")
        and str(context["agentGroupId"]) != str(agent_identity["Agent_Group_Id"])
    ):
        add(
            "AGENT_GROUP_IDENTITY_MISMATCH",
            "CRITICAL",
            "availability",
            "Observed agent group differs from the configured estate context.",
            {
                "expectedGroup": context["agentGroupId"],
                "observedGroup": agent_identity["Agent_Group_Id"],
            },
            "Reconcile inventory and Harmony identity before interpreting fleet routing.",
        )
    for name in ["trandbBefore", "trandbAfter"]:
        p = provider(capture, name)
        if p is not None:
            gaps.extend(
                name + "." + key
                for key in DB_QUERIES
                if p.get("queries", {}).get(key, {}).get("status") != "AVAILABLE"
            )
    for row in provider(capture, "jvmProcessesAfter") or []:
        if row.get("status") != "AVAILABLE":
            gaps.append("jvmProcess." + str(row["pid"]) + ".GC_INTERNALS")
        elif row.get("data"):
            snap = row["data"]
            if (
                snap.get("heapMaxBytes", 0) > 0
                and snap.get("heapUsedBytes") is not None
                and snap["heapUsedBytes"] / snap["heapMaxBytes"] * 100
                >= thresholds["heapUsedPercent"]
            ):
                add(
                    "JVM_HEAP_OCCUPANCY_HIGH",
                    "WARNING",
                    "runtime",
                    "An individually measured PA JVM has high heap occupancy.",
                    {
                        "pid": row["pid"],
                        "heapUsedBytes": snap["heapUsedBytes"],
                        "heapMaxBytes": snap["heapMaxBytes"],
                    },
                    "Correlate GC, post-GC heap and allocation; do not equate process RSS with heap.",
                )
            if snap.get("deadlockedThreads", 0) > 0:
                add(
                    "JVM_DEADLOCKED_THREADS",
                    "CRITICAL",
                    "runtime",
                    "The local JVM thread bean reported deadlocked threads.",
                    {"pid": row["pid"], "deadlockedThreads": snap["deadlockedThreads"]},
                    "Investigate the affected runtime; no thread dump or restart is performed automatically.",
                )
    services = provider(capture, "services")
    if services is not None and not services.get("allServicesRunning"):
        add(
            "AGENT_SERVICES_NOT_CONFIRMED_RUNNING",
            "CRITICAL",
            "availability",
            "The native service check did not confirm all services running.",
            services,
            "Inspect service-specific status and qualified Harmony connectivity; do not restart automatically.",
        )
    support = provider(capture, "supportTools")
    if support:
        for key, value in support.items():
            if value is None:
                gaps.append("supportTools." + key)
            elif value is False:
                add(
                    "SUPPORT_TOOLS_CHECK_FAILED",
                    "CRITICAL",
                    "availability",
                    "A qualified support-tool check explicitly failed.",
                    {"check": key},
                    "Inspect local Apache/Tomcat/PostgreSQL/PgBouncer and Harmony reachability; do not infer registration from process existence.",
                )
    before_cg = provider(capture, "cgroupBefore") or {}
    after_cg = provider(capture, "cgroup") or {}

    def numeric_pairs(value):
        result = {}
        for line in value.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit():
                result[parts[0]] = int(parts[1])
        return result

    memory_before = numeric_pairs(before_cg.get("memory.events", ""))
    memory_after = numeric_pairs(after_cg.get("memory.events", ""))
    if (
        memory_after.get("oom_kill", 0) > memory_before.get("oom_kill", 0)
        and "oom_kill" in memory_before
    ):
        add(
            "CGROUP_OOM_KILL",
            "CRITICAL",
            "capacity",
            "The collector cgroup recorded additional OOM kills during capture.",
            {"oomKillDelta": memory_after["oom_kill"] - memory_before["oom_kill"]},
            "Investigate the affected cgroup/service and memory limits; global free RAM may not reflect its available memory.",
        )
    cpu_before = numeric_pairs(before_cg.get("cpu.stat", ""))
    cpu_after = numeric_pairs(after_cg.get("cpu.stat", ""))
    if (
        "nr_throttled" in cpu_before
        and cpu_after.get("nr_throttled", 0) > cpu_before["nr_throttled"]
    ):
        add(
            "CGROUP_CPU_THROTTLING",
            "WARNING",
            "capacity",
            "Cgroup CPU throttling counters increased during capture.",
            {"throttledPeriodsDelta": cpu_after["nr_throttled"] - cpu_before["nr_throttled"]},
            "Review cpu.max and workload; adding host vCPUs without changing a restrictive quota may not help.",
        )
    if provider(capture, "clock") is False:
        add(
            "CLOCK_SYNC_NOT_CONFIRMED",
            "WARNING",
            "host",
            "Clock synchronization is not confirmed by timedatectl.",
            {"source": "timedatectl"},
            "Check time synchronization and token/TLS timestamp correlation.",
        )
    samples = provider(capture, "host") or []
    cpu = [s["cpuBusyPercent"] for s in samples if s.get("cpuBusyPercent") is not None]
    memory = [
        s["memoryAvailablePercent"] for s in samples if s.get("memoryAvailablePercent") is not None
    ]
    duration = sum(s.get("intervalSeconds", 0) for s in samples)
    sustained_cpu = (
        bool(cpu)
        and sum(x >= thresholds["cpuBusyPercent"] for x in cpu) / len(cpu)
        >= thresholds["sustainedFraction"]
    )
    if sustained_cpu:
        add(
            "CPU_PRESSURE_IN_SAMPLE",
            "WARNING",
            "capacity",
            "CPU busy exceeds the configured threshold across most sampled intervals.",
            {"meanPercent": mean(cpu), "windowSeconds": duration},
            "Collect representative peak history and correlate backlog, throughput and latency.",
        )
    if any(s.get("cpuStealPercent", 0) >= thresholds["cpuStealPercent"] for s in samples):
        add(
            "CPU_STEAL",
            "WARNING",
            "host",
            "Hypervisor steal time was observed above the threshold.",
            {"maxStealPercent": max(s.get("cpuStealPercent", 0) for s in samples)},
            "Investigate VM scheduling/host contention before increasing worker concurrency.",
        )
    if memory and min(memory) < thresholds["memoryAvailablePercent"]:
        add(
            "MEMORY_HEADROOM_LOW",
            "WARNING",
            "capacity",
            "Available memory fell below the configured threshold.",
            {"minimumAvailablePercent": min(memory)},
            "Inspect process RSS, heap after GC, native memory, swap activity and container limits.",
        )
    if any(
        s.get("swapInPagesPerSecond", 0) > 0 or s.get("swapOutPagesPerSecond", 0) > 0
        for s in samples
    ):
        add(
            "ACTIVE_SWAPPING",
            "WARNING",
            "capacity",
            "Swap activity occurred during sampling; allocated swap alone is not used as proof of pressure.",
            {"windowSeconds": duration},
            "Correlate memory PSI, available memory and latency before recommending more RAM.",
        )
    io_pressure = False
    for s in samples:
        pressure = s.get("pressure", {}).get("io", {}).get("some", {}).get("avg10", 0)
        slow = [
            d
            for d in s.get("diskIo", [])
            if max(d.get("readAwaitMs") or 0, d.get("writeAwaitMs") or 0) >= thresholds["ioAwaitMs"]
        ]
        if pressure >= thresholds["ioPressureAvg10"] and (
            slow or s.get("cpuIoWaitPercent", 0) >= thresholds["ioWaitPercent"]
        ):
            io_pressure = True
    if io_pressure:
        add(
            "STORAGE_PRESSURE",
            "WARNING",
            "capacity",
            "I/O stalls correlate with elevated device wait or CPU I/O wait.",
            {"ioPressureAvg10Threshold": thresholds["ioPressureAvg10"]},
            "Check storage IOPS/throughput limits, PostgreSQL/log traffic and workload; busy-percent alone is not saturation proof.",
        )
    for fs in provider(capture, "filesystems") or []:
        for field, threshold, code in [
            ("usedPercent", "filesystemUsedPercent", "FILESYSTEM_SPACE_LOW"),
            ("inodeUsedPercent", "inodeUsedPercent", "FILESYSTEM_INODES_LOW"),
        ]:
            if fs.get(field) is not None and fs[field] >= thresholds[threshold]:
                add(
                    code,
                    "CRITICAL" if fs[field] >= 97 else "WARNING",
                    "host",
                    "Filesystem headroom is below the configured threshold.",
                    {"path": fs["path"], field: fs[field]},
                    "Review retention, temp/result/log growth and storage expansion; do not delete business files automatically.",
                )
    fd_rows = {}
    for s in samples:
        for p in s.get("processes", []):
            if (
                p.get("fdLimit")
                and p.get("fdCount") is not None
                and p["fdCount"] / p["fdLimit"] * 100 >= thresholds["fdUsedPercent"]
            ):
                fd_rows[p["pid"]] = p
    if fd_rows:
        add(
            "PROCESS_FD_PRESSURE",
            "WARNING",
            "runtime",
            "A PA process is near its file descriptor limit.",
            {"processes": list(fd_rows.values())},
            "Inspect connection/file leaks and limits; increasing the limit alone may hide a leak.",
        )
    for s in samples:
        network = [
            n
            for n in s.get("network", [])
            if any(
                n.get(k, 0)
                for k in ["rxErrorsDelta", "txErrorsDelta", "rxDropsDelta", "txDropsDelta"]
            )
        ]
        if network:
            add(
                "NETWORK_ERRORS_OR_DROPS",
                "WARNING",
                "host",
                "Network error/drop counters increased.",
                {"interfaces": network},
                "Investigate NIC, queueing, bandwidth limits and downstream latency.",
            )
            break
    active_rows = query(capture, "activeSummary")
    active = active_rows[0] if active_rows else {}
    if (active.get("oldest_running_seconds") or 0) > thresholds["longRunningSeconds"]:
        add(
            "LONG_RUNNING_OPERATIONS",
            "WARNING",
            "operations",
            "A running operation exceeds the configured investigation age.",
            active,
            "Compare against operation-specific SLOs; inspect child work/dependencies before cancellation.",
        )
    for run in query(capture, "activeRuns") or []:
        slo = context.get("operationSloSeconds", {}).get(str(run.get("operation_id")))
        if slo and run.get("status") == 3 and (run.get("age_seconds") or 0) > slo:
            add(
                "OPERATION_SLO_EXCEEDED",
                "WARNING",
                "operations",
                "A running operation exceeded its configured operation-specific investigation SLO.",
                {
                    "runId": run["operation_instance_guid"],
                    "ageSeconds": run.get("age_seconds"),
                    "sloSeconds": slo,
                },
                "Drill into the root/child execution, progress and dependency waits.",
            )
    if (active.get("oldest_pending_seconds") or 0) > thresholds["pendingSeconds"]:
        add(
            "OLD_PENDING_OPERATIONS",
            "WARNING",
            "operations",
            "Pending work exceeds the configured queue-age threshold.",
            active,
            "Inspect group availability, routing, concurrency and resource pressure.",
        )
    states = query(capture, "recentStates")
    errors = (
        sum(r["executions"] for r in states if r["status"] in [7, 9, 11])
        if states is not None
        else None
    )
    warnings = (
        sum(r["executions"] for r in states if r["status"] == 6) if states is not None else None
    )
    if errors:
        add(
            "OPERATION_ERRORS_IN_WINDOW",
            "WARNING",
            "operations",
            "Retained executions include failures in the selected window; these are not proof of infrastructure saturation.",
            {
                "errorExecutions": errors,
                "windowHours": (provider(capture, "trandbAfter") or {}).get("windowHours"),
            },
            "Use pa_assess_operations for the affected roots and distinguish validation, connector, dependency and resource errors.",
        )
    limits_rows = query(capture, "limits") or []
    if limits_rows:
        limits = limits_rows[0]
        if (
            limits.get("max_connections")
            and limits["server_connections"] / limits["max_connections"] * 100
            >= thresholds["connectionUsedPercent"]
        ):
            add(
                "DB_CONNECTION_PRESSURE",
                "WARNING",
                "database",
                "PostgreSQL server-wide connection usage is high.",
                limits,
                "Inspect pooler/server connection limits and long transactions; PostgreSQL connections are not PgBouncer client counts.",
            )
        if (limits.get("oldest_idle_transaction_seconds") or 0) > 300:
            add(
                "DB_IDLE_TRANSACTION",
                "WARNING",
                "database",
                "An idle transaction is older than five minutes.",
                limits,
                "Identify its owner through approved diagnostics; do not terminate it automatically.",
            )
    locks = query(capture, "locks") or []
    if locks and locks[0].get("waiting_locks", 0):
        add(
            "DB_LOCK_WAIT",
            "WARNING",
            "database",
            "PostgreSQL has ungranted locks at capture time.",
            locks,
            "Inspect blockers and wait duration; avoid exporting raw SQL text.",
        )
    stats_before = query(capture, "databaseStats", "trandbBefore") or []
    stats_after = query(capture, "databaseStats") or []
    if (
        stats_before
        and stats_after
        and stats_before[0].get("stats_reset") == stats_after[0].get("stats_reset")
    ):
        delta_deadlocks = stats_after[0].get("deadlocks", 0) - stats_before[0].get("deadlocks", 0)
        if delta_deadlocks > 0:
            add(
                "DATABASE_DEADLOCKS_IN_CAPTURE",
                "WARNING",
                "database",
                "Database deadlock counters increased during capture.",
                {"deadlocksDelta": delta_deadlocks},
                "Investigate transaction/locking behavior; more agents can increase shared-resource contention.",
            )
    apache = provider(capture, "apache")
    if apache and int(apache.get("BusyWorkers", 0)) > 0 and int(apache.get("IdleWorkers", 0)) == 0:
        add(
            "APACHE_NO_IDLE_WORKERS",
            "WARNING",
            "runtime",
            "Apache has busy workers and no idle workers at this instant.",
            apache,
            "Check configured capacity, sustained occupancy, request queues and dependency latency before changing worker limits.",
        )
    jvm = provider(capture, "jvmAfter") or []
    values = {m["name"]: m["value"] for m in jvm if not m.get("labels")}
    used, maximum = (
        values.get("jitterbit_jvm_memory_heap_used_bytes"),
        values.get("jitterbit_jvm_memory_heap_max_bytes"),
    )
    if (
        maximum
        and maximum > 0
        and used is not None
        and used / maximum * 100 >= thresholds["heapUsedPercent"]
    ):
        add(
            "JVM_HEAP_OCCUPANCY_HIGH",
            "WARNING",
            "runtime",
            "JVM heap occupancy is high in the sampled endpoint.",
            {"usedBytes": used, "maxBytes": maximum},
            "Check post-GC occupancy, allocation and GC time; process RSS is not Java heap.",
        )
    previous = provider(capture, "jvmBefore") or []
    old = {(m["name"], tuple(sorted(m.get("labels", {}).items()))): m["value"] for m in previous}
    gc_ms = 0
    for m in jvm:
        key = (m["name"], tuple(sorted(m.get("labels", {}).items())))
        if (
            m["name"] == "jitterbit_jvm_gc_collection_time_ms_total"
            and key in old
            and m["value"] >= old[key]
        ):
            gc_ms += m["value"] - old[key]
    jvm_seconds = None
    try:
        endpoints = capture["providers"]
        jvm_seconds = (
            datetime.fromisoformat(endpoints["jvmAfter"]["observedAt"])
            - datetime.fromisoformat(endpoints["jvmBefore"]["observedAt"])
        ).total_seconds()
    except (KeyError, ValueError):
        pass
    if (
        jvm_seconds
        and jvm_seconds > 0
        and gc_ms / (jvm_seconds * 1000) * 100 >= thresholds["gcTimePercent"]
    ):
        add(
            "JVM_GC_TIME_HIGH",
            "WARNING",
            "runtime",
            "GC collection-time counters increased materially during sampling.",
            {"gcTimeDeltaMs": gc_ms, "jvmSampleSeconds": jvm_seconds},
            "Check collector semantics, pause percentiles and post-GC heap before sizing; summed collector time is not process CPU.",
        )
    by_labels = {(m["name"], tuple(sorted(m.get("labels", {}).items()))): m["value"] for m in jvm}
    for m in jvm:
        if m["name"] == "jitterbit_tomcat_thread_pool_current_threads_busy":
            maximum = by_labels.get(
                (
                    "jitterbit_tomcat_thread_pool_max_threads",
                    tuple(sorted(m.get("labels", {}).items())),
                )
            )
            if (
                maximum
                and maximum > 0
                and m["value"] / maximum * 100 >= thresholds["tomcatBusyPercent"]
            ):
                add(
                    "TOMCAT_THREAD_PRESSURE",
                    "WARNING",
                    "runtime",
                    "Tomcat busy threads approach the configured maximum.",
                    {"connector": m.get("labels"), "busy": m["value"], "maximum": maximum},
                    "Check sustained occupancy and blocked dependencies; raising maxThreads may worsen memory/DB pressure.",
                )
    before_active = query(capture, "activeSummary", "trandbBefore") or []
    sync_before = query(capture, "logSync", "trandbBefore")
    sync_after = query(capture, "logSync")
    unsynced_before = (
        sum(r["records"] for r in sync_before if r.get("is_synced") == 0)
        if sync_before is not None
        else None
    )
    unsynced_after = (
        sum(r["records"] for r in sync_after if r.get("is_synced") == 0)
        if sync_after is not None
        else None
    )
    sync_growth = (
        unsynced_after - unsynced_before
        if unsynced_before is not None and unsynced_after is not None
        else None
    )
    if (
        unsynced_after is not None
        and unsynced_after >= thresholds["logSyncBacklogRecords"]
        and sync_growth is not None
        and sync_growth > 0
    ):
        add(
            "LOG_SYNC_BACKLOG_GROWING",
            "WARNING",
            "runtime",
            "Records marked not synced accumulated during the capture.",
            {
                "recordsBefore": unsynced_before,
                "recordsAfter": unsynced_after,
                "growth": sync_growth,
            },
            "Check whether this backlog drains after load, logging volume, sync errors and Harmony connectivity; these are sync records, not failed operations.",
        )
    queue_growth = (
        active.get("pending", 0) - before_active[0].get("pending", 0)
        if before_active and active_rows
        else None
    )
    enough_history = duration >= thresholds["minimumCapacityWindowSeconds"] and bool(
        context.get("representativePeak")
    )
    candidate = (
        enough_history
        and sustained_cpu
        and queue_growth is not None
        and queue_growth > 0
        and not io_pressure
        and not any(f["category"] == "database" or f["severity"] == "CRITICAL" for f in findings)
    )
    status = (
        "CRITICAL"
        if any(f["severity"] == "CRITICAL" for f in findings)
        else "DEGRADED"
        if findings
        else "UNKNOWN"
        if gaps or not samples
        else "HEALTHY"
    )
    return {
        "targetId": target,
        "hostname": capture.get("hostname"),
        "observedAt": capture.get("observedAt"),
        "completedAt": capture.get("completedAt"),
        "agentIdentity": agent_identity,
        "status": status,
        "coverage": "PARTIAL" if gaps else "COMPLETE",
        "coverageGaps": gaps,
        "findings": findings,
        "sampleSeconds": duration,
        "measurements": {
            "cpuMeanPercent": mean(cpu) if cpu else None,
            "minimumAvailableMemoryPercent": min(memory) if memory else None,
            "running": active.get("running"),
            "pending": active.get("pending"),
            "pendingGrowth": queue_growth,
            "errorsInWindow": errors,
            "warningsInWindow": warnings,
            "unsyncedLogRecords": unsynced_after,
            "unsyncedLogGrowth": sync_growth,
        },
        "capacity": {
            "decision": "CPU_CAPACITY_CANDIDATE" if candidate else "INSUFFICIENT_EVIDENCE",
            "sustainedCpu": sustained_cpu,
            "representativePeakConfirmed": bool(context.get("representativePeak")),
            "enoughHistory": enough_history,
            "queueGrowth": queue_growth,
            "horizontallyScalableConfirmed": bool(context.get("horizontallyScalable")),
            "nextAction": "Compare peer saturation, routing, single-operation limits, DB/dependency capacity and load tests; no automatic VM/agent sizing.",
        },
    }


def assess_estate(captures, expected_targets, policy=None, contexts=None, roster_verified=False):
    contexts = contexts or {}
    nodes = []
    for target in expected_targets:
        capture = captures.get(target)
        if capture is None:
            nodes.append(
                {
                    "targetId": target,
                    "status": "UNKNOWN",
                    "coverage": "UNAVAILABLE",
                    "coverageGaps": ["HOST_UNREACHABLE_OR_NOT_COLLECTED"],
                    "findings": [],
                    "capacity": {"decision": "INSUFFICIENT_EVIDENCE"},
                }
            )
        else:
            nodes.append(assess_node(target, capture, policy, contexts.get(target)))
    candidates = [n for n in nodes if n["capacity"]["decision"] == "CPU_CAPACITY_CANDIDATE"]
    groups = {}
    for n in nodes:
        group = contexts.get(n["targetId"], {}).get("agentGroupId", "UNVERIFIED_GROUP")
        groups.setdefault(str(group), []).append(n)
    recommendations = []
    for group, peers in groups.items():
        loaded = [n for n in peers if n in candidates]
        if not loaded:
            continue
        idle = [
            n
            for n in peers
            if n.get("measurements", {}).get("cpuMeanPercent") is not None
            and n["measurements"]["cpuMeanPercent"] < 40
        ]
        if idle:
            decision = "INVESTIGATE_ROUTING_OR_SERIALIZATION_FIRST"
        elif (
            group != "UNVERIFIED_GROUP"
            and len(loaded) == len(peers)
            and all(n["capacity"].get("horizontallyScalableConfirmed") for n in peers)
            and all(n["coverage"] == "COMPLETE" for n in peers)
            and roster_verified
        ):
            decision = "SCALE_OUT_CANDIDATE_VALIDATE_WITH_LOAD_TEST"
        else:
            decision = "INVESTIGATE_SCALE_UP_VS_SCALE_OUT"
        recommendations.append(
            {
                "agentGroupId": group,
                "decision": decision,
                "targets": [n["targetId"] for n in loaded],
                "exactAdditionalAgents": None,
                "exactVmSize": None,
                "confidence": "CONDITIONAL",
                "requiredEvidence": [
                    "Peak workload and SLOs",
                    "Routing/parallelism",
                    "Dependencies and DB pressure",
                    "Licensing and N-1 failover test",
                ],
            }
        )
    status = (
        "CRITICAL"
        if any(n["status"] == "CRITICAL" for n in nodes)
        else "DEGRADED"
        if any(n["status"] == "DEGRADED" for n in nodes)
        else "UNKNOWN"
        if any(n["status"] == "UNKNOWN" for n in nodes) or not roster_verified
        else "HEALTHY"
    )
    return {
        "schemaVersion": 1,
        "kind": "estateHealthAssessment",
        "status": status,
        "coverage": "COMPLETE"
        if roster_verified and all(n["coverage"] == "COMPLETE" for n in nodes)
        else "PARTIAL",
        "rosterVerifiedAgainstHarmony": roster_verified,
        "expectedTargetCount": len(expected_targets),
        "collectedTargetCount": sum(t in captures for t in expected_targets),
        "nodes": nodes,
        "capacityRecommendations": recommendations,
        "limitations": [
            "Inventory coverage is not proof that every Harmony agent is represented.",
            "A short/idle sample cannot support exact VM or agent sizing.",
            "Process existence does not establish Harmony registration or JVM internal health.",
            "Historical errors and log-tail matches are not automatically current incidents.",
        ],
    }


def prometheus_metrics(assessment):
    """Low-cardinality gauges from an assessment, never raw logs, IDs or credentials."""
    lines = []
    names = {
        "cpuMeanPercent": "cpu_busy_mean_percent",
        "minimumAvailableMemoryPercent": "memory_available_min_percent",
        "running": "operations_running",
        "pending": "operations_pending",
        "errorsInWindow": "operation_errors_in_window",
        "warningsInWindow": "operation_warnings_in_window",
    }
    for node in assessment["nodes"]:
        label = node["targetId"].replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        labels = '{target="' + label + '"}'
        values = {
            "collection_available": 0 if node["coverage"] == "UNAVAILABLE" else 1,
            "coverage_complete": 1 if node["coverage"] == "COMPLETE" else 0,
            "findings": len(node["findings"]),
            **{metric: node.get("measurements", {}).get(field) for field, metric in names.items()},
        }
        if node.get("completedAt"):
            values["observed_timestamp_seconds"] = datetime.fromisoformat(
                node["completedAt"]
            ).timestamp()
        for key, value in values.items():
            if value is not None:
                lines.append("jbpa_health_" + key + labels + " " + str(value))
    return "\n".join(lines) + "\n"
