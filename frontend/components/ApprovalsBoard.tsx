'use client';

import {useEffect,useState} from 'react';
import {api} from '@/lib/api';
import type {Approval} from '@/types/api';
import StatusBadge from './StatusBadge';

export default function ApprovalsBoard(){
  const[items,setItems]=useState<Approval[]>([]);
  const[busy,setBusy]=useState('');
  const[error,setError]=useState('');
  const load=()=>api.approvals().then(setItems);
  useEffect(()=>{load().catch(e=>setError(String(e)))},[]);

  async function act(id:string,kind:'approve'|'reject'|'retry'){
    setBusy(id);setError('');
    try{
      if(kind==='approve')await api.approve(id);
      else if(kind==='reject')await api.reject(id);
      else await api.retry(id);
      await load();
    }catch(e){setError(String(e))}
    finally{setBusy('')}
  }

  const awaiting=items.filter(x=>x.status==='AWAITING_APPROVAL').length;

  return <div className="space-y-4">
    <div className="flex flex-col gap-3 rounded-2xl border border-[#e7e9ea] bg-white px-5 py-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] sm:flex-row sm:items-center sm:justify-between">
      <div><div className="text-sm font-semibold">Decision queue</div><div className="mt-1 text-xs text-ink-600">{awaiting} action{awaiting===1?'':'s'} currently waiting for a human decision.</div></div>
      <div className="text-[11px] text-ink-600">Approve → execute → verify → audit</div>
    </div>

    {error&&<div className="rounded-xl border border-red-100 bg-red-50 p-4 text-xs text-red-700">{error}</div>}

    {items.map(a=><article key={a.id} className="overflow-hidden rounded-2xl border border-[#e7e9ea] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
      <div className="flex flex-col gap-3 border-b border-[#eceeef] px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
        <div><div className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-600">Controlled action</div><div className="mt-1 text-base font-semibold capitalize tracking-tight">{a.action_type.replaceAll('_',' ')}</div><div className="mt-1 text-[11px] text-ink-600">{a.id} · attempt {a.attempt_number}</div></div>
        <StatusBadge value={a.status}/>
      </div>
      <div className="p-5">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-600">Proposal payload</div>
        <pre className="max-h-64 overflow-auto rounded-xl border border-[#eceeef] bg-[#fafbfb] p-4 text-[11px] leading-5 text-ink-600">{a.proposal_json}</pre>
        {(a.status==='AWAITING_APPROVAL'||a.status==='FAILED')&&<div className="mt-4 flex flex-wrap gap-2 border-t border-[#eceeef] pt-4">
          {a.status==='AWAITING_APPROVAL'&&<><button disabled={busy===a.id} onClick={()=>act(a.id,'approve')} className="rounded-lg bg-[#111619] px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-[#20282d] disabled:opacity-50">{busy===a.id?'Processing…':'Approve & execute'}</button><button disabled={busy===a.id} onClick={()=>act(a.id,'reject')} className="rounded-lg border border-[#dfe2e3] bg-white px-4 py-2.5 text-xs font-semibold text-ink-900 transition hover:bg-paper-50 disabled:opacity-50">Reject</button></>}
          {a.status==='FAILED'&&<button disabled={busy===a.id} onClick={()=>act(a.id,'retry')} className="rounded-lg bg-[#111619] px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">Retry failed action</button>}
        </div>}
      </div>
    </article>)}

    {!items.length&&<div className="rounded-2xl border border-dashed border-[#d8dddc] bg-white p-10 text-center"><div className="text-sm font-semibold">No approval requests</div><p className="mx-auto mt-1 max-w-md text-xs leading-5 text-ink-600">Ask the AI Controller to resolve the highest-priority issue. Any controlled action will appear here before execution.</p></div>}
  </div>
}
