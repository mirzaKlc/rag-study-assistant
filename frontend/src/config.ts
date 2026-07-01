/**
 * Centralised application configuration, sourced from Vite environment
 * variables (.env). Nothing outside this file should read import.meta.env
 * directly — this keeps every config value in one auditable place.
 */

const DEFAULT_TIMEOUT_MS = 60_000
// Gemini summarization/question-generation regularly takes 30-60s+ for larger
// documents — the general API timeout above is too short for these calls.
const DEFAULT_AI_TIMEOUT_MS = 120_000

function parseTimeout(raw: string | undefined, fallback: number): number {
  const parsed = Number(raw)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  apiTimeoutMs: parseTimeout(import.meta.env.VITE_API_TIMEOUT_MS, DEFAULT_TIMEOUT_MS),
  aiRequestTimeoutMs: parseTimeout(
    import.meta.env.VITE_AI_REQUEST_TIMEOUT_MS,
    DEFAULT_AI_TIMEOUT_MS,
  ),
} as const

export const ALLOWED_UPLOAD_EXTENSIONS = ['.pdf', '.txt']
export const MAX_UPLOAD_SIZE_MB = 50
