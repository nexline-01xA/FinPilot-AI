import os,sys
from datetime import datetime
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finpilot.core import db,generator,reconciliation,forecasting,anomaly
from finpilot.core.agent_tools import FinanceTools
from finpilot.core.agent import DeterministicDemoAgent
DB_PATH='/tmp/finpilot_eval.db'
def main():
    conn=db.init_db(DB_PATH,fresh=True); gt=generator.generate(conn,seed=42); mid=gt['merchant_id']; start=datetime.fromisoformat(gt['start_date'].replace('Z','+00:00')).replace(tzinfo=None); days=gt['days']; print('='*70); print('FinPilot AI — Core Engine Evaluation (seed=42, synthetic NovaCart data)'); print('='*70); matches=reconciliation.reconcile(conn,mid); health=reconciliation.reconciliation_health(conn,mid); print(f'\n[Reconciliation] {len(matches)} matches created.'); print(f'  Health: {health}')
    checks={'A_delayed_settlement':conn.execute("SELECT 1 FROM reconciliation_match WHERE settlement_id=? AND status='MISSING_SETTLEMENT'",(gt['scenarios']['A_delayed_settlement']['settlement_id'],)).fetchone() is not None,'B_duplicate_debit':conn.execute("SELECT 1 FROM reconciliation_match WHERE status='DUPLICATE'").fetchone() is not None,'D_settlement_mismatch':conn.execute("SELECT 1 FROM reconciliation_match WHERE settlement_id=? AND status='AMOUNT_MISMATCH'",(gt['scenarios']['D_settlement_mismatch']['settlement_id'],)).fetchone() is not None,'E_unmatched_credit':conn.execute("SELECT 1 FROM reconciliation_match WHERE status='UNKNOWN_CREDIT'").fetchone() is not None}
    findings=anomaly.detect(conn,mid,start,days); checks['C_refund_spike']=any(f['category']=='refund_rate_spike' for f in findings); checks['F_recurring_expense_spike']=any(f['category']=='recurring_expense_jump' for f in findings); tp=sum(1 for v in checks.values() if v); print(f'\n[Ground-truth scenario detection] {tp}/{len(checks)} injected scenarios detected:')
    for k,v in checks.items(): print(f"  {'DETECTED' if v else 'MISSED  '}  {k}")
    tools=FinanceTools(conn,mid,start,57); forecast=tools.get_cash_forecast(30); bm=forecast['benchmark']; print(f"\n[Forecasting] naive baseline MAE: ₹{bm['naive_baseline_mae_paise']/100:,.2f}"); print(f"              exp-smoothing MAE: ₹{bm['model_mae_paise']/100:,.2f}"); print(f"              model beats naive: {bm['model_beats_naive']}"); agent=DeterministicDemoAgent(tools); print(f"\n[Agent] {agent.will_cash_cover_payroll(30)['answer']}"); print(f'RESULT: {tp}/{len(checks)} ground-truth scenarios detected.'); conn.close()
if __name__=='__main__': main()
