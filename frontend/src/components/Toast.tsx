import s from './Toast.module.css'

/**
 * Toast — small bottom-center pill (DESIGN.md §8.11, persona-report mock).
 * Presentational only: the owner (see hooks/useRegeneration) controls the message
 * and the 2 s lifetime. `message` falsy → renders nothing. `role="status"`.
 */
interface ToastProps {
  // TODO(ts): callers pass a string or { key, text }; property access on the union needs a runtime narrow (no logic edits)
  message?: any
}

export default function Toast({ message }: ToastProps) {
  if (!message) return null
  return (
    <div key={message.key ?? message} className={s.toast} role="status" aria-live="polite">
      {message.text ?? message}
    </div>
  )
}
