import AuditTimeline from '@/components/AuditTimeline';

export default function Page(){
  return <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
    <header className="mb-6 border-b border-[#e7e9ea] pb-6">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-600">Accountability layer</div>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">Audit Trail</h1>
      <p className="mt-1.5 max-w-3xl text-sm leading-6 text-ink-600">Trace proposal, human decision, execution, verification, failure and retry events across the governed finance workflow.</p>
    </header>
    <AuditTimeline/>
  </div>
}
