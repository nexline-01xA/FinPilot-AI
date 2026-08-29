'use client';

import {useState} from 'react';
import {api} from '@/lib/api';

export default function DemoResetButton(){
  const[status,setStatus]=useState('');
  const[busy,setBusy]=useState(false);
  async function reset(){setBusy(true);setStatus('Resetting deterministic dataset…');try{await api.reset();setStatus('Reset complete. Refresh any open finance views.')}catch(error){setStatus(String(error))}finally{setBusy(false)}}
  return <div>
    <button disabled={busy} onClick={reset} className="rounded-lg border border-red-200 bg-white px-4 py-2.5 text-xs font-semibold text-red-700 transition hover:bg-red-50 disabled:opacity-50">{busy?'Resetting…':'Reset NovaCart demo'}</button>
    {status&&<div className="mt-2 text-[11px] leading-5 text-ink-600">{status}</div>}
  </div>
}
