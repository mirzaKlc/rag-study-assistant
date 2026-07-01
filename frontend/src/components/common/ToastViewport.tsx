import type { ReactNode } from 'react'
import { useToast } from '../../context/ToastContext'
import type { ToastVariant } from '../../context/ToastContext'
import { CheckIcon, CloseIcon } from './Icons'

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: 'border-emerald-500/40 bg-emerald-950/90 text-emerald-100',
  error: 'border-rose-500/40 bg-rose-950/90 text-rose-100',
  info: 'border-indigo-500/40 bg-indigo-950/90 text-indigo-100',
}

const VARIANT_ICON: Record<ToastVariant, ReactNode> = {
  success: <CheckIcon className="h-3 w-3" />,
  error: <span aria-hidden="true">!</span>,
  info: <span aria-hidden="true">i</span>,
}

export function ToastViewport() {
  const { toasts, dismissToast } = useToast()

  if (toasts.length === 0) return null

  return (
    <div className="pointer-events-none fixed inset-x-0 top-4 z-50 flex flex-col items-center gap-2 px-4 sm:items-end sm:right-4 sm:left-auto">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="alert"
          className={`pointer-events-auto w-full max-w-sm animate-toast-in rounded-xl border px-4 py-3 shadow-lg shadow-black/30 backdrop-blur-sm ${VARIANT_STYLES[toast.variant]}`}
        >
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-bold">
              {VARIANT_ICON[toast.variant]}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">{toast.title}</p>
              {toast.description && (
                <p className="mt-0.5 text-xs leading-relaxed text-white/70">
                  {toast.description}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismissToast(toast.id)}
              className="shrink-0 rounded-md p-1 text-white/50 transition hover:bg-white/10 hover:text-white"
              aria-label="Kapat"
            >
              <CloseIcon />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
