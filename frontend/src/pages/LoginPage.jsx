/**
 * pages/LoginPage.jsx
 * Single-screen social login: Google (auth-code popup) or Kakao (redirect).
 * First-time users are sent to /onboarding by App.handleLogin
 * (user.onboarding_required) to pick their ID, affiliation and objective.
 *
 * Visual language: business-card ("paper card") — see components/cardLanguage.js.
 */

import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import styles from './LoginPage.module.css'
import * as api from '../api/client.js'
import GoogleLoginButton from '../components/GoogleLoginButton.jsx'
import KakaoLoginButton from '../components/KakaoLoginButton.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import { hasGoogleLogin } from '../utils/loginFlow.js'
import { useTranslation } from '../i18n/index.js'
import { paperFaceStyle, inkGhostStyle } from '../components/cardLanguage.js'

export default function LoginPage({ onLogin }) {
  const { t } = useTranslation()
  const location = useLocation()

  const [loading, setLoading] = useState(null)
  const [error, setError]     = useState(location.state?.error === 'kakao' ? { key: 'login.kakaoFailed' } : null)

  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)
  const isBusy           = loading !== null
  const errorText        = error && (error.key ? t(error.key, error.params) : error.text)

  async function handleGoogleSuccess(codeResponse) {
    setLoading('google')
    setError(null)
    try {
      const user = await api.socialLogin('google', { code: codeResponse.code })
      onLogin(user)
    } catch (err) {
      const detail = err?.data?.detail || err?.message || 'Unknown error'
      setError({ key: 'login.error.googleFailed', params: { detail } })
    } finally {
      setLoading(null)
    }
  }

  function handleGoogleError(errorResponse) {
    const detail = errorResponse?.error_description || errorResponse?.error || 'cancelled or failed'
    setError({ key: 'login.error.googleError', params: { detail } })
    setLoading(null)
  }

  function handleGoogleNonOAuthError(err) {
    if (err?.type === 'popup_closed') {
      setError(null)
    } else if (err?.type === 'popup_failed_to_open') {
      setError({ key: 'login.error.popupBlocked' })
    } else {
      setError({ key: 'login.error.loginStart' })
    }
    setLoading(null)
  }

  async function handleDevClick() {
    setError(null)
    setLoading('dev')
    try {
      const secret = import.meta.env.VITE_DEV_LOGIN_SECRET
      if (!secret) throw new Error('VITE_DEV_LOGIN_SECRET not set in frontend/.env')
      const user = await api.devLogin(secret)
      onLogin(user)
    } catch (err) {
      setError({ key: 'login.error.devFailed', params: { detail: err.message } })
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className={styles.page} style={pageStyle}>
      <PageTopControls />
      <PageLogoHeader style={{ position: 'absolute', top: 0, left: 0 }} />
      <main style={mainStyle}>
        <section className={styles.cardIn} style={cardStyle} aria-label={t('login.google')}>
          <h1 style={titleStyle}>ArchiTinder</h1>
          <p style={taglineStyle}>{t('login.tagline')}</p>

          <div style={buttonColStyle}>
            {googleConfigured && (
              <GoogleLoginButton
                onSuccess={handleGoogleSuccess}
                onError={handleGoogleError}
                onNonOAuthError={handleGoogleNonOAuthError}
                disabled={isBusy}
                loading={loading === 'google'}
                label={t('login.google')}
                className={styles.btn}
                style={{ width: '100%', minHeight: 48, borderRadius: 12 }}
              />
            )}
            <KakaoLoginButton disabled={isBusy} />
          </div>

          {import.meta.env.DEV && (
            <button
              type="button"
              className={styles.btn}
              onClick={handleDevClick}
              disabled={isBusy}
              style={inkGhostStyle(isBusy)}
            >
              {t('login.dev.button')}
            </button>
          )}
        </section>

        <p role="alert" style={errorStyle}>
          {errorText || ''}
        </p>
      </main>
    </div>
  )
}

const pageStyle = {
  minHeight: '100vh',
  display: 'grid',
  placeItems: 'center',
  padding: '64px 16px 16px',
  boxSizing: 'border-box',
}

const mainStyle = {
  width: '100%',
  maxWidth: 380,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: 16,
}

const cardStyle = {
  ...paperFaceStyle({ radius: 20 }),
  width: '100%',
  boxSizing: 'border-box',
  padding: '40px 32px',
  gap: 20,
}

const titleStyle = {
  margin: 0,
  color: 'var(--color-text)',
  fontSize: 28,
  fontWeight: 700,
  letterSpacing: '-0.01em',
  textAlign: 'center',
}

const taglineStyle = {
  margin: 0,
  color: 'var(--color-text-2)',
  fontSize: 15,
  fontWeight: 500,
  lineHeight: 1.55,
  textAlign: 'center',
}

const buttonColStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
}

const errorStyle = {
  minHeight: 35,
  color: 'var(--color-destructive, #D73A49)',
  fontSize: 12,
  fontWeight: 500,
  fontFamily: 'var(--font-family)',
  margin: 0,
  textAlign: 'center',
  lineHeight: 1.45,
}
