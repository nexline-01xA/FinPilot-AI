"""
FastAPI TestClient integration tests -- the full HTTP-layer scenarios an
external review specifically asked for, covering exactly the buttons/flows
a demo reviewer would exercise.

>>> EXTERNAL RUNTIME VERIFICATION REQUIRED. <<<
This file has NOT been executed in this sandbox: FastAPI, Pydantic, and
httpx (TestClient's transport) are not installed here (no PyPI access).
Written correctly to FastAPI's documented TestClient API, structured so it
can run with a single `pytest backend/tests/test_api.py` once those
packages are installed -- but until that command has actually been run
somewhere, treat every test below as unverified, not passing. See
docs/VERIFICATION_MATRIX.md.

Run with: pytest backend/tests/test_api.py -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/httpx not installed -- see module docstring")
class TestAPIIntegration(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.environ["SQLITE_PATH"] = self.db_path
        for mod in list(sys.modules):
            if mod.startswith("app."):
                del sys.modules[mod]
        from app.main import app
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        os.close(self.db_fd)
        os.remove(self.db_path)
        os.environ.pop("SQLITE_PATH", None)

    def test_fresh_db_bootstraps_and_overview_works(self):
        r = self.client.get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "healthy")
        self.assertTrue(r.json()["demo_state_usable"])
        r = self.client.get("/api/v1/overview")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.json()["current_cash"]["paise"], 0)

    def test_fresh_db_reconciliation_and_anomalies_also_work(self):
        r = self.client.get("/api/v1/reconciliation")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total_matches"], 62)
        r = self.client.get("/api/v1/anomalies")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_transactions_and_settlements(self):
        self.assertEqual(len(self.client.get("/api/v1/transactions?limit=10").json()), 10)
        self.assertEqual(self.client.get("/api/v1/settlements?limit=5").status_code, 200)

    def test_reconciliation_detail_and_history(self):
        report = self.client.get("/api/v1/reconciliation").json()
        case_id = report["cases"][0]["id"]
        r = self.client.get(f"/api/v1/reconciliation/{case_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("observation_history", r.json())

    def test_anomaly_detail_and_history(self):
        anomalies = self.client.get("/api/v1/anomalies").json()
        if anomalies:
            r = self.client.get(f"/api/v1/anomalies/{anomalies[0]['id']}")
            self.assertEqual(r.status_code, 200)
            self.assertIn("observation_history", r.json())

    def test_forecast_response_shape_matches_response_model(self):
        r = self.client.get("/api/v1/cash-flow?horizon_days=14")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("benchmark", body)
        self.assertTrue(body["benchmark"]["model_beats_naive"])
        self.assertIn("expected_cash_paise", body["points"][0])

    def test_scenario_simulation_request_contract(self):
        r = self.client.post("/api/v1/forecasts/simulate", json={"type": "refund_increase_pct", "pct": 10})
        self.assertEqual(r.status_code, 200)

    def test_exact_q1_over_http(self):
        r = self.client.post("/api/v1/controller/query", json={"question": "Why is our cash position expected to weaken next week?"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["matched_route"], "cash_weakening")

    def test_exact_q2_over_http(self):
        r = self.client.post("/api/v1/controller/query", json={"question": "What requires my attention first?"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["matched_route"], "top_priority")

    def test_exact_q3_over_http_creates_awaiting_approval(self):
        r = self.client.post("/api/v1/controller/query", headers={"X-Demo-Role": "ANALYST"}, json={"question": "Can you resolve the most important issue?"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["matched_route"], "resolve_top_priority")
        self.assertEqual(r.json()["action"]["status"], "AWAITING_APPROVAL")
        self.assertEqual(len(self.client.get("/api/v1/approvals").json()), 1)

    def test_viewer_cannot_create_controller_action(self):
        r = self.client.post("/api/v1/controller/query", headers={"X-Demo-Role": "VIEWER"}, json={"question": "Can you resolve the most important issue?"})
        self.assertEqual(r.status_code, 403)

    def test_analyst_can_propose_via_controller(self):
        r = self.client.post("/api/v1/controller/query", headers={"X-Demo-Role": "ANALYST"}, json={"question": "Can you resolve the most important issue?"})
        self.assertEqual(r.status_code, 200)

    def test_viewer_cannot_approve(self):
        self.client.post("/api/v1/controller/query", headers={"X-Demo-Role": "ANALYST"}, json={"question": "Can you resolve the most important issue?"})
        req_id = self.client.get("/api/v1/approvals").json()[0]["id"]
        r = self.client.post(f"/api/v1/approvals/{req_id}/approve", headers={"X-Demo-Role": "VIEWER"}, json={"decided_by": "x"})
        self.assertEqual(r.status_code, 403)

    def test_approver_can_approve_and_it_executes_and_verifies(self):
        self.client.post("/api/v1/controller/query", headers={"X-Demo-Role": "ANALYST"}, json={"question": "Can you resolve the most important issue?"})
        req_id = self.client.get("/api/v1/approvals").json()[0]["id"]
        r = self.client.post(f"/api/v1/approvals/{req_id}/approve", headers={"X-Demo-Role": "APPROVER"}, json={"decided_by": "reviewer"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "SUCCEEDED")

    def test_audit_contains_the_full_chain(self):
        self.client.post("/api/v1/controller/query", headers={"X-Demo-Role": "ANALYST"}, json={"question": "Can you resolve the most important issue?"})
        req_id = self.client.get("/api/v1/approvals").json()[0]["id"]
        self.client.post(f"/api/v1/approvals/{req_id}/approve", headers={"X-Demo-Role": "APPROVER"}, json={"decided_by": "reviewer"})
        ops = {e["operation"] for e in self.client.get("/api/v1/audit").json()}
        self.assertIn("propose_action", ops)
        self.assertIn("decide", ops)
        self.assertIn("execute_verify", ops)

    def test_viewer_cannot_trigger_reconciliation_run(self):
        self.assertEqual(self.client.post("/api/v1/reconciliation/run", headers={"X-Demo-Role": "VIEWER"}).status_code, 403)

    def test_demo_reset_requires_admin(self):
        self.assertEqual(self.client.post("/api/v1/demo/reset", headers={"X-Demo-Role": "ANALYST"}).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/demo/reset", headers={"X-Demo-Role": "ADMIN"}).status_code, 200)

    def test_tenant_isolation_over_http(self):
        other_mid = "merch_http_other"
        from app.core.config import settings
        from finpilot.core import db as core_db
        conn = core_db.connect(settings.sqlite_path)
        try:
            conn.execute("INSERT INTO merchant (id, name, created_at) VALUES (?, 'Other', ?)", (other_mid, "2026-01-01T00:00:00Z"))
            conn.execute("INSERT INTO settlement (id, merchant_id, amount_paise, expected_amount_paise, utr, status, expected_date, settled_date) VALUES ('set_http_secret', ?, 99999999, 99999999, 'UTRSECRET', 'settled', '2026-01-01', '2026-01-01')", (other_mid,))
            conn.commit()
        finally:
            conn.close()
        r = self.client.get("/api/v1/settlements", headers={"X-Merchant-Id": "merch_novacart"})
        self.assertFalse(any(s["id"] == "set_http_secret" for s in r.json()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
