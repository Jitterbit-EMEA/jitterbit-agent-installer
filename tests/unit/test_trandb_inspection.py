"""Regression guards for private read-only queries through configured PgBouncer."""

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "inspect_trandb", Path(__file__).resolve().parents[2] / "scripts/management/inspect-trandb.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InspectionSafetyTests(unittest.TestCase):
    def setUp(self):
        module.QUERIES.clear()

    def test_pooler_query_does_not_use_unsupported_startup_options(self):
        with patch.object(module.subprocess, "run", return_value=object()) as run:
            module.readonly_runner(
                ["psql", "-X"],
                env={"PGOPTIONS": "old", "PGPASSWORD": "synthetic-local-password"},
                capture_output=True,
            )
            args, kw = run.call_args
            self.assertEqual(args[0][:2], ["psql", "-q"])
            self.assertNotIn("PGOPTIONS", kw["env"])
            self.assertEqual(kw["env"]["PGPASSWORD"], "synthetic-local-password")

    def test_every_query_requires_readonly_transaction_and_rollback(self):
        with patch.object(
            module.provider, "_query", return_value='[{"transaction_read_only":"on"}]'
        ) as run:
            data = module.query("guard", "SELECT current_setting('transaction_read_only')")
            sql = run.call_args.args[0]
            self.assertTrue(sql.startswith("BEGIN READ ONLY;"))
            self.assertTrue(sql.endswith("ROLLBACK;"))
            self.assertIn("statement_timeout='5s'", sql)
            self.assertEqual(data[0]["transaction_read_only"], "on")

    def test_failure_is_not_empty_success_and_private_error_is_not_retained(self):
        with patch.object(
            module.provider, "_query", side_effect=RuntimeError("synthetic-private-credential")
        ):
            self.assertIsNone(module.query("failure", "SELECT 1"))
        self.assertEqual(module.QUERIES[-1]["status"], "UNAVAILABLE")
        self.assertNotIn("synthetic-private", json.dumps(module.QUERIES))

    def test_identifier_escape_preserves_quotes_as_data(self):
        self.assertEqual(module.ident('x"; SELECT 1; --'), '"x""; SELECT 1; --"')
