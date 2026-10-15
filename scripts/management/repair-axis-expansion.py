#!/usr/bin/env python3
"""Approved one-host Axis expansion repair; preserves WAR/config and keeps rollback."""

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

sys.path[:0] = ["/opt/jbpa/releases/jbpa-1.0.0-rc9/lib", "/opt/jbpa/releases/jbpa-1.0.0-rc9/src"]
from jbpa.pending_operations import TranDbOperationProvider  # noqa: E402

EXPECTED_WAR = "440a995a09f0da9ff33b678c15c6adfee99664f3959957b19279679c4cfac84c"
WAR = Path("/opt/jitterbit/tomcat/webapps/axis.war")
APP = WAR.parent / "axis"
CTL = "/opt/jitterbit/bin/jitterbit"
RUN = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
BACKUP = Path("/var/lib/jbpa/backups") / ("axis-" + RUN)
RESULT = Path("/var/lib/jbpa/results") / ("axis-repair-" + RUN + ".json")
result = {
    "startedAtUtc": datetime.now(timezone.utc).isoformat(),
    "backupPath": str(BACKUP),
    "resultPath": str(RESULT),
    "state": "PREFLIGHT",
    "steps": [],
}


def runner(argv, **kw):
    env = dict(kw.get("env", {}))
    env.pop("PGOPTIONS", None)
    kw["env"] = env
    return subprocess.run([argv[0], "-q", *argv[1:]], **kw)


def query(sql):
    provider = TranDbOperationProvider(runner=runner)
    return json.loads(
        provider._query(
            "BEGIN READ ONLY; SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='1s'; SELECT COALESCE(jsonb_agg(to_jsonb(q)),'[]'::jsonb)::text FROM ("
            + sql
            + ") q; ROLLBACK;"
        )
    )


def control(action):
    proc = subprocess.run([CTL, action], capture_output=True, timeout=150)
    result["steps"].append({"serviceAction": action, "exitCode": proc.returncode})
    return proc.returncode


def tomcat_processes():
    p = subprocess.run(["ps", "-eo", "args="], capture_output=True, text=True, timeout=10)
    if p.returncode:
        raise RuntimeError("PROCESS_CHECK_UNAVAILABLE")
    return sum("org.apache.catalina.startup.Bootstrap" in line for line in p.stdout.splitlines())


def fingerprints():
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        for p in [
            Path("/opt/jitterbit/jitterbit.conf"),
            Path("/etc/jbpa/agent.yaml"),
            Path("/etc/jbpa/credentials.json"),
            Path("/opt/jitterbit/Resources/credentials.txt"),
        ]
    }


def library_check():
    missing, mismatched = [], []
    with zipfile.ZipFile(WAR) as z:
        expected = [
            i
            for i in z.infolist()
            if i.filename.startswith("WEB-INF/lib/") and i.filename.endswith(".jar")
        ]
        for item in expected:
            p = APP / item.filename
            if not p.is_file():
                missing.append(p.name)
                continue
            crc = 0
            with p.open("rb") as f:
                for block in iter(lambda: f.read(1048576), b""):
                    crc = zlib.crc32(block, crc)
            if p.stat().st_size != item.file_size or crc != item.CRC:
                mismatched.append(p.name)
    return {
        "expected": len(expected),
        "expanded": len(list((APP / "WEB-INF/lib").glob("*.jar"))),
        "missing": missing,
        "contentMismatches": mismatched,
    }


def http_probe():
    try:
        with urllib.request.urlopen("http://127.0.0.1:46912/axis/", timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError):
        return None


def save():
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(RESULT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result))


