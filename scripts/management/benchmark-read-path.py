#!/usr/bin/env python3
"""Measure CLI end-to-end read latency; raw captures remain in a private local directory."""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--output", type=Path, required=True, help="New private benchmark directory")
    p.add_argument("--samples", type=int, default=3)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument(
        "--modes",
        nargs="+",
        choices=[
            "reporting",
            "running",
            "active",
            "errors",
            "definitions",
            "backlog",
            "identity",
            "profile",
        ],
        default=["reporting", "running"],
    )
    a = p.parse_args()
    if not 1 <= a.samples <= 10 or not 1 <= a.limit <= 2000:
        p.error("samples must be 1..10 and limit 1..2000")
    a.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    samples = []
    for i in range(a.samples):
        for mode in a.modes:
            output = a.output / f"{mode}-{i + 1}.json"
            start = time.monotonic()
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/management/capture-trandb.py"),
                    "--inventory",
                    str(a.inventory),
                    "--target",
                    a.target,
                    "--mode",
                    mode,
                    "--limit",
                    str(a.limit),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                timeout=330,
            )
            if result.returncode:
                raise SystemExit("Benchmark failed; private error output withheld")
            elapsed = round((time.monotonic() - start) * 1000, 2)
            data = json.loads(output.read_text())
            row = {
                "mode": mode,
                "sample": i + 1,
                "elapsedMs": elapsed,
                "queries": len(data["queries"]),
                "timings": data["timings"],
                "failures": [q["label"] for q in data["queries"] if q["status"] != "SUCCESS"],
                "truncated": data.get("potentiallyTruncatedReports", []),
            }
            samples.append(row)
            print(json.dumps(row), flush=True)
    summary = {
        "samples": samples,
        "mediansMs": {
            mode: statistics.median(r["elapsedMs"] for r in samples if r["mode"] == mode)
            for mode in a.modes
        },
        "scope": "CLI launch through private capture write; SSH/network included; AI/tool-scheduler latency excluded",
    }
    fd = os.open(a.output / "summary.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps({"mediansMs": summary["mediansMs"]}))


if __name__ == "__main__":
    main()
