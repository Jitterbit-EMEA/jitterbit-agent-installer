#!/usr/bin/env python3
"""Capture a private TranDb evidence bundle or compare two bundles offline."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        out.write(data)


def indexed(rows, fields):
    return {tuple(row.get(f) for f in fields): row for row in rows or []}


def compare(before, after):
    """Absence from a bounded capture is deliberately not reported as deletion."""
    bp, br = before
    ap, ar = after
    if bp.get("host") != ap.get("host"):
        raise ValueError("Cannot compare different hosts")
    for left, right in [(bp, ap), (br, ar)]:
        if left.get("sourceTarget") and right.get("sourceTarget") != left["sourceTarget"]:
            raise ValueError("Cannot compare different targets")
    result = {
        "beforeObservedAtUtc": br["observedAtUtc"],
        "afterObservedAtUtc": ar["observedAtUtc"],
        "host": ap["host"],
        "newlyPopulatedTables": [],
        "tableRowChanges": [],
        "schemaChanges": {},
        "reportChanges": {},
        "warnings": [
            "Each query is a separate snapshot, not a transaction spanning the bundle.",
            "Missing sampled rows are not proof of deletion or non-execution.",
            "Polling can miss brief runs; retention and ignore_history can suppress history.",
            "Counters and timestamps retain raw meanings until workload evidence qualifies units and semantics.",
        ],
    }
    tables = indexed(bp.get("tables"), ["schema", "name"])
    for table in ap.get("tables", []):
        key = (table["schema"], table["name"])
        old = tables.get(key, {})
        prev, now = old.get("exactRows"), table.get("exactRows")
        if old.get("countStatus") == table.get("countStatus") == "SUCCESS":
            if prev == 0 and now > 0:
                result["newlyPopulatedTables"].append(".".join(key))
            if prev != now:
                result["tableRowChanges"].append(
                    {"table": ".".join(key), "before": prev, "after": now, "delta": now - prev}
                )
    for family, fields in [
        ("columns", ["schema", "name", "column"]),
        ("constraints", ["schema", "name", "constraint_name"]),
        ("indexes", ["schema", "name", "indexname"]),
        ("views", ["schema", "name"]),
    ]:
        old, new = indexed(bp.get(family), fields), indexed(ap.get(family), fields)
        result["schemaChanges"][family] = {
            "added": [list(k) for k in new.keys() - old.keys()],
            "removed": [list(k) for k in old.keys() - new.keys()],
            "changed": [list(k) for k in new.keys() & old.keys() if new[k] != old[k]],
        }
    keys = {
        "operation_runs": ["operation_instance_guid"],
        "operation_definitions": ["operation_id", "environment_id"],
        "child_runs": ["child_run"],
        "transformation_summaries": ["operation_summary_id"],
        "run_progress": ["operation_progress_id"],
        "file_result_counters": ["operation_file_status_id"],
        "instance_links": ["operation_instance_guid"],
    }
    for family, fields in keys.items():
        previous, current = br["reports"].get(family), ar["reports"].get(family)
        if previous is None or current is None:
            result["reportChanges"][family] = {"availableForComparison": False}
            continue
        old, new = indexed(previous, fields), indexed(current, fields)
        result["reportChanges"][family] = {
            "availableForComparison": True,
            "newlyObserved": [new[k] for k in new.keys() - old.keys()],
            "changed": [
                {"before": old[k], "after": new[k]}
                for k in new.keys() & old.keys()
                if new[k] != old[k]
            ],
            "absentFromLaterSampleCount": len(old.keys() - new.keys()),
        }
    result["afterChecks"] = {
        k: ar["reports"].get(k)
        for k in [
            "run_status_counts",
            "run_grain_checks",
            "logical_relationship_checks",
            "catalog_join_cardinality",
            "pending_by_definition",
            "log_sync_backlog",
            "incoming_queue_summary",
        ]
    }
    result["unavailableQueries"] = {
        "before": [
            q["label"] for doc in before for q in doc["queries"] if q["status"] != "SUCCESS"
        ],
        "after": [q["label"] for doc in after for q in doc["queries"] if q["status"] != "SUCCESS"],
    }
    result["potentiallyTruncatedReports"] = ar.get("potentiallyTruncatedReports", [])
    return result


def load_bundle(path):
    manifest = json.loads((path / "manifest.json").read_text())
    for name, digest in manifest["sha256"].items():
        if name not in ("profile.json", "reporting.json"):
            raise ValueError("Unexpected bundle filename")
        if hashlib.sha256((path / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Evidence digest mismatch")
    return tuple(
        json.loads((path / name).read_text()) for name in ["profile.json", "reporting.json"]
    )


def markdown(data):
    lines = [
        "# TranDb workload comparison",
        "",
        f"Host: `{data['host']}`",
        "",
        f"Before: {data['beforeObservedAtUtc']}  \nAfter: {data['afterObservedAtUtc']}",
        "",
        "## Table population",
        "",
        "| Table | Before | After | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in data["tableRowChanges"]:
        lines.append(f"| {row['table']} | {row['before']} | {row['after']} | {row['delta']:+d} |")
    lines.extend(
        [
            "",
            "## Execution and supporting evidence",
            "",
            "| Query family | Newly observed | Changed |",
            "| --- | ---: | ---: |",
        ]
    )
    for family, value in data["reportChanges"].items():
        lines.append(
            f"| {family} | {len(value['newlyObserved']) if value['availableForComparison'] else 'Unavailable'} | {len(value['changed']) if value['availableForComparison'] else 'Unavailable'} |"
        )
    lines.extend(
        [
            "",
            "Full run GUIDs, parent/child links, counters and before/after values are in `comparison.json`.",
            "",
            "## Evidence limits",
            "",
        ]
    )
    lines.extend("- " + w for w in data["warnings"])
    lines.extend(
        [
            f"- Unavailable queries: `{json.dumps(data['unavailableQueries'])}`",
            f"- Reports at the row bound: `{json.dumps(data['potentiallyTruncatedReports'])}`",
            "",
            "New population is evidence of availability, not automatic validation of a field's meaning. Review new status codes, timing units, relationship checks and logging coverage before promoting API mappings.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--inventory", type=Path, required=True)
    capture.add_argument("--target", required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--limit", type=int, default=500)
    diff = sub.add_parser("compare")
    diff.add_argument("--before", type=Path, required=True)
    diff.add_argument("--after", type=Path, required=True)
    diff.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "capture" and not 1 <= args.limit <= 2000:
        parser.error("limit must be between 1 and 2000")
    args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    if args.command == "capture":
        for mode in ["profile", "reporting"]:
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/management/capture-trandb.py"),
                    "--inventory",
                    str(args.inventory),
                    "--target",
                    args.target,
                    "--mode",
                    mode,
                    "--limit",
                    str(args.limit),
                    "--output",
                    str(args.output / (mode + ".json")),
                ],
                check=True,
            )
        paths = [args.output / name for name in ["profile.json", "reporting.json"]]
        manifest = {
            "formatVersion": 1,
            "createdAtUtc": datetime.now(timezone.utc).isoformat(),
            "target": args.target,
            "sampleLimit": args.limit,
            "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "collectorSha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ROOT / "scripts/management").glob("*trandb*.py")
            },
        }
        write_private(args.output / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    else:
        data = compare(load_bundle(args.before), load_bundle(args.after))
        write_private(args.output / "comparison.json", json.dumps(data, indent=2) + "\n")
        write_private(args.output / "comparison.md", markdown(data))
    print(json.dumps({"status": "COMPLETE", "output": str(args.output), "command": args.command}))


if __name__ == "__main__":
    main()
