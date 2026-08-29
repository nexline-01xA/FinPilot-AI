import type {Overview,ReconReport,ReconCase,Anomaly,Forecast,Approval,AuditEvent} from '@/types/api';
export type DemoRole='VIEWER'|'ANALYST'|'APPROVER'|'ADMIN';
const base=()=>typeof window==='undefined'?(process.env.INTERNAL_API_URL||process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1'):(process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1');
async function req<T>(path:string,init:RequestInit={}):Promise<T>{const r=await fetch(`${base()}${path}`,{...init,headers:{'Content-Type':'application/json',...(init.headers||{})},cache:'no-store'});if(!r.ok)throw new Error(`${r.status} ${await r.text()}`);return r.json();}
const role=(r:DemoRole)=>({'X-Demo-Role':r});
export const api={
 overview:()=>req<Overview>('/overview'),transactions:(limit=100)=>req<any[]>(`/transactions?limit=${limit}`),settlements:(limit=100)=>req<any[]>(`/settlements?limit=${limit}`),
 reconciliationReport:(resolved=false)=>req<ReconReport>(`/reconciliation?include_resolved=${resolved}`),reconciliationCase:(id:string)=>req<ReconCase>(`/reconciliation/${id}`),
 anomalies:(resolved=false)=>req<Anomaly[]>(`/anomalies?include_resolved=${resolved}`),anomaly:(id:string)=>req<Anomaly>(`/anomalies/${id}`),forecast:(days=30)=>req<Forecast>(`/cash-flow?horizon_days=${days}`),
 simulate:(scenario:Record<string,unknown>)=>req<any>('/forecasts/simulate',{method:'POST',body:JSON.stringify(scenario)}),
 ask:(question:string,r:DemoRole='ANALYST')=>req<any>('/controller/query',{method:'POST',headers:role(r),body:JSON.stringify({question})}),
 approvals:()=>req<Approval[]>('/approvals'),approve:(id:string,by='demo-approver')=>req<Approval>(`/approvals/${id}/approve`,{method:'POST',headers:role('APPROVER'),body:JSON.stringify({decided_by:by})}),reject:(id:string,by='demo-approver')=>req<Approval>(`/approvals/${id}/reject`,{method:'POST',headers:role('APPROVER'),body:JSON.stringify({decided_by:by})}),retry:(id:string)=>req<Approval>(`/approvals/${id}/retry`,{method:'POST',headers:role('APPROVER'),body:JSON.stringify({retry_by:'demo-approver',reason:'manual retry after review'})}),
 audit:()=>req<AuditEvent[]>('/audit'),reset:()=>req<any>('/demo/reset',{method:'POST',headers:role('ADMIN')})
};
