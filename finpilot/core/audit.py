import json,uuid
from datetime import datetime,timezone
def _uid(): return f'audit_{uuid.uuid4().hex[:10]}'
def record(conn,merchant_id:str,actor:str,operation:str,inputs:dict,evidence:dict,decision:str=None,approval_state:str=None,result:dict=None,error:str=None,commit:bool=True)->dict:
    row_id=_uid(); now=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    conn.execute('INSERT INTO audit_event (id, merchant_id, actor, operation, inputs_json, evidence_json, decision, approval_state, result_json, error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',(row_id,merchant_id,actor,operation,json.dumps(inputs),json.dumps(evidence),decision,approval_state,json.dumps(result) if result is not None else None,error,now))
    if commit: conn.commit()
    return {'id':row_id,'actor':actor,'operation':operation,'created_at':now}
def history(conn,merchant_id:str,limit:int=100)->list[dict]:
    return [dict(r) for r in conn.execute('SELECT * FROM audit_event WHERE merchant_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?',(merchant_id,limit)).fetchall()]
