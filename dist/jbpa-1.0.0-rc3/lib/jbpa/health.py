"""Read-only local native-agent health, separate from Harmony confirmation."""

import json
import subprocess
import sys
from pathlib import Path

from .native_linux import REQUIRED_SERVICES

JITTERBIT = Path("/opt/jitterbit/bin/jitterbit")


def execute(*, runner=subprocess.run, stdout=None):
    stdout = stdout or sys.stdout
    result = {
        "operation": "HEALTH",
        "scope": "LOCAL_ONLY",
        "status": "UNHEALTHY",
        "packageCommandPresent": JITTERBIT.is_file(),
        "serviceRunning": False,
        "harmonyRegistered": None,
    }
    if JITTERBIT.is_file():
        try:
            completed = runner(
                [str(JITTERBIT), "status"], capture_output=True, text=True, timeout=30
            )
            result["serviceRunning"] = completed.returncode == 0 and all(
                item in completed.stdout
                for item in (*REQUIRED_SERVICES, "All services are running")
            )
            if result["serviceRunning"]:
                result["status"] = "HEALTHY"
        except (OSError, subprocess.TimeoutExpired):
            pass
    stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0 if result["serviceRunning"] else 60


def main():
    if len(sys.argv) != 1:
        return 2
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
