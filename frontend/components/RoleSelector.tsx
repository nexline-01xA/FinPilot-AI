'use client';
import type {DemoRole} from '@/lib/api';
export default function RoleSelector({value,onChange}:{value:DemoRole;onChange:(v:DemoRole)=>void}){return <label className="flex items-center gap-2 text-xs text-ink-600">Acting as <select value={value} onChange={e=>onChange(e.target.value as DemoRole)} className="rounded border border-paper-200 bg-white px-2 py-1 text-ink-900">{['VIEWER','ANALYST','APPROVER','ADMIN'].map(r=><option key={r}>{r}</option>)}</select></label>}
