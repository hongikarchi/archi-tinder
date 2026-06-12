/**
 * components/GoogleLoginButton.jsx
 * Thin wrapper that calls useGoogleLogin inside a GoogleOAuthProvider-guarded tree.
 * ONLY mount this component when googleConfigured === true (parent's responsibility).
 * Encapsulates the hook so LoginPage never calls useGoogleLogin unconditionally.
 */

import { useGoogleLogin } from '@react-oauth/google'

function Spinner() {
  return (
    <span aria-hidden="true" style={{
      width: 18,
      height: 18,
      border: '2px solid currentColor',
      borderTopColor: 'transparent',
      borderRadius: '50%',
      display: 'inline-block',
      animation: 'spin 0.7s linear infinite',
    }} />
  )
}

function GoogleIcon() {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
  )
}

/**
 * Props:
 *   onSuccess  (codeResponse) => void  — called with the auth-code response
 *   onError    (errorResponse) => void — called on OAuth error
 *   onNonOAuthError (err) => void      — called on popup-close / popup-failed
 *   disabled   bool
 *   loading    bool                    — shows spinner when true
 *   style      object                  — merged into button style
 *   label      string                  — button label text (default 'Continue with Google')
 *   className  string                  — extra class(es) applied to button element
 */
export default function GoogleLoginButton({ onSuccess, onError, onNonOAuthError, disabled, loading, style, label = 'Continue with Google', className }) {
  const googleLogin = useGoogleLogin({
    flow: 'auth-code',
    onSuccess,
    onError,
    onNonOAuthError,
  })

  const baseStyle = {
    minHeight: 46,
    borderRadius: 8,
    border: '1px solid var(--color-border)',
    background: 'var(--color-surface)',
    color: 'var(--color-text)',
    fontSize: 14,
    fontWeight: 600,
    fontFamily: 'inherit',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.65 : 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  }

  return (
    <button
      type="button"
      className={className}
      onClick={() => googleLogin()}
      disabled={disabled}
      aria-label="Continue with Google for existing accounts"
      style={{ ...baseStyle, ...style }}
    >
      {loading ? <Spinner /> : <GoogleIcon />}
      {label}
    </button>
  )
}
