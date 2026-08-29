"""
REAL, executable tests for the service layer. Zero FastAPI/SQLAlchemy
dependency -- these import app.services directly and run against the real
sqlite3-backed finpilot core, exactly like finpilot/tests/test_core.py does.
This is the layer that is ACTUALLY verified in this build; api/v1/*.py
(the FastAPI routing on top of these same functions) is not (see
docs/VERIFICATION_MATRIX.md).
"""
import os
import sys
import json
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import demo_service, finance_service, controller_service, approval_service, audit_service
from app.core.constants import DEMO_TODAY_OFFSET_DAYS
from finpilot.core import db as core_db, approvals

DB_PATH = "/tmp/finpilot_backend_test.db"


class BaseCase(unittest.TestCase):
    def setUp(self):
        result = demo_service.reset_demo(DB_PATH)
        self.mid = result["merchant_id"]
        self.conn = core_db.connect(DB_PATH)

    def tearDown(self):
        self.conn.close()


class TestDemoService(BaseCase):
    def test_reset_seeds_all_six_scenarios(self):
        result = demo_service.reset_demo(DB_PATH)
        self.assertEqual(len(result["scenarios_seeded"]), 6)

    def test_reset_is_deterministic(self):
        r1 = demo_service.reset_demo(DB_PATH, seed=42)
        conn1 = core_db.connect(DB_PATH)
        cash1 = finance_service.get_overview(conn1, r1["merchant_id"], DEMO_TODAY_OFFSET_DAYS)["current_cash_paise"]
        conn1.close()
        r2 = demo_service.reset_demo(DB_PATH, seed=42)
        conn2 = core_db.connect(DB_PATH)
        cash2 = finance_service.get_overview(conn2, r2["merchant_id"], DEMO_TODAY_OFFSET_DAYS)["current_cash_paise"]
        conn2.close()
        self.assertEqual(cash1, cash2)


class TestFinanceService(BaseCase):
    def test_overview_numbers_are_real(self):
        overview = finance_service.get_overview(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS)
        self.assertGreater(overview["current_cash_paise"], 0)
        self.assertEqual(overview["reconciliation_health_pct"], 93.5)

    def test_reconciliation_report_matches_core_directly(self):
        report = finance_service.get_reconciliation_report(self.conn, self.mid)
        self.assertEqual(report["total_matches"], 62)
        self.assertEqual(len(report["cases"]), 62)
        for c in report["cases"]:
            self.assertIsInstance(c["evidence"], dict)

    def test_reconciliation_case_detail_includes_observation_history(self):
        report = finance_service.get_reconciliation_report(self.conn, self.mid)
        case_id = report["cases"][0]["id"]
        detail = finance_service.get_reconciliation_case(self.conn, self.mid, case_id)
        self.assertIsNotNone(detail)
        self.assertIn("observation_history", detail)
        self.assertGreaterEqual(len(detail["observation_history"]), 1)

    def test_reconciliation_case_not_found_returns_none_not_exception(self):
        self.assertIsNone(finance_service.get_reconciliation_case(self.conn, self.mid, "nonexistent"))

    def test_anomalies_default_to_active_only(self):
        all_active = finance_service.get_anomalies(self.conn, self.mid)
        for a in all_active:
            self.assertTrue(a["active"])

    def test_forecast_has_real_benchmark(self):
        forecast = finance_service.get_forecast(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS, 14)
        self.assertIn("benchmark", forecast)
        self.assertTrue(forecast["benchmark"]["model_beats_naive"])

    def test_transactions_and_settlements_list(self):
        txns = finance_service.list_transactions(self.conn, self.mid, limit=10)
        self.assertEqual(len(txns), 10)
        settlements = finance_service.list_settlements(self.conn, self.mid, limit=5)
        self.assertLessEqual(len(settlements), 5)


