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


class TestDatasetDeterminism(BaseCase):
    def test_same_seed_produces_identical_data(self):
        conn2 = db.init_db("/tmp/finpilot_test2.db", fresh=True)
        gt2 = generator.generate(conn2, seed=42)
        rows1 = self.conn.execute("SELECT id, amount_paise FROM payment ORDER BY id").fetchall()
        rows2 = conn2.execute("SELECT id, amount_paise FROM payment ORDER BY id").fetchall()
        self.assertEqual([tuple(r) for r in rows1], [tuple(r) for r in rows2])
        conn2.close()
        os.remove("/tmp/finpilot_test2.db")

    def test_money_conserved_gross_equals_fee_plus_expected(self):
        rows = self.conn.execute("SELECT amount_paise, fee_paise, tax_paise FROM payment").fetchall()
        for r in rows:
            self.assertGreaterEqual(r["amount_paise"], r["fee_paise"] + r["tax_paise"])
            self.assertIsInstance(r["amount_paise"], int)  # never float


class TestReconciliation(BaseCase):
    def setUp(self):
        super().setUp()
        self.matches = reconciliation.reconcile(self.conn, self.mid)

    def test_duplicate_debit_scenario_detected(self):
        gt = self.ground_truth["scenarios"]["B_duplicate_debit"]
        dup_matches = [m for m in self.matches if m["status"] == "DUPLICATE"
                       and m["evidence"].get("settlement_id") == gt["settlement_id"]]
        self.assertTrue(dup_matches, "Scenario B duplicate debit was not detected")

    def test_settlement_mismatch_scenario_detected(self):
        gt = self.ground_truth["scenarios"]["D_settlement_mismatch"]
        row = self.conn.execute(
            "SELECT * FROM reconciliation_match WHERE settlement_id=? AND status='AMOUNT_MISMATCH'",
            (gt["settlement_id"],)
        ).fetchone()
        self.assertIsNotNone(row, "Scenario D amount mismatch was not detected")

    def test_delayed_settlement_scenario_detected(self):
        gt = self.ground_truth["scenarios"]["A_delayed_settlement"]
        row = self.conn.execute(
            "SELECT * FROM reconciliation_match WHERE settlement_id=? AND status='MISSING_SETTLEMENT'",
            (gt["settlement_id"],)
        ).fetchone()
        self.assertIsNotNone(row, "Scenario A delayed settlement was not flagged")

    def test_unmatched_credit_scenario_detected(self):
        unknown_credits = [m for m in self.matches if m["status"] == "UNKNOWN_CREDIT"]
        self.assertTrue(unknown_credits, "Scenario E unmatched credit was not detected")
        amounts = [m["evidence"]["amount_paise"] for m in unknown_credits]
        self.assertIn(self.ground_truth["scenarios"]["E_unmatched_credit"]["amount_paise"], amounts)

    def test_no_settlement_matched_twice(self):
        matched_settlements = [m["settlement_id"] for m in self.matches
                                if m["status"] == "MATCHED" and m["settlement_id"]]
        self.assertEqual(len(matched_settlements), len(set(matched_settlements)),
                          "A settlement was matched more than once")

    def test_reconciliation_health_reproducible(self):
        h1 = reconciliation.reconciliation_health(self.conn, self.mid)
        h2 = reconciliation.reconciliation_health(self.conn, self.mid)
        self.assertEqual(h1, h2)


class TestForecasting(BaseCase):
    def test_naive_baseline_benchmark_is_real_not_invented(self):
        result = forecasting.cash_forecast(self.conn, self.mid, self.start, self.days,
                                            horizon=14, current_cash_paise=0)
        bm = result["benchmark"]
        self.assertIsNotNone(bm["naive_baseline_mae_paise"])
        self.assertIsNotNone(bm["model_mae_paise"])
        self.assertGreater(bm["backtest_points"], 0)
        self.assertGreaterEqual(bm["naive_baseline_mae_paise"], 0)
        self.assertGreaterEqual(bm["model_mae_paise"], 0)

    def test_forecast_reproducible_same_inputs(self):
        r1 = forecasting.cash_forecast(self.conn, self.mid, self.start, self.days, 7, 100000)
        r2 = forecasting.cash_forecast(self.conn, self.mid, self.start, self.days, 7, 100000)
        self.assertEqual(r1["points"], r2["points"])

    def test_insufficient_history_handled_safely(self):
        bt = forecasting.backtest_mae(__import__("numpy").array([]), forecasting.naive_forecast)
        self.assertIsNone(bt["mae_paise"])
        self.assertEqual(bt["n_points"], 0)


