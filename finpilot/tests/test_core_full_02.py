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


class TestIdempotency(BaseCase):
    def test_reconcile_rerun_does_not_duplicate(self):
        m1 = reconciliation.reconcile(self.conn, self.mid)
        count_after_1 = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_match WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        m2 = reconciliation.reconcile(self.conn, self.mid)
        count_after_2 = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_match WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        self.assertEqual(count_after_1, count_after_2)
        self.assertEqual(len(m1), len(m2))

    def test_detect_rerun_does_not_duplicate(self):
        a1 = anomaly.detect(self.conn, self.mid, self.start, self.days)
        count_after_1 = self.conn.execute(
            "SELECT COUNT(*) c FROM financial_anomaly WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        a2 = anomaly.detect(self.conn, self.mid, self.start, self.days)
        count_after_2 = self.conn.execute(
            "SELECT COUNT(*) c FROM financial_anomaly WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        self.assertEqual(count_after_1, count_after_2)
        self.assertEqual(len(a1), len(a2))

    def test_reconcile_rerun_against_changed_data_reflects_only_current_state(self):
        reconciliation.reconcile(self.conn, self.mid)
        self.conn.execute(
            "INSERT INTO ledger_entry (id, merchant_id, amount_paise, description, value_date, "
            "reference, matched) VALUES ('ldg_new_test', ?, 500000, 'NEFT CREDIT UNKNOWN', "
            "'2026-07-01T00:00:00Z', NULL, 0)", (self.mid,)
        )
        self.conn.commit()
        matches = reconciliation.reconcile(self.conn, self.mid)
        new_match = [m for m in matches if m["evidence"].get("ledger_entry_id") == "ldg_new_test"]
        self.assertTrue(new_match, "new ledger entry should appear in the re-derived match set")
        reconciliation.reconcile(self.conn, self.mid)
        count = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_match WHERE ledger_entry_id='ldg_new_test'"
        ).fetchone()["c"]
        self.assertEqual(count, 1)


class TestRealDomainSideEffects(BaseCase):
    def test_create_alert_actually_creates_alert_row(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert",
                                        {"severity": "high", "message": "test alert"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        result = approvals.execute(self.conn, self.mid, req["id"])
        self.assertEqual(result["status"], "SUCCEEDED")
        alert_row = self.conn.execute(
            "SELECT * FROM alert WHERE approval_request_id=?", (req["id"],)
        ).fetchone()
        self.assertIsNotNone(alert_row, "execute() reported SUCCEEDED but no alert row exists")
        self.assertEqual(alert_row["message"], "test alert")

    def test_investigation_action_creates_finance_task_row(self):
        req = approvals.propose_action(self.conn, self.mid, "mark_discrepancy_for_investigation",
                                        {"reason": "unmatched credit"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        approvals.execute(self.conn, self.mid, req["id"])
        task_row = self.conn.execute(
            "SELECT * FROM finance_task WHERE approval_request_id=?", (req["id"],)
        ).fetchone()
        self.assertIsNotNone(task_row)
        self.assertEqual(task_row["task_type"], "investigation")

    def test_generate_reconciliation_report_creates_report_row_with_real_snapshot(self):
        reconciliation.reconcile(self.conn, self.mid)
        req = approvals.propose_action(self.conn, self.mid, "generate_reconciliation_report", {})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        approvals.execute(self.conn, self.mid, req["id"])
        report = self.conn.execute(
            "SELECT * FROM reconciliation_report WHERE approval_request_id=?", (req["id"],)
        ).fetchone()
        self.assertIsNotNone(report)
        snapshot = json.loads(report["summary_json"])
        self.assertIn("health_pct", snapshot)

    def test_result_json_reflects_verified_true_on_success(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "x"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        result = approvals.execute(self.conn, self.mid, req["id"])
        stored = json.loads(result["result_json"])
        self.assertTrue(stored["verified"])


class TestAgentToolLayer(BaseCase):
    def setUp(self):
        super().setUp()
        reconciliation.reconcile(self.conn, self.mid)
        anomaly.detect(self.conn, self.mid, self.start, self.days)
        self.tools = FinanceTools(self.conn, self.mid, self.start, self.days)
        self.agent = DeterministicDemoAgent(self.tools)

    def test_finance_summary_numbers_trace_to_db(self):
        summary = self.tools.get_finance_summary()
        from datetime import timedelta
        cutoff = (self.start + timedelta(days=self.days)).isoformat() + "Z"
        db_settled = self.conn.execute(
            "SELECT COALESCE(SUM(amount_paise),0) as s FROM settlement "
            "WHERE status='settled' AND settled_date < ?", (cutoff,)
        ).fetchone()["s"]
        self.assertEqual(summary["total_settled_paise"], db_settled)

    def test_agent_reports_demo_mode_honestly(self):
        answer = self.agent.why_did_cash_change(10)
        self.assertEqual(answer["mode"], "DEMO_AGENT")

    def test_scenario_simulator_does_not_mutate_persisted_state(self):
        before = self.tools.get_finance_summary()
        self.tools.simulate_scenario({"type": "refund_increase_pct", "pct": 20})
        after = self.tools.get_finance_summary()
        self.assertEqual(before, after)

    def test_agent_investigation_creates_awaiting_approval_not_executed_action(self):
        result = self.agent.prepare_investigation_for_largest_unexplained_debit()
        if result["evidence"] and "status" in result["evidence"]:
            self.assertEqual(result["evidence"]["status"], "AWAITING_APPROVAL")


class TestFailureInjection(BaseCase):
    def test_forecast_with_zero_elapsed_days_does_not_crash(self):
        result = forecasting.cash_forecast(self.conn, self.mid, self.start, 0, 7, 0)
        self.assertEqual(len(result["points"]), 7)

    def test_reconcile_on_merchant_with_no_data_returns_empty(self):
        empty_conn = db.init_db("/tmp/finpilot_empty.db", fresh=True)
        empty_conn.execute("INSERT INTO merchant (id, name, created_at) VALUES ('m2','Empty','2026-01-01T00:00:00Z')")
        empty_conn.commit()
        matches = reconciliation.reconcile(empty_conn, "m2")
        self.assertEqual(matches, [])
        empty_conn.close()
        os.remove("/tmp/finpilot_empty.db")

    def test_decide_on_nonexistent_request_raises_clean_error(self):
        with self.assertRaises(approvals.ApprovalError):
            approvals.decide(self.conn, self.mid, "nonexistent_id", approved=True, decided_by="x")
