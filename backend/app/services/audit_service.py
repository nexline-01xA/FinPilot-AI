"""Thin wrapper over finpilot.core.audit with query filters for the audit UI."""
import json


def list_audit_events(conn, merchant_id: str, operation: str | None = None,
                       actor: str | None = None, limit: int = 200) -> list[dict]:
    clauses, params = [], [merchant_id]
    if operation:
        clauses.append("operation=?")
        params.append(operation)
    if actor:
        clauses.append("actor=?")
        params.append(actor)
    extra = (" AND " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM audit_event WHERE merchant_id=?{extra} "
        f"ORDER BY created_at DESC, rowid DESC LIMIT ?", params
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for f in ("inputs_json", "evidence_json", "result_json"):
            if d.get(f):
                d[f.replace("_json", "")] = json.loads(d.pop(f))
            else:
                d[f.replace("_json", "")] = None
                d.pop(f, None)
        out.append(d)
    return out
