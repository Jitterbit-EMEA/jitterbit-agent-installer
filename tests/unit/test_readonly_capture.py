"""Fast-path transport and fixed-query compatibility/security contracts."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.management.trandb_reporting import REPORTING_QUERIES, selected_queries
from tools.handoff.customer_remote import MAX_OUTPUT, SSH, RemoteError
from tools.handoff.readonly_capture import BOOTSTRAP, COLLECTORS, capture


class ReadQueries(unittest.TestCase):
    def test_full_catalogue_unchanged_and_bounded(self):
        self.assertEqual(len(REPORTING_QUERIES), 25)
        canonical = json.dumps(REPORTING_QUERIES, sort_keys=True, separators=(",", ":"))
        self.assertEqual(
            hashlib.sha256(canonical.encode()).hexdigest(),
            "9c9fe4299fe4e670b521d0281ef72bc4511ff080546c54936d53b63faa552c23",
        )
        self.assertEqual(
            selected_queries(),
            {k: s.replace("LIMIT 100", "LIMIT 500") for k, s in REPORTING_QUERIES.items()},
        )

    def test_focused_filters_and_raw_statuses_are_distinct(self):
        self.assertIn("WHERE status=3 ORDER BY", selected_queries("running")["operation_runs"])
        self.assertIn(
            "WHERE status IN (0,1,3,8,10) ORDER BY", selected_queries("active")["operation_runs"]
        )
        self.assertIn(
            "WHERE status IN (7,9,11) ORDER BY", selected_queries("errors")["operation_runs"]
        )
        self.assertEqual(len(selected_queries("backlog")), 2)
        self.assertEqual(list(selected_queries("identity")), ["agent_identity_whitelist"])

    def test_no_arbitrary_sql_or_unbounded_limit(self):
        for mode, limit in [
            ("SELECT 1", 100),
            ("running", "1; DELETE"),
            ("reporting", 0),
            ("errors", 2001),
            ("identity", True),
        ]:
            with self.subTest(mode=mode, limit=limit), self.assertRaises(ValueError):
                selected_queries(mode, limit)


class Bootstrap(unittest.TestCase):
    def bundle(self, inspector=None):
        # Deliberately unavailable source demonstrates partial results retain unavailable metadata.
        inspector = (
            inspector
            or """
QUERIES=[]
def query(label, sql):
    QUERIES.append({"label":label,"status":"UNAVAILABLE","elapsedMs":3,"sql":sql,"reason":"OperationQueryError"})
    return None
"""
        )
        return {
            k: inspector if k == "inspect_trandb" else p.read_text() for k, p in COLLECTORS.items()
        }

    def run_bundle(self, bundle, mode="running", digest=None):
        payload = json.dumps(bundle)
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                BOOTSTRAP,
                digest or hashlib.sha256(payload.encode()).hexdigest(),
                mode,
                "100",
            ],
            input=payload,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def test_one_query_failures_are_explicit_and_no_staging(self):
        result = self.run_bundle(self.bundle())
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["failures"], ["operation_runs"])
        self.assertIsNone(data["reports"]["operation_runs"])
        self.assertEqual(len(data["queries"]), 1)
        self.assertEqual(data["timings"]["queryElapsedMs"], 3)

    def test_full_mode_runs_all_original_queries(self):
        result = self.run_bundle(self.bundle(), "reporting")
        data = json.loads(result.stdout)
        self.assertEqual(set(data["reports"]), set(REPORTING_QUERIES))
        self.assertEqual(len(data["queries"]), 25)

    def test_digest_manifest_and_mode_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "must-not-exist"
            bundle = self.bundle(f"open({str(marker)!r}, 'w').write('executed')")
            for kind in ("hash", "manifest", "mode"):
                values = dict(bundle)
                if kind == "manifest":
                    values.pop("validate")
                result = self.run_bundle(
                    values,
                    "arbitrary SQL" if kind == "mode" else "running",
                    "0" * 64 if kind == "hash" else None,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists())

    def test_profile_entrypoint_preserved(self):
        inspector = """
import json
def main():
    print(json.dumps({"readOnlyEnforced":True,"queries":[],"tables":[{"name":"synthetic"}]}))
