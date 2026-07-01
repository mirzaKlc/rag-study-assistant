import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { SummaryResponse } from '../../types'

export function SummaryCard({ summary }: { summary: SummaryResponse }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-4">
        <h3 className="text-sm font-semibold text-slate-100">Özet</h3>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="rounded-full bg-indigo-500/10 px-2.5 py-1 font-medium text-indigo-300">
            {summary.model_used}
          </span>
          <span>{summary.context_chunks_used} parça kullanıldı</span>
        </div>
      </div>

      <article className="prose prose-invert prose-slate mt-4 max-w-none prose-headings:font-semibold prose-headings:text-slate-100 prose-p:text-slate-300 prose-strong:text-slate-100 prose-li:text-slate-300 prose-a:text-indigo-400">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary.summary}</ReactMarkdown>
      </article>
    </div>
  )
}
