from . import audit
READ_TOOL_SCHEMAS={'get_finance_summary':{'description':'Current cash, settled/outstanding totals, refund exposure, reconciliation health.','input_schema':{'type':'object','properties':{}}},'get_cash_forecast':{'description':'Forecast cash position with benchmark and obligations.','input_schema':{'type':'object','properties':{'horizon_days':{'type':'integer'}}}},'get_reconciliation_report':{'description':'Reconciliation health plus exceptions.','input_schema':{'type':'object','properties':{}}},'get_unmatched_transactions':{'description':'Unmatched ledger entries.','input_schema':{'type':'object','properties':{}}},'get_settlement':{'description':'Look up settlement.','input_schema':{'type':'object','properties':{'settlement_id':{'type':'string'}},'required':['settlement_id']}},'get_transaction':{'description':'Look up payment.','input_schema':{'type':'object','properties':{'payment_id':{'type':'string'}},'required':['payment_id']}},'get_anomalies':{'description':'Detected anomalies.','input_schema':{'type':'object','properties':{}}},'get_upcoming_obligations':{'description':'Scheduled expenses due soon.','input_schema':{'type':'object','properties':{'days':{'type':'integer'}}}},'explain_cash_change':{'description':'Attribute a day cash change.','input_schema':{'type':'object','properties':{'day_index':{'type':'integer'}},'required':['day_index']}},'simulate_scenario':{'description':'Deterministic what-if forecast.','input_schema':{'type':'object','properties':{'scenario':{'type':'object'}},'required':['scenario']}},'get_audit_history':{'description':'Recent audit events.','input_schema':{'type':'object','properties':{'limit':{'type':'integer'}}}}}
WRITE_TOOL_SCHEMAS={'prepare_action':{'description':'Propose an action for human approval; never executes it.','input_schema':{'type':'object','properties':{'action_type':{'type':'string'},'proposal':{'type':'object'}},'required':['action_type','proposal']}},'request_approval':{'description':'Read approval status.','input_schema':{'type':'object','properties':{'request_id':{'type':'string'}},'required':['request_id']}},'retry_action':{'description':'Explicitly re-authorize a FAILED action.','input_schema':{'type':'object','properties':{'request_id':{'type':'string'},'retry_by':{'type':'string'},'reason':{'type':'string'}},'required':['request_id','retry_by','reason']}}}
class ToolPermissionError(Exception): pass
class ToolRegistry:
    def __init__(self,tools,actor='agent'): self.tools=tools; self.actor=actor
    def schemas_for_anthropic(self,include_write=True):
        names=dict(READ_TOOL_SCHEMAS)
        if include_write: names.update(WRITE_TOOL_SCHEMAS)
        return [{'name':n,'description':s['description'],'input_schema':s['input_schema']} for n,s in names.items()]
    def call(self,name,**kwargs):
        is_read=name in READ_TOOL_SCHEMAS; is_write=name in WRITE_TOOL_SCHEMAS
        if not(is_read or is_write): raise ToolPermissionError(f"Tool '{name}' is not in the allowlist.")
        method=getattr(self.tools,name,None)
        if method is None: raise ToolPermissionError(f"Tool '{name}' is allowlisted but not implemented.")
        result=method(**kwargs)
        if is_write: audit.record(self.tools.conn,self.tools.merchant_id,actor=self.actor,operation=f'tool_call:{name}',inputs=kwargs,evidence={'tool':name,'permission':'WRITE'},result=result if isinstance(result,dict) else {'value':result})
        return result
