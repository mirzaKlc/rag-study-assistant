import type { GenerateQuestionsResponse } from '../../types'
import { QuestionCard } from './QuestionCard'

export function QuestionsList({ result }: { result: GenerateQuestionsResponse }) {
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-100">
          Üretilen Sorular <span className="text-slate-500">({result.count})</span>
        </h3>
        <span className="rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs font-medium text-indigo-300">
          {result.model_used}
        </span>
      </div>

      <div className="space-y-4">
        {result.questions.map((question) => (
          <QuestionCard key={question.question_number} question={question} />
        ))}
      </div>
    </div>
  )
}
