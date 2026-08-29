"""
Finance read/query services. Plain functions returning plain dicts -- no
FastAPI or Pydantic dependency here by design, so this layer is fully
unit-testable against the real (sqlite3-backed) finpilot core without
needing FastAPI installed. The api/v1 layer wraps these dict returns into
Pydantic response models; this layer is the actual logic.
"""
from app.core import _bootstrap  # noqa: F401 -- must run before any `finpilot` import below
import json
from finpilot.core import reconciliation, anomaly, forecasting
from finpilot.core.agent_tools import FinanceTools
from app.core.constants import DATASET_START


def _tools(conn, merchant_id: str, today_offset: int) -> FinanceTools:
    return FinanceTools(conn, merchant_id, DATASET_START, today_offset)


def get_overview(conn, merchant_id: str, today_offset: int) -> dict:
    tools = _tools(conn, merchant_id, today_offset)
    summary = tools.get_finance_summary()
    anomalies = tools.get_anomalies()
    forecast = tools.get_cash_forecast(7)
    return {"current_cash_paise": summary["current_cash_paise"], "total_settled_paise": summary["total_settled_paise"], "outstanding_receivables_paise": summary["outstanding_receivables_paise"], "total_refund_exposure_paise": summary["total_refund_exposure_paise"], "reconciliation_health_pct": summary["reconciliation_health"]["health_pct"], "reconciliation_exceptions": summary["reconciliation_health"]["exceptions"], "open_anomalies": len(anomalies["anomalies"]), "forecast_7d_cash_paise": forecast["points"][-1]["expected_cash_paise"] if forecast["points"] else 0, "possible_shortfall_dates": forecast["possible_shortfall_dates"]}


def get_reconciliation_report(conn, merchant_id: str, include_resolved: bool = False) -> dict:
    active_clause = "" if include_resolved else "AND active = 1 "
    rows = conn.execute(f"SELECT * FROM reconciliation_match WHERE merchant_id=? {active_clause}ORDER BY updated_at DESC", (merchant_id,)).fetchall()
    health = reconciliation.reconciliation_health(conn, merchant_id)
    return {**health, "cases": [_case_row_to_dict(r) for r in rows]}


def get_reconciliation_case(conn, merchant_id: str, case_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM reconciliation_match WHERE id=? AND merchant_id=?", (case_id, merchant_id)).fetchone()
    if not row: return None
    case = _case_row_to_dict(row)
    observations = conn.execute("SELECT * FROM reconciliation_observation WHERE case_id=? ORDER BY observed_at ASC, rowid ASC", (case_id,)).fetchall()
    case["observation_history"] = [{"run_id": o["run_id"], "status": o["status"], "confidence": o["confidence"], "evidence": json.loads(o["evidence_json"]), "active": bool(o["active"]), "observed_at": o["observed_at"]} for o in observations]
    return case


def get_reconciliation_runs(conn, merchant_id: str, limit: int = 20) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM reconciliation_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT ?", (merchant_id, limit)).fetchall()]


def run_reconciliation(conn, merchant_id: str) -> dict:
    results = reconciliation.reconcile(conn, merchant_id)
    return {"cases_processed": len(results), "health": reconciliation.reconciliation_health(conn, merchant_id)}


def get_anomalies(conn, merchant_id: str, include_resolved: bool = False) -> list[dict]:
    active_clause = "" if include_resolved else "AND active = 1 "
    rows = conn.execute(f"SELECT * FROM financial_anomaly WHERE merchant_id=? {active_clause}ORDER BY severity DESC, updated_at DESC", (merchant_id,)).fetchall()
    return [_anomaly_row_to_dict(r) for r in rows]


def get_anomaly(conn, merchant_id: str, anomaly_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM financial_anomaly WHERE id=? AND merchant_id=?", (anomaly_id, merchant_id)).fetchone()
    if not row: return None
    result = _anomaly_row_to_dict(row)
    observations = conn.execute("SELECT * FROM anomaly_observation WHERE case_id=? ORDER BY observed_at ASC, rowid ASC", (anomaly_id,)).fetchall()
    result["observation_history"] = [{"run_id": o["run_id"], "severity": o["severity"], "evidence": json.loads(o["evidence_json"]), "active": bool(o["active"]), "observed_at": o["observed_at"]} for o in observations]
    return result


def get_anomaly_runs(conn, merchant_id: str, limit: int = 20) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM anomaly_detection_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT ?", (merchant_id, limit)).fetchall()]


def run_anomaly_detection(conn, merchant_id: str, today_offset: int) -> dict:
    findings = anomaly.detect(conn, merchant_id, DATASET_START, today_offset)
    return {"findings_count": len(findings)}


def get_forecast(conn, merchant_id: str, today_offset: int, horizon_days: int = 30) -> dict:
    return _tools(conn, merchant_id, today_offset).get_cash_forecast(horizon_days)


def simulate_scenario(conn, merchant_id: str, today_offset: int, scenario: dict) -> dict:
    return _tools(conn, merchant_id, today_offset).simulate_scenario(scenario)


def list_transactions(conn, merchant_id: str, limit: int = 100, status: str | None = None) -> list[dict]:
    clause = "AND status=? " if status else ""
    params = (merchant_id, status, limit) if status else (merchant_id, limit)
    return [dict(r) for r in conn.execute(f"SELECT * FROM payment WHERE merchant_id=? {clause}ORDER BY created_at DESC LIMIT ?", params).fetchall()]


def list_settlements(conn, merchant_id: str, limit: int = 100, status: str | None = None) -> list[dict]:
    clause = "AND status=? " if status else ""
    params = (merchant_id, status, limit) if status else (merchant_id, limit)
    return [dict(r) for r in conn.execute(f"SELECT * FROM settlement WHERE merchant_id=? {clause}ORDER BY expected_date DESC LIMIT ?", params).fetchall()]


def _case_row_to_dict(r) -> dict:
    d = dict(r); d["evidence"] = json.loads(d.pop("evidence_json")); d["active"] = bool(d["active"]); return d


def _anomaly_row_to_dict(r) -> dict:
    d = dict(r); d["evidence"] = json.loads(d.pop("evidence_json")); d["active"] = bool(d["active"]); return d
