import { useCallback, useState } from 'react'
import { generateQuestions, summarize } from '../api/aiService'
import { toAPIError } from '../api/axiosInstance'
import { uploadCourseContent, uploadPastExam } from '../api/uploadService'
import { useToast } from '../context/ToastContext'
import { useFileUpload } from '../hooks/useFileUpload'
import { FileDropzone } from './upload/FileDropzone'
import { ActionPanel } from './actions/ActionPanel'
import { SummaryCard } from './results/SummaryCard'
import { QuestionsList } from './results/QuestionsList'
import { SummarySkeleton, QuestionsSkeleton } from './common/Skeleton'
import type { GenerateQuestionsResponse, SummaryResponse } from '../types'

export function Dashboard() {
  const { showToast } = useToast()

  const courseUpload = useFileUpload(uploadCourseContent, 'Ders notu yüklendi')
  const examUpload = useFileUpload(uploadPastExam, 'Geçmiş sınav yüklendi')

  const [topicHint, setTopicHint] = useState('')
  const [questionCount, setQuestionCount] = useState(5)

  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [isSummarizing, setIsSummarizing] = useState(false)

  const [questionsResult, setQuestionsResult] = useState<GenerateQuestionsResponse | null>(null)
  const [isGeneratingQuestions, setIsGeneratingQuestions] = useState(false)

  const canSummarize = courseUpload.state.status === 'success' && Boolean(courseUpload.state.document)
  const canGenerateQuestions = canSummarize && examUpload.state.status === 'success' && Boolean(examUpload.state.document)

  const handleSummarize = useCallback(async () => {
    if (!courseUpload.state.document) return

    setIsSummarizing(true)
    setSummary(null)
    try {
      const result = await summarize({
        content_file_id: courseUpload.state.document.file_id,
        topic_hint: topicHint.trim() || undefined,
      })
      setSummary(result)
      showToast('success', 'Özet hazır', 'İçerik başarıyla özetlendi.')
    } catch (error) {
      const apiError = toAPIError(error)
      showToast('error', 'Özet üretilemedi', apiError.detail)
    } finally {
      setIsSummarizing(false)
    }
  }, [courseUpload.state.document, topicHint, showToast])

  const handleGenerateQuestions = useCallback(async () => {
    if (!courseUpload.state.document || !examUpload.state.document) return

    setIsGeneratingQuestions(true)
    setQuestionsResult(null)
    try {
      const result = await generateQuestions({
        content_file_id: courseUpload.state.document.file_id,
        exam_file_id: examUpload.state.document.file_id,
        count: questionCount,
        topic_hint: topicHint.trim() || undefined,
      })
      setQuestionsResult(result)
      showToast('success', 'Sorular hazır', `${result.count} soru üretildi.`)
    } catch (error) {
      const apiError = toAPIError(error)
      showToast('error', 'Sorular üretilemedi', apiError.detail)
    } finally {
      setIsGeneratingQuestions(false)
    }
  }, [courseUpload.state.document, examUpload.state.document, questionCount, topicHint, showToast])

  const hasAnyResult = summary || questionsResult || isSummarizing || isGeneratingQuestions

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur supports-backdrop-blur:bg-slate-950/60">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-5 sm:px-6">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-sm font-bold text-white">
            Oz
          </div>
          <div>
            <h1 className="text-base font-semibold text-slate-100">OzetAI</h1>
            <p className="text-xs text-slate-500">RAG destekli çalışma asistanı</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-8 px-4 py-8 sm:px-6">
        <section className="grid gap-4 sm:grid-cols-2">
          <FileDropzone
            title="Ders Notları"
            description="PDF veya TXT formatında ders materyali yükleyin."
            status={courseUpload.state.status}
            progress={courseUpload.state.progress}
            document={courseUpload.state.document}
            errorMessage={courseUpload.state.error}
            onFileSelected={courseUpload.upload}
          />
          <FileDropzone
            title="Geçmiş Sınavlar"
            description="Soru tarzını öğrenmek için geçmiş bir sınav yükleyin."
            status={examUpload.state.status}
            progress={examUpload.state.progress}
            document={examUpload.state.document}
            errorMessage={examUpload.state.error}
            onFileSelected={examUpload.upload}
          />
        </section>

        <ActionPanel
          canSummarize={canSummarize}
          canGenerateQuestions={canGenerateQuestions}
          isSummarizing={isSummarizing}
          isGeneratingQuestions={isGeneratingQuestions}
          topicHint={topicHint}
          onTopicHintChange={setTopicHint}
          questionCount={questionCount}
          onQuestionCountChange={setQuestionCount}
          onSummarize={handleSummarize}
          onGenerateQuestions={handleGenerateQuestions}
        />

        {hasAnyResult && (
          <section className="animate-fade-in space-y-6">
            {isSummarizing && <SummarySkeleton />}
            {summary && !isSummarizing && <SummaryCard summary={summary} />}

            {isGeneratingQuestions && <QuestionsSkeleton count={questionCount > 3 ? 3 : questionCount} />}
            {questionsResult && !isGeneratingQuestions && <QuestionsList result={questionsResult} />}
          </section>
        )}
      </main>
    </div>
  )
}
