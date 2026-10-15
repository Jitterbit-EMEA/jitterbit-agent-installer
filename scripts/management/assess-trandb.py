#!/usr/bin/env python3
"""Assess one root execution from bounded local QA evidence; no network or mutation."""

import argparse
import json
import os
from collections import Counter
from pathlib import Path

STATUSES = {
    0: "Submitted", 1: "Pending", 2: "Cancelled", 3: "Running", 4: "Success",
    5: "SuccessWithInfo", 6: "SuccessWithWarning", 7: "Error", 8: "CancelRequested",
    9: "SuccessWithChildError", 10: "Received", 11: "SOAPFault",
}
ACTIVE = {0, 1, 3, 8, 10}
FAILED = {7, 9, 11}


def assess(report, root_id, transfer=None):
    reports = report.get("reports", {})
    source_rows = reports.get("operation_runs")
    selected = [r for r in source_rows or [] if
                (r.get("root_operation_instance_guid") or r.get("operation_instance_guid"))
                == root_id]
    # Count an execution once; inconsistent duplicates invalidate clean-health conclusions.
    unique = {}
    duplicates = 0
    missing_identity = 0
    for row in selected:
        guid = row.get("operation_instance_guid")
        if not guid:
            missing_identity += 1
            continue
        if guid in unique:
            duplicates += 1
        else:
            unique[guid] = row
    rows = list(unique.values())
    codes = Counter(r.get("status") for r in rows)
    gaps = [r["operation_instance_guid"] for r in rows
            if r.get("parent_operation_instance_guid") and
            r["parent_operation_instance_guid"] not in unique]
    unknown = any(code not in STATUSES for code in codes)
    truncated = "operation_runs" in report.get("potentiallyTruncatedReports", [])
    failures = report.get("failures", [])
    unavailable = source_rows is None
    partial = bool(truncated or failures or gaps or duplicates or missing_identity)
    coverage = "UNAVAILABLE" if unavailable else "PARTIAL" if partial else "COMPLETE"
    if not rows or unavailable:
        outcome = "UNKNOWN"
    elif any(c in FAILED for c in codes):
        outcome = "FAILED"
    elif any(c in ACTIVE for c in codes):
        outcome = "IN_PROGRESS"
    elif unknown or partial:
        outcome = "UNKNOWN"
    elif 6 in codes or 2 in codes:
        outcome = "DEGRADED"
    else:
        outcome = "HEALTHY"
    findings = []
    for code, label in [(7, "EXECUTION_ERROR"), (9, "CHILD_ERROR"),
                        (11, "SOAP_FAULT"), (6, "EXECUTION_WARNING"),
                        (2, "CANCELLED_EXECUTION")]:
        if codes[code]:
            findings.append({"code": label, "count": codes[code], "basis": "OBSERVED_STATUS"})
    if any(c in ACTIVE for c in codes):
        findings.append({"code": "ACTIVE_EXECUTIONS", "count": sum(codes[c] for c in ACTIVE)})
    if unknown:
        findings.append({"code": "UNKNOWN_STATUS"})
    if gaps:
        findings.append({"code": "MISSING_PARENT_IN_SAMPLE", "count": len(gaps)})
    if duplicates or missing_identity:
        findings.append({"code": "EXECUTION_IDENTITY_QUALITY", "duplicates": duplicates,
                         "missingIdentity": missing_identity})
    groups = {}
    for row in rows:
        key = (row.get("operation_id"), row.get("operation_name"))
        groups.setdefault(key, Counter())[row.get("status")] += 1
    data = {
        "rootRunId": root_id, "outcome": outcome, "coverage": coverage,
        "observedAt": report.get("observedAtUtc"), "sourceTarget": report.get("sourceTarget"),
        "executionCount": len(rows), "businessFileCount": None,
        "statusCounts": [{"originalStatusCode": c, "statusName": STATUSES.get(c, "Unknown"),
                          "count": n} for c, n in sorted(codes.items(), key=lambda x: str(x[0]))],
        "operationGroups": [{"operationId": k[0], "operationName": k[1],
                             "statusCounts": [{"originalStatusCode": c, "count": n}
                                              for c, n in counts.items()]}
                            for k, counts in groups.items()],
        "rootStatusCode": unique.get(root_id, {}).get("status"),
        "findings": findings,
        "coverageDetails": {"sourceRows": len(source_rows or []), "selectedRows": len(selected),
                            "rootPresent": root_id in unique, "missingParentRunIds": gaps,
                            "potentiallyTruncated": truncated, "failedQueries": failures,
                            "snapshotSemantics": report.get("captureSemantics")},
        "warnings": ["Coverage describes this bounded capture, not complete retained history.",
                     "Operation executions are not business files or transfer requests.",
                     "Status timestamp is not a qualified finish time.",
                     "Stage outcomes require a configured operation-role map."],
    }
    if rows and root_id not in unique:
        data["coverage"] = "PARTIAL"
        if data["outcome"] == "HEALTHY":
            data["outcome"] = "UNKNOWN"
    if transfer is not None:
        text = [line for f in transfer.get("files", []) for line in f.get("textLines", [])]
        data["transferDiagnostics"] = {
            "observedAt": transfer.get("observedAtUtc"),
            "tracesAvailable": bool(transfer.get("files")),
            "traceFileCount": transfer.get("fileCount"),
            "inspectedFileCount": len(transfer.get("files", [])),
            "authenticationCompleteEventsInRetainedText": sum("Authentication complete" in l for l in text),
            "rmMissingFileEventsInRetainedText": sum("rm command failed: No such file or directory" in l for l in text),
            "correlation": "UNMATCHED_TO_SELECTED_ROOT",
            "source": "Filtered curl diagnostic TEXT tails; headers/payload excluded",
        }
        data["warnings"].append("Transfer events cannot be assigned to this root from file GUID or time alone.")
    return {"schemaVersion": 1, "kind": "operationAssessment", "data": data}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reporting", type=Path, required=True)
    parser.add_argument("--root-run-id", required=True)
    parser.add_argument("--transfer", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.reporting.read_text())
    transfer = json.loads(args.transfer.read_text()) if args.transfer else None
    result = assess(report, args.root_run_id, transfer)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps({"status": "COMPLETE", "output": str(args.output),
                      "outcome": result["data"]["outcome"], "coverage": result["data"]["coverage"]}))


if __name__ == "__main__":
    main()
