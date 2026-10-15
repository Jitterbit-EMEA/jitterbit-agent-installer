#!/usr/bin/env python3
"""Bounded Linux PA health capture. No added listener, raw messages or configuration writes."""

import argparse
import base64
import gzip
import hashlib
import json
import os
import pwd
import re
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def utc():
    return datetime.now(timezone.utc).isoformat()


def guarded(fn):
    started = time.monotonic()
    try:
        return {
            "status": "AVAILABLE",
            "observedAt": utc(),
            "data": fn(),
            "elapsedMs": round((time.monotonic() - started) * 1000),
        }
    except Exception as exc:
        return {"status": "UNAVAILABLE", "observedAt": utc(), "error": type(exc).__name__}


def fields(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        key, _, value = line.partition(":")
        parts = value.split()
        if parts and parts[0].isdigit():
            result[key] = int(parts[0]) * (1024 if parts[-1] == "kB" else 1)
    return result


def sample():
    cpu = list(map(int, Path("/proc/stat").read_text().splitlines()[0].split()[1:9]))
    disks = {}
    for line in Path("/proc/diskstats").read_text().splitlines():
        v = line.split()
        if len(v) < 14 or v[2].startswith(("loop", "ram")):
            continue
        if (Path("/sys/class/block") / v[2] / "partition").exists():
            continue
        disks[v[2]] = list(map(int, v[3:14]))
    network = {}
    for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        name, values = line.split(":")
        v = list(map(int, values.split()))
        if name.strip() != "lo":
            network[name.strip()] = v
    processes = {}
    try:
        agent_uid = pwd.getpwnam("jitterbit").pw_uid
    except KeyError:
        agent_uid = None
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            comm = (p / "comm").read_text().strip()
            # Restrict Java/Apache to the PA account; never export process argv/env.
            if agent_uid is None or p.stat().st_uid != agent_uid:
                continue
            if not re.search(r"java|httpd|apache|Jitterbit|Scheduler|FileCleanup", comm, re.I):
                continue
            stat = (p / "stat").read_text().rsplit(")", 1)[1].split()
            status = fields(p / "status")
            io = fields(p / "io")
            limit = None
            for line in (p / "limits").read_text().splitlines():
                if line.startswith("Max open files"):
                    value = line.split()[3]
                    limit = int(value) if value.isdigit() else None
            processes[p.name] = {
                "name": comm,
                "startTicks": int(stat[19]),
                "cpuTicks": int(stat[11]) + int(stat[12]),
                "rssBytes": status.get("VmRSS"),
                "threads": status.get("Threads"),
                "fdCount": len(list((p / "fd").iterdir())),
                "fdLimit": limit,
                "io": io,
            }
        except (OSError, ValueError, IndexError):
            continue  # Processes can exit during enumeration.
    pressure = {}
    for name in ["cpu", "memory", "io"]:
        path = Path("/proc/pressure") / name
        if path.is_file():
            pressure[name] = {}
            for line in path.read_text().splitlines():
                pieces = line.split()
                pressure[name][pieces[0]] = {
                    k: float(v) for k, v in (piece.split("=") for piece in pieces[1:])
                }
    vm = dict(line.split() for line in Path("/proc/vmstat").read_text().splitlines())
    return {
        "observedAt": utc(),
        "monotonic": time.monotonic(),
        "cpu": cpu,
        "memory": fields("/proc/meminfo"),
        "load": list(os.getloadavg()),
        "disks": disks,
        "network": network,
        "processes": processes,
        "pressure": pressure,
        "swapInPages": int(vm.get("pswpin", 0)),
        "swapOutPages": int(vm.get("pswpout", 0)),
    }


def delta(before, after):
    elapsed = after["monotonic"] - before["monotonic"]
    cpu = [b - a for a, b in zip(before["cpu"], after["cpu"], strict=True)]
    total = sum(cpu)
    if elapsed <= 0 or total <= 0 or any(v < 0 for v in cpu):
        raise ValueError("COUNTER_RESET_OR_INVALID_INTERVAL")
    mem = after["memory"]
    total_mem = mem.get("MemTotal")
    available = mem.get("MemAvailable")
    result = {
        "observedAt": after["observedAt"],
        "intervalSeconds": elapsed,
        "cpuBusyPercent": 100 * sum(cpu[i] for i in [0, 1, 2, 5, 6]) / total,
        "cpuIoWaitPercent": 100 * cpu[4] / total,
        "cpuStealPercent": 100 * cpu[7] / total,
        "memoryAvailableBytes": available,
        "memoryTotalBytes": total_mem,
        "memoryAvailablePercent": 100 * available / total_mem
        if available is not None and total_mem
        else None,
        "swapUsedBytes": mem.get("SwapTotal", 0) - mem.get("SwapFree", 0),
        "swapInPagesPerSecond": max(0, after["swapInPages"] - before["swapInPages"]) / elapsed,
        "swapOutPagesPerSecond": max(0, after["swapOutPages"] - before["swapOutPages"]) / elapsed,
        "loadPerCore": [x / (os.cpu_count() or 1) for x in after["load"]],
        "pressure": after["pressure"],
        "diskIo": [],
        "network": [],
        "processes": [],
    }
    for name, b in after["disks"].items():
        a = before["disks"].get(name)
        if a is None or any(y < x for x, y in zip(a, b, strict=True)):
            continue
        reads, writes = b[0] - a[0], b[4] - a[4]
        result["diskIo"].append(
            {
                "device": name,
                "readsPerSecond": reads / elapsed,
                "writesPerSecond": writes / elapsed,
                "readBytesPerSecond": (b[2] - a[2]) * 512 / elapsed,
                "writeBytesPerSecond": (b[6] - a[6]) * 512 / elapsed,
                "readAwaitMs": (b[3] - a[3]) / reads if reads else None,
                "writeAwaitMs": (b[7] - a[7]) / writes if writes else None,
                "busyPercent": (b[9] - a[9]) / elapsed / 10,
                "inFlight": b[8],
            }
        )
    for name, b in after["network"].items():
        a = before["network"].get(name)
        if a is None:
            continue
        result["network"].append(
            {
                "interface": name,
                "rxBytesPerSecond": max(0, b[0] - a[0]) / elapsed,
                "txBytesPerSecond": max(0, b[8] - a[8]) / elapsed,
                "rxErrorsDelta": max(0, b[2] - a[2]),
                "txErrorsDelta": max(0, b[10] - a[10]),
                "rxDropsDelta": max(0, b[3] - a[3]),
                "txDropsDelta": max(0, b[11] - a[11]),
            }
        )
    ticks = os.sysconf("SC_CLK_TCK")
    for pid, b in after["processes"].items():
        a = before["processes"].get(pid)
        row = {k: v for k, v in b.items() if k not in ["cpuTicks", "io"]}
        row["pid"] = int(pid)
        row["cpuCorePercent"] = None
        if a and a["startTicks"] == b["startTicks"] and b["cpuTicks"] >= a["cpuTicks"]:
            row["cpuCorePercent"] = 100 * (b["cpuTicks"] - a["cpuTicks"]) / ticks / elapsed
        row["readBytesTotal"] = b["io"].get("read_bytes")
        row["writeBytesTotal"] = b["io"].get("write_bytes")
        result["processes"].append(row)
    return result


def filesystems():
    paths = ["/", "/opt/jitterbit", "/opt/jitterbit/log", "/opt/jitterbit/DataInterchange", "/tmp"]
    result = []
    for path in paths:
        if not Path(path).exists():
            continue
        s = os.statvfs(path)
        result.append(
            {
                "path": path,
                "deviceId": os.stat(path).st_dev,
                "sizeBytes": s.f_blocks * s.f_frsize,
                "availableBytes": s.f_bavail * s.f_frsize,
                "usedPercent": 100 * (1 - s.f_bavail / s.f_blocks) if s.f_blocks else None,
                "inodeUsedPercent": 100 * (1 - s.f_favail / s.f_files) if s.f_files else None,
            }
        )
    return result


def services():
    p = subprocess.run(
        ["/opt/jitterbit/bin/jitterbit", "status"], capture_output=True, text=True, timeout=20
    )
    expected = ["JitterbitProcessEngine", "Scheduler", "FileCleanup", "VerboseLogShipper"]
    return {
        "commandExitCode": p.returncode,
        "allServicesRunning": p.returncode == 0
        and "All services are running" in p.stdout
        and all(name + " is running" in p.stdout for name in expected),
        "requiredServiceMentions": {name: name in p.stdout for name in expected},
    }


def support_tools():
    sys.path[:0] = [
        "/opt/jbpa/releases/jbpa-1.0.0-rc9/lib",
        "/opt/jbpa/releases/jbpa-1.0.0-rc9/src",
    ]
    from jbpa.restart_health import connection_check, support_service_status

    result = {}
    for name, parse in [
        ("connection-check", connection_check),
        ("service-status", support_service_status),
    ]:
        p = subprocess.run(
            ["/bin/bash", "/opt/jitterbit/AgentSupportTools/run.sh"],
            input=name + "\nexit\n",
            capture_output=True,
            text=True,
            cwd="/opt/jitterbit/AgentSupportTools",
            timeout=30,
        )
        result[name] = parse(p.stdout, p.returncode)
    return result


def database(window_hours):
    sys.path[:0] = [
        "/opt/jbpa/releases/jbpa-1.0.0-rc9/lib",
        "/opt/jbpa/releases/jbpa-1.0.0-rc9/src",
    ]
    from jbpa.pending_operations import TranDbOperationProvider

    def runner(argv, **kwargs):
        env = dict(kwargs.get("env", {}))
        env.pop("PGOPTIONS", None)
        kwargs["env"] = env
        return subprocess.run([argv[0], "-q", *argv[1:]], **kwargs)

    provider = TranDbOperationProvider(runner=runner)
    recent = f"entered_ts >= now()-interval '{int(window_hours)} hours'"
    sqls = {
        "identity": "SELECT current_setting('server_version') server_version,pg_database_size(current_database()) database_bytes,current_setting('transaction_read_only') read_only",
        "agentIdentity": "SELECT key_name,key_value FROM key_values WHERE key_name IN ('Agent_Group_Id','Agent_Group_Name','Agent_Id','Agent_Name','VersionNumber','Agent_Group_Size') ORDER BY key_name",
        "connections": "SELECT state,wait_event_type,count(*) count FROM pg_stat_activity WHERE datname=current_database() GROUP BY state,wait_event_type",
        "limits": "SELECT current_setting('max_connections')::int max_connections,(SELECT count(*) FROM pg_stat_activity) server_connections,count(*) FILTER (WHERE state='idle in transaction') idle_in_transaction,max(extract(epoch FROM now()-xact_start)) FILTER (WHERE state='idle in transaction') oldest_idle_transaction_seconds FROM pg_stat_activity WHERE datname=current_database()",
        "databaseStats": "SELECT numbackends,xact_commit,xact_rollback,blks_read,blks_hit,temp_files,temp_bytes,deadlocks,blk_read_time,blk_write_time,stats_reset FROM pg_stat_database WHERE datname=current_database()",
        "ioTimingEnabled": "SELECT current_setting('track_io_timing') enabled",
        "locks": "SELECT count(*) FILTER (WHERE NOT granted) waiting_locks FROM pg_locks",
        "tableMaintenance": "SELECT relname,n_live_tup,n_dead_tup,last_autovacuum,last_autoanalyze FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 20",
        "recentStates": f"SELECT status,count(*) executions FROM operationlogtab WHERE {recent} GROUP BY status",
        "recentOperations": f"SELECT operation_id,operation_name,status,count(*) executions FROM operationlogtab WHERE {recent} GROUP BY operation_id,operation_name,status ORDER BY executions DESC LIMIT 200",
        "activeSummary": "SELECT count(*) FILTER (WHERE status=3) running,count(*) FILTER (WHERE status IN (0,1,10)) pending,count(*) FILTER (WHERE status=8) cancel_requested,max(extract(epoch FROM now()-started_ts)) FILTER (WHERE status=3) oldest_running_seconds,max(extract(epoch FROM now()-entered_ts)) FILTER (WHERE status IN (0,1,10)) oldest_pending_seconds FROM operationlogtab WHERE status IN (0,1,3,8,10)",
        "activeRuns": "SELECT operation_instance_guid,operation_id,operation_name,environment_id,agent_id,status,entered_ts,started_ts,extract(epoch FROM now()-coalesce(started_ts,entered_ts)) age_seconds FROM operationlogtab WHERE status IN (0,1,3,8,10) ORDER BY coalesce(started_ts,entered_ts) LIMIT 100",
        "incomingQueue": "SELECT isexecuting,count(*) requests FROM incomingmsgtab GROUP BY isexecuting",
        "logSync": "SELECT is_synced,count(*) records FROM logsynctab GROUP BY is_synced",
        "errorMessageCounts": f"SELECT m.field_name,count(*) records FROM operationmessagetab m WHERE EXISTS (SELECT 1 FROM operationlogtab l WHERE l.operation_instance_guid=m.operation_instance_guid AND l.{recent}) AND (m.field_name='Warning' OR m.field_name LIKE 'Fatal Error%') GROUP BY m.field_name LIMIT 100",
    }
    result = {}
    deadline = time.monotonic() + 30
    for name, sql in sqls.items():
        if time.monotonic() >= deadline:
            result[name] = {"status": "SKIPPED_BUDGET", "observedAt": utc()}
            continue

        def run(sql=sql):
            q = (
                "BEGIN READ ONLY; SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='1s'; SELECT coalesce(jsonb_agg(to_jsonb(q)),'[]'::jsonb)::text FROM ("
                + sql
                + ") q; ROLLBACK;"
            )
            return json.loads(provider._query(q))

        result[name] = guarded(run)
    return {
        "windowHours": window_hours,
        "queries": result,
        "snapshotSemantics": "Separate bounded read-only query transactions; no finish-time inference",
    }


def cgroup():
    root = Path("/sys/fs/cgroup")
    result = {}
    for name in [
        "cpu.max",
        "cpu.stat",
        "memory.current",
        "memory.max",
        "memory.events",
        "pids.current",
        "pids.max",
    ]:
        p = root / name
        if p.is_file():
            result[name] = p.read_text().strip()
    if not result:
        raise ValueError("CGROUP_V2_NOT_AVAILABLE")
    result["scope"] = (
        "Collector current cgroup root; individual service subgroups require separate qualification"
    )
    return result


def sockets():
    stats = {}
    for line in Path("/proc/net/sockstat").read_text().splitlines():
        key, values = line.split(":", 1)
        parts = values.split()
        stats[key] = {
            parts[i]: int(parts[i + 1])
            for i in range(0, len(parts) - 1, 2)
            if parts[i + 1].isdigit()
        }
    return {
        "sockstat": stats,
        "note": "Socket counters only; not connection ownership or remote addresses",
        "openFileHandles": list(map(int, Path("/proc/sys/fs/file-nr").read_text().split())),
        "kernelPidMax": int(Path("/proc/sys/kernel/pid_max").read_text()),
    }


def jvm_processes():
    result = []
    uid = pwd.getpwnam("jitterbit").pw_uid
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != uid or (p / "comm").read_text().strip() != "java":
                continue
            stat = (p / "stat").read_text().rsplit(")", 1)[1].split()
            row = {"pid": int(p.name), "startTicks": int(stat[19]), "status": "UNAVAILABLE"}
            exe = (p / "exe").resolve()
            tool = exe.parent / "jstat"
            if tool.is_file():
                command = subprocess.run(
                    [str(tool), "-gc", p.name], capture_output=True, text=True, timeout=3
                )
                lines = command.stdout.splitlines()
                if command.returncode == 0 and len(lines) >= 2:
                    keys, values = lines[0].split(), lines[1].split()
                    if len(keys) == len(values):
                        row["gcCounters"] = {
                            k: float(v)
                            for k, v in zip(keys, values, strict=True)
                            if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", v)
                        }
                        row["status"] = "AVAILABLE"
                        row["source"] = (
                            "Same-runtime jstat -gc; capacities/use are KiB, times seconds"
                        )
            result.append(row)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    return result


def local_jvm_snapshots(jar, helper, expected_hash):
    if not str(jar).startswith("/var/tmp/jbpa-noport-") or not str(helper).startswith(
        "/var/tmp/jbpa-noport-"
    ):
        raise ValueError("CONTROLLED_STAGE_REQUIRED")
    if hashlib.sha256(Path(jar).read_bytes()).hexdigest() != expected_hash:
        raise ValueError("PROBE_DIGEST_MISMATCH")
    output = Path(jar).parent / "output"
    result = []
    uid = pwd.getpwnam("jitterbit").pw_uid
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != uid or (p / "comm").read_text().strip() != "java":
                continue
            start = int((p / "stat").read_text().rsplit(")", 1)[1].split()[19])
            name = output / ("metrics-" + p.name + "-" + uuid.uuid4().hex + ".json")
            command = subprocess.run(
                ["python3", str(helper), "--pid", p.name, "--jar", str(jar), "--output", str(name)],
                capture_output=True,
                text=True,
                timeout=12,
            )
            row = json.loads(command.stdout) if command.stdout else {"status": "UNAVAILABLE"}
            row.update(
                {
                    "pid": int(p.name),
                    "startTicks": start,
                    "observedAt": utc(),
                    "source": "Bounded local attach; no network port",
                }
            )
            result.append(row)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            result.append({"pid": int(p.name), "status": "UNAVAILABLE"})
    if not result:
        raise ValueError("NO_PA_JVMS")
    return result


def probe_metrics(rows):
    result = []
    for row in rows:
        if row.get("status") != "AVAILABLE":
            continue
        snapshot = row["data"]
        labels = {"pid": str(row["pid"]), "startTicks": str(row["startTicks"])}
        fields = {
            "heapUsedBytes": "memory_heap_used_bytes",
            "heapCommittedBytes": "memory_heap_committed_bytes",
            "heapMaxBytes": "memory_heap_max_bytes",
            "nonheapUsedBytes": "memory_nonheap_used_bytes",
            "liveThreads": "threads_current",
            "daemonThreads": "threads_daemon",
            "peakThreads": "threads_peak",
        }
        for field, name in fields.items():
            result.append(
                {"name": "jitterbit_jvm_" + name, "labels": labels, "value": snapshot[field]}
            )
        for gc in snapshot["gc"]:
            for field, name in [
                ("count", "collection_count_total"),
                ("timeMs", "collection_time_ms_total"),
            ]:
                if gc[field] >= 0:
                    result.append(
                        {
                            "name": "jitterbit_jvm_gc_" + name,
                            "labels": {**labels, "collector": gc["name"]},
                            "value": gc[field],
                        }
                    )
        for index, bean in enumerate(snapshot["tomcat"]):
            names = {
                "ThreadPool": {
                    "currentThreadCount": "thread_pool_current_threads",
                    "currentThreadsBusy": "thread_pool_current_threads_busy",
                    "maxThreads": "thread_pool_max_threads",
                },
                "GlobalRequestProcessor": {
                    "requestCount": "global_request_processor_request_count_total",
                    "errorCount": "global_request_processor_error_count_total",
                    "processingTime": "global_request_processor_processing_time_ms_total",
                },
            }
            for attr, name in names.get(bean["type"], {}).items():
                if attr in bean["attributes"]:
                    result.append(
                        {
                            "name": "jitterbit_tomcat_" + name,
                            "labels": {
                                **labels,
                                "connector": bean["connector"],
                                "beanIndex": str(index),
                            },
                            "value": bean["attributes"][attr],
                        }
                    )
    if not result:
        raise ValueError("LOCAL_JVM_METRICS_UNAVAILABLE")
    return result


def listening_ports():
    command = subprocess.run(["ss", "-H", "-ltnu"], capture_output=True, text=True, timeout=3)
    if command.returncode:
        raise ValueError("LISTENER_DISCOVERY_UNAVAILABLE")
    return sorted(
        [
            {"protocol": v[0], "localEndpoint": v[4]}
            for line in command.stdout.splitlines()
            if len(v := line.split()) > 4
        ],
        key=lambda r: (r["protocol"], r["localEndpoint"]),
    )


def endpoint(url, kind):
    parts = urlsplit(url)
    if (
        parts.scheme != "http"
        or parts.hostname not in ["127.0.0.1", "localhost", "::1"]
        or parts.username
        or parts.password
    ):
        raise ValueError("ONLY_EXISTING_LOOPBACK_ENDPOINTS_ALLOWED")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(url, timeout=3) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError("ENDPOINT_RESPONSE_LIMIT")
    text = raw.decode("utf-8")
    if kind == "apache":
        allowed = [
            "BusyWorkers",
            "IdleWorkers",
            "Total Accesses",
            "Total kBytes",
            "Uptime",
            "Scoreboard",
        ]
        result = {
            k.strip(): v.strip()
            for line in text.splitlines()
            if ":" in line
            for k, v in [line.split(":", 1)]
            if k.strip() in allowed
        }
        if not all(result.get(k, "").isdigit() for k in ["BusyWorkers", "IdleWorkers"]):
            raise ValueError("APACHE_WORKER_METRICS_NOT_FOUND")
        return result
    result = []
    for line in text.splitlines():
        match = re.match(
            r"^(jitterbit_(?:jvm|tomcat)_[a-z0-9_]+)(?:\{([^}]*)\})?\s+([-+0-9.eE]+)(?:\s+\d+)?$",
            line,
        )
        if not match:
            continue
        value = float(match[3])
        labels = {}
        for key, value_label in re.findall(r'(\w+)="([^"\\]*)"', match[2] or ""):
            if key in ["collector", "connector"] and len(value_label) <= 100:
                labels[key] = value_label
        result.append({"name": match[1], "labels": labels, "value": value})
    if not result:
        raise ValueError("QUALIFIED_JVM_METRICS_NOT_FOUND")
    return result


def existing_apache_url():
    p = Path("/opt/jitterbit/apache/conf/httpd.conf")
    if not p.is_file():
        return None
    text = p.read_text()
    if not re.search(r"SetHandler\s+server-status", text) or not re.search(
        r"Require\s+local", text
    ):
        return None
    match = re.search(r"(?m)^\s*Listen\s+(?:127\.0\.0\.1:)?(\d+)\s*$", text)
    return "http://127.0.0.1:" + match[1] + "/server-status?auto" if match else None


def log_indicators():
    classes = {
        "oom": r"OutOfMemoryError|oom-kill|Killed process",
        "connection": r"Connection refused|Connection reset|timed? out",
        "tls": r"SSLHandshakeException|PKIX",
        "connector_load": r"OverlappingFileLockException|unable to find connector",
        "database": r"deadlock detected|too many clients|remaining connection slots",
        "disk": r"No space left on device|Read-only file system",
    }
    result = []
    for name in [
        "jitterbit-agent.log",
        "jitterbit-axis.log",
        "OperationEngine.log",
        "ProcessEngine.log",
    ]:
        p = Path("/opt/jitterbit/log") / name
        if not p.is_file():
            result.append({"name": name, "available": False})
            continue
        size = p.stat().st_size
        with p.open("rb") as f:
            f.seek(max(0, size - 1048576))
            text = f.read().decode("utf-8", "replace")
        result.append(
            {
                "name": name,
                "available": True,
                "tailTruncated": size > 1048576,
                "modifiedAt": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
                "countsInTail": {k: len(re.findall(v, text, re.I)) for k, v in classes.items()},
            }
        )
    return {
        "logs": result,
        "semantics": "Tail indicators may be historical; no raw text or causal attribution",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--apache-url")
    parser.add_argument("--jmx-url")
    parser.add_argument("--local-jvm-probe")
    parser.add_argument("--local-jvm-helper")
    parser.add_argument("--local-jvm-probe-sha256")
    parser.add_argument("--compressed-output", action="store_true")
    args = parser.parse_args()
    args.apache_url = args.apache_url or existing_apache_url()
    if (
        not 5 <= args.seconds <= 300
        or not 1 <= args.interval <= 30
        or not 1 <= args.window_hours <= 24
    ):
        parser.error("Invalid sampling/window bounds")
    out = {
        "schemaVersion": 1,
        "kind": "estateNodeCapture",
        "observedAt": utc(),
        "readOnly": True,
        "hostname": socket.gethostname(),
        "logicalCpus": os.cpu_count(),
        "uptimeSeconds": float(Path("/proc/uptime").read_text().split()[0]),
        "sampleWindowSeconds": args.seconds,
        "providers": {},
    }
    providers = out["providers"]
    providers["listeningPortsBefore"] = guarded(listening_ports)
    providers["filesystems"] = guarded(filesystems)
    providers["cgroupBefore"] = guarded(cgroup)
    providers["sockets"] = guarded(sockets)
    providers["services"] = guarded(services)
    providers["trandbBefore"] = guarded(lambda: database(args.window_hours))
    providers["logs"] = guarded(log_indicators)
    providers["apache"] = (
        guarded(lambda: endpoint(args.apache_url, "apache"))
        if args.apache_url
        else {"status": "NOT_CONFIGURED"}
    )
    providers["jvmBefore"] = (
        guarded(lambda: endpoint(args.jmx_url, "jvm"))
        if args.jmx_url
        else {"status": "NOT_CONFIGURED"}
    )
    if args.local_jvm_probe:
        providers["jvmProcessesBefore"] = guarded(
            lambda: local_jvm_snapshots(
                args.local_jvm_probe, args.local_jvm_helper, args.local_jvm_probe_sha256
            )
        )
        providers["jvmBefore"] = guarded(
            lambda: probe_metrics(providers["jvmProcessesBefore"]["data"])
        )
    else:
        providers["jvmProcessesBefore"] = guarded(jvm_processes)
    samples = []
    first = guarded(sample)
    if first["status"] == "AVAILABLE":
        before = first["data"]
        start = time.monotonic()
        while time.monotonic() - start < args.seconds:
            time.sleep(min(args.interval, max(0, args.seconds - (time.monotonic() - start))))
            after = guarded(sample)
            if after["status"] != "AVAILABLE":
                first = after
                break
            samples.append(delta(before, after["data"]))
            before = after["data"]
        providers["host"] = {"status": first["status"], "observedAt": utc(), "data": samples}
    else:
        providers["host"] = first
    providers["trandbAfter"] = guarded(lambda: database(args.window_hours))
    if args.apache_url:
        providers["apacheAfter"] = guarded(lambda: endpoint(args.apache_url, "apache"))
    providers["cgroup"] = guarded(cgroup)
    providers["jvmAfter"] = (
        guarded(lambda: endpoint(args.jmx_url, "jvm"))
        if args.jmx_url
        else {"status": "NOT_CONFIGURED"}
    )
    if args.local_jvm_probe:
        providers["jvmProcessesAfter"] = guarded(
            lambda: local_jvm_snapshots(
                args.local_jvm_probe, args.local_jvm_helper, args.local_jvm_probe_sha256
            )
        )
        providers["jvmAfter"] = guarded(
            lambda: probe_metrics(providers["jvmProcessesAfter"]["data"])
        )
    else:
        providers["jvmProcessesAfter"] = guarded(jvm_processes)
    providers["clock"] = guarded(
        lambda: (
            subprocess.run(
                ["timedatectl", "show", "-p", "NTPSynchronized"],
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout.strip()
            == "NTPSynchronized=yes"
        )
    )
    # Keep Java diagnostic launcher startup outside the measured host/JVM window.
    providers["supportTools"] = guarded(support_tools)
    out["completedAt"] = utc()
    providers["listeningPortsAfter"] = guarded(listening_ports)
    out["listeningPortSetUnchanged"] = (
        providers["listeningPortsBefore"].get("data")
        == providers["listeningPortsAfter"].get("data")
        if providers["listeningPortsBefore"]["status"] == "AVAILABLE"
        and providers["listeningPortsAfter"]["status"] == "AVAILABLE"
        else None
    )
    document = json.dumps(out, allow_nan=False)
    print(
        base64.b64encode(gzip.compress(document.encode())).decode()
        if args.compressed_output
        else document
    )


if __name__ == "__main__":
    main()
