import json
import uuid
from datetime import datetime, timezone
from . import audit
TASK_ACTION_TYPES={'create_finance_task':'finance_task','schedule_review':'schedule_review','mark_discrepancy_for_investigation':'investigation','prepare_payout_proposal':'payout_proposal','prepare_refund_recommendation':'refund_recommendation'}
VALID_ACTION_TYPES=set(TASK_ACTION_TYPES)|{'create_alert','generate_reconciliation_report'}
class ApprovalError(Exception): pass
def _uid(prefix='appr'): return f'{prefix}_{uuid.uuid4().hex[:10]}'
def _now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def propose_action(conn,merchant_id:str,action_type:str,proposal:dict)->dict:
    if action_type not in VALID_ACTION_TYPES: raise ApprovalError(f'Unsupported action type: {action_type}')
    row_id=_uid()
    try:
        conn.execute("INSERT INTO approval_request (id, merchant_id, action_type, proposal_json, status, created_at) VALUES (?, ?, ?, ?, 'AWAITING_APPROVAL', ?)",(row_id,merchant_id,action_type,json.dumps(proposal),_now()))
        audit.record(conn,merchant_id,actor='agent',operation='propose_action',inputs={'action_type':action_type,'proposal':proposal},evidence=proposal,decision=None,approval_state='AWAITING_APPROVAL',commit=False)
        conn.commit()
    except Exception:
        conn.rollback(); raise
    return _get(conn,merchant_id,row_id)
def decide(conn,merchant_id:str,request_id:str,approved:bool,decided_by:str)->dict:
    req=_get(conn,merchant_id,request_id)
    if req['status']!='AWAITING_APPROVAL': raise ApprovalError(f"Request {request_id} is in state {req['status']}; only AWAITING_APPROVAL requests can be decided (idempotency guard).")
    new_status='APPROVED' if approved else 'REJECTED'
    try:
        cur=conn.execute("UPDATE approval_request SET status = ?, decided_at = ?, decided_by = ? WHERE id = ? AND merchant_id = ? AND status = 'AWAITING_APPROVAL'",(new_status,_now(),decided_by,request_id,merchant_id))
        if cur.rowcount==0: raise ApprovalError(f'Request {request_id} was not AWAITING_APPROVAL at decision time (concurrent decision?).')
        audit.record(conn,merchant_id,actor=decided_by,operation='decide',inputs={'request_id':request_id,'approved':approved},evidence={'action_type':req['action_type']},decision=new_status,approval_state=new_status,commit=False)
        conn.commit()
    except Exception:
        conn.rollback(); raise
    return _get(conn,merchant_id,request_id)
def retry(conn,merchant_id:str,request_id:str,retry_by:str,reason:str)->dict:
    req=_get(conn,merchant_id,request_id)
    if req['status']!='FAILED': raise ApprovalError(f"Request {request_id} is in state {req['status']}; only FAILED requests can be retried.")
    previous_error=None
    if req['result_json']:
        try: previous_error=json.loads(req['result_json']).get('error')
        except (json.JSONDecodeError,AttributeError): pass
    try:
        cur=conn.execute("UPDATE approval_request SET status = 'APPROVED', attempt_number = attempt_number + 1 WHERE id = ? AND merchant_id = ? AND status = 'FAILED'",(request_id,merchant_id))
        if cur.rowcount==0: raise ApprovalError(f'Request {request_id} was not FAILED at retry time (concurrent change, or already retried?).')
        audit.record(conn,merchant_id,actor=retry_by,operation='retry_authorized',inputs={'request_id':request_id,'reason':reason},evidence={'previous_error':previous_error,'action_type':req['action_type'],'new_attempt_number':req['attempt_number']+1},decision='APPROVED',approval_state='APPROVED',commit=False)
        conn.commit()
    except Exception:
        conn.rollback(); raise
    return _get(conn,merchant_id,request_id)
