import random,uuid
from datetime import datetime,timedelta,timezone
MERCHANT_ID='merch_novacart'; MERCHANT_NAME='NovaCart Technologies'; DAYS=60; START=datetime(2026,6,1,tzinfo=timezone.utc)
def _iso(dt): return dt.strftime('%Y-%m-%dT00:00:00Z')
def _uid(prefix,rng): return f'{prefix}_{uuid.UUID(int=rng.getrandbits(128)).hex[:10]}'
def generate(conn,seed:int=42)->dict:
    rng=random.Random(seed); gt={'scenarios':{}}
    conn.execute('INSERT INTO merchant (id, name, created_at) VALUES (?, ?, ?)',(MERCHANT_ID,MERCHANT_NAME,_iso(START)))
    day_payments={}
    for d in range(DAYS):
        day=START+timedelta(days=d); day_payments[d]=[]
        for _ in range(rng.randint(15,40)):
            amount=rng.randint(5000,1500000); order_id=_uid('order',rng); conn.execute("INSERT INTO order_tbl (id, merchant_id, amount_paise, created_at, status) VALUES (?, ?, ?, ?, 'paid')",(order_id,MERCHANT_ID,amount,_iso(day))); fee=round(amount*.02); payment_id=_uid('pay',rng); tax=round(fee*.18)
            conn.execute("INSERT INTO payment (id, order_id, merchant_id, amount_paise, fee_paise, tax_paise, status, method, created_at) VALUES (?, ?, ?, ?, ?, ?, 'captured', ?, ?)",(payment_id,order_id,MERCHANT_ID,amount,fee,tax,rng.choice(['card','upi','netbanking']),_iso(day))); day_payments[d].append({'id':payment_id,'amount':amount,'fee':fee,'tax':tax,'day':d})
    all_payments=[p for day in day_payments.values() for p in day]; refund_start=38
    for p in all_payments:
        rate=.4 if refund_start<=p['day']<refund_start+6 else .03
        if rng.random()<rate:
            conn.execute("INSERT INTO refund (id, payment_id, merchant_id, amount_paise, created_at, status) VALUES (?, ?, ?, ?, ?, 'processed')",(_uid('rfnd',rng),p['id'],MERCHANT_ID,p['amount'],_iso(START+timedelta(days=p['day']+rng.randint(0,2)))))
    gt['scenarios']['C_refund_spike']={'description':'Refund rate jumps from ~3% baseline to ~40% for days 38-43','day_range':[refund_start,refund_start+5]}
    duplicate_day=20; mismatch_day=30; delayed_day=DAYS-4; unmatched_day=25; settlement_ids={}
    for d,payments in day_payments.items():
        gross=sum(p['amount'] for p in payments); fees=sum(p['fee']+p['tax'] for p in payments); expected=gross-fees; sid=_uid('stl',rng); settlement_ids[d]=sid; expected_date=START+timedelta(days=d+2); actual=expected; status='settled'; settled_date=_iso(expected_date)
        if d==mismatch_day: actual=expected-2225000
        if d==delayed_day: status='delayed'; settled_date=None
        conn.execute('INSERT INTO settlement (id, merchant_id, amount_paise, expected_amount_paise, utr, status, expected_date, settled_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',(sid,MERCHANT_ID,actual,expected,_uid('utr',rng) if status=='settled' else None,status,_iso(expected_date),settled_date))
        for p in payments: conn.execute('UPDATE payment SET settlement_id = ? WHERE id = ?',(sid,p['id']))
        if status=='settled': conn.execute('INSERT INTO ledger_entry (id, merchant_id, amount_paise, description, value_date, reference, matched) VALUES (?, ?, ?, ?, ?, ?, 0)',(_uid('ldg',rng),MERCHANT_ID,actual,f'NEFT CREDIT SETTLEMENT {sid}',settled_date,sid))
        if d==duplicate_day:
            for _ in range(2): conn.execute('INSERT INTO ledger_entry (id, merchant_id, amount_paise, description, value_date, reference, matched) VALUES (?, ?, ?, ?, ?, ?, 0)',(_uid('ldg',rng),MERCHANT_ID,-fees,f'BANK FEE DEBIT {sid}',settled_date,sid))
    gt['scenarios']['A_delayed_settlement']={'description':'Settlement shortly before payroll is delayed.','settlement_id':settlement_ids[delayed_day],'day':delayed_day}
    gt['scenarios']['B_duplicate_debit']={'description':'Two identical fee-debit ledger entries were posted for the same settlement.','settlement_id':settlement_ids[duplicate_day],'day':duplicate_day}
    gt['scenarios']['D_settlement_mismatch']={'description':'Settlement amount is short of the expected payment aggregation by exactly ₹22,250.00.','settlement_id':settlement_ids[mismatch_day],'day':mismatch_day,'expected_shortfall_paise':2225000}
    unmatched_amount=4850000; conn.execute('INSERT INTO ledger_entry (id, merchant_id, amount_paise, description, value_date, reference, matched) VALUES (?, ?, ?, ?, ?, NULL, 0)',(_uid('ldg',rng),MERCHANT_ID,unmatched_amount,'NEFT CREDIT UNKNOWN SENDER',_iso(START+timedelta(days=unmatched_day)))); gt['scenarios']['E_unmatched_credit']={'description':'An incoming credit with no matching settlement or payment reference.','amount_paise':unmatched_amount,'day':unmatched_day}
    payroll=185000000
    for md in [10,40]: conn.execute("INSERT INTO expense (id, merchant_id, category, amount_paise, due_date, recurring, status) VALUES (?, ?, 'payroll', ?, ?, 1, 'scheduled')",(_uid('exp',rng),MERCHANT_ID,payroll,_iso(START+timedelta(days=md))))
    conn.execute("INSERT INTO expense (id, merchant_id, category, amount_paise, due_date, recurring, status) VALUES (?, ?, 'payroll', ?, ?, 1, 'scheduled')",(_uid('exp',rng),MERCHANT_ID,payroll,_iso(START+timedelta(days=DAYS-1))))
    saas=4500000
    for d in range(0,DAYS,30):
        amount=saas if d<30 else round(saas*1.65); conn.execute("INSERT INTO expense (id, merchant_id, category, amount_paise, due_date, recurring, status) VALUES (?, ?, 'saas_subscriptions', ?, ?, 1, 'scheduled')",(_uid('exp',rng),MERCHANT_ID,amount,_iso(START+timedelta(days=d+5))))
    gt['scenarios']['F_recurring_expense_spike']={'description':'Recurring SaaS expense jumps ~65% starting month 2 (from ₹45,000 to ~₹74,250).','category':'saas_subscriptions','old_amount_paise':saas,'new_amount_paise':round(saas*1.65)}
    conn.commit(); gt['merchant_id']=MERCHANT_ID; gt['days']=DAYS; gt['start_date']=_iso(START); return gt
