import {api} from '@/lib/api';
import {Card,StatTile} from '@/components/Card';
import ForecastChart from '@/components/ForecastChart';

export default async function Page(){
  const f=await api.forecast(30);
  const money=(x:number|null)=>x===null?'—':`₹${(x/100).toLocaleString('en-IN',{maximumFractionDigits:0})}`;
  return <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
    <header className="mb-7 border-b border-[#e7e9ea] pb-6">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-600">Forward cash intelligence</div>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">Cash Flow & Forecast</h1>
      <p className="mt-1.5 text-sm text-ink-600">{f.model} · walk-forward benchmark across {f.benchmark.backtest_points} historical points.</p>
    </header>

    <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile label="Naive MAE" value={money(f.benchmark.naive_baseline_mae_paise)} sub="Reference forecast error"/>
      <StatTile label="Model MAE" value={money(f.benchmark.model_mae_paise)} sub="Exponential-smoothing error"/>
      <StatTile label="Benchmark Result" value={f.benchmark.model_beats_naive?'Model wins':'Naive wins'} sub="Walk-forward comparison"/>
      <StatTile label="Forecast Horizon" value={`${f.horizon_days} days`} sub="Expected cash with uncertainty bounds"/>
    </section>

    <Card className="mb-5 overflow-hidden">
      <div className="flex flex-col gap-2 border-b border-[#eceeef] px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><div><div className="text-sm font-semibold">Projected cash position</div><div className="mt-0.5 text-[11px] text-ink-600">Expected path with upper and lower forecast bounds.</div></div><span className={`w-fit rounded-lg px-2.5 py-1.5 text-[10px] font-semibold ${f.benchmark.model_beats_naive?'bg-emerald-50 text-emerald-700':'bg-amber-50 text-amber-800'}`}>{f.benchmark.model_beats_naive?'Outperforms baseline':'Baseline stronger'}</span></div>
      <div className="p-4 sm:p-5"><ForecastChart points={f.points}/></div>
    </Card>

    <Card className="overflow-hidden">
      <div className="border-b border-[#eceeef] px-5 py-4"><div className="text-sm font-semibold">Upcoming obligations</div><div className="mt-0.5 text-[11px] text-ink-600">Scheduled outflows included in the operating cash view.</div></div>
      <div className="divide-y divide-paper-100">{f.upcoming_obligations.map(o=><div key={o.id} className="grid grid-cols-[1fr_auto] gap-3 px-5 py-4 sm:grid-cols-[1fr_auto_120px]"><div><div className="text-sm font-medium capitalize">{o.category.replaceAll('_',' ')}</div><div className="mt-0.5 text-[10px] text-ink-600">{o.id}</div></div><div className="self-center text-right text-sm font-semibold tabular">₹{(o.amount_paise/100).toLocaleString('en-IN')}</div><div className="col-span-2 text-xs text-ink-600 sm:col-span-1 sm:self-center sm:text-right">{o.due_date.slice(0,10)}</div></div>)}</div>
    </Card>
  </div>
}