def execute(conn,merchant_id:str,request_id:str)->dict:
    req=_get(conn,merchant_id,request_id)
    if req['status']!='APPROVED': raise ApprovalError(f"Request {request_id} is in state {req['status']}; only APPROVED requests can execute (prevents unapproved or duplicate execution).")
    try:
        cur=conn.execute("UPDATE approval_request SET status = 'EXECUTING' WHERE id = ? AND merchant_id = ? AND status = 'APPROVED'",(request_id,merchant_id))
        if cur.rowcount==0: raise ApprovalError(f'Request {request_id} was not APPROVED at execution time (concurrent execution?).')
        audit.record(conn,merchant_id,actor='system',operation='execute_start',inputs={'request_id':request_id,'attempt_number':req['attempt_number']},evidence={'action_type':req['action_type']},approval_state='EXECUTING',commit=False)
        conn.commit()
    except Exception:
        conn.rollback(); raise
    try:
        effect_ref=_perform_domain_effect(conn,req)
        verified,verification_evidence=_verify_effect(conn,effect_ref)
        final_status='SUCCEEDED' if verified else 'VERIFICATION_FAILED'
        result={'executed_action':req['action_type'],'effect':effect_ref,'verified':verified,'verification_evidence':verification_evidence}
        conn.execute('UPDATE approval_request SET status = ?, result_json = ? WHERE id = ? AND merchant_id = ?',(final_status,json.dumps(result),request_id,merchant_id))
        audit.record(conn,merchant_id,actor='system',operation='execute_verify',inputs={'request_id':request_id},evidence=verification_evidence,decision=final_status,approval_state=final_status,result=result,error=None if verified else 'Persisted row could not be read back after write.',commit=False)
        conn.commit()
    except Exception as e:
        conn.rollback(); error_result={'executed_action':req['action_type'],'error':str(e),'error_type':type(e).__name__}
        try:
            conn.execute("UPDATE approval_request SET status = 'FAILED', result_json = ? WHERE id = ? AND merchant_id = ?",(json.dumps(error_result),request_id,merchant_id))
            audit.record(conn,merchant_id,actor='system',operation='execute_failed',inputs={'request_id':request_id},evidence={'action_type':req['action_type']},decision='FAILED',approval_state='FAILED',result=error_result,error=str(e),commit=False)
            conn.commit()
        except Exception:
            conn.rollback(); raise
        raise
    return _get(conn,merchant_id,request_id)
def _perform_domain_effect(conn,req:dict)->dict:
    action_type=req['action_type']; proposal=json.loads(req['proposal_json']); mid=req['merchant_id']
    if action_type=='create_alert':
        row_id=_uid('alert'); conn.execute("INSERT INTO alert (id, merchant_id, approval_request_id, severity, message, evidence_json, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",(row_id,mid,req['id'],proposal.get('severity','medium'),proposal.get('message') or proposal.get('note','Alert'),json.dumps(proposal),_now())); return {'table':'alert','id':row_id,'merchant_id':mid}
    if action_type=='generate_reconciliation_report':
        from . import reconciliation
        summary=reconciliation.reconciliation_health(conn,mid); row_id=_uid('report'); conn.execute('INSERT INTO reconciliation_report (id, merchant_id, approval_request_id, summary_json, generated_at) VALUES (?, ?, ?, ?, ?)',(row_id,mid,req['id'],json.dumps(summary),_now())); return {'table':'reconciliation_report','id':row_id,'merchant_id':mid}
    if action_type in TASK_ACTION_TYPES:
        task_type=TASK_ACTION_TYPES[action_type]; row_id=_uid('task'); title=proposal.get('title') or proposal.get('reason') or action_type.replace('_',' '); conn.execute("INSERT INTO finance_task (id, merchant_id, approval_request_id, task_type, title, detail_json, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",(row_id,mid,req['id'],task_type,title,json.dumps(proposal),_now())); return {'table':'finance_task','id':row_id,'merchant_id':mid}
    raise ApprovalError(f'No domain effect implemented for action type: {action_type}')
def _verify_effect(conn,effect_ref:dict):
    row=conn.execute(f"SELECT * FROM {effect_ref['table']} WHERE id = ? AND merchant_id = ?",(effect_ref['id'],effect_ref['merchant_id'])).fetchone()
    if row is None: return False,{'table':effect_ref['table'],'id':effect_ref['id'],'found':False}
    return True,{'table':effect_ref['table'],'id':effect_ref['id'],'found':True,'row_snapshot':dict(row)}
def _get(conn,merchant_id:str,request_id:str)->dict:
    r=conn.execute('SELECT * FROM approval_request WHERE id = ? AND merchant_id = ?',(request_id,merchant_id)).fetchone()
    if not r: raise ApprovalError(f'No such approval request for this merchant: {request_id}')
    return dict(r)
