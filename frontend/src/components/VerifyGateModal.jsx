/**
 * components/VerifyGateModal.jsx
 * Shown when a guest user tries to create a 4th board (board_limit_reached).
 * Terminal-aesthetic copy matches the LoginPage wizard.
 * On Google verify success → promotes account → swaps JWTs → closes modal.
 *
 * Mounted globally in App.jsx. Listens for 'archithon:verify-required' event.
 */

import { useState } from 'react'
import { promoteAccount } from '../api/auth.js'
import { hasGoogleLogin } from '../utils/loginFlow.js'
import GoogleVerifyButton from './GoogleVerifyButton.jsx'

export default function VerifyGateModal({ onClose, onPromoted }) {
  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // useGoogleLogin is NOT called here — it lives inside GoogleVerifyButton,
  // which is only rendered when googleConfigured === true (inside GoogleOAuthProvider).

  async function handleVerifySuccess(codeResponse) {
    setLoading(true)
    setError(null)
    try {
      const data = await promoteAccount(codeResponse.code)
      // promoteAccount swaps JWTs in localStorage automatically.
      // Pass user + merged flag so App.jsx can re-sync state correctly.
      onPromoted(data.user, data.merged)
      onClose()
    } catch (err) {
      const detail = err?.data?.detail || err?.message || 'Verification failed'
      // Fix 2: backend returns 400 + detail:'not_a_guest' when the guest was
      // already promoted (e.g. another tab completed the flow).
      if (err?.status === 400 && detail === 'not_a_guest') {
        // Treat as success — the account is already verified.
        onPromoted(null, false)
        onClose()
      } else {
        setError(`Google verify failed: ${detail}`)
      }
    } finally {
      setLoading(false)
    }
  }

  function handleVerifyError(errorResponse) {
    const detail = errorResponse?.error_description || errorResponse?.error || 'cancelled or failed'
    setError(`Google error: ${detail}`)
    setLoading(false)
  }

  function handleVerifyNonOAuthError(err) {
    if (err?.type === 'popup_closed') {
      setError(null)
    } else if (err?.type === 'popup_failed_to_open') {
      setError('Popup was blocked. Please allow popups for this site.')
    } else {
      setError('Verification could not start. Check browser settings.')
    }
    setLoading(false)
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="verify-gate-title"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10100,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(94vw, 440px)',
          background: 'var(--color-surface)',
          borderRadius: 16,
          border: '1px solid var(--color-border)',
          color: 'var(--color-text)',
          overflow: 'hidden',
          boxShadow: '0 18px 40px rgba(0,0,0,0.28)',
        }}
      >
        {/* Terminal header block */}
        <div style={{
          background: '#111827',
          border: '0',
          borderBottom: '1px solid rgba(255,255,255,0.10)',
          padding: '16px 18px 14px',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
          fontSize: 13,
          lineHeight: 1.7,
          color: '#e5e7eb',
        }}>
          <div style={{ color: '#94a3b8' }}>$ board.create --count 4</div>
          <div>
            <span style={{ color: '#ef4444' }}>&gt; </span>
            <span>trial limit reached (3/3 boards used)</span>
          </div>
          <div>
            <span style={{ color: '#94a3b8' }}># </span>
            <span style={{ color: '#fbbf24' }}>verify with Google to continue</span>
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: '20px 20px 8px' }}>
          <h2
            id="verify-gate-title"
            style={{ fontSize: 17, fontWeight: 700, margin: '0 0 8px', color: 'var(--color-text)' }}
          >
            3 boards = trial limit
          </h2>
          <p style={{
            fontSize: 14,
            color: 'var(--color-text-dimmer)',
            margin: '0 0 20px',
            lineHeight: 1.55,
          }}>
            Verify with Google to unlock unlimited boards and keep all your data.
          </p>

          {error && (
            <p style={{
              color: 'var(--color-destructive, #D73A49)',
              fontSize: 13,
              margin: '0 0 14px',
              lineHeight: 1.4,
            }}>
              {error}
            </p>
          )}

          <div style={{ display: 'grid', gap: 10 }}>
            {/* GoogleVerifyButton conditionally rendered so hook stays inside GoogleOAuthProvider */}
            {googleConfigured ? (
              <GoogleVerifyButton
                onSuccess={handleVerifySuccess}
                onError={handleVerifyError}
                onNonOAuthError={handleVerifyNonOAuthError}
                disabled={loading}
                loading={loading}
              />
            ) : (
              <p style={{
                fontSize: 13,
                color: 'var(--color-text-dimmer)',
                margin: 0,
                textAlign: 'center',
              }}>
                Google verification is not available in this environment.
              </p>
            )}

            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              aria-label="Cancel verification"
              style={{
                minHeight: 46,
                borderRadius: 8,
                border: '1px solid var(--color-border)',
                background: 'transparent',
                color: 'var(--color-text)',
                fontSize: 14,
                fontWeight: 600,
                fontFamily: 'inherit',
                cursor: loading ? 'default' : 'pointer',
                opacity: loading ? 0.5 : 1,
              }}
            >
              Not now
            </button>
          </div>
        </div>

        {/* Legal footer */}
        <p style={{
          fontSize: 11,
          color: 'var(--color-text-dimmest, #8C959F)',
          margin: '12px 20px 16px',
          lineHeight: 1.45,
          textAlign: 'center',
        }}>
          Verification links your existing boards and swipe history to your Google account.
          No data is lost.
        </p>
      </div>
    </div>
  )
}