class TestControllerService(BaseCase):
    def test_cash_weakening_answer_is_internally_consistent(self):
        result = controller_service.answer_cash_weakening(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS)
        if not result["weakening"]:
            self.assertEqual(result["drivers"], [], "non-weakening verdict listed drivers anyway")

    def test_top_priority_ranks_by_urgency(self):
        result = controller_service.answer_top_priority(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS)
        self.assertIsNotNone(result["top_priority"])
        urgencies = [c["urgency"] for c in result["all_candidates"]]
        self.assertEqual(urgencies, sorted(urgencies, reverse=True))

    def test_propose_resolution_creates_real_awaiting_approval_request(self):
        result = controller_service.propose_resolution_for_top_priority(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS)
        self.assertIsNotNone(result["action"])
        self.assertEqual(result["action"]["status"], "AWAITING_APPROVAL")

    def test_full_three_question_demo_flow_end_to_end(self):
        q1 = controller_service.answer_cash_weakening(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS)
        q2 = controller_service.answer_top_priority(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS)
        q3 = controller_service.propose_resolution_for_top_priority(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS)
        self.assertIsNotNone(q3["action"])
        approved = approval_service.decide(self.conn, self.mid, q3["action"]["id"], approved=True,
                                           decided_by="test_approver")
        self.assertEqual(approved["status"], "APPROVED")
        executed = approval_service.execute(self.conn, self.mid, q3["action"]["id"])
        self.assertEqual(executed["status"], "SUCCEEDED")

    def test_ask_routes_known_questions(self):
        r = controller_service.ask(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS,
                                    "Why is our cash position expected to weaken next week?")
        self.assertEqual(r["matched_route"], "cash_weakening")

    def test_exact_three_demo_questions_route_correctly_through_ask(self):
        cases = [
            ("Why is our cash position expected to weaken next week?", "cash_weakening"),
            ("What requires my attention first?", "top_priority"),
            ("Can you resolve the most important issue?", "resolve_top_priority"),
        ]
        for question, expected_route in cases:
            r = controller_service.ask(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS, question)
            self.assertEqual(r["matched_route"], expected_route, f"question: {question!r}")

    def test_exact_q3_sentence_creates_real_approval_via_ask(self):
        before = len(approval_service.list_approvals(self.conn, self.mid))
        r = controller_service.ask(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS,
                                    "Can you resolve the most important issue?")
        self.assertEqual(r["matched_route"], "resolve_top_priority")
        self.assertIn("action", r)
        self.assertIsNotNone(r["action"])
        self.assertEqual(r["action"]["status"], "AWAITING_APPROVAL")
        after = approval_service.list_approvals(self.conn, self.mid)
        self.assertEqual(len(after), before + 1)

    def test_action_producing_route_classification_matches_reality(self):
        cases = [
            ("Why is our cash position expected to weaken next week?", False),
            ("What requires my attention first?", False),
            ("Can you resolve the most important issue?", True),
        ]
        for question, should_produce_action in cases:
            route = controller_service.classify_route(question)
            is_action_producing = route in controller_service.ACTION_PRODUCING_ROUTES
            self.assertEqual(is_action_producing, should_produce_action, f"question: {question!r}")

    def test_ask_falls_back_honestly_on_unrecognized_question(self):
        r = controller_service.ask(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS,
                                    "What's the weather like in Bangalore?")
        self.assertIsNone(r["matched_route"])
        self.assertIn("don't have a specific handler", r["answer"])


class TestApprovalServiceTenantScoping(BaseCase):
    def test_service_layer_rejects_cross_tenant_execute(self):
        other_mid = "merch_other_via_service"
        self.conn.execute("INSERT INTO merchant (id, name, created_at) VALUES (?, 'Other', ?)",
                          (other_mid, "2026-01-01T00:00:00Z"))
        self.conn.commit()
        req = approval_service.propose(self.conn, other_mid, "create_alert", {"note": "x"})
        approval_service.decide(self.conn, other_mid, req["id"], approved=True, decided_by="t")
        with self.assertRaises(approvals.ApprovalError):
            approval_service.execute(self.conn, self.mid, req["id"])


class TestAuditService(BaseCase):
    def test_list_audit_events_parses_json_fields(self):
        controller_service.propose_resolution_for_top_priority(self.conn, self.mid, DEMO_TODAY_OFFSET_DAYS)
        events = audit_service.list_audit_events(self.conn, self.mid, limit=5)
        self.assertTrue(events)
        self.assertIsInstance(events[0]["inputs"], (dict, type(None)))

    def test_filter_by_operation(self):
        events = audit_service.list_audit_events(self.conn, self.mid, operation="reconcile")
        self.assertTrue(all(e["operation"] == "reconcile" for e in events))


if __name__ == "__main__":
    unittest.main(verbosity=2)
