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


class TestExecutionFailureHandling(BaseCase):
    def test_domain_write_exception_results_in_failed_not_stuck_executing(self):
        self.conn.execute("DROP TABLE alert")
        self.conn.commit()
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "will fail"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        with self.assertRaises(Exception):
            approvals.execute(self.conn, self.mid, req["id"])
        final = self.conn.execute(
            "SELECT status, result_json FROM approval_request WHERE id=?", (req["id"],)
        ).fetchone()
        self.assertEqual(final["status"], "FAILED")
        self.assertNotEqual(final["status"], "EXECUTING")
        result = json.loads(final["result_json"])
        self.assertIn("error", result)

    def test_execution_failure_is_audited(self):
        self.conn.execute("DROP TABLE alert")
        self.conn.commit()
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "will fail"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        try:
            approvals.execute(self.conn, self.mid, req["id"])
        except Exception:
            pass
        events = audit.history(self.conn, self.mid)
        failed_events = [e for e in events if e["operation"] == "execute_failed"]
        self.assertTrue(failed_events, "no execute_failed audit event was written")
        self.assertEqual(failed_events[0]["approval_state"], "FAILED")
        self.assertIsNotNone(failed_events[0]["error"])

    def test_execute_only_transitions_from_approved_atomically(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "race"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        self.conn.execute("UPDATE approval_request SET status='EXECUTING' WHERE id=?", (req["id"],))
        self.conn.commit()
        with self.assertRaises(approvals.ApprovalError):
            approvals.execute(self.conn, self.mid, req["id"])


class TestStableEntityIdentity(BaseCase):
    def test_reconciliation_ids_are_stable_across_reruns(self):
        m1 = reconciliation.reconcile(self.conn, self.mid)
        ids1 = {r["id"] for r in m1}
        m2 = reconciliation.reconcile(self.conn, self.mid)
        ids2 = {r["id"] for r in m2}
        self.assertEqual(ids1, ids2, "reconciliation case ids changed across an unchanged rerun")

    def test_anomaly_ids_are_stable_across_reruns(self):
        a1 = anomaly.detect(self.conn, self.mid, self.start, self.days)
        ids1 = {f["id"] for f in a1}
        a2 = anomaly.detect(self.conn, self.mid, self.start, self.days)
        ids2 = {f["id"] for f in a2}
        self.assertEqual(ids1, ids2, "anomaly case ids changed across an unchanged rerun")

    def test_investigation_reference_survives_a_rerun(self):
        matches = reconciliation.reconcile(self.conn, self.mid)
        target = matches[0]
        target_id = target["id"]
        reconciliation.reconcile(self.conn, self.mid)
        still_there = self.conn.execute(
            "SELECT * FROM reconciliation_match WHERE id=?", (target_id,)
        ).fetchone()
        self.assertIsNotNone(still_there, "a reference captured before a rerun no longer resolves")
        self.assertEqual(still_there["case_key"], target["case_key"])

    def test_case_that_stops_reproducing_is_marked_inactive_not_deleted(self):
        reconciliation.reconcile(self.conn, self.mid)
        before_count = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_match WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        row = self.conn.execute(
            "SELECT ledger_entry_id FROM reconciliation_match WHERE merchant_id=? "
            "AND status='UNKNOWN_CREDIT' AND active=1 LIMIT 1", (self.mid,)
        ).fetchone()
        self.assertIsNotNone(row, "test setup assumption failed: expected an UNKNOWN_CREDIT case")
        self.conn.execute("UPDATE ledger_entry SET reference='explained_elsewhere' WHERE id=?",
                          (row["ledger_entry_id"],))
        self.conn.commit()
        reconciliation.reconcile(self.conn, self.mid)
        after_count = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_match WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        self.assertEqual(before_count, after_count)
        still_active = self.conn.execute(
            "SELECT active FROM reconciliation_match WHERE merchant_id=? AND "
            "ledger_entry_id=?", (self.mid, row["ledger_entry_id"])
        ).fetchone()
        self.assertEqual(still_active["active"], 0)

    def test_reconciliation_health_only_counts_active_cases(self):
        reconciliation.reconcile(self.conn, self.mid)
        health_before = reconciliation.reconciliation_health(self.conn, self.mid)
        row = self.conn.execute(
            "SELECT ledger_entry_id FROM reconciliation_match WHERE merchant_id=? "
            "AND status='UNKNOWN_CREDIT' AND active=1 LIMIT 1", (self.mid,)
        ).fetchone()
        self.conn.execute("UPDATE ledger_entry SET reference='explained_elsewhere' WHERE id=?",
                          (row["ledger_entry_id"],))
        self.conn.commit()
        reconciliation.reconcile(self.conn, self.mid)
        health_after = reconciliation.reconciliation_health(self.conn, self.mid)
        self.assertEqual(health_after["total_matches"], health_before["total_matches"] - 1)
