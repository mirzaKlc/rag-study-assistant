interface ActionPanelProps {
  canSummarize: boolean
  canGenerateQuestions: boolean
  isSummarizing: boolean
  isGeneratingQuestions: boolean
  topicHint: string
  onTopicHintChange: (value: string) => void
  questionCount: number
  onQuestionCountChange: (value: number) => void
  onSummarize: () => void
  onGenerateQuestions: () => void
}

const MIN_QUESTIONS = 1
const MAX_QUESTIONS = 20

export function ActionPanel({
  canSummarize,
  canGenerateQuestions,
  isSummarizing,
  isGeneratingQuestions,
  topicHint,
  onTopicHintChange,
  questionCount,
  onQuestionCountChange,
  onSummarize,
  onGenerateQuestions,
}: ActionPanelProps) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-sm font-semibold text-slate-100">İşlem Paneli</h2>
      <p className="mt-1 text-xs text-slate-400">
        Dosyalarınız yüklendikten sonra özet veya pratik sorular üretebilirsiniz.
      </p>

      <div className="mt-4">
        <label htmlFor="topic-hint" className="text-xs font-medium text-slate-300">
          Konu odağı <span className="text-slate-500">(opsiyonel)</span>
        </label>
        <input
          id="topic-hint"
          type="text"
          value={topicHint}
          onChange={(event) => onTopicHintChange(event.target.value)}
          placeholder="Örn: Bağlantılı listeler"
          maxLength={300}
          className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <button
          type="button"
          onClick={onSummarize}
          disabled={!canSummarize || isSummarizing}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-indigo-950/50 transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500 disabled:shadow-none"
        >
          {isSummarizing && <Spinner />}
          Özet Üret
        </button>

        <div className="flex flex-1 items-center gap-2">
          <button
            type="button"
            onClick={onGenerateQuestions}
            disabled={!canGenerateQuestions || isGeneratingQuestions}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-indigo-500/50 bg-slate-950/40 px-4 py-2.5 text-sm font-semibold text-indigo-300 transition hover:bg-indigo-500/10 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-600"
          >
            {isGeneratingQuestions && <Spinner />}
            Sınav Sorusu Tasarla
          </button>

          <label className="sr-only" htmlFor="question-count">
            Soru adedi
          </label>
          <select
            id="question-count"
            value={questionCount}
            onChange={(event) => onQuestionCountChange(Number(event.target.value))}
            disabled={isGeneratingQuestions}
            className="rounded-lg border border-slate-700 bg-slate-950/60 px-2.5 py-2.5 text-sm text-slate-100 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
          >
            {Array.from({ length: MAX_QUESTIONS - MIN_QUESTIONS + 1 }, (_, i) => i + MIN_QUESTIONS).map(
              (value) => (
                <option key={value} value={value}>
                  {value} soru
                </option>
              ),
            )}
          </select>
        </div>
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin text-current" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  )
}
