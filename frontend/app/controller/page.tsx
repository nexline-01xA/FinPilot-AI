import ControllerChat from '@/components/ControllerChat';

export default function Page(){
  return <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
    <header className="mb-6 border-b border-[#e7e9ea] pb-6">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-600">Governed intelligence</div>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">AI Finance Controller</h1>
      <p className="mt-1.5 max-w-3xl text-sm leading-6 text-ink-600">Ask operational finance questions, inspect evidence and propose controlled actions. The model reasons over verified tools; deterministic services remain the source of financial truth.</p>
    </header>
    <ControllerChat/>
  </div>
}
