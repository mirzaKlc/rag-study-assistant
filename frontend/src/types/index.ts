/**
 * Type contracts mirroring the backend's Pydantic schemas
 * (see app/models/schemas.py). Keep these in sync with the API.
 */

export type UploadCategory = 'course_content' | 'past_exam'

export type DocumentStatus = 'pending' | 'processing' | 'indexed' | 'failed'

export interface Document {
  file_id: string
  original_filename: string
  stored_filename: string
  category: UploadCategory
  size_bytes: number
  extension: string
  uploaded_at: string
  status: DocumentStatus
}

export interface SummarizeRequest {
  content_file_id: string
  topic_hint?: string
}

export interface SummaryResponse {
  content_file_id: string
  summary: string
  model_used: string
  context_chunks_used: number
  generated_at: string
}

export type QuestionDifficulty = 'easy' | 'medium' | 'hard'

export type QuestionType = 'multiple_choice' | 'open_ended' | 'coding' | 'true_false'

export interface Question {
  question_number: number
  question: string
  options?: string[] | null
  correct_answer: string
  detailed_solution: string
  difficulty?: QuestionDifficulty | null
  question_type?: QuestionType | null
}

export interface GenerateQuestionsRequest {
  content_file_id: string
  exam_file_id: string
  count: number
  topic_hint?: string
}

export interface GenerateQuestionsResponse {
  content_file_id: string
  exam_file_id: string
  questions: Question[]
  count: number
  model_used: string
  generated_at: string
}

/** Standard error envelope returned by the backend's global exception handler. */
export interface APIError {
  status_code: number
  detail: string
  timestamp: string
  path?: string | null
  request_id?: string | null
}
