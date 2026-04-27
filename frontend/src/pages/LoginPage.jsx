import { useState } from 'react'
import { useGoogleLogin } from '@react-oauth/google'
import * as api from '../api/client.js'

export default function LoginPage({ onLogin }) {
  const [loading, setLoading] = useState(null)  // 'google' | 'kakao' | null
  const [error, setError] = useState(null)

  // -- Google (auth-code flow for mobile compatibility) ----------------------
  const googleLogin = useGoogleLogin({
    flow: 'auth-code',
    onSuccess: async (codeResponse) => {
      try {
        const user = await api.socialLogin('google', null, codeResponse.code)
        onLogin(user)
      } catch (err) {
        const detail = err.message || 'Unknown error'
        setError(`Google login failed: ${detail}`)
      } finally {
        setLoading(null)
      }
    },
    onError: (errorResponse) => {
      const detail = errorResponse?.error_description || errorResponse?.error || 'cancelled or failed'
      setError(`Google login error: ${detail}`)
      setLoading(null)
    },
    onNonOAuthError: (err) => {
      if (err?.type === 'popup_closed') {
        setError(null) // User closed popup intentionally, don't show error
      } else if (err?.type === 'popup_failed_to_open') {
        setError('Popup was blocked by the browser. Please allow popups for this site.')
      } else {
        setError('Login could not start. Please check your browser settings.')
      }
      setLoading(null)
    },
  })

  function handleGoogleClick() {
    setError(null)
    setLoading('google')
    googleLogin()
  }

  async function handleDevClick() {
    setError(null)
    setLoading('dev')
    try {
      const secret = import.meta.env.VITE_DEV_LOGIN_SECRET
      if (!secret) {
        throw new Error('VITE_DEV_LOGIN_SECRET not set in frontend/.env')
      }
      const user = await api.devLogin(secret)
      onLogin(user)
    } catch (err) {
      setError(`Dev login failed: ${err.message}`)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div style={{
      height: '100vh', overflow: 'hidden', background: 'var(--color-bg)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: 24, position: 'relative',
    }}>
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <h1 style={{ fontSize: 36, fontWeight: 700, margin: '0 0 10px', letterSpacing: '-0.02em' }}>
          <span style={{ color: 'var(--color-text)' }}>Archi</span>
          <span style={{ color: '#ec4899' }}>Tinder</span>
        </h1>
        <p style={{ color: 'var(--color-text-dimmer)', fontSize: 14, margin: 0 }}>
          Discover architecture that inspires you
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%', maxWidth: 320 }}>
        <SocialButton
          onClick={handleGoogleClick}
          loading={loading === 'google'}
          disabled={loading !== null}
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
          }
          label="Continue with Google"
          style={{ background: '#fff', color: '#111', border: '1px solid rgba(0,0,0,0.1)' }}
        />

        {import.meta.env.DEV && (
          <SocialButton
            onClick={handleDevClick}
            loading={loading === 'dev'}
            disabled={loading !== null}
            label="🚀 Dev Login (Bypass)"
            style={{ background: '#2d3139', color: '#ec4899', border: '1px solid #ec4899' }}
          />
        )}
      </div>

      {error && (
        <p style={{
          color: '#f43f5e', fontSize: 13, marginTop: 16, textAlign: 'center',
          maxWidth: 320,
        }}>
          {error}
        </p>
      )}

      <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, marginTop: 32, textAlign: 'center' }}>
        By continuing, you agree to our terms of service
      </p>
    </div>
  )
}

function SocialButton({ onClick, icon, label, style, loading, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        width: '100%', padding: '14px 20px', borderRadius: 14, border: 'none',
        fontSize: 14, fontWeight: 600, cursor: disabled ? 'default' : 'pointer',
        fontFamily: 'inherit', transition: 'opacity 0.15s',
        opacity: disabled ? 0.6 : 1,
        ...style,
      }}
      onMouseEnter={e => { if (!disabled) e.currentTarget.style.opacity = '0.88' }}
      onMouseLeave={e => { if (!disabled) e.currentTarget.style.opacity = '1' }}
    >
      {loading ? (
        <span style={{
          width: 18, height: 18, border: '2px solid currentColor',
          borderTopColor: 'transparent', borderRadius: '50%',
          display: 'inline-block', animation: 'spin 0.7s linear infinite',
        }} />
      ) : icon}
      {label}
    </button>
  )
}
