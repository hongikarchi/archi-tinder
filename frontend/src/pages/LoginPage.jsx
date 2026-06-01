/**
 * pages/LoginPage.jsx
 * Conversational swipe onboarding for returning Google users and new guests.
 */

import { useEffect, useRef, useState } from 'react'
import * as api from '../api/client.js'
import GoogleLoginButton from '../components/GoogleLoginButton.jsx'
import { CARD_HEIGHT, CARD_WIDTH } from '../components/SwipeCard.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'
import { SWIPE_PREVENT_ALL, SWIPE_PREVENT_VERTICAL } from '../components/swipeGestureConfig.js'
import {
  LOGIN_SWIPE_ACTIONS,
  ONBOARDING_ROLES,
  buildGuestLoginPayload,
  getLoginSwipeAction,
  hasGoogleLogin,
  isDisplayNameReady,
  isGuestProfileReady,
  isRoleReady,
} from '../utils/loginFlow.js'

const FLOW_STEPS = {
  choice: 'choice',
  returning: 'returning',
  profile: 'profile',
  consent: 'consent',
}

const STEP_PROMPTS = {
  choice: 'Tell me how to welcome you.',
  returning: 'I can restore your verified profile.',
  profile: 'A name and objective shape your first deck.',
  consent: 'One right swipe creates the guest profile.',
}

const AUTH_STAGE_WIDTH = `${CARD_WIDTH}px`
const AUTH_CARD_HEIGHT = `${CARD_HEIGHT}px`

