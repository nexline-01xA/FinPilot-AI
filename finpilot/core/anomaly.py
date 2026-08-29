"""
Financial anomaly engine. Two independent detector families, never blurred:

  RULE_BASED_ALERT   - fixed, explainable thresholds (e.g. refund rate > 15%)
  STATISTICAL_ANOMALY - z-score outliers vs the merchant's own historical distribution

Agent interpretation of these findings happens elsewhere (agent.py), never here.

IDENTITY: most categories key off an absolute, stable natural key. Refund spike
identity is overlap-matched against an existing active incident so a rolling
analysis window cannot fork the same real-world episode into new logical cases.

TRANSACTIONAL INTEGRITY & RUN HISTORY: derivation, resolution and finalization
share one transaction. Any exception rolls back all partial derived state; the
run is then marked failed in a clean transaction. Every case touched by a run
gets an immutable observation row.
"""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
import numpy as np
from . import audit

REFUND_RATE_ALERT_THRESHOLD = 0.15
Z_SCORE_THRESHOLD = 2.5
RECURRING_EXPENSE_JUMP_THRESHOLD = 0.30


def _uid(): return f"anom_{uuid.uuid4().hex[:10]}"
def _run_uid(): return f"anomrun_{uuid.uuid4().hex[:10]}"
def _obs_uid(): return f"anomobs_{uuid.uuid4().hex[:10]}"
def _now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _case_key(merchant_id: str, category: str, natural_key: str) -> str:
    return "anomcase_" + hashlib.sha256(f"{merchant_id}|{category}|{natural_key}".encode()).hexdigest()[:20]


def _write_observation(conn, run_id, case_id, merchant_id, case_key, kind, category, severity,
                       evidence: dict, active: int, observed_at: str):
    conn.execute("INSERT INTO anomaly_observation (id, run_id, case_id, merchant_id, case_key, kind, category, severity, evidence_json, active, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (_obs_uid(), run_id, case_id, merchant_id, case_key, kind, category, severity,
                  json.dumps(evidence), active, observed_at))


def _upsert(conn, merchant_id, run_id, kind, category, natural_key, severity, evidence,
            detected_at, seen_keys_this_run: set) -> dict:
    key = _case_key(merchant_id, category, natural_key)
    seen_keys_this_run.add(key)
    now = _now()
    conn.execute("""
        INSERT INTO financial_anomaly
            (id, merchant_id, case_key, kind, category, severity, evidence_json,
             active, last_run_id, detected_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        ON CONFLICT(merchant_id, case_key) DO UPDATE SET
            severity = excluded.severity, evidence_json = excluded.evidence_json,
            active = 1, last_run_id = excluded.last_run_id, updated_at = excluded.updated_at
        """, (_uid(), merchant_id, key, kind, category, severity, json.dumps(evidence), run_id, detected_at, now))
    saved = conn.execute("SELECT * FROM financial_anomaly WHERE merchant_id=? AND case_key=?", (merchant_id, key)).fetchone()
    _write_observation(conn, run_id, saved["id"], merchant_id, key, kind, category, severity, evidence, 1, now)
    return {"id": saved["id"], "case_key": key, "kind": kind, "category": category,
            "severity": severity, "evidence": evidence, "detected_at": saved["detected_at"]}


def _dates_overlap(s1, e1, s2, e2) -> bool:
    return s1 <= e2 and s2 <= e1


def _upsert_refund_spike(conn, merchant_id, run_id, abs_start, abs_end, severity, evidence,
                          seen_keys_this_run: set) -> dict:
    candidates = conn.execute("SELECT * FROM financial_anomaly WHERE merchant_id=? AND category='refund_rate_spike' AND active=1", (merchant_id,)).fetchall()
    existing = None
    for c in candidates:
        span = json.loads(c["evidence_json"]).get("date_span")
        if span and _dates_overlap(span[0], span[1], abs_start, abs_end):
            existing = c; break
    now = _now()
    if existing:
        old_span = json.loads(existing["evidence_json"]).get("date_span", [abs_start, abs_end])
        evidence["date_span"] = [min(old_span[0], abs_start), max(old_span[1], abs_end)]
        key = existing["case_key"]
        seen_keys_this_run.add(key)
        conn.execute("UPDATE financial_anomaly SET severity=?, evidence_json=?, active=1, last_run_id=?, updated_at=? WHERE id=?",
                     (severity, json.dumps(evidence), run_id, now, existing["id"]))
        _write_observation(conn, run_id, existing["id"], merchant_id, key, "RULE_BASED_ALERT", "refund_rate_spike", severity, evidence, 1, now)
        return {"id": existing["id"], "case_key": key, "kind": "RULE_BASED_ALERT", "category": "refund_rate_spike", "severity": severity, "evidence": evidence, "detected_at": existing["detected_at"]}
    return _upsert(conn, merchant_id, run_id, "RULE_BASED_ALERT", "refund_rate_spike",
                   f"{abs_start}:{abs_end}", severity, evidence, abs_start + "T00:00:00Z", seen_keys_this_run)


