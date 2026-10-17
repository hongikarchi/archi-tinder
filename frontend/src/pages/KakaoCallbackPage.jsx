/**
 * pages/KakaoCallbackPage.jsx
 * Receives ?code&state from Kakao, verifies state, exchanges the code via the
 * backend, then hands the user to App's handleLogin.
 */

import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { socialLogin } from '../api/auth.js'
import { KAKAO_STATE_KEY } from '../components/KakaoLoginButton.jsx'
import RouteFallback from '../components/RouteFallback.jsx'

export default function KakaoCallbackPage({ onLogin }) {
  const navigate = useNavigate()
  const ranRef = useRef(false)

  useEffect(() => {
    // The auth code is single-use: guard against StrictMode double-invoke.
    if (ranRef.current) return
    ranRef.current = true

    const fail = () => navigate('/login', { replace: true, state: { error: 'kakao' } })
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const state = params.get('state')
    const expected = sessionStorage.getItem(KAKAO_STATE_KEY)
    sessionStorage.removeItem(KAKAO_STATE_KEY)

    if (params.get('error') || !code || !state || state !== expected) {
      fail()
      return
    }

    socialLogin('kakao', { code, redirect_uri: window.location.origin + '/auth/kakao/callback' })
      .then(user => onLogin(user))
      .catch(fail)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return <RouteFallback />
}