export default function LoginPage({ onLogin }) {
  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)
  const pendingChoiceAction = useRef(null)
  const pendingConsentAction = useRef(null)

  const [step, setStep] = useState(FLOW_STEPS.choice)
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('')
  const [consentGiven, setConsentGiven] = useState(false)
  const [consentResetTick, setConsentResetTick] = useState(0)
  const [loading, setLoading] = useState(null) // 'guest' | 'google' | 'dev' | null
  const [error, setError] = useState(null)

  const typedLine = useTypedLine(STEP_PROMPTS[step] || STEP_PROMPTS.choice)
  const isBusy = loading !== null
  const profileReady = isGuestProfileReady({ displayName, role })

  function moveToStep(nextStep) {
    setError(null)
    setStep(nextStep)
  }

  function handleChoiceAction(action) {
    pendingChoiceAction.current = null
    setConsentGiven(false)
    if (action === LOGIN_SWIPE_ACTIONS.left) {
      moveToStep(FLOW_STEPS.returning)
    } else if (action === LOGIN_SWIPE_ACTIONS.right) {
      moveToStep(FLOW_STEPS.profile)
    }
  }

  function handleChoiceSwipe(direction) {
    const action = getLoginSwipeAction(direction)
    if (action) pendingChoiceAction.current = action
  }

  function handleChoiceLeftScreen() {
    if (pendingChoiceAction.current) {
      handleChoiceAction(pendingChoiceAction.current)
    }
  }

  async function handleGoogleSuccess(codeResponse) {
    setLoading('google')
    setError(null)
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

  function handleProfileContinue(event) {
    event.preventDefault()
    setError(null)
    if (!isDisplayNameReady(displayName)) {
      setError('Enter a display name to continue.')
      return
    }
    if (!isRoleReady(role)) {
      setError('Choose an objective to continue.')
      return
    }
    setConsentGiven(false)
    moveToStep(FLOW_STEPS.consent)
  }

  async function handleGuestSubmit({ consentConfirmed = consentGiven } = {}) {
    if (isBusy) return
    setError(null)
    if (!isGuestProfileReady({ displayName, role })) {
      setError('Add a display name and objective before consent.')
      setStep(FLOW_STEPS.profile)
      return
    }
    if (!consentConfirmed) {
      setError('Consent is required before creating a guest profile.')
      return
    }

    setLoading('guest')
    try {
      const user = await api.guestLogin(buildGuestLoginPayload({ displayName, role }))
      onLogin(user)
    } catch (err) {
      const detail = err?.data?.detail || err?.message || 'Unknown error'
      if (detail === 'consent_required') {
        setError('Consent is required to continue. Please try the consent step again.')
        setConsentGiven(false)
      } else {
        setError(`Sign in failed: ${detail}`)
      }
      setConsentResetTick(t => t + 1)
    } finally {
      setLoading(null)
    }
  }

  function handleConsentSwipe(direction) {
    if (isBusy) return
    if (direction === 'left') {
      pendingConsentAction.current = 'back'
    } else if (direction === 'right') {
      pendingConsentAction.current = 'submit'
      setConsentGiven(true)
    }
  }

  function handleConsentLeftScreen() {
    const action = pendingConsentAction.current
    if (!action) return
    pendingConsentAction.current = null
    if (action === 'back') {
      setConsentGiven(false)
      moveToStep(FLOW_STEPS.profile)
      return
    }
    handleGuestSubmit({ consentConfirmed: true })
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
      setError(`Dev login failed: ${err.message}`)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div style={pageStyle}>
      <main style={mainStyle}>
        <header style={headerStyle}>
          <h1 style={wordmarkStyle}>
            <span style={{ color: 'var(--color-text)' }}>Archi</span>
            <span style={{ color: 'var(--accent-1, #0969DA)' }}>Tinder</span>
          </h1>
          <p style={taglineStyle}>Start with a swipe, then tune a taste profile.</p>
        </header>

        <div style={stageStyle}>
          {step === FLOW_STEPS.choice && (
            <ChoiceStep
              typedLine={typedLine}
              disabled={isBusy}
              onSwipe={handleChoiceSwipe}
              onCardLeftScreen={handleChoiceLeftScreen}
            />
          )}

          {step === FLOW_STEPS.returning && (
            <ReturningStep
              typedLine={typedLine}
              showGoogle={googleConfigured}
              disabled={isBusy}
              googleLoading={loading === 'google'}
              onBack={() => moveToStep(FLOW_STEPS.choice)}
              onGoogleSuccess={handleGoogleSuccess}
              onGoogleError={handleGoogleError}
              onGoogleNonOAuthError={handleGoogleNonOAuthError}
            />
          )}

          {step === FLOW_STEPS.profile && (
            <ProfileStep
              typedLine={typedLine}
              displayName={displayName}
              role={role}
              profileReady={profileReady}
              disabled={isBusy}
              onDisplayNameChange={(value) => {
                setDisplayName(value)
                setError(null)
                setConsentGiven(false)
              }}
              onRoleChange={(value) => {
                setRole(value)
                setError(null)
                setConsentGiven(false)
              }}
              onBack={() => moveToStep(FLOW_STEPS.choice)}
              onSubmit={handleProfileContinue}
            />
          )}

          {step === FLOW_STEPS.consent && (
            <ConsentStep
              key={`consent-step-${consentResetTick}`}
              typedLine={typedLine}
              displayName={displayName}
              role={role}
              profileReady={profileReady}
              disabled={isBusy}
              onSwipe={handleConsentSwipe}
              onCardLeftScreen={handleConsentLeftScreen}
            />
          )}
        </div>

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

        {error && (
          <p role="alert" style={errorStyle}>
            {error}
          </p>
        )}
      </main>
    </div>
  )
}

function useTypedLine(line) {
  const [typedLine, setTypedLine] = useState('')

  useEffect(() => {
    setTypedLine('')
    let index = 0
    const timer = window.setInterval(() => {
      index += 1
      setTypedLine(line.slice(0, index))
      if (index >= line.length) window.clearInterval(timer)
    }, 24)
    return () => window.clearInterval(timer)
  }, [line])

  return typedLine
}

