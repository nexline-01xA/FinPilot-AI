'use client';

import Link from 'next/link';
import {useState} from 'react';
import {api,type DemoRole} from '@/lib/api';
import RoleSelector from './RoleSelector';
import EvidencePanel from './EvidencePanel';

const qs=[
  ['Cash outlook','Why is our cash position expected to weaken next week?'],
  ['Priority queue','What requires my attention first?'],
  ['Resolve issue','Can you resolve the most important issue?'],
] as const;

export default function ControllerChat(){
  const[role,setRole]=useState<DemoRole>('ANALYST');
  const[q,setQ]=useState('');
  const[answer,setAnswer]=useState<any>(null);
  const[busy,setBusy]=useState(false);
  const[err,setErr]=useState('');

  async function ask(text=q){
    if(!text.trim()||busy)return;
    setBusy(true);setErr('');
    try{setAnswer(await api.ask(text,role));setQ('')}
    catch(e){setErr(String(e))}
    finally{setBusy(false)}
  }

  return <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)]">
    <aside className="space-y-4">
      <div className="rounded-2xl border border-[#e7e9ea] bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-600">Demo authority</div>
        <div className="mt-3"><RoleSelector value={role} onChange={setRole}/></div>
        <p className="mt-3 text-[11px] leading-5 text-ink-600">VIEWER is read-only. ANALYST can propose controlled actions. APPROVER decides before execution.</p>
      </div>
      <div>
        <div className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-600">Flagship questions</div>
        <div className="space-y-2">{qs.map(([label,text],index)=><button key={text} disabled={busy} onClick={()=>ask(text)} className="w-full rounded-xl border border-[#e7e9ea] bg-white p-3 text-left transition hover:border-[#b8c9c6] hover:bg-[#fbfdfc] disabled:opacity-50"><div className="flex items-center gap-2"><span className="grid h-5 w-5 place-items-center rounded-md bg-[#eef5f4] text-[10px] font-semibold text-[#0f766e]">{index+1}</span><span className="text-xs font-semibold">{label}</span></div><div className="mt-1.5 pl-7 text-[11px] leading-4 text-ink-600">{text}</div></button>)}</div>
      </div>
    </aside>

    <section className="overflow-hidden rounded-2xl border border-[#e7e9ea] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
      <div className="flex items-center justify-between border-b border-[#eceeef] px-5 py-4">
        <div><div className="text-sm font-semibold">Controller workspace</div><div className="mt-0.5 text-[11px] text-ink-600">Reasoning is grounded in allowlisted finance tools</div></div>
        <div className="flex items-center gap-1.5 text-[10px] font-medium text-emerald-700"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500"/>Governed</div>
      </div>

      <div className="min-h-[360px] bg-[#fbfcfc] p-5 sm:p-6">
        {!answer&&!err&&<div className="flex min-h-[280px] items-center justify-center"><div className="max-w-sm text-center"><div className="mx-auto grid h-10 w-10 place-items-center rounded-xl border border-[#dce4e2] bg-white text-sm font-semibold text-[#0f766e]">FP</div><h3 className="mt-3 text-sm font-semibold">Ask about the finance state</h3><p className="mt-1 text-xs leading-5 text-ink-600">FinPilot explains evidence, ranks operational priorities and proposes approval-bound actions without treating the model as the financial source of truth.</p></div></div>}
        {err&&<div className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700"><div className="font-semibold">Controller request failed</div><div className="mt-1 text-xs leading-5">{err}</div></div>}
        {answer&&<div className="space-y-4">
          <div className="rounded-2xl border border-[#e4e8e7] bg-white p-5"><div className="mb-3 flex flex-wrap items-center gap-2"><span className="rounded-md bg-[#eef5f4] px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-[#0f766e]">{answer.mode||'Controller'}</span>{answer.matched_route&&<span className="text-[10px] text-ink-600">route · {answer.matched_route}</span>}</div><div className="text-sm leading-7 text-ink-900">{answer.answer}</div></div>
          {answer.action&&<div className="rounded-xl border border-amber-200 bg-amber-50 p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><div className="text-xs font-semibold text-amber-900">Controlled action proposed</div><div className="mt-1 text-[11px] text-amber-800">{answer.action.id} · {answer.action.status}</div></div><Link href="/approvals" className="rounded-lg bg-amber-900 px-3 py-2 text-center text-xs font-semibold text-white">Review approval →</Link></div></div>}
          {answer.evidence&&<EvidencePanel evidence={answer.evidence}/>} 
        </div>}
      </div>

      <div className="border-t border-[#eceeef] bg-white p-4 sm:p-5">
        <div className="flex gap-2"><input aria-label="Ask FinPilot" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&ask()} placeholder="Ask about cash, reconciliation, anomalies or actions…" className="min-w-0 flex-1 rounded-xl border border-[#dfe2e3] bg-white px-4 py-3 text-sm outline-none transition placeholder:text-stone-400 focus:border-[#83b8b1] focus:ring-2 focus:ring-teal-50"/><button disabled={busy||!q.trim()} onClick={()=>ask()} className="rounded-xl bg-[#111619] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#20282d] disabled:cursor-not-allowed disabled:opacity-40">{busy?'Working…':'Ask'}</button></div>
        <div className="mt-2 text-[10px] text-ink-600">Financial calculations, approval state and execution state remain deterministic.</div>
      </div>
    </section>
  </div>
}
