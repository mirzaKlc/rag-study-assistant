import type { AxiosProgressEvent } from 'axios'
import { axiosInstance } from './axiosInstance'
import type { Document } from '../types'

export type ProgressCallback = (percent: number) => void

async function uploadFile(
  endpoint: string,
  file: File,
  onProgress?: ProgressCallback,
): Promise<Document> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await axiosInstance.post<Document>(endpoint, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (!onProgress || !event.total) return
      onProgress(Math.round((event.loaded * 100) / event.total))
    },
  })

  return response.data
}

export function uploadCourseContent(file: File, onProgress?: ProgressCallback): Promise<Document> {
  return uploadFile('/uploads/course-content', file, onProgress)
}

export function uploadPastExam(file: File, onProgress?: ProgressCallback): Promise<Document> {
  return uploadFile('/uploads/past-exams', file, onProgress)
}
