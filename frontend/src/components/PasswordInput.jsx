/**
 * PasswordInput — <input> with a show/hide toggle.
 * Passes every prop through to the input (ref via forwardRef); only `type` is owned here.
 * The toggle never steals focus (mousedown preventDefault) so caret position is kept.
 */
import { forwardRef, useState } from 'react'
import { useTranslation } from '../i18n/index.js'
import styles from './PasswordInput.module.css'

const PasswordInput = forwardRef(function PasswordInput({ style, disabled, ...rest }, ref) {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(false)
  const label = visible ? t('auth.hidePassword') : t('auth.showPassword')

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <input
        {...rest}
        ref={ref}
        disabled={disabled}
        type={visible ? 'text' : 'password'}
        style={{ ...style, paddingRight: 44 }}
      />
      <button
        type="button"
        className={`pressable ${styles.toggle}`}
        aria-label={label}
        aria-pressed={visible}
        title={label}
        disabled={disabled}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => setVisible(v => !v)}
      >
        {visible ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
            <line x1="1" y1="1" x2="23" y2="23" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        )}
      </button>
    </div>
  )
})

export default PasswordInput
