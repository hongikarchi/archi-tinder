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
 *
 * UI-CONSISTENCY-B Phase 2b: rebuilt on the shared `Modal` component (chosen
 * as the simplest existing modal to prove it out). Visual changes vs. the
 * previous hand-rolled dialog: backdrop `--color-scrim-soft` (0.55) ->
 * `--color-scrim-modal` (0.4, DESIGN.md §1.4/§8.10 standard); width 440 ->
 * 480; radius 16 -> `--radius-md` (12); title 17px -> `--fs-heading` (20px);
 * gained a top-right (X) close button; now renders as a mobile bottom sheet
 * (<=768px) instead of always being a centered box. `zIndex={10100}`
 * preserved so it still stacks above SaveToBoardModal.
 */

import { hasGoogleLogin } from '../utils/loginFlow.js'
import { useGoogleEmailVerify } from '../hooks/useGoogleEmailVerify.js'
import { useTranslation } from '../i18n/index.js'
import GoogleVerifyButton from './GoogleVerifyButton.jsx'
import Modal from './Modal.jsx'

export default function VerifyGateModal({ onClose, onPromoted }) {
  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)
  const { t } = useTranslation()

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
    <Modal
      open
      onClose={onClose}
      title={t('auth.gateTitle')}
      zIndex={10100}
      closeLabel={t('auth.gateCancelAria')}
    >
      <p style={{
        fontSize: 14,
        color: 'var(--color-text-dimmer)',
        margin: '0 0 20px',
        lineHeight: 1.55,
      }}>
        {t('auth.gateBody')}
      </p>

      {error && (
        <p style={{
          color: 'var(--color-destructive, #D73A49)',
          fontSize: 13,
          margin: '0 0 14px',
          lineHeight: 1.4,
        }}>
          {t(error.key, error.params)}
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
            label={t('auth.gateVerifyBtn')}
          />
        ) : (
          <p style={{
            fontSize: 13,
            color: 'var(--color-text-dimmer)',
            margin: 0,
            textAlign: 'center',
          }}>
            {t('auth.gateGoogleUnavailable')}
          </p>
        )}

        <button
          type="button"
          onClick={onClose}
          disabled={loading}
          aria-label={t('auth.gateCancelAria')}
          style={{
            minHeight: 46,
            borderRadius: 'var(--radius-md)',
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
          {t('auth.gateLater')}
        </button>
      </div>

      {/* Legal footer */}
      <p style={{
        fontSize: 11,
        color: 'var(--color-text-dimmest, #8C959F)',
        margin: '16px 0 0',
        lineHeight: 1.45,
        textAlign: 'center',
      }}>
        {t('auth.gateFooter')}
      </p>
    </Modal>
  )
}