function ChoiceStep({ typedLine, disabled, onSwipe, onCardLeftScreen }) {
  return (
    <div style={swipeStepStyle}>
      <div style={swipeDeckStyle}>
        <SwipeGestureFrame
          onSwipe={onSwipe}
          onCardLeftScreen={onCardLeftScreen}
          preventSwipe={disabled ? SWIPE_PREVENT_ALL : undefined}
        >
          <AuthCard absolute ariaLabel="Choose login path">
            <CardHeader
              eyebrow="First card"
              title="Are you new here?"
              typedLine={typedLine}
            />
            <div style={choiceBodyStyle}>
              <div style={directionGridStyle} aria-hidden="true">
                <DirectionHint tone="left" label="Returning" sublabel="Left" />
                <DirectionHint tone="right" label="New profile" sublabel="Right" />
              </div>
            </div>
          </AuthCard>
        </SwipeGestureFrame>
      </div>
    </div>
  )
}

function ReturningStep({
  typedLine,
  showGoogle,
  disabled,
  googleLoading,
  onBack,
  onGoogleSuccess,
  onGoogleError,
  onGoogleNonOAuthError,
}) {
  return (
    <AuthCard ariaLabel="Returning user login">
      <CardHeader
        eyebrow="Returning"
        title="Continue with your saved profile."
        typedLine={typedLine}
      />
      <p style={bodyCopyStyle}>
        Verified profiles use Google sign-in. Starting Google stays on this button only.
      </p>
      {showGoogle ? (
        <GoogleLoginButton
          onSuccess={onGoogleSuccess}
          onError={onGoogleError}
          onNonOAuthError={onGoogleNonOAuthError}
          disabled={disabled}
          loading={googleLoading}
          style={{ width: '100%', minHeight: 48, borderRadius: 12 }}
        />
      ) : (
        <div role="status" style={noticeStyle}>
          Google login is unavailable in this environment. Set VITE_GOOGLE_CLIENT_ID to enable returning accounts.
        </div>
      )}
      <button type="button" onClick={onBack} disabled={disabled} style={ghostButtonStyle(disabled)}>
        Back
      </button>
    </AuthCard>
  )
}

function ProfileStep({
  typedLine,
  displayName,
  role,
  profileReady,
  disabled,
  onDisplayNameChange,
  onRoleChange,
  onBack,
  onSubmit,
}) {
  const nameReady = isDisplayNameReady(displayName)

  return (
    <AuthCard ariaLabel="New guest profile">
      <CardHeader
        eyebrow="New guest"
        title="Tell me who is swiping."
        typedLine={typedLine}
      />
      <form onSubmit={onSubmit} style={formStyle}>
        <label style={fieldLabelStyle} htmlFor="guest-display-name">
          Display name
        </label>
        <input
          id="guest-display-name"
          autoFocus
          required
          value={displayName}
          onChange={e => onDisplayNameChange(e.target.value)}
          disabled={disabled}
          placeholder="Alex"
          maxLength={30}
          aria-invalid={displayName.length > 0 && !nameReady ? 'true' : 'false'}
          style={inputStyle}
        />

        <div style={roleHeaderStyle}>
          <span style={fieldLabelStyle}>Objective</span>
          <span style={captionStyle}>{isRoleReady(role) ? 'Selected' : 'Required'}</span>
        </div>
        <div role="radiogroup" aria-label="Select your objective" aria-required="true" style={roleGridStyle}>
          {ONBOARDING_ROLES.map(roleOption => (
            <button
              key={roleOption.value}
              type="button"
              role="radio"
              aria-checked={role === roleOption.value}
              onClick={() => onRoleChange(roleOption.value)}
              disabled={disabled}
              style={roleButtonStyle(disabled, role === roleOption.value)}
            >
              {roleOption.label}
            </button>
          ))}
        </div>

        <div style={buttonGridStyle}>
          <button type="button" onClick={onBack} disabled={disabled} style={secondaryButtonStyle(disabled)}>
            Back
          </button>
          <button type="submit" disabled={disabled || !profileReady} style={primaryButtonStyle(disabled || !profileReady)}>
            Continue
          </button>
        </div>
      </form>
    </AuthCard>
  )
}

