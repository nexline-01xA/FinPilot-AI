import {api} from '@/lib/api';
import {Card,StatTile} from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';

export default async function Page(){
  const tx=await api.transactions(100);
  const gross=tx.reduce((sum:number,t:any)=>sum+Number(t.amount_paise||0),0);
  const fees=tx.reduce((sum:number,t:any)=>sum+Number(t.fee_paise||0)+Number(t.tax_paise||0),0);
  const succeeded=tx.filter((t:any)=>String(t.status).toLowerCase().includes('success')).length;

  return <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
    <header className="mb-7 border-b border-[#e7e9ea] pb-6">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-600">Payment ledger</div>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">Transactions</h1>
      <p className="mt-1.5 text-sm text-ink-600">Synthetic NovaCart payment activity used by the deterministic finance engine.</p>
    </header>

    <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
      <StatTile label="Rows in View" value={tx.length} sub="Latest synthetic payment records"/>
      <StatTile label="Gross Payment Value" value={`₹${(gross/100).toLocaleString('en-IN')}`} sub="Across the current table view"/>
      <StatTile label="Fees + Tax" value={`₹${(fees/100).toLocaleString('en-IN')}`} sub={`${succeeded} succeeded payment${succeeded===1?'':'s'} in view`}/>
    </section>

    <Card className="overflow-hidden">
      <div className="border-b border-[#eceeef] px-5 py-4"><div className="text-sm font-semibold">Payment activity</div><div className="mt-0.5 text-[11px] text-ink-600">Amounts are stored and calculated in integer paise.</div></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[860px] text-sm"><thead><tr className="border-b border-[#eceeef] bg-[#fafbfb] text-left text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-600"><th className="px-5 py-3">Payment</th><th className="px-3 py-3">Method</th><th className="px-3 py-3">Status</th><th className="px-3 py-3 text-right">Amount</th><th className="px-3 py-3 text-right">Fee + tax</th><th className="px-5 py-3 text-right">Created</th></tr></thead><tbody>{tx.map((t:any)=><tr key={t.id} className="border-b border-paper-100 last:border-0 hover:bg-[#fbfcfc]"><td className="px-5 py-4 font-mono text-xs">{t.id}</td><td className="px-3 py-4 capitalize text-ink-600">{t.method}</td><td className="px-3 py-4"><StatusBadge value={t.status}/></td><td className="px-3 py-4 text-right font-medium tabular">₹{(t.amount_paise/100).toLocaleString('en-IN')}</td><td className="px-3 py-4 text-right tabular text-ink-600">₹{((t.fee_paise+t.tax_paise)/100).toLocaleString('en-IN')}</td><td className="px-5 py-4 text-right text-xs text-ink-600">{t.created_at.slice(0,10)}</td></tr>)}</tbody></table></div>
    </Card>
  </div>
}
