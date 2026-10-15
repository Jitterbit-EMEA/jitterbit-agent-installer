"""Comparison evidence must not turn sampling gaps into business conclusions."""

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "workload", Path(__file__).resolve().parents[2] / "scripts/management/trandb-workload.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def bundle(rows, count=0, host="qa"):
    return (
        {
            "host": host,
            "tables": [
                {
                    "schema": "public",
                    "name": "summary",
                    "countStatus": "SUCCESS",
                    "exactRows": count,
                }
            ],
            "queries": [],
        },
        {"observedAtUtc": "test", "reports": {"operation_runs": rows}, "queries": []},
    )


class WorkloadTests(unittest.TestCase):
    def test_run_change_and_new_run_use_execution_guid(self):
        old = bundle([{"operation_instance_guid": "a", "operation_id": 1, "status": 3}])
        new = bundle(
            [
                {"operation_instance_guid": "a", "operation_id": 1, "status": 4},
                {"operation_instance_guid": "b", "operation_id": 1, "status": 3},
            ],
            2,
        )
        result = module.compare(old, new)
        runs = result["reportChanges"]["operation_runs"]
        self.assertEqual(len(runs["newlyObserved"]), 1)
        self.assertEqual(len(runs["changed"]), 1)
        self.assertEqual(result["newlyPopulatedTables"], ["public.summary"])

    def test_absence_not_classified_as_deleted(self):
        result = module.compare(bundle([{"operation_instance_guid": "a"}]), bundle([]))
        runs = result["reportChanges"]["operation_runs"]
        self.assertEqual(runs["absentFromLaterSampleCount"], 1)
        self.assertNotIn("deleted", runs)

    def test_missing_query_is_not_an_empty_success(self):
        result = module.compare(bundle([]), bundle([]))
        self.assertFalse(result["reportChanges"]["run_progress"]["availableForComparison"])

    def test_different_host_refused(self):
        with self.assertRaises(ValueError):
            module.compare(bundle([]), bundle([], host="other"))