def main():
    stopped = moved = False
    prior_config = None
    try:
        if os.geteuid() != 0:
            raise RuntimeError("ROOT_REQUIRED")
        if APP.is_symlink() or WAR.is_symlink() or not APP.is_dir():
            raise RuntimeError("UNEXPECTED_APPLICATION_PATH")
        if hashlib.sha256(WAR.read_bytes()).hexdigest() != EXPECTED_WAR:
            raise RuntimeError("WAR_CHANGED_SINCE_APPROVAL")
        with zipfile.ZipFile(WAR) as z:
            if z.testzip() is not None:
                raise RuntimeError("SOURCE_ARCHIVE_CORRUPT")
        result["identityBefore"] = query(
            "SELECT key_name,key_value FROM key_values WHERE key_name IN ('Agent_Id','Agent_Group_Id') ORDER BY key_name"
        )
        identity = {x["key_name"]: str(x["key_value"]) for x in result["identityBefore"]}
        if identity != {"Agent_Id": "665400", "Agent_Group_Id": "678370"}:
            raise RuntimeError("IDENTITY_CHANGED")
        prior_config = fingerprints()
        result["preflightWork"] = query(
            "SELECT (SELECT count(*) FROM operationlogtab WHERE status IN (0,1,3,8,10)) active_runs,(SELECT count(*) FROM incomingmsgtab) incoming_requests"
        )[0]
        if any(result["preflightWork"].values()):
            raise RuntimeError("WORK_IN_FLIGHT")
        BACKUP.mkdir(parents=True, mode=0o700, exist_ok=False)
        if control("stop") != 0:
            raise RuntimeError("STOP_FAILED")
        stopped = True
        if tomcat_processes():
            raise RuntimeError("TOMCAT_STILL_RUNNING")
        result["state"] = "STOPPED"
        APP.rename(BACKUP / "axis")
        moved = True
        result["steps"].append({"applicationMovedToBackup": True})
        if control("start") != 0:
            raise RuntimeError("START_FAILED")
        stopped = False
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            check = library_check()
            if (
                not check["missing"]
                and not check["contentMismatches"]
                and check["expanded"] == check["expected"]
            ):
                code = http_probe()
                if code is not None and code != 404 and code < 500:
                    result["axisHttpStatus"] = code
                    break
            time.sleep(3)
        else:
            raise RuntimeError("AXIS_READINESS_FAILED")
        result["libraryIntegrityAfter"] = check
        result["identityAfter"] = query(
            "SELECT key_name,key_value FROM key_values WHERE key_name IN ('Agent_Id','Agent_Group_Id') ORDER BY key_name"
        )
        result["identityUnchanged"] = result["identityBefore"] == result["identityAfter"]
        result["protectedConfigurationUnchanged"] = prior_config == fingerprints()
        if not result["identityUnchanged"] or not result["protectedConfigurationUnchanged"]:
            raise RuntimeError("IDENTITY_OR_CONFIGURATION_CHANGED")
        result["state"] = "REPAIRED_PENDING_DEPLOYMENT_RETRY"
    except Exception as exc:
        result["failureClass"] = type(exc).__name__
        result["reason"] = str(exc) if isinstance(exc, RuntimeError) else "PRIVATE_ERROR_WITHHELD"
        if moved:
            try:
                if control("stop") != 0 or tomcat_processes():
                    raise RuntimeError("ROLLBACK_STOP_FAILED")
                stopped = True
                if APP.exists():
                    APP.rename(BACKUP / "failed-reexpansion")
                (BACKUP / "axis").rename(APP)
                result["rollbackRestored"] = True
                result["rollbackStartExitCode"] = control("start")
                stopped = False
                result["state"] = (
                    "ROLLED_BACK"
                    if result["rollbackStartExitCode"] == 0
                    else "ROLLBACK_START_FAILED"
                )
            except Exception:
                result["state"] = "ROLLBACK_NEEDS_ATTENTION"
        elif stopped or result["steps"]:
            result["recoveryStartExitCode"] = control("start")
            result["state"] = "ABORTED_SERVICE_RECOVERY_ATTEMPTED"
        else:
            result["state"] = "ABORTED_BEFORE_STOP"
    result["finishedAtUtc"] = datetime.now(timezone.utc).isoformat()
    save()
    return 0 if result["state"] == "REPAIRED_PENDING_DEPLOYMENT_RETRY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
