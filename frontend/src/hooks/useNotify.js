import { useCallback, useRef, useState } from 'react'
import { CheckCircle, WarningCircle, X, XCircle } from '@phosphor-icons/react'
import { formatError } from '../lib/utils'

const TOAST_DURATION = { error: 16000, warning: 12000, success: 7000 }

export function ToastStack({ toasts, dismiss, pauseToast, resumeToast }) {
  const icons = { error: XCircle, success: CheckCircle, warning: WarningCircle }
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => {
        const Icon = icons[toast.type] || WarningCircle
        return (
          <div
            key={toast.id}
            className={`toast toast-${toast.type}`}
            role="alert"
            onMouseEnter={() => pauseToast(toast.id)}
            onMouseLeave={() => resumeToast(toast.id)}
            onFocus={() => pauseToast(toast.id)}
            onBlur={() => resumeToast(toast.id)}
          >
            <span className="toast-icon"><Icon size={22} weight="fill" /></span>
            <div className="toast-body">
              <b>{toast.type === 'error' ? 'Xatolik' : toast.type === 'success' ? 'Muvaffaqiyatli' : 'Ogohlantirish'}</b>
              <span>{toast.message}</span>
            </div>
            <button type="button" className="toast-close" onClick={() => dismiss(toast.id)} aria-label="Yopish">
              <X size={18} />
            </button>
            <span
              className="toast-progress"
              style={{ animationDuration: `${toast.durationMs}ms`, animationPlayState: toast.paused ? 'paused' : 'running' }}
              aria-hidden="true"
            />
          </div>
        )
      })}
    </div>
  )
}

export function useNotify() {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())
  const recent = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) { clearTimeout(timer); timers.current.delete(id) }
  }, [])

  const scheduleDismiss = useCallback((id, delayMs) => {
    const timer = setTimeout(() => dismiss(id), delayMs)
    timers.current.set(id, timer)
    return timer
  }, [dismiss])

  const pauseToast = useCallback((id) => {
    const timer = timers.current.get(id)
    if (!timer) return
    clearTimeout(timer)
    timers.current.delete(id)
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, paused: true } : t)))
  }, [])

  const resumeToast = useCallback((id) => {
    setToasts((prev) => {
      const toast = prev.find((t) => t.id === id)
      if (!toast?.paused) return prev
      scheduleDismiss(id, 6000)
      return prev.map((t) => (t.id === id ? { ...t, paused: false } : t))
    })
  }, [scheduleDismiss])

  const notify = useCallback((message, type = 'error') => {
    const formatted = formatError(message)
    const key = `${type}:${formatted}`
    const now = Date.now()
    const lastSeen = recent.current.get(key) || 0
    if (now - lastSeen < 1500) return
    recent.current.set(key, now)
    const id = Date.now() + Math.random()
    const durationMs = TOAST_DURATION[type] || TOAST_DURATION.error
    setToasts((prev) => [...prev, { id, message: formatted, type, durationMs, paused: false }])
    scheduleDismiss(id, durationMs)
  }, [scheduleDismiss])

  return { toasts, notify, dismiss, pauseToast, resumeToast }
}

export default useNotify
