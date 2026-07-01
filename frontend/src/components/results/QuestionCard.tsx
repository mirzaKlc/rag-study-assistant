import { useState } from 'react'
import type { Question } from '../../types'
import { ChevronRightIcon } from '../common/Icons'

const DIFFICULTY_LABEL: Record<string, string> = {
  easy: 'Kolay',
  medium: 'Orta',
  hard: 'Zor',
}

const DIFFICULTY_STYLE: Record<string, string> = {
  easy: 'bg-emerald-500/10 text-emerald-300',
  medium: 'bg-amber-500/10 text-amber-300',
  hard: 'bg-rose-500/10 text-rose-300',
}

const TYPE_LABEL: Record<string, string> = {
  multiple_choice: 'Çoktan Seçmeli',
  open_ended: 'Açık Uçlu',
  coding: 'Kodlama',
  true_false: 'Doğru / Yanlış',
}

export function QuestionCard({ question }: { question: Question }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 transition-colors hover:border-slate-700">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-500/15 text-xs font-semibold text-indigo-300">
          {question.question_number}
        </span>
        {question.difficulty && (
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${DIFFICULTY_STYLE[question.difficulty] ?? 'bg-slate-800 text-slate-300'}`}
          >
            {DIFFICULTY_LABEL[question.difficulty] ?? question.difficulty}
          </span>
        )}
        {question.question_type && (
          <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-slate-300">
            {TYPE_LABEL[question.question_type] ?? question.question_type}
          </span>
        )}
      </div>

      <p className="mt-3 text-sm font-medium leading-relaxed text-slate-100">
        {question.question}
      </p>

      {question.options && question.options.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {question.options.map((option, index) => (
            <li
              key={index}
              className="rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm text-slate-300"
            >
              {option}
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-indigo-500/60 hover:bg-indigo-500/10 hover:text-indigo-300"
      >
        <span
          className={`inline-block transition-transform duration-300 ${isOpen ? 'rotate-90' : 'rotate-0'}`}
        >
          <ChevronRightIcon />
        </span>
        {isOpen ? 'Çözümü Gizle' : 'Çözümü Göster'}
      </button>

      <div
        className="grid transition-[grid-template-rows] duration-300 ease-in-out"
        style={{ gridTemplateRows: isOpen ? '1fr' : '0fr' }}
      >
        <div className="overflow-hidden">
          <div className="mt-4 space-y-2 rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-300">
              Doğru Cevap
            </p>
            <p className="text-sm text-slate-100">{question.correct_answer}</p>

            <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-indigo-300">
              Detaylı Çözüm
            </p>
            <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300">
              {question.detailed_solution}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
