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


class TestToolRegistry(BaseCase):
    def setUp(self):
        super().setUp()
        self.tools = FinanceTools(self.conn, self.mid, self.start, self.days)
        from finpilot.core.tool_registry import ToolRegistry, ToolPermissionError
        self.ToolPermissionError = ToolPermissionError
        self.registry = ToolRegistry(self.tools, actor="test")

    def test_read_tool_call_succeeds(self):
        result = self.registry.call("get_finance_summary")
        self.assertIn("current_cash_paise", result)

    def test_unknown_tool_name_rejected(self):
        with self.assertRaises(self.ToolPermissionError):
            self.registry.call("delete_all_transactions")

    def test_write_tool_call_is_audited(self):
        before = len(self.conn.execute(
            "SELECT 1 FROM audit_event WHERE merchant_id=?", (self.mid,)).fetchall())
        self.registry.call("prepare_action", action_type="create_alert", proposal={"note": "x"})
        after = len(self.conn.execute(
            "SELECT 1 FROM audit_event WHERE merchant_id=?", (self.mid,)).fetchall())
        self.assertGreater(after, before)

    def test_read_tool_call_is_not_double_audited_by_registry(self):
        before = len(self.conn.execute(
            "SELECT 1 FROM audit_event WHERE merchant_id=?", (self.mid,)).fetchall())
        self.registry.call("get_finance_summary")
        after = len(self.conn.execute(
            "SELECT 1 FROM audit_event WHERE merchant_id=?", (self.mid,)).fetchall())
        self.assertEqual(before, after)


class TestLiveAgentHonestFailure(BaseCase):
    def test_missing_anthropic_package_fails_loudly_not_silently(self):
        import os
        from finpilot.core.agent import get_agent
        os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
        try:
            with self.assertRaises(RuntimeError):
                get_agent(FinanceTools(self.conn, self.mid, self.start, self.days))
        finally:
            del os.environ["ANTHROPIC_API_KEY"]


class TestTenantIsolation(BaseCase):
    def setUp(self):
        super().setUp()
        self.other_mid = "merch_otherco_secret"
        self.conn.execute("INSERT INTO merchant (id, name, created_at) VALUES (?, 'OtherCo', ?)",
                          (self.other_mid, self.ground_truth["start_date"]))
        self.conn.execute(
            "INSERT INTO settlement (id, merchant_id, amount_paise, expected_amount_paise, "
            "utr, status, expected_date, settled_date) VALUES "
            "('set_B_secret', ?, 99999999, 99999999, 'UTRSECRET', 'settled', ?, ?)",
            (self.other_mid, self.ground_truth["start_date"], self.ground_truth["start_date"])
        )
        self.conn.execute(
            "INSERT INTO order_tbl (id, merchant_id, amount_paise, created_at, status) "
            "VALUES ('ord_B_secret', ?, 50000, ?, 'paid')", (self.other_mid, self.ground_truth["start_date"])
        )
        self.conn.execute(
            "INSERT INTO payment (id, order_id, merchant_id, amount_paise, fee_paise, tax_paise, "
            "status, method, created_at, settlement_id) VALUES "
            "('pay_B_secret', 'ord_B_secret', ?, 50000, 1000, 180, 'captured', 'upi', ?, 'set_B_secret')",
            (self.other_mid, self.ground_truth["start_date"])
        )
        self.conn.commit()
        self.other_req = approvals.propose_action(self.conn, self.other_mid, "create_alert",
                                                    {"note": "OtherCo secret alert"})
        self.tools = FinanceTools(self.conn, self.mid, self.start, self.days)

    def test_cannot_read_other_merchant_settlement(self):
        result = self.tools.get_settlement("set_B_secret")
        self.assertIsNone(result["settlement"], "NovaCart's tools leaked OtherCo's settlement")

    def test_cannot_read_other_merchant_payment(self):
        result = self.tools.get_transaction("pay_B_secret")
        self.assertIsNone(result["payment"], "NovaCart's tools leaked OtherCo's payment")

    def test_cannot_simulate_scenario_using_other_merchant_settlement(self):
        result = self.tools.simulate_scenario(
            {"type": "delay_settlement", "settlement_id": "set_B_secret", "delay_days": 3})
        self.assertEqual(result["adjustment_paise"], 0,
                          "NovaCart's tools used OtherCo's settlement amount in a simulation")

    def test_cannot_read_other_merchant_approval_request(self):
        result = self.tools.request_approval(self.other_req["id"])
        self.assertIsNone(result["approval_request"], "NovaCart's tools leaked OtherCo's approval request")

    def test_cannot_decide_other_merchant_approval_request(self):
        with self.assertRaises(approvals.ApprovalError):
            approvals.decide(self.conn, self.mid, self.other_req["id"], approved=True, decided_by="attacker")

    def test_cannot_execute_other_merchant_approval_request(self):
        approvals.decide(self.conn, self.other_mid, self.other_req["id"], approved=True, decided_by="legit")
        with self.assertRaises(approvals.ApprovalError):
            approvals.execute(self.conn, self.mid, self.other_req["id"])

    def test_demo_agent_cannot_explain_other_merchant_mismatch(self):
        reconciliation.reconcile(self.conn, self.other_mid)
        agent = DeterministicDemoAgent(self.tools)
        result = agent.explain_reconciliation_mismatch("set_B_secret")
        self.assertIn("No reconciliation record", result["answer"])

    def test_legitimate_owner_can_still_access_their_own_request(self):
        result = FinanceTools(self.conn, self.other_mid, self.start, self.days).request_approval(
            self.other_req["id"])
        self.assertIsNotNone(result["approval_request"])
