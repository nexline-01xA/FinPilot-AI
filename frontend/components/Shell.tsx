'use client';

import Link from 'next/link';
import {usePathname} from 'next/navigation';
import type {ReactNode} from 'react';

const nav=[
  ['/', 'Overview'],
  ['/transactions','Transactions'],
  ['/reconciliation','Reconciliation'],
  ['/cash-flow','Cash Flow'],
  ['/anomalies','Anomalies'],
  ['/controller','AI Controller'],
  ['/approvals','Approvals'],
  ['/audit','Audit'],
  ['/settings','Settings'],
] as const;

function isActive(pathname:string,href:string){return href==='/'?pathname===href:pathname.startsWith(href)}

export default function Shell({children}:{children:ReactNode}){
  const pathname=usePathname();
  return <div className="min-h-screen bg-[#f6f7f8] text-ink-900">
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-white/5 bg-[#111619] px-4 py-5 text-white md:flex">
      <div className="px-2">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/[0.06] text-sm font-semibold tracking-tight">FP</div>
          <div>
            <div className="text-[15px] font-semibold tracking-tight">FinPilot AI</div>
            <div className="text-[11px] text-white/45">Finance control plane</div>
          </div>
        </div>
        <div className="mt-5 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2.5">
          <div className="text-[10px] uppercase tracking-[0.16em] text-white/35">Workspace</div>
          <div className="mt-1 text-xs font-medium text-white/85">NovaCart Technologies</div>
        </div>
      </div>
      <nav className="mt-5 flex-1 space-y-1">
        {nav.map(([href,label])=>{
          const active=isActive(pathname,href);
          return <Link key={href} href={href} className={`group flex items-center justify-between rounded-lg px-3 py-2.5 text-sm transition ${active?'bg-white/[0.09] font-medium text-white':'text-white/55 hover:bg-white/[0.05] hover:text-white/90'}`}>
            <span>{label}</span>{active&&<span className="h-1.5 w-1.5 rounded-full bg-[#5eead4]"/>}
          </Link>
        })}
      </nav>
      <div className="border-t border-white/10 px-2 pt-4">
        <div className="flex items-center gap-2 text-[11px] text-white/45"><span className="h-2 w-2 rounded-full bg-emerald-400"/>Deterministic demo runtime</div>
        <div className="mt-1 text-[10px] text-white/30">Humans approve controlled actions</div>
      </div>
    </aside>

    <div className="sticky top-0 z-20 border-b border-paper-200 bg-white/95 backdrop-blur md:hidden">
      <div className="flex h-14 items-center justify-between px-4"><div><div className="text-sm font-semibold">FinPilot AI</div><div className="text-[10px] text-ink-600">NovaCart Technologies</div></div><span className="rounded-md bg-emerald-50 px-2 py-1 text-[10px] font-medium text-emerald-700">Demo</span></div>
      <nav className="flex gap-1 overflow-x-auto border-t border-paper-100 px-3 py-2 scrollbar-hide">{nav.map(([href,label])=><Link key={href} href={href} className={`whitespace-nowrap rounded-md px-3 py-1.5 text-xs ${isActive(pathname,href)?'bg-[#111619] text-white':'text-ink-600'}`}>{label}</Link>)}</nav>
    </div>

    <main className="md:ml-64">{children}</main>
  </div>
}
