"""
Agent provider abstraction.

DeterministicDemoAgent: answers a fixed set of finance-controller questions by
calling the tool registry (same allowlisted, audited surface a live agent
uses), with templated (not model-generated) prose. This is the mode actually
exercised and verified in this build.

ClaudeAgentProvider: a genuine tool-calling loop against the Anthropic
Messages API (model="claude-sonnet-4-6"), taking an arbitrary natural-language
finance question rather than a fixed set of Python methods -- this is what
answers point 7 of the review ("build a genuine generic controller"). It is
written to the documented Messages API tool-use request/response shape.

>>> THIS PATH IS UNVERIFIED. <<<
It has NOT been executed in this session: this sandbox has no network egress
(confirmed earlier in this conversation -- pypi.org and razorpay.com both
returned 403 to a direct curl test), so there is no way to actually call
api.anthropic.com from here and confirm the loop runs end to end. Constructing
ClaudeAgentProvider does not require network (it just builds a client), but
calling .ask() does, and that call path has not been exercised. Test it for
real in an environment with internet access before treating it as working --
that is the honest status, not "should work in theory."
"""
import os
import json
from .tool_registry import ToolRegistry
from . import audit

SYSTEM_PROMPT = """You are FinPilot AI's Finance Controller agent for a merchant's
internal finance dashboard. You answer questions ONLY by calling the tools
provided -- never invent a transaction id, amount, date, or balance. Every
number in your answer must trace back to a tool result.

Label each part of your answer as one of: FACT (a stored value), CALCULATION
(derived deterministically from stored values), FORECAST (from the forecasting
tool, always with its stated uncertainty band), INFERENCE (a pattern you are
pointing out, not a certainty), or RECOMMENDATION (a suggested next step).
Never state an INFERENCE or RECOMMENDATION as if it were a FACT.

If you believe a financial action is warranted (investigating a discrepancy,
raising an alert, generating a report), call prepare_action to propose it.
NEVER claim an action has been taken -- prepare_action only creates a request
awaiting human approval. You have no ability to execute anything yourself.

Cite specific evidence: transaction ids, settlement ids, dates, amounts,
anomaly ids, confidence scores -- pulled from tool results, never guessed."""


