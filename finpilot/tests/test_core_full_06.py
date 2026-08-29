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


class TestRetryWorkflow(BaseCase):
    def _fail_then_repair(self):
        self.conn.execute("DROP TABLE alert")
        self.conn.commit()
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "retry me"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        with self.assertRaises(Exception):
            approvals.execute(self.conn, self.mid, req["id"])
        failed = self.conn.execute(
            "SELECT status FROM approval_request WHERE id=?", (req["id"],)
        ).fetchone()
        self.assertEqual(failed["status"], "FAILED")
        self.conn.execute(
            "CREATE TABLE alert (id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, "
            "approval_request_id TEXT NOT NULL UNIQUE, severity TEXT NOT NULL, message TEXT NOT NULL, "
            "evidence_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL)"
        )
        self.conn.commit()
        return req["id"]

    def test_cannot_execute_directly_from_failed_without_retry(self):
        req_id = self._fail_then_repair()
        with self.assertRaises(approvals.ApprovalError):
            approvals.execute(self.conn, self.mid, req_id)

    def test_retry_then_execute_succeeds(self):
        req_id = self._fail_then_repair()
        retried = approvals.retry(self.conn, self.mid, req_id, retry_by="ops_engineer",
                                   reason="alert table restored")
        self.assertEqual(retried["status"], "APPROVED")
        self.assertEqual(retried["attempt_number"], 2)
        result = approvals.execute(self.conn, self.mid, req_id)
        self.assertEqual(result["status"], "SUCCEEDED")

    def test_retry_is_audited(self):
        req_id = self._fail_then_repair()
        approvals.retry(self.conn, self.mid, req_id, retry_by="ops_engineer", reason="fixed it")
        events = audit.history(self.conn, self.mid)
        retry_events = [e for e in events if e["operation"] == "retry_authorized"]
        self.assertTrue(retry_events)
        self.assertEqual(retry_events[0]["actor"], "ops_engineer")

    def test_only_one_domain_effect_exists_after_retry(self):
        req_id = self._fail_then_repair()
        approvals.retry(self.conn, self.mid, req_id, retry_by="ops_engineer", reason="fixed it")
        approvals.execute(self.conn, self.mid, req_id)
        count = self.conn.execute(
            "SELECT COUNT(*) c FROM alert WHERE approval_request_id=?", (req_id,)
        ).fetchone()["c"]
        self.assertEqual(count, 1)

    def test_double_retry_is_rejected(self):
        req_id = self._fail_then_repair()
        approvals.retry(self.conn, self.mid, req_id, retry_by="ops_engineer", reason="fixed it")
        with self.assertRaises(approvals.ApprovalError):
            approvals.retry(self.conn, self.mid, req_id, retry_by="ops_engineer", reason="again?")


class TestRunHistory(BaseCase):
    def test_reconciliation_run_recorded_as_completed(self):
        reconciliation.reconcile(self.conn, self.mid)
        run = self.conn.execute(
            "SELECT * FROM reconciliation_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (self.mid,)
        ).fetchone()
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "completed")
        self.assertIsNotNone(run["completed_at"])
        self.assertGreater(run["settlements_considered"], 0)

    def test_cases_reference_the_run_that_last_touched_them(self):
        reconciliation.reconcile(self.conn, self.mid)
        run = self.conn.execute(
            "SELECT id FROM reconciliation_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (self.mid,)
        ).fetchone()
        case = self.conn.execute(
            "SELECT last_run_id FROM reconciliation_match WHERE merchant_id=? LIMIT 1", (self.mid,)
        ).fetchone()
        self.assertEqual(case["last_run_id"], run["id"])

    def test_failed_run_is_recorded_with_error(self):
        self.conn.execute("DROP TABLE reconciliation_match")
        self.conn.commit()
        with self.assertRaises(Exception):
            reconciliation.reconcile(self.conn, self.mid)
        run = self.conn.execute(
            "SELECT * FROM reconciliation_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (self.mid,)
        ).fetchone()
        self.assertEqual(run["status"], "failed")
        self.assertIsNotNone(run["error"])

    def test_anomaly_detection_run_recorded(self):
        anomaly.detect(self.conn, self.mid, self.start, self.days)
        run = self.conn.execute(
            "SELECT * FROM anomaly_detection_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (self.mid,)
        ).fetchone()
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "completed")
