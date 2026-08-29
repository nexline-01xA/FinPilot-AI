import os
import sys
import json
import unittest
from datetime import datetime, timezone

# Repo root (not finpilot/) on sys.path, and package-qualified imports below --
# same fix, same reason, as run_evaluation.py: this only worked before when
# invoked with cwd=finpilot/; `python -m finpilot.tests.test_core` from the
# repo root would otherwise fail the same way. Packaging-only change, zero
# test logic touched -- rerun to confirm: still 84/84. See docs/VERIFICATION_MATRIX.md.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from finpilot.core import db, generator, reconciliation, forecasting, anomaly, approvals, audit
from finpilot.core.agent_tools import FinanceTools
from finpilot.core.agent import DeterministicDemoAgent

DB_PATH = "/tmp/finpilot_test.db"


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(DB_PATH, fresh=True)
        self.ground_truth = generator.generate(self.conn, seed=42)
        self.mid = self.ground_truth["merchant_id"]
        self.start = datetime.fromisoformat(self.ground_truth["start_date"].replace("Z", "+00:00")).replace(tzinfo=None)
        self.days = self.ground_truth["days"]

    def tearDown(self):
        self.conn.close()


class TestFailedRunLeavesNoPartialState(BaseCase):
    def test_reconciliation_failure_after_first_upsert_leaves_zero_partial_rows(self):
        from unittest import mock
        call_count = [0]
        original = reconciliation._upsert
        def failing(*args, **kwargs):
            call_count[0] += 1
            result = original(*args, **kwargs)
            if call_count[0] == 1:
                raise RuntimeError("injected failure right after first upsert")
            return result
        with mock.patch.object(reconciliation, "_upsert", side_effect=failing):
            with self.assertRaises(RuntimeError):
                reconciliation.reconcile(self.conn, self.mid)
        count = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_match WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        self.assertEqual(count, 0)
        run = self.conn.execute(
            "SELECT status FROM reconciliation_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (self.mid,)
        ).fetchone()
        self.assertEqual(run["status"], "failed")

    def test_reconciliation_failure_after_multiple_upserts_leaves_zero_partial_rows(self):
        from unittest import mock
        call_count = [0]
        original = reconciliation._upsert
        def failing(*args, **kwargs):
            call_count[0] += 1
            result = original(*args, **kwargs)
            if call_count[0] == 5:
                raise RuntimeError("injected failure after several upserts")
            return result
        with mock.patch.object(reconciliation, "_upsert", side_effect=failing):
            with self.assertRaises(RuntimeError):
                reconciliation.reconcile(self.conn, self.mid)
        count = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_match WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        self.assertEqual(count, 0)

    def test_anomaly_failure_after_first_upsert_leaves_zero_partial_rows(self):
        from unittest import mock
        call_count = [0]
        original = anomaly._upsert
        def failing(*args, **kwargs):
            call_count[0] += 1
            result = original(*args, **kwargs)
            if call_count[0] == 1:
                raise RuntimeError("injected failure right after first anomaly upsert")
            return result
        with mock.patch.object(anomaly, "_upsert", side_effect=failing):
            with self.assertRaises(RuntimeError):
                anomaly.detect(self.conn, self.mid, self.start, self.days)
        count = self.conn.execute(
            "SELECT COUNT(*) c FROM financial_anomaly WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        self.assertEqual(count, 0)
        run = self.conn.execute(
            "SELECT status FROM anomaly_detection_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (self.mid,)
        ).fetchone()
        self.assertEqual(run["status"], "failed")

    def test_previous_successful_state_survives_a_later_failed_run(self):
        reconciliation.reconcile(self.conn, self.mid)
        count_before = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_match WHERE merchant_id=? AND active=1", (self.mid,)
        ).fetchone()["c"]
        from unittest import mock
        with mock.patch.object(reconciliation, "_upsert", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                reconciliation.reconcile(self.conn, self.mid)
        count_after = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_match WHERE merchant_id=? AND active=1", (self.mid,)
        ).fetchone()["c"]
        self.assertEqual(count_before, count_after,
                          "a failed rerun corrupted or removed the previous successful run's state")

    def test_run_finalization_audit_failure_does_not_leave_run_stuck_running(self):
        from unittest import mock
        original_record = audit.record
        def failing_record(conn, merchant_id, actor, operation, *a, **kw):
            if operation == "reconcile":
                raise RuntimeError("audit_event unavailable")
            return original_record(conn, merchant_id, actor, operation, *a, **kw)
        with mock.patch.object(audit, "record", side_effect=failing_record):
            with mock.patch.object(reconciliation, "audit", audit):
                with self.assertRaises(RuntimeError):
                    reconciliation.reconcile(self.conn, self.mid)
        run = self.conn.execute(
            "SELECT status, completed_at FROM reconciliation_run WHERE merchant_id=? "
            "ORDER BY started_at DESC, rowid DESC LIMIT 1", (self.mid,)
        ).fetchone()
        self.assertEqual(run["status"], "failed")
        self.assertIsNotNone(run["completed_at"])
