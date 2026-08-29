import hashlib,json,uuid
from datetime import datetime,timezone
from . import audit
AMOUNT_TOLERANCE_PAISE=100
def _uid(): return f'rec_{uuid.uuid4().hex[:10]}'
def _run_uid(): return f'recrun_{uuid.uuid4().hex[:10]}'
def _obs_uid(): return f'recobs_{uuid.uuid4().hex[:10]}'
def _now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def _case_key(merchant_id,role,settlement_id,ledger_entry_id): return 'case_'+hashlib.sha256(f"{merchant_id}|{role}|{settlement_id or ''}|{ledger_entry_id or ''}".encode()).hexdigest()[:20]
def reconcile(conn,merchant_id):
    run_id=_run_uid(); conn.execute("INSERT INTO reconciliation_run (id, merchant_id, started_at, status) VALUES (?, ?, ?, 'running')",(run_id,merchant_id,_now())); conn.commit()
    try:
        results,before,seen,n_set,n_led=_do_reconcile(conn,merchant_id,run_id); resolved=before-seen
        if resolved: _resolve_cases(conn,merchant_id,run_id,resolved)
        conn.execute("UPDATE reconciliation_run SET status='completed', completed_at=?, settlements_considered=?, ledger_entries_considered=?, active_cases_before=?, active_cases_after=?, new_cases=?, resolved_cases=? WHERE id=?",(_now(),n_set,n_led,len(before),len(seen),len(seen-before),len(resolved),run_id))
        audit.record(conn,merchant_id,actor='system',operation='reconcile',inputs={'merchant_id':merchant_id},evidence={'run_id':run_id,'settlements_considered':n_set,'ledger_entries_considered':n_led},result={'active_cases_before_run':len(before),'active_cases_after_run':len(seen),'new_cases':len(seen-before),'resolved_cases':len(resolved),'by_status':{s:sum(1 for r in results if r['status']==s) for s in set(r['status'] for r in results)}},commit=False); conn.commit(); return results
    except Exception as e:
        conn.rollback(); err=str(e); conn.execute("UPDATE reconciliation_run SET status='failed', completed_at=?, error=? WHERE id=?",(_now(),err,run_id)); conn.commit()
        try: audit.record(conn,merchant_id,actor='system',operation='reconcile_failed',inputs={'merchant_id':merchant_id},evidence={'run_id':run_id},error=err)
        except Exception: pass
        raise
def _do_reconcile(conn,merchant_id,run_id):
    before={r['case_key'] for r in conn.execute('SELECT case_key FROM reconciliation_match WHERE merchant_id = ? AND active = 1',(merchant_id,)).fetchall()}; settlements=conn.execute('SELECT * FROM settlement WHERE merchant_id = ?',(merchant_id,)).fetchall(); ledger=conn.execute('SELECT * FROM ledger_entry WHERE merchant_id = ?',(merchant_id,)).fetchall(); refs={}
    for le in ledger:
        if le['reference']: refs.setdefault(le['reference'],[]).append(le)
    results=[]; matched=set(); seen=set()
    for s in settlements:
        ev={'settlement_id':s['id'],'expected_amount_paise':s['expected_amount_paise'],'actual_amount_paise':s['amount_paise']}
        if s['status']=='delayed' or s['settled_date'] is None:
            results.append(_upsert(conn,merchant_id,run_id,'settlement_match',s['id'],None,'MISSING_SETTLEMENT',.95,{**ev,'reason':'Settlement not yet settled as of latest data; no bank credit expected yet.'},seen)); continue
        candidates=[le for le in refs.get(s['id'],[]) if le['amount_paise']>0]
        if not candidates:
            results.append(_upsert(conn,merchant_id,run_id,'settlement_match',s['id'],None,'MISSING_SETTLEMENT',.9,{**ev,'reason':'No bank ledger credit references this settlement.'},seen)); continue
        best=sorted(candidates,key=lambda r:abs(r['amount_paise']-s['amount_paise']))[0]; diff=abs(best['amount_paise']-s['amount_paise']); expected_diff=abs(s['amount_paise']-s['expected_amount_paise'])
        if diff<=AMOUNT_TOLERANCE_PAISE and expected_diff<=AMOUNT_TOLERANCE_PAISE: confidence,status,reason=1.0,'MATCHED','Ledger credit matches settlement amount, which matches expected payment aggregation.'
        elif diff<=AMOUNT_TOLERANCE_PAISE and expected_diff>AMOUNT_TOLERANCE_PAISE: confidence,status,reason=.4,'AMOUNT_MISMATCH',f"Settlement {s['id']} amount (₹{s['amount_paise']/100:,.2f}) does not match expected payment aggregation (₹{s['expected_amount_paise']/100:,.2f}); shortfall of ₹{expected_diff/100:,.2f}. Bank credit itself matches the (incorrect) settlement amount."
        elif diff<=AMOUNT_TOLERANCE_PAISE+500: confidence,status,reason=.6,'PARTIAL','Ledger credit amount is close to but not exactly equal to settlement amount.'
        else: confidence,status,reason=.3,'AMOUNT_MISMATCH',f"Ledger credit (₹{best['amount_paise']/100:,.2f}) differs from settlement amount (₹{s['amount_paise']/100:,.2f}) by ₹{diff/100:,.2f}, exceeding tolerance."
        results.append(_upsert(conn,merchant_id,run_id,'settlement_match',s['id'],best['id'],status,confidence,{**ev,'ledger_entry_id':best['id'],'ledger_amount_paise':best['amount_paise'],'difference_paise':diff,'reason':reason},seen)); matched.add(best['id'])
        debits=[le for le in refs.get(s['id'],[]) if le['amount_paise']<0]; amounts={}
        for le in debits: amounts.setdefault(le['amount_paise'],[]).append(le)
        for amt,entries in amounts.items():
            if len(entries)>1:
                results.append(_upsert(conn,merchant_id,run_id,'duplicate_debit',s['id'],entries[0]['id'],'DUPLICATE',.92,{'settlement_id':s['id'],'duplicate_ledger_entry_ids':[e['id'] for e in entries],'amount_paise':amt,'count':len(entries),'reason':f"{len(entries)} identical debit ledger entries of ₹{abs(amt)/100:,.2f} reference the same settlement; a bank fee debit should post once."},seen)); matched.update(e['id'] for e in entries)
    for le in ledger:
        if le['id'] in matched or le['reference'] is not None: continue
        status='UNKNOWN_CREDIT' if le['amount_paise']>0 else 'UNKNOWN_DEBIT'; results.append(_upsert(conn,merchant_id,run_id,'unmatched_ledger',None,le['id'],status,.85,{'ledger_entry_id':le['id'],'amount_paise':le['amount_paise'],'value_date':le['value_date'],'description':le['description'],'reason':'Ledger entry has no settlement reference and does not correspond to any known settlement.'},seen))
    return results,before,seen,len(settlements),len(ledger)