"""
        result = self.run_bundle(self.bundle(inspector), "profile")
        self.assertEqual(json.loads(result.stdout)["tables"], [{"name": "synthetic"}])


class Transport(unittest.TestCase):
    def test_stdin_keeps_pinned_transport_controls_and_is_bounded(self):
        target = {
            "host": "qa.example",
            "user": "qa",
            "identityFile": "/key",
            "knownHostsFile": "/known",
        }
        done = subprocess.CompletedProcess([], 0, b"{}", b"")
        with patch("tools.handoff.customer_remote.subprocess.run", return_value=done) as run:
            SSH(target).run(["sudo", "-n", "python", "-B"], input_text="bundle")
            self.assertEqual(run.call_args.kwargs["input"], b"bundle")
            self.assertIn("StrictHostKeyChecking=yes", run.call_args.args[0])
            self.assertIn("BatchMode=yes", run.call_args.args[0])
            with self.assertRaises(RemoteError):
                SSH(target).run(["true"], input_text="x" * (MAX_OUTPUT + 1))
            self.assertEqual(run.call_count, 1)

    def test_one_ssh_call_and_invalid_selection_never_connects(self):
        class FakeSSH:
            def __init__(self):
                self.calls = []

            def run(self, argv, **kwargs):
                self.calls.append((argv, kwargs))
                return 0, json.dumps(
                    {"readOnlyEnforced": True, "queries": [], "timings": {"remoteElapsedMs": 1}}
                )

        ssh = FakeSSH()
        data = capture(ssh, "identity", 100)
        self.assertEqual(len(ssh.calls), 1)
        self.assertEqual(data["timings"]["sshInvocations"], 1)
        self.assertEqual(ssh.calls[0][0][:2], ["sudo", "-n"])
        self.assertIn("-B", ssh.calls[0][0])
        for mode, limit in [("SELECT 1", 100), ("reporting", 0)]:
            with self.assertRaises(RemoteError):
                capture(ssh, mode, limit)
        self.assertEqual(len(ssh.calls), 1)

    def test_readonly_evidence_and_remote_failures_fail_closed(self):
        for code, raw in [
            (1, "synthetic-private-output"),
            (0, "not JSON"),
            (0, "[]"),
            (
                0,
                json.dumps(
                    {"readOnlyEnforced": True, "queries": [], "timings": {"remoteElapsedMs": "NaN"}}
                ),
            ),
            (0, json.dumps({"readOnlyEnforced": False, "queries": []})),
        ]:
            with patch.object(SSH, "run", return_value=(code, raw)):
                with self.assertRaises(RemoteError) as caught:
                    capture(
                        SSH(
                            {
                                "user": "qa",
                                "host": "qa",
                                "identityFile": "/key",
                                "knownHostsFile": "/known",
                            }
                        ),
                        "running",
                        100,
                    )
                self.assertNotIn("synthetic-private-output", str(caught.exception))


class CaptureCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "read_cli", Path(__file__).resolve().parents[2] / "scripts/management/capture-trandb.py"
        )
        cls.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cli)

    def invoke(self, args):
        data = {
            "observedAtUtc": "synthetic",
            "readOnlyEnforced": True,
            "queries": [],
            "reports": {},
            "timings": {},
        }
        with (
            patch.object(
                sys,
                "argv",
                [
                    "capture",
                    "--inventory",
                    "/private/inventory",
                    "--target",
                    "qa",
                    "--mode",
                    "running",
                    *args,
                ],
            ),
            patch.object(self.cli, "capture", return_value=data) as collect,
            patch.object(self.cli, "load_target", return_value={}),
            patch.object(self.cli, "SSH"),
            patch("builtins.print"),
        ):
            self.cli.main()
        return collect

    def test_capture_is_exclusive_and_private_even_with_permissive_umask(self):
        import os
        import stat

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            previous = os.umask(0)
            try:
                self.invoke(["--output", str(path)])
            finally:
                os.umask(previous)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(SystemExit):
                self.invoke(["--output", str(path)])
            link = Path(directory) / "link.json"
            link.symlink_to(Path(directory) / "absent")
            with self.assertRaises(SystemExit):
                self.invoke(["--output", str(link)])
            self.assertFalse((Path(directory) / "absent").exists())

    def test_stdout_requires_no_capture_file(self):
        self.assertEqual(self.invoke([]).call_count, 1)
