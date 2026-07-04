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
        setError('이메일 미인증: Google 계정의 이메일이 인증되지 않았습니다.')
      } else if (detail === 'email_already_linked') {
        setError('이미 존재하는 계정입니다. 다른 구글 계정으로 인증해 주세요.')
      } else {
        setError(`인증 실패: ${detail}`)
      }
    } finally {
      setLoading(false)
    }
  }

  /** GoogleVerifyButton onError handler (OAuth-level error from Google). */
  function onError(errorResponse) {
    const detail =
      errorResponse?.error_description || errorResponse?.error || 'cancelled or failed'
    setError(`Google 오류: ${detail}`)
    setLoading(false)
  }

  /** GoogleVerifyButton onNonOAuthError handler (popup blocked / closed). */
  function onNonOAuthError(err) {
    if (err?.type === 'popup_closed') {
      setError(null)
    } else if (err?.type === 'popup_failed_to_open') {
      setError('팝업이 차단되었습니다. 사이트의 팝업을 허용해 주세요.')
    } else {
      setError('인증을 시작할 수 없습니다. 브라우저 설정을 확인해 주세요.')
    }
    setLoading(false)
  }

  return { loading, error, onSuccess, onError, onNonOAuthError }
}
