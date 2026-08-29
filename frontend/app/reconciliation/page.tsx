import Link from 'next/link';
import {api} from '@/lib/api';
import {Card,StatTile} from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';

export default async function Page(){
  const r=await api.reconciliationReport(false);
  const cases=r.cases.filter(c=>c.status!=='MATCHED');
  const exposure=cases.reduce((s,c)=>s+Math.abs(Number(c.evidence.difference_paise??c.evidence.amount_paise??0)),0);

  return <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
    <header className="mb-7 border-b border-[#e7e9ea] pb-6">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-600">Deterministic control</div>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">Reconciliation Workspace</h1>
      <p className="mt-1.5 max-w-3xl text-sm leading-6 text-ink-600">Settlement-to-ledger matching with stable case identity, explicit evidence and reconstructable run history.</p>
    </header>

    <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile label="Reconciliation Health" value={r.health_pct===null?'—':`${Number(r.health_pct).toFixed(1)}%`} sub="Active deterministic match state"/>
      <StatTile label="Cases Analysed" value={r.total_matches} sub="Current active reconciliation set"/>
      <StatTile label="Exceptions" value={r.exceptions} sub="Cases requiring investigation"/>
      <StatTile label="Exception Exposure" value={`₹${(exposure/100).toLocaleString('en-IN')}`} sub="Absolute amount represented in active exceptions"/>
    </section>

    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-[#eceeef] px-5 py-4"><div><div className="text-sm font-semibold">Exception queue</div><div className="mt-0.5 text-[11px] text-ink-600">Open a case to inspect evidence and observation history.</div></div><span className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-[10px] font-semibold text-amber-800">{cases.length} open</span></div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead><tr className="border-b border-[#eceeef] bg-[#fafbfb] text-left text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-600"><th className="px-5 py-3">Case</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Settlement</th><th className="px-3 py-3">Confidence</th><th className="px-5 py-3 text-right">Updated</th></tr></thead>
          <tbody>{cases.map(c=><tr key={c.id} className="border-b border-paper-100 last:border-0 hover:bg-[#fbfcfc]"><td className="px-5 py-4"><Link className="font-medium text-[#0f766e] hover:underline" href={`/reconciliation/${c.id}`}>{c.id}</Link></td><td className="px-3 py-4"><StatusBadge value={c.status}/></td><td className="px-3 py-4 font-mono text-xs text-ink-600">{c.settlement_id||'—'}</td><td className="px-3 py-4 tabular text-ink-900">{(c.confidence*100).toFixed(0)}%</td><td className="px-5 py-4 text-right text-xs text-ink-600">{c.updated_at.slice(0,10)}</td></tr>)}</tbody>
        </table>
      </div>
      {!cases.length&&<div className="p-10 text-center text-sm text-ink-600">No active reconciliation exceptions.</div>}
    </Card>
  </div>
}
