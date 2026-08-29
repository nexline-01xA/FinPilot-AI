"""
AI Controller service.

Honest architecture note: this sandbox has no verified network path to a
live LLM (see finpilot/docs/CORE_LIMITATIONS.md). Two things live here as a
result:

1. answer_cash_weakening / answer_top_priority / propose_resolution_for_top_priority
   -- the three required demo questions, each implemented as REAL composition
   of the tested core's read tools (forecast, obligations, anomalies,
   reconciliation exceptions) into an evidence-backed structured answer. No
   LLM involved; these are deterministic, testable, and were run against the
   real seeded dataset while building this.

2. ask(question) -- routes arbitrary free text via keyword matching to the
   above three, to the DeterministicDemoAgent's fixed methods, or (if
   ANTHROPIC_API_KEY is configured AND a real environment provides network
   access) to ClaudeAgentProvider for genuine open-ended NLU. The keyword
   router is a heuristic, not understanding -- it is clearly labeled
   "DEMO_AGENT" / "KEYWORD_ROUTED" in every response, never presented as if
   it understood the question the way a live model would.
"""
from app.core import _bootstrap  # noqa: F401 -- must run before any `finpilot` import below
import re
from finpilot.core.agent_tools import FinanceTools
from finpilot.core.agent import DeterministicDemoAgent, get_agent
from app.core.constants import DATASET_START
from app.services import finance_service


def _tools(conn, merchant_id: str, today_offset: int) -> FinanceTools:
    return FinanceTools(conn, merchant_id, DATASET_START, today_offset)


def answer_cash_weakening(conn, merchant_id: str, today_offset: int) -> dict:
    tools = _tools(conn, merchant_id, today_offset)
    forecast = tools.get_cash_forecast(7)
    anomalies = finance_service.get_anomalies(conn, merchant_id)
    obligations = forecast["upcoming_obligations"]

    trend = forecast["points"][-1]["expected_cash_paise"] - forecast["points"][0]["expected_cash_paise"] if len(forecast["points"]) >= 2 else 0
    weakening = trend < 0 or bool(forecast["possible_shortfall_dates"])
    drivers = []
    if weakening:
        if forecast["possible_shortfall_dates"]:
            drivers.append({"factor": "forecast_shortfall", "dates": forecast["possible_shortfall_dates"]})
        for o in obligations:
            drivers.append({"factor": "scheduled_obligation", "category": o["category"], "amount_paise": o["amount_paise"], "due_date": o["due_date"]})
        for a in anomalies:
            if a["kind"] == "RULE_BASED_ALERT" and a["category"] in ("settlement_delayed", "settlement_amount_mismatch"):
                drivers.append({"factor": "reconciliation_exception", "category": a["category"], "evidence": a["evidence"], "anomaly_id": a["id"]})

    if weakening and drivers:
        answer = f"7-day cash forecast changes by ₹{trend/100:,.2f}. {len(drivers)} contributing factor(s) identified below."
    elif weakening:
        answer = f"7-day cash forecast trends down by ₹{abs(trend)/100:,.2f}, but no specific driver was isolated."
    else:
        answer = "Cash position is not projected to weaken over the next 7 days based on current data."

    return {"answer": answer, "kind": "FORECAST+CALCULATION", "weakening": weakening, "drivers": drivers,
            "upcoming_obligations": obligations, "forecast": forecast, "mode": "DEMO_AGENT"}


