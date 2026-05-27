/**
 * pages/LoginPage.jsx
 * Guest-first onboarding wizard (3 steps: intro → name → role).
 * Terminal-style typing animation on each step.
 * PIPA consent capture on intro step before wizard can proceed.
 * "Continue with Google" CTA for returning verified users (no re-consent needed).
 */

import { useEffect, useMemo, useState } from 'react'
import * as api from '../api/client.js'
import {
  ONBOARDING_ROLES,
  buildGuestLoginPayload,
  hasGoogleLogin,
} from '../utils/loginFlow.js'
import GoogleLoginButton from '../components/GoogleLoginButton.jsx'

// Terminal prompt lines per step
const STEP_COPY = {
  intro: ['boot architinder://profile', 'First time here?'],
  name:  ['guest profile selected',     'What should we call you?'],
  role:  ['name saved',                 'Which one fits you best?'],
}

export default function LoginPage({ onLogin }) {
  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)

  // Wizard state
  const [step, setStep] = useState('intro')
  const [consentGiven, setConsentGiven] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('')

  // Terminal typing animation
  const [typedLine, setTypedLine] = useState('')
  const terminalLines = useMemo(() => STEP_COPY[step] || STEP_COPY.intro, [step])
  const activeLine = terminalLines[terminalLines.length - 1]

  useEffect(() => {
    setTypedLine('')
    let index = 0
    const timer = window.setInterval(() => {
      index += 1
      setTypedLine(activeLine.slice(0, index))
      if (index >= activeLine.length) window.clearInterval(timer)
    }, 24)
    return () => window.clearInterval(timer)
  }, [activeLine])

  // Loading and error state
  const [loading, setLoading] = useState(null)  // 'guest' | 'google' | 'dev' | null
  const [error, setError] = useState(null)

  const isBusy = loading !== null

  // -- Google (returning verified users, auth-code flow) ---------------------
  // useGoogleLogin is NOT called here — it lives inside GoogleLoginButton,
  // which is only mounted when googleConfigured === true (inside GoogleOAuthProvider).

  async function handleGoogleSuccess(codeResponse) {
    setLoading('google')
    try {
      const user = await api.socialLogin('google', null, codeResponse.code)
      onLogin(user)
    } catch (err) {
      const detail = err.message || 'Unknown error'
      setError(`Google login failed: ${detail}`)
    } finally {
      setLoading(null)
    }
  }

  function handleGoogleError(errorResponse) {
    const detail = errorResponse?.error_description || errorResponse?.error || 'cancelled or failed'
    setError(`Google login error: ${detail}`)
    setLoading(null)
  }

  function handleGoogleNonOAuthError(err) {
    if (err?.type === 'popup_closed') {
      setError(null)
    } else if (err?.type === 'popup_failed_to_open') {
      setError('Popup was blocked by the browser. Please allow popups for this site.')
    } else {
      setError('Login could not start. Please check your browser settings.')
    }
    setLoading(null)
  }

  // -- Guest (wizard submit) ------------------------------------------------
  async function handleGuestSubmit(event) {
    event?.preventDefault()
    setError(null)
    setLoading('guest')
    try {
      const user = await api.guestLogin(buildGuestLoginPayload({ displayName, role }))
      onLogin(user)
    } catch (err) {
      const detail = err?.data?.detail || err?.message || 'Unknown error'
      if (detail === 'consent_required') {
        setError('Consent is required to continue. Please accept the terms on the first screen.')
        setStep('intro')
        setConsentGiven(false)
      } else {
        setError(`Sign in failed: ${detail}`)
      }
    } finally {
      setLoading(null)
    }
  }

  // -- Dev bypass (dev env only) --------------------------------------------
  async function handleDevClick() {
    setError(null)
    setLoading('dev')
    try {
      const secret = import.meta.env.VITE_DEV_LOGIN_SECRET
      if (!secret) throw new Error('VITE_DEV_LOGIN_SECRET not set in frontend/.env')
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
      minHeight: '100vh',
      background: 'var(--color-bg)',
      display: 'grid',
      placeItems: 'center',
      padding: 24,
    }}>
      <main style={{
        width: '100%',
        maxWidth: 420,
        display: 'flex',
        flexDirection: 'column',
        gap: 22,
      }}>
        {/* Wordmark */}
        <header style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <h1 style={{ fontSize: 34, fontWeight: 700, margin: 0, letterSpacing: 0 }}>
            <span style={{ color: 'var(--color-text)' }}>Archi</span>
            <span style={{ color: 'var(--accent-1, #0969DA)' }}>Tinder</span>
          </h1>
          <p style={{ color: 'var(--color-text-dimmer)', fontSize: 14, margin: 0 }}>
            Build a taste profile before you build a board.
          </p>
        </header>

        {/* Terminal card */}
        <section
          style={{
            border: '1px solid var(--color-border)',
            borderRadius: 8,
            background: 'var(--color-surface)',
            padding: 18,
            boxShadow: '0 18px 40px rgba(0,0,0,0.14)',
          }}
          aria-label="Onboarding wizard"
        >
          {/* Terminal display */}
          <div
            aria-hidden="true"
            style={{
              minHeight: 104,
              borderRadius: 6,
              background: '#111827',
              border: '1px solid rgba(255,255,255,0.10)',
              padding: 14,
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
              fontSize: 13,
              lineHeight: 1.7,
              color: '#e5e7eb',
            }}
          >
            <div style={{ color: '#94a3b8' }}>$ {terminalLines[0]}</div>
            <div>
              <span style={{ color: 'var(--accent-1, #0969DA)' }}>&gt; </span>
              {typedLine}
              <span style={{ opacity: typedLine.length === activeLine.length ? 1 : 0 }}>_</span>
            </div>
          </div>

          {/* Step content */}
          <div style={{ marginTop: 18 }}>
            {step === 'intro' && (
              <IntroStep
                disabled={isBusy}
                consentGiven={consentGiven}
                onConsentToggle={() => setConsentGiven(prev => !prev)}
                onNew={() => {
                  setError(null)
                  setStep('name')
                }}
                showGoogle={googleConfigured}
                googleLoading={loading === 'google'}
                onGoogleSuccess={handleGoogleSuccess}
                onGoogleError={handleGoogleError}
                onGoogleNonOAuthError={handleGoogleNonOAuthError}
              />
            )}

            {step === 'name' && (
              <NameStep
                value={displayName}
                disabled={isBusy}
                onChange={setDisplayName}
                onBack={() => setStep('intro')}
                onNext={() => {
                  setError(null)
                  setStep('role')
                }}
              />
            )}

            {step === 'role' && (
              <RoleStep
                value={role}
                disabled={isBusy}
                loading={loading === 'guest'}
                onChange={setRole}
                onBack={() => setStep('name')}
                onSubmit={handleGuestSubmit}
              />
            )}
          </div>
        </section>

        {/* Dev bypass */}
        {import.meta.env.DEV && (
          <button
            type="button"
            onClick={handleDevClick}
            disabled={isBusy}
            style={secondaryButtonStyle(isBusy)}
          >
            {loading === 'dev' ? <Spinner /> : 'Dev login'}
          </button>
        )}

        {/* Error display */}
        {error && (
          <p role="alert" style={{
            color: 'var(--color-destructive, #D73A49)',
            fontSize: 13,
            margin: 0,
            textAlign: 'center',
          }}>
            {error}
          </p>
        )}
      </main>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Intro step — PIPA consent capture + both CTAs