def detect(conn, merchant_id: str, start_date: datetime, days: int) -> list[dict]:
    run_id = _run_uid()
    conn.execute("INSERT INTO anomaly_detection_run (id, merchant_id, started_at, status, days_scanned) VALUES (?, ?, ?, 'running', ?)", (run_id, merchant_id, _now(), days))
    conn.commit()
    try:
        findings, before_active, seen = _run_detectors(conn, merchant_id, run_id, start_date, days)
        resolved = before_active - seen
        if resolved: _resolve_cases(conn, merchant_id, run_id, resolved)
        conn.execute("UPDATE anomaly_detection_run SET status='completed', completed_at=?, active_before=?, active_after=?, new_cases=?, resolved_cases=? WHERE id=?",
                     (_now(), len(before_active), len(seen), len(seen - before_active), len(resolved), run_id))
        audit.record(conn, merchant_id, actor="system", operation="detect_anomalies",
                     inputs={"merchant_id": merchant_id, "days": days}, evidence={"run_id": run_id, "days_scanned": days},
                     result={"active_before_run": len(before_active), "active_after_run": len(seen), "new_cases": len(seen-before_active), "resolved_cases": len(resolved),
                             "by_kind": {k: sum(1 for f in findings if f["kind"] == k) for k in set(f["kind"] for f in findings)}}, commit=False)
        conn.commit(); return findings
    except Exception as e:
        conn.rollback(); error_str = str(e)
        conn.execute("UPDATE anomaly_detection_run SET status='failed', completed_at=?, error=? WHERE id=?", (_now(), error_str, run_id)); conn.commit()
        try:
            audit.record(conn, merchant_id, actor="system", operation="detect_anomalies_failed", inputs={"merchant_id": merchant_id, "days": days}, evidence={"run_id": run_id}, error=error_str)
        except Exception: pass
        raise


def _resolve_cases(conn, merchant_id, run_id, resolved_keys):
    now = _now()
    for key in resolved_keys:
        case = conn.execute("SELECT * FROM financial_anomaly WHERE merchant_id=? AND case_key=?", (merchant_id, key)).fetchone()
        conn.execute("UPDATE financial_anomaly SET active=0, updated_at=?, last_run_id=? WHERE id=?", (now, run_id, case["id"]))
        _write_observation(conn, run_id, case["id"], merchant_id, key, case["kind"], case["category"], case["severity"], json.loads(case["evidence_json"]), 0, now)