function ConsentStep({
  typedLine,
  displayName,
  role,
  profileReady,
  disabled,
  onSwipe,
  onCardLeftScreen,
}) {
  const selectedRole = ONBOARDING_ROLES.find(roleOption => roleOption.value === role)
  const lockSwipe = disabled || !profileReady

  return (
    <div style={swipeStepStyle}>
      <div style={swipeDeckStyle}>
        <SwipeGestureFrame
          onSwipe={onSwipe}
          onCardLeftScreen={onCardLeftScreen}
          preventSwipe={lockSwipe ? SWIPE_PREVENT_ALL : SWIPE_PREVENT_VERTICAL}
        >
          <AuthCard absolute ariaLabel="Guest consent">
            <CardHeader
              eyebrow="Consent"
              title="Create the guest account."
              typedLine={typedLine}
            />
            <div style={summaryBoxStyle}>
              <div>
                <span style={summaryLabelStyle}>Name</span>
                <strong style={summaryValueStyle}>{displayName.trim()}</strong>
              </div>
              <div>
                <span style={summaryLabelStyle}>Objective</span>
                <strong style={summaryValueStyle}>{selectedRole?.label || 'Not selected'}</strong>
              </div>
            </div>
            <p style={bodyCopyStyle}>
              By continuing, you agree that ArchiTinder can use this guest profile to provide the service and save your taste signals.
            </p>
            <div style={directionGridStyle} aria-hidden="true">
              <DirectionHint tone="left" label="Back" sublabel="Left swipe" />
              <DirectionHint tone="right" label="Consent and enter" sublabel="Right swipe" />
            </div>
          </AuthCard>
        </SwipeGestureFrame>
      </div>
    </div>
  )
}

function CardHeader({ eyebrow, title, typedLine }) {
  return (
    <div style={cardHeaderStyle}>
      <p style={eyebrowStyle}>{eyebrow}</p>
      <h2 style={titleStyle}>{title}</h2>
      <p style={typedLineStyle}>
        {typedLine}
        <span aria-hidden="true" style={{ opacity: typedLine ? 1 : 0 }}>_</span>
      </p>
    </div>
  )
}

function AuthCard({ children, absolute = false, ariaLabel }) {
  return (
    <section
      aria-label={ariaLabel}
      style={{
        ...authCardStyle,
        ...(absolute ? absoluteCardStyle : staticCardStyle),
      }}
    >
      {children}
    </section>
  )
}

function DirectionHint({ tone, label, sublabel }) {
  const isLeft = tone === 'left'
  return (
    <div style={{
      ...directionHintStyle,
      borderColor: isLeft ? 'var(--color-destructive, #D73A49)' : 'var(--accent-1, #0969DA)',
      color: isLeft ? 'var(--color-destructive, #D73A49)' : 'var(--accent-1, #0969DA)',
    }}>
      <span style={directionLabelStyle}>{label}</span>
      <span style={directionSublabelStyle}>{sublabel}</span>
    </div>
  )
}

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

