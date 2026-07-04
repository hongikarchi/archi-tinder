/**
 * components/VerifyGateModal.jsx
 * Shown when a guest user tries to create a 4th board (board_limit_reached).
 * Terminal-aesthetic copy matches the LoginPage wizard.
 * On Google verify success → links email (POST /auth/link-email/) → flips
 * is_guest=False → re-fetches /auth/me/ → calls onPromoted(freshUser, false)
 * → closes modal.
 *
 * Mounted globally in App.jsx. Listens for 'archithon:verify-required' event.
 *
 * Verify flow: uses useGoogleEmailVerify (same as AccountScreen "구글로 이메일 인증").
 * To change the verify logic, edit src/hooks/useGoogleEmailVerify.js — NOT this file.
 */

import { hasGoogleLogin } from '../utils/loginFlow.js'
import { useGoogleEmailVerify } from '../hooks/useGoogleEmailVerify.js'
import GoogleVerifyButton from './GoogleVerifyButton.jsx'

export default function VerifyGateModal({ onClose, onPromoted }) {
  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)

  // useGoogleLogin is NOT called here — it lives inside GoogleVerifyButton,
  // which is only rendered when googleConfigured === true (inside GoogleOAuthProvider).

  // Shared verify hook — identical flow to AccountScreen "구글로 이메일 인증".
  // onVerified: guest is now verified (is_guest=false). Pass freshUser to
  // onPromoted so App.jsx can re-sync state, then close the modal.
  const {
    loading,
    error,
    onSuccess: handleVerifySuccess,
    onError: handleVerifyError,
    onNonOAuthError: handleVerifyNonOAuthError,
  } = useGoogleEmailVerify({
    onVerified: (freshUser) => {
      // link-email does NOT merge accounts (no token swap, no merged flag).
      // Treat as in-place promote: merged=false, pass the fresh user object.
      onPromoted(freshUser, false)
      onClose()
    },
  })

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
        {/* Body */}
        <div style={{ padding: '20px 20px 8px' }}>
          <h2
            id="verify-gate-title"
            style={{ fontSize: 17, fontWeight: 700, margin: '0 0 8px', color: 'var(--color-text)' }}
          >
            guest 계정은 보드를 3개까지만 생성할 수 있습니다.
          </h2>
          <p style={{
            fontSize: 14,
            color: 'var(--color-text-dimmer)',
            margin: '0 0 20px',
            lineHeight: 1.55,
          }}>
            이메일 인증 후 무제한으로 보드를 만들고, 지금까지의 데이터를 유지할 수 있습니다.
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
                label="이메일 인증하러 가기"
              />
            ) : (
              <p style={{
                fontSize: 13,
                color: 'var(--color-text-dimmer)',
                margin: 0,
                textAlign: 'center',
              }}>
                Google 인증을 사용할 수 없는 환경입니다.
              </p>
            )}

            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              aria-label="인증 취소"
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
              나중에
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
          인증 시 기존 보드와 스와이프 기록이 Google 계정에 연결됩니다.
          데이터는 사라지지 않습니다.
        </p>
      </div>
    </div>
  )
}
