"""Guard the disruptive repair's preflight and rollback boundaries."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    "axis_repair",
    Path(__file__).resolve().parents[2] / "scripts/management/repair-axis-expansion.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AxisRepairTests(unittest.TestCase):
    def setUp(self):
        m.result = {"state": "PREFLIGHT", "steps": []}

    def test_changed_war_does_not_stop_agent(self):
        app = MagicMock()
        app.is_symlink.return_value = False
        app.is_dir.return_value = True
        war = MagicMock()
        war.is_symlink.return_value = False
        war.read_bytes.return_value = b"changed"
        with (
            patch.object(m, "APP", app),
            patch.object(m, "WAR", war),
            patch.object(m.os, "geteuid", return_value=0),
            patch.object(m, "control") as control,
            patch.object(m, "save"),
        ):
            self.assertEqual(m.main(), 1)
        control.assert_not_called()
        self.assertEqual(m.result["reason"], "WAR_CHANGED_SINCE_APPROVAL")

    def test_inflight_work_does_not_stop_or_move_application(self):
        app = MagicMock()
        app.is_symlink.return_value = False
        app.is_dir.return_value = True
        war = MagicMock()
        war.is_symlink.return_value = False
        war.read_bytes.return_value = b"approved"
        digest = m.hashlib.sha256(b"approved").hexdigest()
        identity = [
            {"key_name": "Agent_Id", "key_value": "665400"},
            {"key_name": "Agent_Group_Id", "key_value": "678370"},
        ]
        with (
            patch.object(m, "APP", app),
            patch.object(m, "WAR", war),
            patch.object(m, "EXPECTED_WAR", digest),
            patch.object(m.os, "geteuid", return_value=0),
            patch.object(m.zipfile, "ZipFile") as archive,
            patch.object(
                m, "query", side_effect=[identity, [{"active_runs": 1, "incoming_requests": 0}]]
            ),
            patch.object(m, "fingerprints", return_value={}),
            patch.object(m, "control") as control,
            patch.object(m, "save"),
        ):
            archive.return_value.__enter__.return_value.testzip.return_value = None
            self.assertEqual(m.main(), 1)
        control.assert_not_called()
        app.rename.assert_not_called()
        self.assertEqual(m.result["reason"], "WORK_IN_FLIGHT")
