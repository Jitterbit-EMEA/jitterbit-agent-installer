#!/usr/bin/env python3
"""Run bounded read-only reporting and data-grain validation on the PA host."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The one-shot transport registers these integrity-checked modules in memory.
from inspect_trandb import QUERIES, query
from trandb_reporting import MODES, selected_queries

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--limit", type=int, default=500)
parser.add_argument("--mode", choices=MODES, default="reporting")
args = parser.parse_args()
if not 1 <= args.limit <= 2000:
    parser.error("limit must be between 1 and 2000")
reports = {}
queries = selected_queries(args.mode, args.limit)
for label, sql in queries.items():
    reports[label] = query(label, sql)
    if label == "view_sizes" and reports[label]:
        for view in reports[label]:
            view["definition"] = re.sub(r"'(?:''|[^'])*'", "'[LITERAL]'", view["definition"])
print(
    json.dumps(
        {
            "observedAtUtc": datetime.now(timezone.utc).isoformat(),
            "readOnlyEnforced": True,
            "sampleLimit": args.limit,
            "mode": args.mode,
            "captureSemantics": "Separate read-only query snapshots; recent bounded rows, not a complete execution ledger",
            "potentiallyTruncatedReports": [
                label
                for label, rows in reports.items()
                if "LIMIT" in queries[label] and rows is not None and len(rows) >= args.limit
            ],
            "reports": reports,
            "queries": QUERIES,
            "failures": [q["label"] for q in QUERIES if q["status"] != "SUCCESS"],
        },
        default=str,
    )
)
