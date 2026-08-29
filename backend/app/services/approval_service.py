"""Thin wrapper over finpilot.core.approvals -- all logic lives there and is tested there."""
from app.core import _bootstrap  # noqa: F401
from finpilot.core import approvals


def list_approvals(conn, merchant_id: str, status: str | None = None) -> list[dict]:
    clause = "AND status=? " if status else ""
    params = (merchant_id, status) if status else (merchant_id,)
    rows = conn.execute(
        f"SELECT * FROM approval_request WHERE merchant_id=? {clause}ORDER BY created_at DESC, rowid DESC",
        params
    ).fetchall()
    return [dict(r) for r in rows]


def get_approval(conn, merchant_id: str, request_id: str) -> dict | None:
    try:
        return approvals._get(conn, merchant_id, request_id)
    except approvals.ApprovalError:
        return None


def propose(conn, merchant_id: str, action_type: str, proposal: dict) -> dict:
    return approvals.propose_action(conn, merchant_id, action_type, proposal)


def decide(conn, merchant_id: str, request_id: str, approved: bool, decided_by: str) -> dict:
    return approvals.decide(conn, merchant_id, request_id, approved, decided_by)


def execute(conn, merchant_id: str, request_id: str) -> dict:
    return approvals.execute(conn, merchant_id, request_id)


def retry(conn, merchant_id: str, request_id: str, retry_by: str, reason: str) -> dict:
    return approvals.retry(conn, merchant_id, request_id, retry_by, reason)
