"""
Agent tool layer.

Every tool is READ-ONLY except prepare_action/request_approval, which only
create AWAITING_APPROVAL rows — they never move money or auto-execute.
Tools return structured dicts, tagged by kind (FACT / CALCULATION / FORECAST)
so the agent (and the UI) never has to guess what a number represents.
"""
from datetime import datetime, timedelta
from . import reconciliation, forecasting, anomaly, approvals, audit


class FinanceTools:
    """Bound to one merchant + one open connection. Read tools first, write tools gated."""

    def __init__(self, conn, merchant_id: str, start_date: datetime, elapsed_days: int):
        self.conn = conn
        self.merchant_id = merchant_id
        self.start_date = start_date
        self.elapsed_days = elapsed_days

    def get_finance_summary(self) -> dict:
        conn, mid = self.conn, self.merchant_id
        today_cutoff = (self.start_date + timedelta(days=self.elapsed_days)).isoformat() + "Z"
        cash = self._current_cash()
        settled = conn.execute("SELECT COALESCE(SUM(amount_paise),0) as s FROM settlement WHERE merchant_id=? AND status='settled' AND settled_date < ?", (mid, today_cutoff)).fetchone()["s"]
        outstanding = conn.execute("SELECT COALESCE(SUM(expected_amount_paise),0) as s FROM settlement WHERE merchant_id=? AND status IN ('expected','delayed')", (mid,)).fetchone()["s"]
        refund_exposure = conn.execute("SELECT COALESCE(SUM(amount_paise),0) as s FROM refund WHERE merchant_id=? AND status='processed' AND created_at < ?", (mid, today_cutoff)).fetchone()["s"]
        health = reconciliation.reconciliation_health(conn, mid)
        return {"kind": "FACT+CALCULATION", "current_cash_paise": cash, "total_settled_paise": settled,
                "outstanding_receivables_paise": outstanding, "total_refund_exposure_paise": refund_exposure,
                "reconciliation_health": health}

    def get_cash_forecast(self, horizon_days: int = 30) -> dict:
        f = forecasting.cash_forecast(self.conn, self.merchant_id, self.start_date, self.elapsed_days,
                                      horizon_days, self._current_cash())
        f["kind"] = "FORECAST"
        return f

    def get_reconciliation_report(self, include_resolved: bool = False) -> dict:
        health = reconciliation.reconciliation_health(self.conn, self.merchant_id)
        active_clause = "" if include_resolved else "AND active = 1 "
        exceptions = self.conn.execute(
            f"SELECT * FROM reconciliation_match WHERE merchant_id=? {active_clause}AND status != 'MATCHED'",
            (self.merchant_id,)).fetchall()
        return {"kind": "FACT+CALCULATION", "health": health, "exceptions": [dict(r) for r in exceptions],
                "includes_resolved": include_resolved}

    def get_unmatched_transactions(self, include_resolved: bool = False) -> dict:
        active_clause = "" if include_resolved else "AND active = 1 "
        rows = self.conn.execute(
            f"SELECT * FROM reconciliation_match WHERE merchant_id=? {active_clause}AND status IN ('UNKNOWN_CREDIT','UNKNOWN_DEBIT','MISSING_SETTLEMENT')",
            (self.merchant_id,)).fetchall()
        return {"kind": "FACT", "unmatched": [dict(r) for r in rows], "includes_resolved": include_resolved}

    def get_settlement(self, settlement_id: str) -> dict:
        r = self.conn.execute("SELECT * FROM settlement WHERE id=? AND merchant_id=?", (settlement_id, self.merchant_id)).fetchone()
        return {"kind": "FACT", "settlement": dict(r) if r else None}

    def get_transaction(self, payment_id: str) -> dict:
        r = self.conn.execute("SELECT * FROM payment WHERE id=? AND merchant_id=?", (payment_id, self.merchant_id)).fetchone()
        return {"kind": "FACT", "payment": dict(r) if r else None}

    def get_anomalies(self, include_resolved: bool = False) -> dict:
        active_clause = "" if include_resolved else "AND active = 1 "
        rows = self.conn.execute(f"SELECT * FROM financial_anomaly WHERE merchant_id=? {active_clause}ORDER BY severity DESC", (self.merchant_id,)).fetchall()
        return {"kind": "FACT", "anomalies": [dict(r) for r in rows], "includes_resolved": include_resolved}

    def get_upcoming_obligations(self, days: int = 30) -> dict:
        cutoff = (self.start_date + timedelta(days=self.elapsed_days + days)).isoformat() + "Z"
        floor = (self.start_date + timedelta(days=self.elapsed_days)).isoformat() + "Z"
        rows = self.conn.execute("SELECT * FROM expense WHERE merchant_id=? AND status='scheduled' AND due_date >= ? AND due_date < ?", (self.merchant_id, floor, cutoff)).fetchall()
        return {"kind": "FACT", "obligations": [dict(r) for r in rows]}

    def explain_cash_change(self, day_index: int) -> dict:
        day_start = (self.start_date + timedelta(days=day_index)).isoformat() + "Z"
        day_end = (self.start_date + timedelta(days=day_index + 1)).isoformat() + "Z"
        conn, mid = self.conn, self.merchant_id
        settled = conn.execute("SELECT id, amount_paise FROM settlement WHERE merchant_id=? AND status='settled' AND settled_date >= ? AND settled_date < ?", (mid, day_start, day_end)).fetchall()
        refunds = conn.execute("SELECT id, amount_paise FROM refund WHERE merchant_id=? AND created_at >= ? AND created_at < ?", (mid, day_start, day_end)).fetchall()
        expenses = conn.execute("SELECT id, category, amount_paise FROM expense WHERE merchant_id=? AND due_date >= ? AND due_date < ?", (mid, day_start, day_end)).fetchall()
        net = sum(r["amount_paise"] for r in settled) - sum(r["amount_paise"] for r in refunds) - sum(r["amount_paise"] for r in expenses)
        return {"kind": "CALCULATION", "day_index": day_index, "net_change_paise": net,
                "settlements": [dict(r) for r in settled], "refunds": [dict(r) for r in refunds], "expenses": [dict(r) for r in expenses]}

    def simulate_scenario(self, scenario: dict) -> dict:
        base = self.get_cash_forecast(30)
        adjustment_paise = 0
        note = ""
        if scenario.get("type") == "delay_settlement":
            r = self.conn.execute("SELECT expected_amount_paise FROM settlement WHERE id=? AND merchant_id=?", (scenario["settlement_id"], self.merchant_id)).fetchone()
            if r:
                adjustment_paise = -r["expected_amount_paise"]
                note = f"Settlement {scenario['settlement_id']} (₹{r['expected_amount_paise']/100:,.2f}) delayed by {scenario.get('delay_days')} days; removed from near-term horizon."
        elif scenario.get("type") == "refund_increase_pct":
            baseline = self.conn.execute("SELECT COALESCE(AVG(amount_paise),0) as a FROM refund WHERE merchant_id=?", (self.merchant_id,)).fetchone()["a"]
            adjustment_paise = -round(baseline * (scenario.get("pct", 0) / 100.0) * 7)
            note = f"Refunds increased {scenario.get('pct')}% -> approx extra outflow over 7 days."
        elif scenario.get("type") == "volume_change_pct":
            avg_settlement = self.conn.execute("SELECT COALESCE(AVG(amount_paise),0) as a FROM settlement WHERE merchant_id=? AND status='settled'", (self.merchant_id,)).fetchone()["a"]
            adjustment_paise = round(avg_settlement * (scenario.get("pct", 0) / 100.0) * 7)
            note = f"Transaction volume change {scenario.get('pct')}% -> adjusted 7-day inflow."
        adjusted_points = [{**p, "expected_cash_paise": p["expected_cash_paise"] + adjustment_paise,
                            "lower_paise": p["lower_paise"] + adjustment_paise,
                            "upper_paise": p["upper_paise"] + adjustment_paise} for p in base["points"]]
        return {"kind": "FORECAST", "scenario": scenario, "note": note, "adjustment_paise": adjustment_paise,
                "adjusted_points": adjusted_points, "baseline_points": base["points"]}

    def get_audit_history(self, limit: int = 100) -> dict:
        return {"kind": "FACT", "events": audit.history(self.conn, self.merchant_id, limit)}

    def prepare_action(self, action_type: str, proposal: dict) -> dict:
        row = approvals.propose_action(self.conn, self.merchant_id, action_type, proposal)
        return {"kind": "ACTION_PROPOSAL", **row}

    def request_approval(self, request_id: str) -> dict:
        r = self.conn.execute("SELECT * FROM approval_request WHERE id=? AND merchant_id=?", (request_id, self.merchant_id)).fetchone()
        return {"kind": "FACT", "approval_request": dict(r) if r else None}

    def retry_action(self, request_id: str, retry_by: str, reason: str) -> dict:
        return {"kind": "ACTION_PROPOSAL", **approvals.retry(self.conn, self.merchant_id, request_id, retry_by, reason)}

    def _current_cash(self) -> int:
        today_cutoff = (self.start_date + timedelta(days=self.elapsed_days)).isoformat() + "Z"
        settled = self.conn.execute("SELECT COALESCE(SUM(amount_paise),0) as s FROM settlement WHERE merchant_id=? AND status='settled' AND settled_date < ?", (self.merchant_id, today_cutoff)).fetchone()["s"]
        expenses_paid = self.conn.execute("SELECT COALESCE(SUM(amount_paise),0) as s FROM expense WHERE merchant_id=? AND due_date < ?", (self.merchant_id, today_cutoff)).fetchone()["s"]
        return settled - expenses_paid
