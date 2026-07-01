import { axiosInstance } from './axiosInstance'
import { config } from '../config'
import type {
  GenerateQuestionsRequest,
  GenerateQuestionsResponse,
  SummarizeRequest,
  SummaryResponse,
} from '../types'

// Gemini generation calls run well past the general API timeout, especially
// for larger documents or higher question counts — give them more headroom.
const AI_REQUEST_CONFIG = { timeout: config.aiRequestTimeoutMs }

export async function summarize(request: SummarizeRequest): Promise<SummaryResponse> {
  const response = await axiosInstance.post<SummaryResponse>(
    '/ai/summarize',
    request,
    AI_REQUEST_CONFIG,
  )
  return response.data
}

export async function generateQuestions(
  request: GenerateQuestionsRequest,
): Promise<GenerateQuestionsResponse> {
  const response = await axiosInstance.post<GenerateQuestionsResponse>(
    '/ai/generate-questions',
    request,
    AI_REQUEST_CONFIG,
  )
  return response.data
}
