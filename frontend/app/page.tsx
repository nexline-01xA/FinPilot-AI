import Link from 'next/link';
import {api} from '@/lib/api';
import {StatTile,Card} from '@/components/Card';
import Money from '@/components/Money';

export default async function OverviewPage(){
  const o=await api.overview();
  const health=o.reconciliation_health_pct===null?null:Number(o.reconciliation_health_pct);
  const shortfall=o.possible_shortfall_dates?.[0]||null;

  return <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
    <header className="mb-7 flex flex-col gap-4 border-b border-[#e7e9ea] pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-600"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500"/>Operating snapshot</div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">Finance Overview</h1>
        <p className="mt-1.5 text-sm text-ink-600">NovaCart Technologies · deterministic finance intelligence with governed actions</p>
      </div>
      <Link href="/controller" className="inline-flex items-center justify-center rounded-lg bg-[#111619] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#20282d]">Open AI Controller <span className="ml-2 text-white/55">→</span></Link>
    </header>

    <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile label="Available Cash" value={<Money value={o.current_cash}/>} sub="Current deterministic ledger position"/>
      <StatTile label="Outstanding Receivables" value={<Money value={o.outstanding_receivables}/>} sub="Expected but not yet settled"/>
      <StatTile label="7-Day Cash Position" value={<Money value={o.forecast_7d_cash}/>} sub={shortfall?`Potential shortfall: ${shortfall}`:'No projected shortfall in horizon'}/>
      <StatTile label="Reconciliation Health" value={health===null?'—':`${health.toFixed(1)}%`} sub={`${o.reconciliation_exceptions} active exception${o.reconciliation_exceptions===1?'':'s'}`}/>
    </section>

    <section className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2 p-5 sm:p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-ink-600">Control status</div>
            <h2 className="mt-2 text-lg font-semibold tracking-tight">{o.reconciliation_exceptions>0?'Finance operations need review':'Finance operations are clear'}</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-ink-600">FinPilot has {o.reconciliation_exceptions} reconciliation exception{o.reconciliation_exceptions===1?'':'s'} and {o.open_anomalies} open anomal{o.open_anomalies===1?'y':'ies'}. Evidence remains traceable to deterministic finance tools.</p>
          </div>
          <div className={`shrink-0 rounded-lg px-3 py-2 text-xs font-medium ${o.reconciliation_exceptions>0||o.open_anomalies>0?'bg-amber-50 text-amber-800':'bg-emerald-50 text-emerald-700'}`}>{o.reconciliation_exceptions>0||o.open_anomalies>0?'Review required':'Healthy'}</div>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <Link href="/reconciliation" className="group rounded-xl border border-[#e7e9ea] p-4 transition hover:border-[#cbd5d1] hover:bg-[#fafbfb]"><div className="flex items-center justify-between"><span className="text-sm font-semibold">Reconciliation queue</span><span className="text-sm text-ink-600 transition group-hover:translate-x-0.5">→</span></div><p className="mt-1.5 text-xs leading-5 text-ink-600">Inspect cases, evidence and immutable run history.</p></Link>
          <Link href="/anomalies" className="group rounded-xl border border-[#e7e9ea] p-4 transition hover:border-[#cbd5d1] hover:bg-[#fafbfb]"><div className="flex items-center justify-between"><span className="text-sm font-semibold">Anomaly desk</span><span className="text-sm text-ink-600 transition group-hover:translate-x-0.5">→</span></div><p className="mt-1.5 text-xs leading-5 text-ink-600">Review rule-based and statistical detections separately.</p></Link>
        </div>
      </Card>

      <Card className="p-5 sm:p-6">
        <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-ink-600">Exposure</div>
        <div className="mt-4 space-y-4">
          <div className="flex items-end justify-between gap-4 border-b border-paper-100 pb-4"><span className="text-sm text-ink-600">Settled</span><span className="text-base font-semibold tabular"><Money value={o.total_settled}/></span></div>
          <div className="flex items-end justify-between gap-4 border-b border-paper-100 pb-4"><span className="text-sm text-ink-600">Refund exposure</span><span className="text-base font-semibold tabular"><Money value={o.total_refund_exposure}/></span></div>
          <div className="flex items-end justify-between gap-4"><span className="text-sm text-ink-600">Open anomalies</span><span className="text-base font-semibold tabular">{o.open_anomalies}</span></div>
        </div>
      </Card>
    </section>
  </div>
}
