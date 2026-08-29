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


class TestActiveStateExposure(BaseCase):
    def _resolve_one_unknown_credit_case(self):
        reconciliation.reconcile(self.conn, self.mid)
        row = self.conn.execute(
            "SELECT id, ledger_entry_id FROM reconciliation_match WHERE merchant_id=? "
            "AND status='UNKNOWN_CREDIT' AND active=1 LIMIT 1", (self.mid,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.conn.execute("UPDATE ledger_entry SET reference='explained_elsewhere' WHERE id=?",
                          (row["ledger_entry_id"],))
        self.conn.commit()
        reconciliation.reconcile(self.conn, self.mid)
        resolved = self.conn.execute(
            "SELECT active FROM reconciliation_match WHERE id=?", (row["id"],)
        ).fetchone()
        self.assertEqual(resolved["active"], 0, "test setup: case should now be inactive")
        return row["id"]

    def test_resolved_case_absent_from_reconciliation_report_by_default(self):
        case_id = self._resolve_one_unknown_credit_case()
        tools = FinanceTools(self.conn, self.mid, self.start, self.days)
        report = tools.get_reconciliation_report()
        ids = [e["id"] for e in report["exceptions"]]
        self.assertNotIn(case_id, ids)

    def test_resolved_case_absent_from_unmatched_transactions_by_default(self):
        case_id = self._resolve_one_unknown_credit_case()
        tools = FinanceTools(self.conn, self.mid, self.start, self.days)
        result = tools.get_unmatched_transactions()
        ids = [e["id"] for e in result["unmatched"]]
        self.assertNotIn(case_id, ids)

    def test_resolved_case_visible_with_explicit_include_resolved(self):
        case_id = self._resolve_one_unknown_credit_case()
        tools = FinanceTools(self.conn, self.mid, self.start, self.days)
        report = tools.get_reconciliation_report(include_resolved=True)
        ids = [e["id"] for e in report["exceptions"]]
        self.assertIn(case_id, ids)

    def test_resolved_anomaly_absent_from_get_anomalies_by_default(self):
        anomaly.detect(self.conn, self.mid, self.start, self.days)
        row = self.conn.execute(
            "SELECT id, category FROM financial_anomaly WHERE merchant_id=? AND active=1 LIMIT 1",
            (self.mid,)
        ).fetchone()
        self.conn.execute("UPDATE financial_anomaly SET active=0 WHERE id=?", (row["id"],))
        self.conn.commit()
        tools = FinanceTools(self.conn, self.mid, self.start, self.days)
        result = tools.get_anomalies()
        ids = [a["id"] for a in result["anomalies"]]
        self.assertNotIn(row["id"], ids)
        result_with_history = tools.get_anomalies(include_resolved=True)
        ids_with_history = [a["id"] for a in result_with_history["anomalies"]]
        self.assertIn(row["id"], ids_with_history)


class TestAnomalyIdentityAcrossShiftedWindows(BaseCase):
    def test_refund_spike_survives_window_shifted_by_one_day(self):
        anomaly.detect(self.conn, self.mid, self.start, self.days)
        run1 = self.conn.execute(
            "SELECT id, case_key FROM financial_anomaly WHERE merchant_id=? "
            "AND category='refund_rate_spike' AND active=1", (self.mid,)
        ).fetchall()
        self.assertTrue(run1, "test setup: expected a refund_rate_spike finding")
        ids_run1 = {r["id"] for r in run1}
        keys_run1 = {r["case_key"] for r in run1}

        from datetime import timedelta
        shifted_start = self.start - timedelta(days=1)
        anomaly.detect(self.conn, self.mid, shifted_start, self.days + 1)
        run2 = self.conn.execute(
            "SELECT id, case_key FROM financial_anomaly WHERE merchant_id=? "
            "AND category='refund_rate_spike' AND active=1", (self.mid,)
        ).fetchall()
        ids_run2 = {r["id"] for r in run2}
        keys_run2 = {r["case_key"] for r in run2}

        self.assertEqual(ids_run1, ids_run2,
                          "the same real-world refund spike got a new id after the window shifted")
        self.assertEqual(keys_run1, keys_run2)

    def test_payment_volume_outlier_key_is_calendar_date_not_day_index(self):
        anomaly.detect(self.conn, self.mid, self.start, self.days)
        from datetime import timedelta
        shifted_start = self.start - timedelta(days=3)
        anomaly.detect(self.conn, self.mid, shifted_start, self.days + 3)
        rows = self.conn.execute(
            "SELECT category, case_key, evidence_json FROM financial_anomaly "
            "WHERE merchant_id=? AND category='payment_volume_outlier' AND active=1", (self.mid,)
        ).fetchall()
        for r in rows:
            evidence = json.loads(r["evidence_json"])
            self.assertIn("date", evidence)
            self.assertNotIn("day_index", evidence)


class TestAuditAtomicity(BaseCase):
    def test_propose_action_does_not_persist_without_its_audit_event(self):
        self.conn.execute("DROP TABLE audit_event")
        self.conn.commit()
        with self.assertRaises(Exception):
            approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "x"})
        count = self.conn.execute("SELECT COUNT(*) c FROM approval_request").fetchone()["c"]
        self.assertEqual(count, 0, "an approval row survived even though its audit write failed")

    def test_decide_does_not_persist_without_its_audit_event(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "x"})
        self.conn.execute("DROP TABLE audit_event")
        self.conn.commit()
        with self.assertRaises(Exception):
            approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        status = self.conn.execute(
            "SELECT status FROM approval_request WHERE id=?", (req["id"],)
        ).fetchone()["status"]
        self.assertEqual(status, "AWAITING_APPROVAL", "decide() left a partial state change in place")
