#!/usr/bin/env python3
"""Read-only deployment/connectivity evidence; no raw log or credential export."""

import json
import re
import shutil
import socket
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

patterns = {
    "token_invalidation": r"AGENT_TOKEN_INVALIDATION_ERROR|token.{0,40}invalidat|invalidat.{0,40}token",
    "authentication_error": r"401|403|unauthori[sz]ed|authentication.{0,30}(fail|error)|invalid.{0,20}token",
    "connection_error": r"Connection refused|Connection reset|ConnectException|timed? out|SSLHandshakeException|PKIX|UnknownHostException",
    "websocket_event": r"websocket|\bwss\b|connection.{0,20}(closed|lost|established)",
    "deployment_sync": r"environment-deploy|sync.{0,20}(fail|error|complete)|synchroniz",
    "agent_login": r"Agent Logged in|Heartbeat|heart-beat",
}
compiled = {k: re.compile(v, re.I) for k, v in patterns.items()}
result = {
    "observedAtUtc": datetime.now(timezone.utc).isoformat(),
    "host": socket.gethostname(),
    "scope": "Last 2 MiB per allowlisted log; classified records only; messages withheld",
    "logs": [],
}
root = Path("/opt/jitterbit/log")
for name in ["jitterbit-agent.log", "ProcessEngine.log", "Scheduler.log", "Cleanup.log"]:
    p = root / name
    if not p.is_file():
        result["logs"].append({"name": name, "available": False})
        continue
    size = p.stat().st_size
    with p.open("rb") as f:
        f.seek(max(0, size - 2 * 1024 * 1024))
        raw = f.read().decode("utf-8", errors="replace")
    events = []
    counts = Counter()
    timestamps = []
    for line in raw.splitlines():
        stamp = re.search(
            r"\b(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?)", line
        )
        if stamp:
            timestamps.append(stamp.group(1))
        classes = [k for k, v in compiled.items() if v.search(line)]
        if classes:
            counts.update(classes)
            event = {"timestamp": stamp.group(1) if stamp else None, "classes": classes}
            event["exceptionClasses"] = re.findall(
                r"\b([A-Za-z][A-Za-z0-9_.$]*(?:Exception|Error))\b", line
            )[:8]
            event["failureIndicators"] = [
                term
                for term in [
                    "401 Unauthorized",
                    "403 Forbidden",
                    "404 Not Found",
                    "500 Internal Server Error",
                    "Connection refused",
                    "Connection reset",
                    "Read timed out",
                    "connect timed out",
                    "Invalid JWT",
                    "expired",
                    "PKIX",
                ]
                if term.lower() in line.lower()
            ]
            event["httpStatusCodes"] = re.findall(
                r"(?:HTTP(?:/[0-9.]+)?\s+|status(?: code)?[ :=]+|response code[ :=]+)([1-5][0-9]{2})\b",
                line,
                re.I,
            )
            ids = re.search(r"Agent Logged in: AgentId = (\d+); AgentGroupId = (\d+)", line)
            if ids:
                event.update({"agentId": int(ids.group(1)), "agentGroupId": int(ids.group(2))})
            env = re.search(r"environment(?:Id| id|[-_]id)?\s*[:=]\s*(\d+)", line, re.I)
            if env:
                event["environmentId"] = int(env.group(1))
            events.append(event)
    result["logs"].append(
        {
            "name": name,
            "available": True,
            "bytes": size,
            "tailTruncated": size > 2 * 1024 * 1024,
            "modifiedAtUtc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
            "firstTailTimestamp": timestamps[0] if timestamps else None,
            "lastTailTimestamp": timestamps[-1] if timestamps else None,
            "counts": dict(counts),
            "recentClassifiedEvents": events[-100:],
        }
    )
result["disk"] = {
    "totalBytes": shutil.disk_usage("/opt/jitterbit").total,
    "freeBytes": shutil.disk_usage("/opt/jitterbit").free,
}
probe = subprocess.run(
    ["timedatectl", "show", "--property=NTPSynchronized", "--property=Timezone"],
    capture_output=True,
    text=True,
    timeout=10,
)
result["clock"] = {
    line.split("=", 1)[0]: line.split("=", 1)[1]
    for line in probe.stdout.splitlines()
    if "=" in line
}
print(json.dumps(result))
