import { useCallback, useId, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_SIZE_MB } from '../../config'
import type { Document } from '../../types'
import { CheckIcon, UploadIcon } from '../common/Icons'

export type UploadStatus = 'idle' | 'uploading' | 'success' | 'error'

interface FileDropzoneProps {
  title: string
  description: string
  status: UploadStatus
  progress: number
  document: Document | null
  errorMessage?: string | null
  onFileSelected: (file: File) => void
}

function isExtensionAllowed(filename: string): boolean {
  const lower = filename.toLowerCase()
  return ALLOWED_UPLOAD_EXTENSIONS.some((ext) => lower.endsWith(ext))
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function FileDropzone({
  title,
  description,
  status,
  progress,
  document,
  errorMessage,
  onFileSelected,
}: FileDropzoneProps) {
  const [isDragActive, setIsDragActive] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)

  const validateAndEmit = useCallback(
    (file: File) => {
      setLocalError(null)

      if (!isExtensionAllowed(file.name)) {
        setLocalError(`Yalnızca ${ALLOWED_UPLOAD_EXTENSIONS.join(', ')} dosyaları desteklenir.`)
        return
      }
      if (file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024) {
        setLocalError(`Dosya boyutu ${MAX_UPLOAD_SIZE_MB} MB sınırını aşıyor.`)
        return
      }

      onFileSelected(file)
    },
    [onFileSelected],
  )

  const handleDrop = useCallback(
    (event: DragEvent<HTMLLabelElement>) => {
      event.preventDefault()
      setIsDragActive(false)
      const file = event.dataTransfer.files?.[0]
      if (file) validateAndEmit(file)
    },
    [validateAndEmit],
  )

  const handleInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (file) validateAndEmit(file)
      event.target.value = ''
    },
    [validateAndEmit],
  )

  const displayError = localError ?? errorMessage
  const isUploading = status === 'uploading'

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
        <p className="text-xs text-slate-400">{description}</p>
      </div>

      <label
        htmlFor={inputId}
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragActive(true)
        }}
        onDragLeave={() => setIsDragActive(false)}
        onDrop={handleDrop}
        className={`group relative flex min-h-[160px] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-6 text-center transition-colors duration-200 ${
          isDragActive
            ? 'border-indigo-400 bg-indigo-500/10'
            : displayError
              ? 'border-rose-500/60 bg-rose-500/5'
              : status === 'success'
                ? 'border-emerald-500/50 bg-emerald-500/5'
                : 'border-slate-700 bg-slate-900/40 hover:border-indigo-500/60 hover:bg-slate-900/70'
        }`}
      >
        <input
          id={inputId}
          ref={inputRef}
          type="file"
          accept={ALLOWED_UPLOAD_EXTENSIONS.join(',')}
          className="sr-only"
          onChange={handleInputChange}
          disabled={isUploading}
        />

        {status === 'success' && document ? (
          <>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400">
              <CheckIcon />
            </span>
            <p className="max-w-full truncate text-sm font-medium text-slate-100">
              {document.original_filename}
            </p>
            <p className="text-xs text-slate-400">
              {formatBytes(document.size_bytes)} · yüklendi
            </p>
            <span className="text-xs font-medium text-indigo-400 underline-offset-2 group-hover:underline">
              Değiştirmek için tıkla veya sürükle
            </span>
          </>
        ) : isUploading ? (
          <>
            <span className="text-sm font-medium text-slate-200">Yükleniyor…</span>
            <div className="h-2 w-full max-w-[220px] overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-indigo-500 transition-[width] duration-200 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-xs text-slate-400">%{progress}</span>
          </>
        ) : (
          <>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-slate-300 transition-colors group-hover:bg-indigo-500/20 group-hover:text-indigo-300">
              <UploadIcon />
            </span>
            <p className="text-sm font-medium text-slate-200">
              Dosyayı sürükle bırak veya <span className="text-indigo-400">seç</span>
            </p>
            <p className="text-xs text-slate-500">
              {ALLOWED_UPLOAD_EXTENSIONS.join(' / ').toUpperCase()} · maks. {MAX_UPLOAD_SIZE_MB} MB
            </p>
          </>
        )}
      </label>

      {displayError && <p className="text-xs font-medium text-rose-400">{displayError}</p>}
    </div>
  )
}
