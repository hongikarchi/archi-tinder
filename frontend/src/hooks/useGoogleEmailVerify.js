/**
 * hooks/useGoogleEmailVerify.js
 *
 * Shared Google email-verify flow used by BOTH:
 *   - src/pages/settings/AccountScreen.jsx  ("구글로 이메일 인증" button)
 *   - src/components/VerifyGateModal.jsx    ("이메일 인증하러 가기" button)
 *
 * IMPORTANT: These two surfaces MUST stay functionally identical.
 * Do NOT inline this logic in either site — always edit this hook.
 * If you need to change the verify flow, change it HERE only.
 *
 * The hook calls POST /auth/link-email/ with the Google auth-code, then
 * re-fetches GET /auth/me/ to obtain the fresh UserSerializer state.
 * No token swap occurs (link-email does not issue new tokens).
 *
 * Usage:
 *   const { loading, error, onSuccess, onError, onNonOAuthError } =
 *     useGoogleEmailVerify({ onVerified })
 *
 *   onVerified(freshUser: object) — called on success with the re-fetched user.
 *   Callers are responsible for clearing any local error state passed in via
 *   an external setter if needed, but this hook manages its own `error` state
 *   for display purposes.
 *
 * error shape: { key: string, params?: object } — consumers must call
 *   t(error.key, error.params) to render the message.
 *   This matches the FRONT-AUTH-3 {key,params} precedent from LoginPage.
 *   useTranslation is NOT called here (hooks rules — this is a plain hook,
 *   not a component; consumers handle the render layer).
 */

import { useState } from 'react'
import { linkEmail as apiLinkEmail, getMe } from '../api/client.js'

/**
 * @param {object} options
 * @param {(freshUser: object) => void} options.onVerified
 *   Called after link-email succeeds + getMe() refresh completes.
 *   Receives the freshly fetched user object.
 */
export function useGoogleEmailVerify({ onVerified }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  /**
   * GoogleVerifyButton onSuccess handler.
   * codeResponse — the object from useGoogleLogin's callback, must have .code
   */
  async function onSuccess(codeResponse) {
    setLoading(true)
    setError(null)
    try {
      await apiLinkEmail(codeResponse.code)
      // Re-fetch /auth/me/ to get fresh email + email_verified_at.
      // link-email returns UserSerializer which may omit self-only fields;
      // re-fetch guarantees accurate state and is_guest = false.
      const fresh = await getMe()
      onVerified(fresh)
    } catch (err) {
      const detail = err?.data?.detail || err?.message || 'error'
      if (detail === 'unverified_email') {
        setError({ key: 'auth.verifyUnverifiedEmail' })
      } else if (detail === 'email_already_linked') {
        setError({ key: 'auth.verifyAlreadyLinked' })
      } else {
        setError({ key: 'auth.verifyFailed', params: { detail } })
      }
    } finally {
      setLoading(false)
    }
  }

  /** GoogleVerifyButton onError handler (OAuth-level error from Google). */
  function onError(errorResponse) {
    const detail =
      errorResponse?.error_description || errorResponse?.error || 'cancelled or failed'
    setError({ key: 'auth.verifyGoogleError', params: { detail } })
    setLoading(false)
  }

  /** GoogleVerifyButton onNonOAuthError handler (popup blocked / closed). */
  function onNonOAuthError(err) {
    if (err?.type === 'popup_closed') {
      setError(null)
    } else if (err?.type === 'popup_failed_to_open') {
      setError({ key: 'auth.verifyPopupBlocked' })
    } else {
      setError({ key: 'auth.verifyCannotStart' })
    }
    setLoading(false)
  }

  return { loading, error, onSuccess, onError, onNonOAuthError }
}
