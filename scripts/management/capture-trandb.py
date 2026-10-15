#!/usr/bin/env python3
"""Capture bounded, read-only TranDb results in one existing SSH connection."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.management.trandb_reporting import MODES  # noqa: E402
from tools.handoff.customer_remote import SSH, RemoteError, load_target  # noqa: E402
from tools.handoff.readonly_capture import capture  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--mode", choices=("profile", *MODES), default="profile")
    p.add_argument("--output", type=Path, help="Optional private capture; otherwise print results")
    p.add_argument("--limit", type=int, default=500, help="Reporting row bound: 1 to 2000")
    a = p.parse_args()
    if not 1 <= a.limit <= 2000:
        p.error("limit must be between 1 and 2000")
    if a.output and (a.output.exists() or a.output.is_symlink()):
        raise SystemExit("Output exists; choose a new snapshot filename.")
    data = capture(SSH(load_target(a.inventory, a.target)), a.mode, a.limit)
    data["sourceTarget"] = a.target
    failures = [q["label"] for q in data["queries"] if q["status"] != "SUCCESS"]
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive mode-0600 creation, including symlink rejection, before writing any rows.
        fd = os.open(a.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as f:
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
                    "timings": data["timings"],
                }
            )
        )
    else:
        print(json.dumps(data, separators=(",", ":")))
    # Preserve capture exit semantics: partial data is returned with explicit failure metadata.


if __name__ == "__main__":
    try:
        main()
    except RemoteError as e:
        raise SystemExit(str(e)) from None