function primaryButtonStyle(disabled) {
  return {
    minHeight: 46,
    borderRadius: 12,
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
    borderRadius: 12,
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

function ghostButtonStyle(disabled) {
  return {
    minHeight: 42,
    borderRadius: 12,
    border: '1px solid transparent',
    background: 'transparent',
    color: 'var(--color-text-dim)',
    fontSize: 13,
    fontWeight: 600,
    fontFamily: 'inherit',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.65 : 1,
  }
}

function roleButtonStyle(disabled, active) {
  return {
    minHeight: 42,
    borderRadius: 12,
    border: active ? '1px solid var(--accent-1, #0969DA)' : '1px solid var(--color-border)',
    background: active ? 'rgba(9,105,218,0.10)' : 'var(--color-bg)',
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

const pageStyle = {
  minHeight: '100vh',
  background: 'var(--color-bg)',
  display: 'grid',
  placeItems: 'center',
  padding: 16,
  boxSizing: 'border-box',
}

const mainStyle = {
  width: '100%',
  maxWidth: 420,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: 16,
}

const headerStyle = {
  width: '100%',
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

const wordmarkStyle = {
  fontSize: 30,
  fontWeight: 700,
  margin: 0,
  letterSpacing: 0,
  lineHeight: 1.1,
}

const taglineStyle = {
  color: 'var(--color-text-dim)',
  fontSize: 14,
  margin: 0,
  lineHeight: 1.45,
}

const stageStyle = {
  width: AUTH_STAGE_WIDTH,
}

const swipeStepStyle = {
  width: '100%',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

const swipeDeckStyle = {
  width: '100%',
  height: AUTH_CARD_HEIGHT,
  position: 'relative',
}

const authCardStyle = {
  borderRadius: 20,
  border: '1px solid var(--color-border-soft)',
  background: 'var(--color-surface)',
  color: 'var(--color-text)',
  boxShadow: '0 24px 52px rgba(0,0,0,0.18)',
  padding: 22,
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  gap: 18,
  overflowY: 'auto',
}

const absoluteCardStyle = {
  position: 'absolute',
  top: 0,
  left: 0,
  width: AUTH_STAGE_WIDTH,
  height: AUTH_CARD_HEIGHT,
  cursor: 'grab',
  userSelect: 'none',
  WebkitUserSelect: 'none',
}

const staticCardStyle = {
  position: 'relative',
  width: '100%',
  height: AUTH_CARD_HEIGHT,
}

const cardHeaderStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

const eyebrowStyle = {
  margin: 0,
  color: 'var(--accent-1, #0969DA)',
  fontSize: 12,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: 0,
}

const titleStyle = {
  margin: 0,
  color: 'var(--color-text)',
  fontSize: 26,
  fontWeight: 700,
  lineHeight: 1.16,
  letterSpacing: 0,
}

const typedLineStyle = {
  minHeight: 44,
  margin: 0,
  color: 'var(--color-text-2)',
  fontSize: 16,
  lineHeight: 1.45,
}

const bodyCopyStyle = {
  margin: 0,
  color: 'var(--color-text-dim)',
  fontSize: 14,
  lineHeight: 1.55,
}

const choiceBodyStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 18,
  marginTop: 'auto',
}

const directionGridStyle = {
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: 10,
}

const directionHintStyle = {
  minHeight: 74,
  borderRadius: 16,
  border: '1px solid',
  background: 'var(--color-bg)',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 4,
}

const directionLabelStyle = {
  fontSize: 14,
  fontWeight: 700,
  lineHeight: 1.2,
  textAlign: 'center',
}

const directionSublabelStyle = {
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--color-text-dim)',
  lineHeight: 1.2,
}

const buttonGridStyle = {
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: 10,
}

const noticeStyle = {
  borderRadius: 12,
  border: '1px solid var(--color-border)',
  background: 'var(--color-bg)',
  color: 'var(--color-text-dim)',
  padding: '14px 16px',
  fontSize: 13,
  lineHeight: 1.55,
}

const formStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

const fieldLabelStyle = {
  color: 'var(--color-text)',
  fontSize: 13,
  fontWeight: 700,
  lineHeight: 1.2,
}

const inputStyle = {
  minHeight: 46,
  borderRadius: 12,
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

const roleHeaderStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  marginTop: 4,
}

const captionStyle = {
  color: 'var(--color-text-dim)',
  fontSize: 12,
  fontWeight: 600,
}

const roleGridStyle = {
  display: 'grid',
  gap: 8,
}

const summaryBoxStyle = {
  borderRadius: 16,
  border: '1px solid var(--color-border)',
  background: 'var(--color-bg)',
  padding: 14,
  display: 'grid',
  gap: 12,
}

const summaryLabelStyle = {
  display: 'block',
  color: 'var(--color-text-dim)',
  fontSize: 11,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: 0,
  marginBottom: 4,
}

const summaryValueStyle = {
  display: 'block',
  color: 'var(--color-text)',
  fontSize: 15,
  fontWeight: 700,
  lineHeight: 1.3,
}

const errorStyle = {
  color: 'var(--color-destructive, #D73A49)',
  fontSize: 13,
  margin: 0,
  textAlign: 'center',
  lineHeight: 1.45,
}
