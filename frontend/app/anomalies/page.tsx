import Link from 'next/link';
import {api} from '@/lib/api';
import {Card,StatTile} from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';

export default async function Page(){
  const a=await api.anomalies(false);
  const high=a.filter(x=>x.severity==='high').length;
  const statistical=a.filter(x=>x.kind==='STATISTICAL_ANOMALY').length;
  const rules=a.filter(x=>x.kind==='RULE_BASED_ALERT').length;

  return <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
    <header className="mb-7 border-b border-[#e7e9ea] pb-6">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-600">Detection desk</div>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">Anomalies</h1>
      <p className="mt-1.5 max-w-3xl text-sm leading-6 text-ink-600">Rule-based finance alerts and statistical outliers are kept separate so reviewers can distinguish policy violations from unusual patterns.</p>
    </header>

    <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile label="Active Detections" value={a.length} sub="Current unresolved anomaly set"/>
      <StatTile label="High Severity" value={high} sub="Prioritised for immediate review"/>
      <StatTile label="Rule-Based" value={rules} sub="Explicit finance-control rules"/>
      <StatTile label="Statistical" value={statistical} sub="Distribution or trend outliers"/>
    </section>

    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-[#eceeef] px-5 py-4"><div><div className="text-sm font-semibold">Active anomaly register</div><div className="mt-0.5 text-[11px] text-ink-600">Open a detection to inspect evidence and history.</div></div><span className={`rounded-lg px-2.5 py-1.5 text-[10px] font-semibold ${high?'bg-red-50 text-red-700':'bg-emerald-50 text-emerald-700'}`}>{high?`${high} high severity`:'No high severity'}</span></div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[780px] text-sm">
          <thead><tr className="border-b border-[#eceeef] bg-[#fafbfb] text-left text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-600"><th className="px-5 py-3">Anomaly</th><th className="px-3 py-3">Detection type</th><th className="px-3 py-3">Category</th><th className="px-3 py-3">Severity</th><th className="px-5 py-3 text-right">Detected</th></tr></thead>
          <tbody>{a.map(x=><tr key={x.id} className="border-b border-paper-100 last:border-0 hover:bg-[#fbfcfc]"><td className="px-5 py-4"><Link className="font-medium text-[#0f766e] hover:underline" href={`/anomalies/${x.id}`}>{x.id}</Link></td><td className="px-3 py-4 text-xs text-ink-600">{x.kind==='RULE_BASED_ALERT'?'Rule based':'Statistical'}</td><td className="px-3 py-4 capitalize">{x.category.replaceAll('_',' ')}</td><td className="px-3 py-4"><StatusBadge value={x.severity}/></td><td className="px-5 py-4 text-right text-xs text-ink-600">{x.detected_at.slice(0,10)}</td></tr>)}</tbody>
        </table>
      </div>
      {!a.length&&<div className="p-10 text-center text-sm text-ink-600">No active anomaly detections.</div>}
    </Card>
  </div>
}
