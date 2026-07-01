import { useCallback, useState } from 'react'
import { toAPIError } from '../api/axiosInstance'
import { useToast } from '../context/ToastContext'
import type { ProgressCallback } from '../api/uploadService'
import type { Document } from '../types'
import type { UploadStatus } from '../components/upload/FileDropzone'

interface UploadState {
  status: UploadStatus
  progress: number
  document: Document | null
  error: string | null
}

const INITIAL_STATE: UploadState = {
  status: 'idle',
  progress: 0,
  document: null,
  error: null,
}

type UploadFn = (file: File, onProgress?: ProgressCallback) => Promise<Document>

/** Drives a single drag-and-drop upload zone: tracks progress, result, and errors. */
export function useFileUpload(uploadFn: UploadFn, successLabel: string) {
  const [state, setState] = useState<UploadState>(INITIAL_STATE)
  const { showToast } = useToast()

  const upload = useCallback(
    async (file: File) => {
      setState({ status: 'uploading', progress: 0, document: null, error: null })

      try {
        const document = await uploadFn(file, (progress) => {
          setState((current) => ({ ...current, progress }))
        })

        if (document.status === 'failed') {
          setState({
            status: 'error',
            progress: 0,
            document: null,
            error: 'Dosya kaydedildi ancak içerik çıkarılıp indexlenemedi. Lütfen başka bir dosya deneyin.',
          })
          showToast(
            'error',
            'İşleme başarısız',
            `${document.original_filename} indexlenemedi.`,
          )
          return
        }

        setState({ status: 'success', progress: 100, document, error: null })
        showToast('success', successLabel, document.original_filename)
      } catch (error) {
        const apiError = toAPIError(error)
        setState({ status: 'error', progress: 0, document: null, error: apiError.detail })
        showToast('error', 'Yükleme başarısız', apiError.detail)
      }
    },
    [uploadFn, successLabel, showToast],
  )

  return { state, upload }
}
