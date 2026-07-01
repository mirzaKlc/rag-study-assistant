import axios, { AxiosError } from 'axios'
import { config } from '../config'
import type { APIError } from '../types'

/**
 * Single shared Axios instance for all API requests.
 * Base URL and timeout come from src/config.ts (sourced from .env).
 */
export const axiosInstance = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: config.apiTimeoutMs,
  headers: {
    Accept: 'application/json',
  },
})

/**
 * Normalises any Axios failure into the backend's APIError shape so callers
 * never have to deal with network errors, timeouts, and HTTP errors differently.
 */
export function toAPIError(error: unknown): APIError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<APIError>
    const responseBody = axiosError.response?.data

    if (responseBody?.detail) {
      return responseBody
    }

    if (axiosError.code === 'ECONNABORTED') {
      return {
        status_code: 408,
        detail: 'İstek zaman aşımına uğradı. Lütfen tekrar deneyin.',
        timestamp: new Date().toISOString(),
      }
    }

    if (!axiosError.response) {
      return {
        status_code: 0,
        detail: 'Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.',
        timestamp: new Date().toISOString(),
      }
    }

    return {
      status_code: axiosError.response.status,
      detail: axiosError.message,
      timestamp: new Date().toISOString(),
    }
  }

  return {
    status_code: 500,
    detail: 'Beklenmeyen bir hata oluştu.',
    timestamp: new Date().toISOString(),
  }
}