def _run_detectors(conn, merchant_id, run_id, start_date, days):
    before_active = {r["case_key"] for r in conn.execute("SELECT case_key FROM financial_anomaly WHERE merchant_id = ? AND active = 1", (merchant_id,)).fetchall()}
    seen, findings = set(), []
    payments = _count_by_day(conn, "payment", "created_at", merchant_id, start_date, days)
    refunds = _count_by_day(conn, "refund", "created_at", merchant_id, start_date, days)
    breaching=[]
    for w_start in range(0, max(days-5+1,0)):
        window=range(w_start,w_start+5); pay_n=sum(payments.get(d,0) for d in window); ref_n=sum(refunds.get(d,0) for d in window); rate=ref_n/pay_n if pay_n else 0.0
        if rate>REFUND_RATE_ALERT_THRESHOLD: breaching.append((w_start,rate,pay_n,ref_n))
    if breaching:
        prev=breaching[0][0]; group=[breaching[0]]
        for item in breaching[1:]:
            if item[0]==prev+1: group.append(item); prev=item[0]
            else: findings.append(_merge_refund_spike(conn,merchant_id,run_id,group,start_date,seen)); group=[item]; prev=item[0]
        findings.append(_merge_refund_spike(conn,merchant_id,run_id,group,start_date,seen))
    for m in conn.execute("SELECT id, amount_paise, expected_amount_paise, expected_date FROM settlement WHERE merchant_id = ? AND ABS(amount_paise - expected_amount_paise) > 100", (merchant_id,)).fetchall():
        diff=m["amount_paise"]-m["expected_amount_paise"]
        findings.append(_upsert(conn,merchant_id,run_id,"RULE_BASED_ALERT","settlement_amount_mismatch",m["id"],"high",
            {"settlement_id":m["id"],"expected_amount_paise":m["expected_amount_paise"],"actual_amount_paise":m["amount_paise"],"difference_paise":diff,"reason":f"Settlement {m['id']} differs from expected aggregation by ₹{abs(diff)/100:,.2f}."},m["expected_date"],seen))
    for s in conn.execute("SELECT id, expected_date, expected_amount_paise FROM settlement WHERE merchant_id = ? AND status = 'delayed'", (merchant_id,)).fetchall():
        findings.append(_upsert(conn,merchant_id,run_id,"RULE_BASED_ALERT","settlement_delayed",s["id"],"high",
            {"settlement_id":s["id"],"expected_date":s["expected_date"],"expected_amount_paise":s["expected_amount_paise"],"reason":f"Settlement {s['id']} expected {s['expected_date']} has not settled."},s["expected_date"],seen))
    daily=_sum_by_day(conn,"payment","amount_paise","created_at",merchant_id,start_date,days); series=np.array([daily.get(d,0) for d in range(days)],dtype=float)
    if series.std()>0:
        z=(series-series.mean())/series.std()
        for d,zscore in enumerate(z):
            if abs(zscore)>=Z_SCORE_THRESHOLD:
                abs_date=(start_date+timedelta(days=d)).strftime("%Y-%m-%d")
                findings.append(_upsert(conn,merchant_id,run_id,"STATISTICAL_ANOMALY","payment_volume_outlier",abs_date,"high" if abs(zscore)>=3.5 else "medium",
                    {"date":abs_date,"amount_paise":round(series[d]),"z_score":round(float(zscore),2),"mean_paise":round(float(series.mean())),"std_paise":round(float(series.std())),"reason":f"Daily gross payment volume z-score {zscore:.2f} exceeds threshold {Z_SCORE_THRESHOLD}."},abs_date+"T00:00:00Z",seen))
    cats=conn.execute("SELECT DISTINCT category FROM expense WHERE merchant_id = ? AND recurring = 1",(merchant_id,)).fetchall()
    for c in cats:
        rows=conn.execute("SELECT id, amount_paise, due_date FROM expense WHERE merchant_id = ? AND category = ? AND recurring = 1 ORDER BY due_date",(merchant_id,c["category"])).fetchall()
        for prev,cur in zip(rows,rows[1:]):
            if prev["amount_paise"]==0: continue
            pct=(cur["amount_paise"]-prev["amount_paise"])/prev["amount_paise"]
            if abs(pct)>=RECURRING_EXPENSE_JUMP_THRESHOLD:
                findings.append(_upsert(conn,merchant_id,run_id,"RULE_BASED_ALERT","recurring_expense_jump",cur["id"],"high" if abs(pct)>=0.5 else "medium",
                    {"expense_id":cur["id"],"category":c["category"],"previous_amount_paise":prev["amount_paise"],"new_amount_paise":cur["amount_paise"],"pct_change":round(pct,3),"due_date":cur["due_date"],"reason":f"{c['category']} expense changed {pct:+.1%} from ₹{prev['amount_paise']/100:,.2f} to ₹{cur['amount_paise']/100:,.2f} between consecutive occurrences."},cur["due_date"],seen))
    return findings,before_active,seen


def _merge_refund_spike(conn,merchant_id,run_id,group,start_date,seen):
    starts=[g[0] for g in group]; max_rate=max(g[1] for g in group); total_pay=sum(g[2] for g in group); total_ref=sum(g[3] for g in group)
    abs_start=(start_date+timedelta(days=min(starts))).strftime("%Y-%m-%d"); abs_end=(start_date+timedelta(days=max(starts)+4)).strftime("%Y-%m-%d")
    severity="high" if max_rate>0.30 else "medium"
    evidence={"date_span":[abs_start,abs_end],"peak_refund_rate":round(max_rate,3),"threshold":REFUND_RATE_ALERT_THRESHOLD,"payments_in_span":total_pay,"refunds_in_span":total_ref,
              "reason":f"Refund rate peaks at {max_rate:.1%} (threshold {REFUND_RATE_ALERT_THRESHOLD:.0%}) across {abs_start} to {abs_end} as visible in this run's analysis window."}
    return _upsert_refund_spike(conn,merchant_id,run_id,abs_start,abs_end,severity,evidence,seen)


def _count_by_day(conn,table,date_col,merchant_id,start_date,days):
    out={}
    for r in conn.execute(f"SELECT {date_col} as d FROM {table} WHERE merchant_id = ?",(merchant_id,)).fetchall():
        idx=(datetime.fromisoformat(r["d"].replace("Z",""))-start_date).days
        if 0<=idx<days: out[idx]=out.get(idx,0)+1
    return out


def _sum_by_day(conn,table,amount_col,date_col,merchant_id,start_date,days):
    out={}
    for r in conn.execute(f"SELECT {date_col} as d, {amount_col} as a FROM {table} WHERE merchant_id = ?",(merchant_id,)).fetchall():
        idx=(datetime.fromisoformat(r["d"].replace("Z",""))-start_date).days
        if 0<=idx<days: out[idx]=out.get(idx,0)+r["a"]
    return out