class TestAnomalyDetection(BaseCase):
    def setUp(self):
        super().setUp()
        self.findings = anomaly.detect(self.conn, self.mid, self.start, self.days)

    def test_refund_spike_scenario_C_detected(self):
        rule_hits = [f for f in self.findings if f["category"] == "refund_rate_spike"]
        self.assertTrue(rule_hits, "Scenario C refund spike was not detected")

    def test_recurring_expense_spike_scenario_F_detected(self):
        hits = [f for f in self.findings if f["category"] == "recurring_expense_jump"]
        self.assertTrue(hits, "Scenario F recurring expense spike was not detected")

    def test_delayed_settlement_rule_alert(self):
        hits = [f for f in self.findings if f["category"] == "settlement_delayed"]
        self.assertTrue(hits)

    def test_rule_based_and_statistical_kept_separate(self):
        kinds = {f["kind"] for f in self.findings}
        self.assertTrue(kinds.issubset({"RULE_BASED_ALERT", "STATISTICAL_ANOMALY"}))
        for f in self.findings:
            self.assertIn(f["kind"], ("RULE_BASED_ALERT", "STATISTICAL_ANOMALY"))


class TestApprovalStateMachine(BaseCase):
    def test_reject_then_execute_is_blocked(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "test"})
        approvals.decide(self.conn, self.mid, req["id"], approved=False, decided_by="tester")
        with self.assertRaises(approvals.ApprovalError):
            approvals.execute(self.conn, self.mid, req["id"])

    def test_approve_then_execute_succeeds_once(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "test"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        result = approvals.execute(self.conn, self.mid, req["id"])
        self.assertEqual(result["status"], "SUCCEEDED")

    def test_double_execution_blocked(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "test"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        approvals.execute(self.conn, self.mid, req["id"])
        with self.assertRaises(approvals.ApprovalError):
            approvals.execute(self.conn, self.mid, req["id"])

    def test_double_decision_blocked(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "test"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        with self.assertRaises(approvals.ApprovalError):
            approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")

    def test_unsupported_action_type_rejected(self):
        with self.assertRaises(approvals.ApprovalError):
            approvals.propose_action(self.conn, self.mid, "wire_real_money", {})


class TestAuditTrail(BaseCase):
    def test_action_proposal_is_audited(self):
        tools = FinanceTools(self.conn, self.mid, self.start, self.days)
        tools.prepare_action("create_alert", {"note": "x"})
        events = audit.history(self.conn, self.mid)
        self.assertTrue(any(e["operation"] == "propose_action" for e in events))

    def test_full_chain_is_audited_propose_decide_execute_verify(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "chain test"})
        approvals.decide(self.conn, self.mid, req["id"], approved=True, decided_by="tester")
        approvals.execute(self.conn, self.mid, req["id"])
        events = audit.history(self.conn, self.mid)
        ops = {e["operation"] for e in events}
        self.assertIn("propose_action", ops)
        self.assertIn("decide", ops)
        self.assertIn("execute_start", ops)
        self.assertIn("execute_verify", ops)

    def test_rejection_is_audited(self):
        req = approvals.propose_action(self.conn, self.mid, "create_alert", {"note": "x"})
        approvals.decide(self.conn, self.mid, req["id"], approved=False, decided_by="tester")
        events = audit.history(self.conn, self.mid)
        decide_events = [e for e in events if e["operation"] == "decide"]
        self.assertTrue(any(e["decision"] == "REJECTED" for e in decide_events))
