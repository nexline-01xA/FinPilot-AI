export default function EvidencePanel({evidence}:{evidence:Record<string,unknown>}){
  return <details className="group rounded-xl border border-[#e7e9ea] bg-[#fafbfb]">
    <summary className="cursor-pointer list-none px-4 py-3 text-xs font-semibold text-ink-900 marker:hidden">Evidence trace <span className="ml-1 font-normal text-ink-600">· verified tool output</span></summary>
    <div className="border-t border-[#e7e9ea] p-3"><pre className="max-h-72 overflow-auto rounded-lg bg-white p-3 text-[11px] leading-5 text-ink-600">{JSON.stringify(evidence,null,2)}</pre></div>
  </details>
}
