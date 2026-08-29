import type {ReactNode} from 'react';
export function Card({children,className=''}:{children:ReactNode;className?:string}){return <div className={`rounded-xl border border-paper-200 bg-white ${className}`}>{children}</div>}
export function StatTile({label,value,sub}:{label:string;value:ReactNode;sub?:ReactNode}){return <Card className="p-4"><div className="text-xs uppercase tracking-wide text-ink-600">{label}</div><div className="mt-2 text-xl font-semibold tabular text-ink-900">{value}</div>{sub&&<div className="mt-1 text-xs text-ink-600">{sub}</div>}</Card>}
