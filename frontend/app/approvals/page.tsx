import ApprovalsBoard from '@/components/ApprovalsBoard';

export default function Page(){
  return <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
    <header className="mb-6 border-b border-[#e7e9ea] pb-6">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-600">Human control layer</div>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">Approvals</h1>
      <p className="mt-1.5 max-w-2xl text-sm leading-6 text-ink-600">Sensitive actions never execute on the model’s authority alone. Review the proposal, decide, then inspect the verified execution trail.</p>
    </header>
    <ApprovalsBoard/>
  </div>
}
