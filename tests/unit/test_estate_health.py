import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jbpa.estate_health import (  # noqa: E402
    DB_QUERIES,
    assess_estate,
    assess_node,
    prometheus_metrics,
)


def available(data):
    return {"status": "AVAILABLE", "data": data}


def fixture(cpu=10, seconds=30, pending_before=0, pending_after=0, errors=0):
    queries = {
        **{key: available([]) for key in DB_QUERIES},
        "activeSummary": available([{"running": 0, "pending": pending_after}]),
        "recentStates": available([{"status": 7, "executions": errors}]),
        "limits": available([]),
        "locks": available([]),
    }
    node = {
        "providers": {
            "host": available(
                [
                    {
                        "cpuBusyPercent": cpu,
                        "memoryAvailablePercent": 70,
                        "intervalSeconds": seconds / 2,
                    },
                    {
                        "cpuBusyPercent": cpu,
                        "memoryAvailablePercent": 70,
                        "intervalSeconds": seconds / 2,
                    },
                ]
            ),
            "filesystems": available([]),
            "services": available({"allServicesRunning": True}),
            "trandbBefore": available(
                {
                    "queries": {
                        **{key: available([]) for key in DB_QUERIES},
                        "activeSummary": available([{"pending": pending_before}]),
                    }
                }
            ),
            "trandbAfter": available({"queries": queries, "windowHours": 24}),
            "apache": available({"BusyWorkers": "1", "IdleWorkers": "5"}),
            "jvmBefore": available([]),
            "jvmAfter": available([]),
            "jvmProcessesBefore": available([]),
            "jvmProcessesAfter": available([]),
            "logs": available({}),
            "clock": available(True),
            "cgroup": available({}),
            "sockets": available({}),
            "supportTools": available({"connection-check": True, "service-status": True}),
        }
    }
    return node


