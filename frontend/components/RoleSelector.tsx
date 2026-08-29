'use client';

import type {DemoRole} from '@/lib/api';

export default function RoleSelector({value,onChange}:{value:DemoRole;onChange:(v:DemoRole)=>void}){
  return <label className="flex items-center gap-2 text-xs text-ink-600">
    <span className="font-medium">Acting as</span>
    <select value={value} onChange={e=>onChange(e.target.value as DemoRole)} className="rounded-lg border border-[#dfe2e3] bg-white px-3 py-2 text-xs font-semibold text-ink-900 outline-none transition focus:border-[#8cbeb8] focus:ring-2 focus:ring-teal-50">
      {['VIEWER','ANALYST','APPROVER','ADMIN'].map(r=><option key={r}>{r}</option>)}
    </select>
  </label>
}
