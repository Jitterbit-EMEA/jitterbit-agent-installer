#!/usr/bin/env python3
"""Repeat the bounded QA TranDb assessment over an existing pinned SSH inventory."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.handoff.customer_remote import SSH, RemoteError, load_target  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--mode", choices=["profile", "reporting"], default="profile")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--limit", type=int, default=500, help="Reporting row bound: 1 to 2000")
    a = p.parse_args()
    if not 1 <= a.limit <= 2000:
        p.error("limit must be between 1 and 2000")
    if a.output.exists():
        raise SystemExit("Output exists; choose a new snapshot filename.")
    ssh = SSH(load_target(a.inventory, a.target))
    ssh.require(["sudo", "-n", "true"], "SUDO_REQUIRED")
    stage = ssh.require(
        ["mktemp", "-d", "/var/tmp/jbpa-trandb-analysis-XXXXXX"], "ANALYSIS_STAGE_FAILED"
    ).strip()
    if not stage.startswith("/var/tmp/jbpa-trandb-analysis-") or "/" in stage[len("/var/tmp/") :]:
        raise SystemExit("Unexpected staging directory")
    try:
        for local, name in [
            (ROOT / "scripts/management/inspect-trandb.py", "inspect_trandb.py"),
            (ROOT / "scripts/management/validate-trandb-reporting.py", "validate.py"),
        ]:
            ssh.copy(local, stage + "/" + name)
            digest = ssh.require(
                ["sha256sum", stage + "/" + name], "ANALYSIS_INTEGRITY_FAILED"
            ).split()[0]
            if digest != hashlib.sha256(local.read_bytes()).hexdigest():
                raise SystemExit("Analysis integrity mismatch")
        script = "inspect_trandb.py" if a.mode == "profile" else "validate.py"
        command = [
            "sudo",
            "-n",
            "/opt/jbpa/releases/jbpa-1.0.0-rc9/.venv/bin/python",
            stage + "/" + script,
        ] + (["--profile"] if a.mode == "profile" else ["--limit", str(a.limit)])
        code, raw = ssh.run(command, timeout=300)
        if code:
            raise SystemExit("Assessment failed; private output withheld.")
        data = json.loads(raw)
        data["sourceTarget"] = a.target
        if not data.get("readOnlyEnforced"):
            raise SystemExit("Read-only evidence missing")
        failures = (
            data.get("failures", [])
            if a.mode == "reporting"
            else [q["label"] for q in data["queries"] if q["status"] != "SUCCESS"]
        )
        a.output.parent.mkdir(parents=True, exist_ok=True)
        # Captured rows remain private by default even though credential/payload values are excluded.
        with a.output.open("x") as f:
            a.output.chmod(0o600)
            json.dump(data, f, indent=2)
            f.write("\n")
        print(
            json.dumps(
                {
                    "target": a.target,
                    "mode": a.mode,
                    "observedAtUtc": data["observedAtUtc"],
                    "output": str(a.output),
                    "queries": len(data["queries"]),
                    "unavailable": failures,
                }
            )
        )
    finally:
        ssh.run(["rm", "-rf", stage], timeout=30)


if __name__ == "__main__":
    try:
        main()
    except RemoteError as e:
        raise SystemExit(str(e)) from None
