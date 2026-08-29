import {Card} from '@/components/Card';
import DemoResetButton from '@/components/DemoResetButton';

export default function Page(){
  return <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
    <header className="mb-6 border-b border-[#e7e9ea] pb-6">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-600">Demo controls</div>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">Settings</h1>
      <p className="mt-1.5 max-w-2xl text-sm leading-6 text-ink-600">Runtime boundaries, demo authority and controlled reset tools for the FinPilot evaluation environment.</p>
    </header>
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-5 sm:p-6"><div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-600">AI Provider</div><div className="mt-2 text-sm font-semibold">Demo Reasoning Mode</div><p className="mt-2 text-sm leading-6 text-ink-600">Deterministic demo reasoning is active by default. Live Claude tool-calling is implemented but requires an API key and is intentionally outside the verified offline path.</p><div className="mt-4 inline-flex items-center gap-2 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-[10px] font-semibold text-emerald-700"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500"/>Verified demo mode active</div></Card>
      <Card className="p-5 sm:p-6"><div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-600">Separation of duties</div><div className="mt-2 text-sm font-semibold">Demo roles</div><div className="mt-4 space-y-2 text-xs"><div className="flex justify-between border-b border-paper-100 pb-2"><span className="font-medium">VIEWER</span><span className="text-ink-600">Inspects</span></div><div className="flex justify-between border-b border-paper-100 pb-2"><span className="font-medium">ANALYST</span><span className="text-ink-600">Proposes</span></div><div className="flex justify-between border-b border-paper-100 pb-2"><span className="font-medium">APPROVER</span><span className="text-ink-600">Decides</span></div><div className="flex justify-between"><span className="font-medium">ADMIN</span><span className="text-ink-600">Resets demo data</span></div></div></Card>
      <Card className="p-5 sm:p-6 lg:col-span-2"><div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-red-600">Destructive demo control</div><div className="mt-2 text-sm font-semibold">NovaCart dataset</div><p className="mt-2 max-w-2xl text-sm leading-6 text-ink-600">Reset the deterministic synthetic dataset to its known seed state. This removes demo-side changes such as approvals and generated sandbox effects.</p><div className="mt-4"><DemoResetButton/></div></Card>
    </div>
  </div>
}
