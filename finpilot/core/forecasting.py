import numpy as np
from datetime import datetime,timedelta
def _daily_net_flows(conn,merchant_id:str,start_date:datetime,days:int)->np.ndarray:
    flows=np.zeros(days)
    for s in conn.execute("SELECT settled_date, amount_paise FROM settlement WHERE merchant_id = ? AND status='settled'",(merchant_id,)).fetchall():
        d=(datetime.fromisoformat(s['settled_date'].replace('Z',''))-start_date).days
        if 0<=d<days: flows[d]+=s['amount_paise']
    for r in conn.execute("SELECT created_at, amount_paise FROM refund WHERE merchant_id = ? AND status='processed'",(merchant_id,)).fetchall():
        d=(datetime.fromisoformat(r['created_at'].replace('Z',''))-start_date).days
        if 0<=d<days: flows[d]-=r['amount_paise']
    for e in conn.execute('SELECT due_date, amount_paise FROM expense WHERE merchant_id = ?',(merchant_id,)).fetchall():
        d=(datetime.fromisoformat(e['due_date'].replace('Z',''))-start_date).days
        if 0<=d<days: flows[d]-=e['amount_paise']
    return flows
def naive_forecast(history:np.ndarray,horizon:int)->np.ndarray: return np.full(horizon,history[-1] if len(history) else 0.0)
def exp_smoothing_forecast(history:np.ndarray,horizon:int,alpha:float=.3)->np.ndarray:
    if len(history)==0: return np.zeros(horizon)
    level=history[0]
    for v in history[1:]: level=alpha*v+(1-alpha)*level
    return np.full(horizon,level)
def backtest_mae(history:np.ndarray,forecast_fn,min_train:int=10)->dict:
    if len(history)<=min_train: return {'mae_paise':None,'n_points':0,'note':'insufficient history for backtest'}
    errors=[]
    for t in range(min_train,len(history)): errors.append(abs(forecast_fn(history[:t],1)[0]-history[t]))
    return {'mae_paise':float(np.mean(errors)),'n_points':len(errors)}
def cash_forecast(conn,merchant_id:str,start_date:datetime,elapsed_days:int,horizon:int,current_cash_paise:int)->dict:
    history=_daily_net_flows(conn,merchant_id,start_date,elapsed_days); naive_bt=backtest_mae(history,naive_forecast); smoothing_bt=backtest_mae(history,exp_smoothing_forecast); daily_flow_forecast=exp_smoothing_forecast(history,horizon); std=float(np.std(history)) if len(history)>1 else 0.; points=[]; cash=current_cash_paise
    for i in range(horizon):
        cash+=daily_flow_forecast[i]; band=std*np.sqrt(i+1); points.append({'day':(start_date+timedelta(days=elapsed_days+i)).strftime('%Y-%m-%d'),'expected_cash_paise':round(cash),'lower_paise':round(cash-1.28*band),'upper_paise':round(cash+1.28*band)})
    upcoming=conn.execute("SELECT id, category, amount_paise, due_date FROM expense WHERE merchant_id = ? AND status = 'scheduled' AND due_date >= ? AND due_date < ?",(merchant_id,(start_date+timedelta(days=elapsed_days)).strftime('%Y-%m-%dT00:00:00Z'),(start_date+timedelta(days=elapsed_days+horizon)).strftime('%Y-%m-%dT00:00:00Z'))).fetchall(); obligations=[{'id':r['id'],'category':r['category'],'amount_paise':r['amount_paise'],'due_date':r['due_date']} for r in upcoming]; shortfall_dates=[p['day'] for p in points if p['lower_paise']<0]
    return {'horizon_days':horizon,'model':'exponential_smoothing(alpha=0.3)','benchmark':{'naive_baseline_mae_paise':naive_bt['mae_paise'],'model_mae_paise':smoothing_bt['mae_paise'],'backtest_points':smoothing_bt['n_points'],'model_beats_naive':smoothing_bt['mae_paise'] is not None and naive_bt['mae_paise'] is not None and smoothing_bt['mae_paise']<=naive_bt['mae_paise']},'points':points,'upcoming_obligations':obligations,'possible_shortfall_dates':shortfall_dates}