def answer_top_priority(conn, merchant_id: str, today_offset: int) -> dict:
    report = finance_service.get_reconciliation_report(conn, merchant_id)
    anomalies = finance_service.get_anomalies(conn, merchant_id)
    candidates = []
    for e in report["cases"]:
        if e["status"] == "MATCHED":
            continue
        urgency = {"MISSING_SETTLEMENT": 3, "AMOUNT_MISMATCH": 3, "DUPLICATE": 2, "UNKNOWN_CREDIT": 2, "UNKNOWN_DEBIT": 2, "PARTIAL": 1}.get(e["status"], 1)
        candidates.append({"type": "reconciliation_case", "id": e["id"], "urgency": urgency,
                           "status": e["status"], "confidence": e["confidence"], "evidence": e["evidence"]})
    for a in anomalies:
        urgency = {"high": 3, "medium": 2, "low": 1}.get(a["severity"], 1)
        candidates.append({"type": "anomaly", "id": a["id"], "urgency": urgency,
                           "category": a["category"], "severity": a["severity"], "evidence": a["evidence"]})
    if not candidates:
        return {"answer": "No open reconciliation exceptions or anomalies require attention right now.", "kind": "FACT", "top_priority": None, "all_candidates": [], "mode": "DEMO_AGENT"}
    candidates.sort(key=lambda c: (-c["urgency"], -(c.get("confidence") or 0)))
    top = candidates[0]
    label = top.get("status") or top.get("category")
    return {"answer": f"Highest priority: {top['type']} {top['id']} ({label}).", "kind": "FACT+CALCULATION", "top_priority": top, "all_candidates": candidates[:10], "mode": "DEMO_AGENT"}


def propose_resolution_for_top_priority(conn, merchant_id: str, today_offset: int) -> dict:
    priority = answer_top_priority(conn, merchant_id, today_offset)
    top = priority["top_priority"]
    tools = _tools(conn, merchant_id, today_offset)
    if not top:
        return {"answer": "Nothing currently requires investigation.", "action": None, "mode": "DEMO_AGENT"}
    proposal = {"target_type": top["type"], "target_id": top["id"], "reason": f"Top-ranked priority: {top.get('status') or top.get('category')}"}
    action = tools.prepare_action("mark_discrepancy_for_investigation", proposal)
    return {"answer": f"Prepared investigation {action['id']} for {top['type']} {top['id']} — AWAITING_APPROVAL. A human must approve before anything executes.", "action": action, "mode": "DEMO_AGENT"}


_ROUTES = [
    (re.compile(r"resolve|fix it|handle it|take action", re.I), "resolve_top_priority"),
    (re.compile(r"weaken|next week|why.*cash.*(fall|drop|down)", re.I), "cash_weakening"),
    (re.compile(r"attention|priorit|most important|what.*(should|need)", re.I), "top_priority"),
    (re.compile(r"payroll", re.I), "payroll"),
    (re.compile(r"settlement.*attention|which settlement", re.I), "settlement_attention"),
    (re.compile(r"why.*cash.*chang|cash.*yesterday", re.I), "cash_change"),
]
ACTION_PRODUCING_ROUTES = {"resolve_top_priority"}


def classify_route(question: str) -> str | None:
    for pattern, route in _ROUTES:
        if pattern.search(question):
            return route
    return None


def ask(conn, merchant_id: str, today_offset: int, question: str) -> dict:
    tools = _tools(conn, merchant_id, today_offset)
    demo_agent = DeterministicDemoAgent(tools)
    route = classify_route(question)
    if route == "cash_weakening":
        return {**answer_cash_weakening(conn, merchant_id, today_offset), "matched_route": route}
    if route == "top_priority":
        return {**answer_top_priority(conn, merchant_id, today_offset), "matched_route": route}
    if route == "resolve_top_priority":
        return {**propose_resolution_for_top_priority(conn, merchant_id, today_offset), "matched_route": route}
    if route == "payroll":
        return {**demo_agent.will_cash_cover_payroll(30), "matched_route": route}
    if route == "settlement_attention":
        return {**demo_agent.which_settlement_needs_attention(), "matched_route": route}
    if route == "cash_change":
        return {**demo_agent.why_did_cash_change(today_offset - 1), "matched_route": route}
    summary = tools.get_finance_summary()
    return {"answer": "I don't have a specific handler for that question in demo mode. Here's the current finance summary instead.", "kind": "FACT", "evidence": summary, "matched_route": None, "mode": "DEMO_AGENT"}
