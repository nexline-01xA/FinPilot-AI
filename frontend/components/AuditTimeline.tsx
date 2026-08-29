'use client';

import {useEffect,useState} from 'react';
import {api} from '@/lib/api';
import type {AuditEvent} from '@/types/api';
import StatusBadge from './StatusBadge';

export default function AuditTimeline(){
  const[events,setEvents]=useState<AuditEvent[]>([]);
  const[error,setError]=useState('');
  useEffect(()=>{api.audit().then(setEvents).catch(e=>setError(String(e)))},[]);

  if(error)return <div className="rounded-xl border border-red-100 bg-red-50 p-4 text-xs text-red-700">{error}</div>;
  return <div className="overflow-hidden rounded-2xl border border-[#e7e9ea] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
    <div className="border-b border-[#eceeef] px-5 py-4"><div className="text-sm font-semibold">Immutable event stream</div><div className="mt-0.5 text-[11px] text-ink-600">Proposal, decision, execution and verification events in reverse chronological order.</div></div>
    <div className="divide-y divide-paper-100">{events.map(e=><div key={e.id} className="grid gap-3 px-5 py-4 sm:grid-cols-[18px_minmax(0,1fr)_auto] sm:items-start"><div className="mt-1.5 hidden h-2 w-2 rounded-full bg-[#0f766e] sm:block"/><div><div className="flex flex-wrap items-center gap-x-2 gap-y-1"><span className="text-sm font-semibold capitalize">{e.operation.replaceAll('_',' ')}</span><span className="text-[11px] text-ink-600">by {e.actor}</span></div><div className="mt-1 font-mono text-[10px] text-ink-600">{e.created_at}</div>{e.error&&<div className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{e.error}</div>}</div><div>{e.approval_state&&<StatusBadge value={e.approval_state}/>}</div></div>)}</div>
    {!events.length&&<div className="p-10 text-center text-sm text-ink-600">No audit events yet.</div>}
  </div>
}