class DeterministicDemoAgent:
    mode = "DEMO_AGENT"

    def __init__(self, tools):
        self.tools = tools
        self.registry = ToolRegistry(tools, actor="demo_agent")

    def why_did_cash_change(self, day_index: int) -> dict:
        evidence = self.registry.call("explain_cash_change", day_index=day_index)
        parts = []
        if evidence["settlements"]:
            total = sum(s["amount_paise"] for s in evidence["settlements"])
            parts.append(f"+₹{total/100:,.2f} from {len(evidence['settlements'])} settlement(s)")
        if evidence["refunds"]:
            total = sum(r["amount_paise"] for r in evidence["refunds"])
            parts.append(f"-₹{total/100:,.2f} from {len(evidence['refunds'])} refund(s)")
        if evidence["expenses"]:
            total = sum(e["amount_paise"] for e in evidence["expenses"])
            parts.append(f"-₹{total/100:,.2f} from {len(evidence['expenses'])} expense(s)")
        answer = (f"Net cash change on day {day_index}: ₹{evidence['net_change_paise']/100:,.2f}. "
                  f"Drivers: {'; '.join(parts) if parts else 'no cash-moving events that day'}.")
        return {"answer": answer, "evidence": evidence, "mode": self.mode}

    def which_settlement_needs_attention(self) -> dict:
        report = self.registry.call("get_reconciliation_report")
        if not report["exceptions"]:
            return {"answer": "No reconciliation exceptions found.", "evidence": report,
                    "mode": self.mode}
        worst = max(report["exceptions"], key=lambda e: 0 if e["confidence"] is None else -e["confidence"])
        answer = (f"Settlement-related exception {worst['id']} (status={worst['status']}, "
                  f"confidence={worst['confidence']}) needs attention.")
        return {"answer": answer, "evidence": worst, "mode": self.mode}

    def will_cash_cover_payroll(self, horizon_days: int = 30) -> dict:
        forecast = self.registry.call("get_cash_forecast", horizon_days=horizon_days)
        payroll = [o for o in forecast["upcoming_obligations"] if o["category"] == "payroll"]
        if not payroll:
            return {"answer": "No payroll obligation scheduled in this horizon.",
                    "evidence": forecast, "mode": self.mode}
        p = payroll[0]
        covering_points = [pt for pt in forecast["points"] if pt["day"] >= p["due_date"][:10]]
        at_risk = covering_points and covering_points[0]["lower_paise"] < p["amount_paise"]
        answer = (f"Payroll of ₹{p['amount_paise']/100:,.2f} due {p['due_date'][:10]}: "
                  f"{'AT RISK — projected lower-bound cash may not cover it' if at_risk else 'projected to be covered'}.")
        return {"answer": answer, "evidence": {"forecast": forecast, "payroll": p}, "mode": self.mode}

    def explain_reconciliation_mismatch(self, settlement_id: str) -> dict:
        rows = self.tools.conn.execute(
            "SELECT * FROM reconciliation_match WHERE settlement_id=? AND merchant_id=?",
            (settlement_id, self.tools.merchant_id)
        ).fetchall()
        if not rows:
            return {"answer": f"No reconciliation record for {settlement_id}.",
                     "evidence": None, "mode": self.mode}
        r = dict(rows[0])
        return {"answer": f"{r['status']}: {r['evidence_json']}", "evidence": r, "mode": self.mode}

    def prepare_investigation_for_largest_unexplained_debit(self) -> dict:
        unmatched = self.registry.call("get_unmatched_transactions")
        debits = [u for u in unmatched["unmatched"] if u["status"] == "UNKNOWN_DEBIT"]
        if not debits:
            return {"answer": "No unexplained debits found.", "evidence": unmatched,
                    "mode": self.mode}
        proposal = {"target": debits[0]["id"], "reason": "largest unexplained debit"}
        action = self.registry.call("prepare_action", action_type="mark_discrepancy_for_investigation",
                                     proposal=proposal)
        return {"answer": f"Prepared investigation action {action['id']} — AWAITING_APPROVAL.",
                "evidence": action, "mode": self.mode}


class ClaudeAgentProvider:
    """
    Real tool-calling loop against the Anthropic Messages API. UNVERIFIED in
    this sandbox -- see module docstring. Requires `pip install anthropic`
    and ANTHROPIC_API_KEY in your real environment; neither is available here.
    """
    mode = "LIVE_AGENT_UNVERIFIED"
    MODEL = "claude-sonnet-4-6"
    MAX_TOOL_ITERATIONS = 8

    def __init__(self, tools):
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "The 'anthropic' package is not installed. This is expected in the "
                "claude.ai sandbox this was built in; run `pip install anthropic` in "
                "your real environment."
            ) from e
        self.tools = tools
        self.registry = ToolRegistry(tools, actor="claude_agent")
        self._client = anthropic.Anthropic()

    def ask(self, question: str) -> dict:
        messages = [{"role": "user", "content": question}]
        tool_calls_made = []
        for _ in range(self.MAX_TOOL_ITERATIONS):
            response = self._client.messages.create(model=self.MODEL, max_tokens=1024, system=SYSTEM_PROMPT,
                tools=self.registry.schemas_for_anthropic(include_write=True), messages=messages)
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b.text for b in response.content if b.type == "text"]
            if not tool_use_blocks:
                return {"answer": "\n".join(text_blocks), "evidence": {"tool_calls": tool_calls_made}, "mode": self.mode}
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in tool_use_blocks:
                try:
                    result = self.registry.call(block.name, **block.input)
                    tool_calls_made.append({"tool": block.name, "input": block.input, "ok": True})
                except Exception as e:
                    result = {"error": str(e)}
                    tool_calls_made.append({"tool": block.name, "input": block.input, "ok": False, "error": str(e)})
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, default=str)})
            messages.append({"role": "user", "content": tool_results})
        return {"answer": "Reached max tool-call iterations without a final answer.", "evidence": {"tool_calls": tool_calls_made}, "mode": self.mode}


def get_agent(tools):
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeAgentProvider(tools)
    return DeterministicDemoAgent(tools)