def _upsert(conn,merchant_id,run_id,role,settlement_id,ledger_entry_id,status,confidence,evidence,seen):
    key=_case_key(merchant_id,role,settlement_id,ledger_entry_id); seen.add(key); now=_now(); conn.execute("INSERT INTO reconciliation_match (id, merchant_id, case_key, settlement_id, ledger_entry_id, status, confidence, evidence_json, active, last_run_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?) ON CONFLICT(merchant_id, case_key) DO UPDATE SET status=excluded.status, confidence=excluded.confidence, evidence_json=excluded.evidence_json, active=1, last_run_id=excluded.last_run_id, updated_at=excluded.updated_at",(_uid(),merchant_id,key,settlement_id,ledger_entry_id,status,confidence,json.dumps(evidence),run_id,now,now)); saved=conn.execute('SELECT * FROM reconciliation_match WHERE merchant_id=? AND case_key=?',(merchant_id,key)).fetchone(); _write_observation(conn,run_id,saved['id'],merchant_id,key,status,confidence,evidence,1,now); return {'id':saved['id'],'case_key':key,'merchant_id':merchant_id,'settlement_id':settlement_id,'ledger_entry_id':ledger_entry_id,'status':status,'confidence':confidence,'evidence':evidence}
def _resolve_cases(conn,merchant_id,run_id,resolved):
    now=_now()
    for key in resolved:
        case=conn.execute('SELECT * FROM reconciliation_match WHERE merchant_id=? AND case_key=?',(merchant_id,key)).fetchone(); conn.execute('UPDATE reconciliation_match SET active=0, updated_at=?, last_run_id=? WHERE id=?',(now,run_id,case['id'])); _write_observation(conn,run_id,case['id'],merchant_id,key,case['status'],case['confidence'],json.loads(case['evidence_json']),0,now)
def _write_observation(conn,run_id,case_id,merchant_id,case_key,status,confidence,evidence,active,observed_at): conn.execute('INSERT INTO reconciliation_observation (id, run_id, case_id, merchant_id, case_key, status, confidence, evidence_json, active, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',(_obs_uid(),run_id,case_id,merchant_id,case_key,status,confidence,json.dumps(evidence),active,observed_at))
def reconciliation_health(conn,merchant_id):
    rows=conn.execute('SELECT status, COUNT(*) as n FROM reconciliation_match WHERE merchant_id = ? AND active = 1 GROUP BY status',(merchant_id,)).fetchall(); counts={r['status']:r['n'] for r in rows}; total=sum(counts.values()); matched=counts.get('MATCHED',0); return {'total_matches':total,'matched':matched,'exceptions':total-matched,'health_pct':round(100*matched/total,1) if total else None,'by_status':counts}
