import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "assessment", Path(__file__).resolve().parents[2] / "scripts/management/assess-trandb.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def report(rows, **extra):
    return {"reports": {"operation_runs": rows}, "failures": [], **extra}


def row(guid, status, parent=None, root="root"):
    return {"operation_instance_guid": guid, "root_operation_instance_guid": root,
            "parent_operation_instance_guid": parent, "status": status}


def test_failed_child_overrides_successful_root_and_excludes_other_run():
    result = module.assess(report([row("root", 5), row("child", 7, "root"),
                                  row("other", 4, root="other")]), "root")["data"]
    assert result["outcome"] == "FAILED"
    assert result["rootStatusCode"] == 5
    assert result["executionCount"] == 2
    assert result["businessFileCount"] is None


def test_missing_failed_source_and_truncated_data_are_not_healthy():
    assert module.assess({"reports": {}}, "root")["data"]["outcome"] == "UNKNOWN"
    for extra in [{"potentiallyTruncatedReports": ["operation_runs"]},
                  {"failures": ["operation_message_metadata"]}]:
        result = module.assess(report([row("root", 4)], **extra), "root")["data"]
        assert result["coverage"] == "PARTIAL"
        assert result["outcome"] == "UNKNOWN"


def test_warning_active_unknown_and_duplicate_semantics():
    assert module.assess(report([row("root", 6)]), "root")["data"]["outcome"] == "DEGRADED"
    assert module.assess(report([row("root", 3)]), "root")["data"]["outcome"] == "IN_PROGRESS"
    assert module.assess(report([row("root", 99)]), "root")["data"]["outcome"] == "UNKNOWN"
    result = module.assess(report([row("root", 4), row("root", 4)]), "root")["data"]
    assert result["executionCount"] == 1
    assert result["coverage"] == "PARTIAL"


def test_transfer_evidence_remains_uncorrelated():
    transfer = {"fileCount": 64, "files": [{"textLines": [
        "CURL_DEBUG_TEXT: rm command failed: No such file or directory"]}]}
    result = module.assess(report([row("root", 4)]), "root", transfer)["data"]
    assert result["outcome"] == "HEALTHY"
    assert result["transferDiagnostics"]["correlation"] == "UNMATCHED_TO_SELECTED_ROOT"
    assert result["transferDiagnostics"]["rmMissingFileEventsInRetainedText"] == 1
