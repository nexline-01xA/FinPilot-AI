import type {ReactNode} from 'react';

export function Card({children,className=''}:{children:ReactNode;className?:string}){
  return <div className={`rounded-2xl border border-[#e8e9ea] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${className}`}>{children}</div>
}

export function StatTile({label,value,sub}:{label:string;value:ReactNode;sub?:ReactNode}){
  return <Card className="p-5">
    <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-ink-600">{label}</div>
    <div className="mt-2 text-[22px] font-semibold tracking-tight tabular text-ink-900">{value}</div>
    {sub&&<div className="mt-1.5 text-xs leading-5 text-ink-600">{sub}</div>}
  </Card>
}