// ---------------------------------------------------------------------------
function IntroStep({
  disabled, consentGiven, onConsentToggle, onNew,
  showGoogle, googleLoading,
  onGoogleSuccess, onGoogleError, onGoogleNonOAuthError,
}) {
  // "Yes, start here" requires consent. "Continue with Google" is always available.
  // GoogleLoginButton is ONLY rendered when showGoogle === true, keeping the
  // useGoogleLogin hook inside GoogleOAuthProvider at all times.
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      {/* PIPA consent block */}
      <div style={{
        borderRadius: 8,
        border: `1px solid ${consentGiven ? 'var(--accent-1, #0969DA)' : 'var(--color-border)'}`,
        background: consentGiven
          ? 'rgba(9,105,218,0.06)'
          : 'var(--color-surface)',
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}>
        <p style={{
          margin: 0,
          fontSize: 12,
          color: 'var(--color-text-dimmer)',
          lineHeight: 1.55,
        }}>
          이름·이메일 수집·이용에 동의합니다.{' '}
          <span style={{ color: 'var(--color-text-dimmest, #8C959F)' }}>
            (개인정보 처리 목적: 서비스 제공)
          </span>
        </p>
        <button
          type="button"
          onClick={onConsentToggle}
          disabled={disabled}
          aria-pressed={consentGiven}
          aria-label={consentGiven ? '동의 취소' : '동의합니다'}
          style={{
            alignSelf: 'flex-start',
            padding: '5px 14px',
            borderRadius: 6,
            border: `1px solid ${consentGiven ? 'var(--accent-1, #0969DA)' : 'var(--color-border)'}`,
            background: consentGiven ? 'var(--accent-1, #0969DA)' : 'transparent',
            color: consentGiven ? '#fff' : 'var(--color-text)',
            fontSize: 12,
            fontWeight: 600,
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
            cursor: disabled ? 'default' : 'pointer',
            opacity: disabled ? 0.65 : 1,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          {consentGiven && (
            <span aria-hidden="true" style={{ fontSize: 13 }}>✓</span>
          )}
          {consentGiven ? '동의됨' : '동의합니다'}
        </button>
      </div>

      {/* Primary CTA — requires consent */}
      <button
        type="button"
        onClick={onNew}
        disabled={disabled || !consentGiven}
        aria-label="Start guest onboarding wizard"
        style={primaryButtonStyle(disabled || !consentGiven)}
      >
        Yes, start here
      </button>

      {/* Divider */}
      {showGoogle && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          color: 'var(--color-text-dimmest, #8C959F)',
          fontSize: 11,
        }}>
          <div style={{ flex: 1, height: 1, background: 'var(--color-border)' }} />
          <span>or returning user</span>
          <div style={{ flex: 1, height: 1, background: 'var(--color-border)' }} />
        </div>
      )}

      {/* Google CTA — conditionally rendered so useGoogleLogin stays inside GoogleOAuthProvider */}
      {showGoogle && (
        <GoogleLoginButton
          onSuccess={onGoogleSuccess}
          onError={onGoogleError}
          onNonOAuthError={onGoogleNonOAuthError}
          disabled={disabled}
          loading={googleLoading}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Name step
// ---------------------------------------------------------------------------
function NameStep({ value, disabled, onChange, onBack, onNext }) {
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onNext() }}
      style={{ display: 'grid', gap: 12 }}
    >
      <input
        autoFocus
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        placeholder="Guest"
        maxLength={30}
        aria-label="Display name"
        style={inputStyle}
      />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <button
          type="button"
          onClick={onBack}
          disabled={disabled}
          aria-label="Back to intro"
          style={secondaryButtonStyle(disabled)}
        >
          Back
        </button>
        <button
          type="submit"
          disabled={disabled}
          aria-label="Proceed to role selection"
          style={primaryButtonStyle(disabled)}
        >
          Next
        </button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Role step
// ---------------------------------------------------------------------------
function RoleStep({ value, disabled, loading, onChange, onBack, onSubmit }) {
  return (
    <form onSubmit={onSubmit} style={{ display: 'grid', gap: 12 }}>
      <div
        role="radiogroup"
        aria-label="Select your role"
        style={{ display: 'grid', gap: 8 }}
      >
        {ONBOARDING_ROLES.map(roleOption => (
          <button
            key={roleOption.value}
            type="button"
            role="radio"
            aria-checked={value === roleOption.value}
            onClick={() => onChange(roleOption.value)}
            disabled={disabled}
            style={roleButtonStyle(disabled, value === roleOption.value)}
          >
            {roleOption.label}
          </button>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <button
          type="button"
          onClick={onBack}
          disabled={disabled}
          aria-label="Back to name step"
          style={secondaryButtonStyle(disabled)}
        >
          Back
        </button>
        <button
          type="submit"
          disabled={disabled}
          aria-label="Create guest account and enter"
          style={primaryButtonStyle(disabled)}
        >
          {loading ? <Spinner /> : 'Enter'}
        </button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Shared micro-components
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------

function primaryButtonStyle(disabled) {
  return {
    minHeight: 46,
    borderRadius: 8,
    border: '1px solid var(--accent-1, #0969DA)',
    background: 'var(--accent-1, #0969DA)',
    color: '#fff',
    fontSize: 14,
    fontWeight: 700,
    fontFamily: 'inherit',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.55 : 1,
  }
}

function secondaryButtonStyle(disabled) {
  return {
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
  }
}

function roleButtonStyle(disabled, active) {
  return {
    minHeight: 42,
    borderRadius: 8,
    border: active ? '1px solid var(--accent-1, #0969DA)' : '1px solid var(--color-border)',
    background: active ? 'rgba(9,105,218,0.12)' : 'transparent',
    color: active ? 'var(--accent-1, #0969DA)' : 'var(--color-text)',
    textAlign: 'left',
    padding: '0 13px',
    fontSize: 14,
    fontWeight: 600,
    fontFamily: 'inherit',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.65 : 1,
  }
}

const inputStyle = {
  minHeight: 46,
  borderRadius: 8,
  border: '1px solid var(--color-border)',
  background: 'var(--color-bg)',
  color: 'var(--color-text)',
  padding: '0 13px',
  fontSize: 15,
  fontFamily: 'inherit',
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
}