class EstateHealthTests(unittest.TestCase):
    def test_missing_hosts_and_missing_telemetry_cannot_be_healthy(self):
        r = assess_estate({"a": fixture()}, ["a", "b"], roster_verified=True)
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertEqual(r["nodes"][1]["coverage"], "UNAVAILABLE")
        n = fixture()
        n["providers"]["jvmAfter"] = {"status": "NOT_CONFIGURED"}
        self.assertEqual(assess_node("a", n)["status"], "UNKNOWN")

    def test_business_errors_do_not_justify_scaling(self):
        r = assess_node("a", fixture(errors=20))
        self.assertEqual(r["status"], "DEGRADED")
        self.assertEqual(r["capacity"]["decision"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("OPERATION_ERRORS_IN_WINDOW", [f["code"] for f in r["findings"]])

    def test_short_busy_sample_is_not_sizing_evidence(self):
        r = assess_node(
            "a", fixture(cpu=95, pending_after=10), context={"representativePeak": True}
        )
        self.assertEqual(r["capacity"]["decision"], "INSUFFICIENT_EVIDENCE")

    def test_idle_peer_requires_routing_investigation(self):
        contexts = {
            k: {"agentGroupId": 1, "representativePeak": True, "horizontallyScalable": True}
            for k in ["busy", "idle"]
        }
        r = assess_estate(
            {"busy": fixture(cpu=95, seconds=300, pending_after=10), "idle": fixture(seconds=300)},
            ["busy", "idle"],
            contexts=contexts,
            roster_verified=True,
        )
        self.assertEqual(
            r["capacityRecommendations"][0]["decision"],
            "INVESTIGATE_ROUTING_OR_SERIALIZATION_FIRST",
        )

    def test_scale_out_candidate_requires_all_peers_and_verified_roster(self):
        contexts = {
            k: {"agentGroupId": 1, "representativePeak": True, "horizontallyScalable": True}
            for k in ["a", "b"]
        }
        captures = {k: fixture(cpu=95, seconds=300, pending_after=10) for k in contexts}
        r = assess_estate(captures, list(contexts), contexts=contexts, roster_verified=True)
        self.assertEqual(
            r["capacityRecommendations"][0]["decision"],
            "SCALE_OUT_CANDIDATE_VALIDATE_WITH_LOAD_TEST",
        )
        self.assertIsNone(r["capacityRecommendations"][0]["exactAdditionalAgents"])
        r = assess_estate(captures, list(contexts), contexts=contexts, roster_verified=False)
        self.assertNotEqual(
            r["capacityRecommendations"][0]["decision"],
            "SCALE_OUT_CANDIDATE_VALIDATE_WITH_LOAD_TEST",
        )

    def test_database_failure_and_stored_swap_are_not_zero_pressure(self):
        n = fixture()
        n["providers"]["trandbAfter"]["data"]["queries"]["limits"] = {"status": "UNAVAILABLE"}
        n["providers"]["host"]["data"][0]["swapUsedBytes"] = 1000000
        r = assess_node("a", n)
        self.assertEqual(r["coverage"], "PARTIAL")
        self.assertNotIn("ACTIVE_SWAPPING", [f["code"] for f in r["findings"]])

    def test_gc_counter_reset_not_interpreted_as_negative_or_high_gc(self):
        n = fixture()
        for key, value, timestamp in [
            ("jvmBefore", 100000, "2026-10-12T10:00:00+00:00"),
            ("jvmAfter", 1, "2026-10-12T10:01:00+00:00"),
        ]:
            n["providers"][key] = {
                "status": "AVAILABLE",
                "observedAt": timestamp,
                "data": [
                    {
                        "name": "jitterbit_jvm_gc_collection_time_ms_total",
                        "labels": {},
                        "value": value,
                    }
                ],
            }
        self.assertNotIn("JVM_GC_TIME_HIGH", [f["code"] for f in assess_node("a", n)["findings"]])

    def test_unavailable_operation_states_not_exported_as_zero(self):
        n = fixture()
        n["providers"]["trandbAfter"]["data"]["queries"]["recentStates"] = {"status": "UNAVAILABLE"}
        result = assess_estate({"a": n}, ["a"], roster_verified=True)
        self.assertIsNone(result["nodes"][0]["measurements"]["errorsInWindow"])
        self.assertNotIn("jbpa_health_operation_errors_in_window", prometheus_metrics(result))

    def test_database_pressure_blocks_scale_out_candidate(self):
        n = fixture(cpu=95, seconds=300, pending_after=10)
        n["providers"]["trandbAfter"]["data"]["queries"]["locks"] = available(
            [{"waiting_locks": 4}]
        )
        result = assess_node("a", n, context={"representativePeak": True})
        self.assertEqual(result["capacity"]["decision"], "INSUFFICIENT_EVIDENCE")

    def test_counter_reset_is_rejected_by_host_delta(self):
        import runpy

        collector = runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "scripts/management/collect-estate-node.py")
        )
        before = {"cpu": [100] * 8, "monotonic": 0}
        after = {"cpu": [1] * 8, "monotonic": 5}
        with self.assertRaises(ValueError):
            collector["delta"](before, after)

    def test_external_metric_endpoint_rejected_before_request(self):
        import runpy

        collector = runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "scripts/management/collect-estate-node.py")
        )
        with self.assertRaises(ValueError):
            collector["endpoint"]("https://example.com/metrics", "apache")

    def test_local_probe_heap_and_deadlock_checks(self):
        n = fixture()
        n["providers"]["jvmProcessesAfter"] = available(
            [
                {
                    "pid": 7,
                    "status": "AVAILABLE",
                    "data": {"heapUsedBytes": 95, "heapMaxBytes": 100, "deadlockedThreads": 2},
                }
            ]
        )
        findings = assess_node("a", n)["findings"]
        codes = [f["code"] for f in findings]
        self.assertIn("JVM_HEAP_OCCUPANCY_HIGH", codes)
        self.assertIn("JVM_DEADLOCKED_THREADS", codes)

    def test_noport_metrics_preserve_two_jvms_and_tomcat(self):
        import runpy

        collector = runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "scripts/management/collect-estate-node.py")
        )
        base = {
            "heapUsedBytes": 10,
            "heapCommittedBytes": 20,
            "heapMaxBytes": 100,
            "nonheapUsedBytes": 3,
            "liveThreads": 4,
            "daemonThreads": 2,
            "peakThreads": 6,
            "gc": [],
            "tomcat": [],
        }
        rows = [
            {
                "pid": 1,
                "startTicks": 1,
                "status": "AVAILABLE",
                "data": {
                    **base,
                    "tomcat": [
                        {
                            "type": "ThreadPool",
                            "connector": "local",
                            "attributes": {"currentThreadsBusy": 1, "maxThreads": 10},
                        }
                    ],
                },
            },
            {"pid": 2, "startTicks": 1, "status": "AVAILABLE", "data": base},
        ]
        metrics = collector["probe_metrics"](rows)
        self.assertEqual({m["labels"]["pid"] for m in metrics}, {"1", "2"})
        self.assertTrue(
            any(m["name"] == "jitterbit_tomcat_thread_pool_max_threads" for m in metrics)
        )

    def test_compressed_collector_transport_accepts_newline(self):
        import base64
        import gzip
        import json
        import runpy
        from unittest.mock import patch

        runner = runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "scripts/management/estate-health.py")
        )
        payload = {"readOnly": True, "providers": {}}

        class FakeSSH:
            def __init__(self, _target):
                pass

            def run(self, command, **kwargs):
                self.assert_command = command
                return 0, base64.b64encode(
                    gzip.compress(json.dumps(payload).encode())
                ).decode() + "\n"

        fn = runner["collect"]
        with patch.dict(fn.__globals__, {"SSH": FakeSSH, "load_target": lambda *_: {}}):
            self.assertEqual(
                fn("target", Path("/tmp/private-inventory"), "source", 5, 1, 1, {}), payload
            )

    def test_io_stalls_with_iowait_do_not_need_high_device_await(self):
        n = fixture()
        n["providers"]["host"]["data"][0].update(
            {
                "cpuIoWaitPercent": 15,
                "pressure": {"io": {"some": {"avg10": 18}}},
                "diskIo": [{"readAwaitMs": 1, "writeAwaitMs": 5}],
            }
        )
        self.assertIn("STORAGE_PRESSURE", [f["code"] for f in assess_node("a", n)["findings"]])

    def test_log_sync_growth_is_distinct_from_pending_operations(self):
        n = fixture()
        n["providers"]["trandbBefore"]["data"]["queries"]["logSync"] = available(
            [{"is_synced": 0, "records": 40000}]
        )
        n["providers"]["trandbAfter"]["data"]["queries"]["logSync"] = available(
            [{"is_synced": 0, "records": 68000}]
        )
        result = assess_node("a", n)
        self.assertEqual(result["measurements"]["pending"], 0)
        self.assertEqual(result["measurements"]["unsyncedLogGrowth"], 28000)
        self.assertIn("LOG_SYNC_BACKLOG_GROWING", [f["code"] for f in result["findings"]])


if __name__ == "__main__":
    unittest.main()
