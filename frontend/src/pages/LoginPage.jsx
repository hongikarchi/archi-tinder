/**
 * pages/LoginPage.jsx
 * Conversational swipe onboarding for returning Google users and new guests.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../api/client.js'
import { login as apiLogin, register as apiRegister } from '../api/auth.js'
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
import { useTranslation } from '../i18n/index.js'
import { useLanguage } from '../hooks/useLanguage.js'

const FLOW_STEPS = {
  choice:    'choice',
  returning: 'returning',
  register:  'register',
  profile:   'profile',
  consent:   'consent',
}

const INTRO_DISMISS_KEY = 'archithon_login_intro_dismissed'
const INTRO_SHOW_ONCE   = false

const AUTH_STAGE_WIDTH = `${CARD_WIDTH}px`
const AUTH_CARD_HEIGHT = `${CARD_HEIGHT}px`

export default function LoginPage({ onLogin }) {
  const { t, language }  = useTranslation()
  const { setLanguage }  = useLanguage()

  const [step, setStep]                       = useState(FLOW_STEPS.choice)
  const [displayName, setDisplayName]         = useState('')
  const [role, setRole]                       = useState('')
  const [jobRole, setJobRole]                 = useState('')
  const [affiliation, setAffiliation]         = useState('')
  const [consentGiven, setConsentGiven]       = useState(false)
  const [consentResetTick, setConsentResetTick] = useState(0)
  const [loading, setLoading]                 = useState(null)
  const [error, setError]                     = useState(null)
  const [showIntro, setShowIntro]             = useState(
    () => INTRO_SHOW_ONCE ? !localStorage.getItem(INTRO_DISMISS_KEY) : true,
  )

  const typedLine = useTypedLine(t('login.prompt.' + step))

  // Latest-ref: stable identity for handleConsentAction while capturing fresh
  // handleGuestSubmit closure every render.
  const guestSubmitRef = useRef(() => {})
  guestSubmitRef.current = () => handleGuestSubmit({ consentConfirmed: true })

  // Stable callbacks — setState setters are stable, module constants are stable.
  const handleChoiceAction = useCallback((action) => {
    setError(null)
    setConsentGiven(false)
    setStep(action === LOGIN_SWIPE_ACTIONS.left ? FLOW_STEPS.returning : FLOW_STEPS.profile)
  }, [])

  const handleConsentAction = useCallback((action) => {
    if (action === 'back') {
      setConsentGiven(false)
      setError(null)
      setStep(FLOW_STEPS.profile)
    } else {
      setConsentGiven(true)
      guestSubmitRef.current()
    }
  }, [])

  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)
  const isBusy           = loading !== null
  const profileReady     = isGuestProfileReady({ displayName, role })
  const errorText        = error && (error.key ? t(error.key, error.params) : error.text)

  function dismissIntro() {
    if (INTRO_SHOW_ONCE) localStorage.setItem(INTRO_DISMISS_KEY, 'true')
    setShowIntro(false)
  }

  function moveToStep(nextStep) {
    setError(null)
    setStep(nextStep)
  }

  async function handleGoogleSuccess(codeResponse) {
    setLoading('google')
    setError(null)
    try {
      const user = await api.socialLogin('google', null, codeResponse.code)
      onLogin(user)
    } catch (err) {
      const detail = err.message || 'Unknown error'
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

  function handleProfileContinue(event) {
    event.preventDefault()
    setError(null)
    if (!isDisplayNameReady(displayName)) {
      setError({ key: 'login.error.displayNameRequired' })
      return
    }
    if (!isRoleReady(role)) {
      setError({ key: 'login.error.objectiveRequired' })
      return
    }
    setConsentGiven(false)
    moveToStep(FLOW_STEPS.consent)
  }

  async function handleGuestSubmit({ consentConfirmed = consentGiven } = {}) {
    if (isBusy) return
    setError(null)
    if (!isGuestProfileReady({ displayName, role })) {
      setError({ key: 'login.error.profileIncomplete' })
      setStep(FLOW_STEPS.profile)
      return
    }
    if (!consentConfirmed) {
      setError({ key: 'login.error.consentRequired' })
      return
    }

    setLoading('guest')
    try {
      const user = await api.guestLogin(buildGuestLoginPayload({ displayName, role, jobRole, affiliation }))
      await onLogin(user)
      setLanguage(language)
    } catch (err) {
      const detail = err?.data?.detail || err?.message || 'Unknown error'
      if (detail === 'consent_required') {
        setError({ key: 'login.error.consentRetry' })
        setConsentGiven(false)
      } else {
        setError({ key: 'login.error.signInFailed', params: { detail } })
      }
      setConsentResetTick(prev => prev + 1)
    } finally {
      setLoading(null)
    }
  }

  async function handleLoginSubmit(handle, password) {
    if (isBusy) return
    setError(null)
    setLoading('login')
    try {
      const user = await apiLogin(handle, password)
      onLogin(user)
    } catch (err) {
      setError(err.message ? { text: err.message } : { key: 'login.error.loginFailed' })
    } finally {
      setLoading(null)
    }
  }

  async function handleRegisterSubmit(handle, password, name) {
    if (isBusy) return
    setError(null)
    setLoading('register')
    try {
      const user = await apiRegister(handle, password, name)
      await onLogin(user)
      setLanguage(language)
    } catch (err) {
      const data = err?.data
      if (data?.handle) {
        const msg = Array.isArray(data.handle) ? data.handle[0] : data.handle
        setError({ text: msg })
      } else if (data?.password) {
        const msg = Array.isArray(data.password) ? data.password[0] : data.password
        setError({ text: msg })
      } else {
        setError(err.message ? { text: err.message } : { key: 'login.error.registerFailed' })
      }
    } finally {
      setLoading(null)
    }
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
    <div style={pageStyle}>
      <main style={mainStyle}>
        <header style={headerStyle}>
          <h1 style={{ ...wordmarkStyle, letterSpacing: '0.2em', color: 'var(--color-text)' }}>
            ARCHIBE
          </h1>
          <p style={taglineStyle}>{t('login.tagline')}</p>
        </header>

        <div key={step} className="lp-card-in" style={stageStyle}>
          {step === FLOW_STEPS.choice && (
            <ChoiceDeck
              t={t}
              typedLine={typedLine}
              disabled={isBusy}
              onAction={handleChoiceAction}
            />
          )}

          {step === FLOW_STEPS.returning && (
            <ReturningStep
              t={t}
              typedLine={typedLine}
              showGoogle={googleConfigured}
              disabled={isBusy}
              googleLoading={loading === 'google'}
              loginLoading={loading === 'login'}
              onBack={() => moveToStep(FLOW_STEPS.choice)}
              onGoogleSuccess={handleGoogleSuccess}
              onGoogleError={handleGoogleError}
              onGoogleNonOAuthError={handleGoogleNonOAuthError}
              onLoginSubmit={handleLoginSubmit}
            />
          )}

          {step === FLOW_STEPS.register && (
            <RegisterStep
              t={t}
              typedLine={typedLine}
              disabled={isBusy}
              registerLoading={loading === 'register'}
              onBack={() => moveToStep(FLOW_STEPS.choice)}
              onRegisterSubmit={handleRegisterSubmit}
            />
          )}

          {step === FLOW_STEPS.profile && (
            <ProfileStep
              t={t}
              typedLine={typedLine}
              displayName={displayName}
              role={role}
              jobRole={jobRole}
              affiliation={affiliation}
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
              onJobRoleChange={(value) => {
                setJobRole(value)
                setConsentGiven(false)
              }}
              onAffiliationChange={(value) => {
                setAffiliation(value)
                setConsentGiven(false)
              }}
              onBack={() => moveToStep(FLOW_STEPS.choice)}
              onSubmit={handleProfileContinue}
            />
          )}

          {step === FLOW_STEPS.consent && (
            <ConsentDeck
              key={`consent-${consentResetTick}`}
              t={t}
              typedLine={typedLine}
              displayName={displayName}
              role={role}
              jobRole={jobRole}
              affiliation={affiliation}
              profileReady={profileReady}
              disabled={isBusy}
              onAction={handleConsentAction}
            />
          )}
        </div>

        <p style={captionTextStyle}>{t('login.caption.' + step)}</p>

        {step === FLOW_STEPS.choice && (
          <button
            type="button"
            className="lp-btn"
            onClick={() => moveToStep(FLOW_STEPS.register)}
            disabled={isBusy}
            style={ghostButtonStyle(isBusy)}
          >
            {t('login.choice.registerLink')}
          </button>
        )}

        {import.meta.env.DEV && (
          <button
            type="button"
            className="lp-btn"
            onClick={handleDevClick}
            disabled={isBusy}
            style={secondaryButtonStyle(isBusy)}
          >
            {loading === 'dev' ? <Spinner /> : t('login.dev.button')}
          </button>
        )}

        {errorText && (
          <p role="alert" style={errorStyle}>
            {errorText}
          </p>
        )}
      </main>

      {showIntro && <IntroOverlay t={t} onDone={dismissIntro} />}
    </div>
  )
}

// ── Utility hook ─────────────────────────────────────────────────────────────

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

// ── Internal components ───────────────────────────────────────────────────────

function LangToggle() {
  const { language, setLanguage } = useLanguage()
  const stop = (e) => e.stopPropagation()
  const langs = [{ id: 'ko', label: '한국어' }, { id: 'en', label: 'ENGLISH' }]

  return (
    <div
      onPointerDown={stop}
      onMouseDown={stop}
      onTouchStart={stop}
      style={{
        display: 'inline-flex',
        gap: 2,
        padding: 3,
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-pill)',
        flexShrink: 0,
      }}
    >
      {langs.map((l) => {
        const sel = language === l.id
        return (
          <button
            key={l.id}
            type="button"
            className="pressable"
            onClick={() => setLanguage(l.id)}
            style={{
              padding: '3px 9px',
              borderRadius: 'var(--radius-pill)',
              border: 0,
              background: sel ? 'var(--color-bg)' : 'transparent',
              color: sel ? 'var(--color-text)' : 'var(--color-text-muted)',
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: l.id === 'en' ? '0.1em' : '0.02em',
              cursor: 'pointer',
              boxShadow: sel ? '0 1px 3px rgba(0,0,0,0.12)' : 'none',
              fontFamily: 'inherit',
              transition: `background var(--motion-fast), color var(--motion-fast)`,
            }}
          >
            {l.label}
          </button>
        )
      })}
    </div>
  )
}

function GestureHint({ side, active, label, sub }) {
  const isLeft = side === 'left'
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: isLeft ? 'flex-start' : 'flex-end',
      gap: 3,
    }}>
      <span style={{
        fontSize: 16,
        fontWeight: 700,
        color: active ? 'var(--accent-1)' : 'var(--color-text-2)',
        transition: `color var(--motion-fast) var(--motion-ease)`,
      }}>
        {isLeft ? `← ${label}` : `${label} →`}
      </span>
      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-dim)' }}>
        {sub}
      </span>
    </div>
  )
}

function ChoiceDeck({ t, typedLine, disabled, onAction }) {
  const pending = useRef(null)
  const [intent, setIntent] = useState(null)

  const handleSwipe = useCallback((dir) => {
    const a = getLoginSwipeAction(dir)
    if (a) pending.current = a
  }, [])

  const handleLeftScreen = useCallback(() => {
    const a = pending.current
    pending.current = null
    if (a) onAction(a)
  }, [onAction])

  const handleFulfilled = useCallback((dir) => {
    if (dir === 'left' || dir === 'right') setIntent(dir)
  }, [])

  const handleUnfulfilled = useCallback(() => setIntent(null), [])

  const preventSwipe = disabled ? SWIPE_PREVENT_ALL : SWIPE_PREVENT_VERTICAL

  return (
    <div style={{ position: 'relative', width: '100%', height: AUTH_CARD_HEIGHT }}>
      {/* faux depth cards — decorative stack behind the live card */}
      <div
        aria-hidden="true"
        style={{
          ...authCardStyle,
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          pointerEvents: 'none',
          transform: 'translateY(14px) scale(0.94)',
          opacity: 0.4,
        }}
      />
      <div
        aria-hidden="true"
        style={{
          ...authCardStyle,
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          pointerEvents: 'none',
          transform: 'translateY(7px) scale(0.97)',
          opacity: 0.7,
        }}
      />
      <SwipeGestureFrame
        className="lp-tinder"
        onSwipe={handleSwipe}
        onCardLeftScreen={handleLeftScreen}
        onSwipeRequirementFulfilled={handleFulfilled}
        onSwipeRequirementUnfulfilled={handleUnfulfilled}
        preventSwipe={preventSwipe}
      >
        <AuthCard absolute ariaLabel={t('login.choice.eyebrow')}>
          <CardHeader
            eyebrow={t('login.choice.eyebrow')}
            title={t('login.choice.title')}
            typedLine={typedLine}
            trailing={<LangToggle />}
          />
          <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12 }}>
            <GestureHint
              side="left"
              active={intent === 'left'}
              label={t('login.choice.left.label')}
              sub={t('login.choice.left.sub')}
            />
            <GestureHint
              side="right"
              active={intent === 'right'}
              label={t('login.choice.right.label')}
              sub={t('login.choice.right.sub')}
            />
          </div>
        </AuthCard>
      </SwipeGestureFrame>
    </div>
  )
}

function ConsentDeck({
  t, typedLine, displayName, role, jobRole, affiliation, profileReady, disabled, onAction,
}) {
  const pending = useRef(null)
  const [intent, setIntent] = useState(null)

  const handleSwipe = useCallback((dir) => {
    if (dir === 'left')       pending.current = 'back'
    else if (dir === 'right') pending.current = 'submit'
  }, [])

  const handleLeftScreen = useCallback(() => {
    const a = pending.current
    pending.current = null
    if (a) onAction(a)
  }, [onAction])

  const handleFulfilled = useCallback((dir) => {
    if (dir === 'left' || dir === 'right') setIntent(dir)
  }, [])

  const handleUnfulfilled = useCallback(() => setIntent(null), [])

  const preventSwipe = (disabled || !profileReady) ? SWIPE_PREVENT_ALL : SWIPE_PREVENT_VERTICAL

  return (
    <div style={{ position: 'relative', width: '100%', height: AUTH_CARD_HEIGHT }}>
      <div
        aria-hidden="true"
        style={{
          ...authCardStyle,
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          pointerEvents: 'none',
          transform: 'translateY(14px) scale(0.94)',
          opacity: 0.4,
        }}
      />
      <div
        aria-hidden="true"
        style={{
          ...authCardStyle,
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          pointerEvents: 'none',
          transform: 'translateY(7px) scale(0.97)',
          opacity: 0.7,
        }}
      />
      <SwipeGestureFrame
        className="lp-tinder"
        onSwipe={handleSwipe}
        onCardLeftScreen={handleLeftScreen}
        onSwipeRequirementFulfilled={handleFulfilled}
        onSwipeRequirementUnfulfilled={handleUnfulfilled}
        preventSwipe={preventSwipe}
      >
        <AuthCard absolute ariaLabel={t('login.consent.eyebrow')}>
          <CardHeader
            eyebrow={t('login.consent.eyebrow')}
            title={t('login.consent.title')}
            typedLine={typedLine}
            trailing={<LangToggle />}
          />
          <div style={summaryBoxStyle}>
            <div>
              <span style={summaryLabelStyle}>{t('login.consent.summary.name')}</span>
              <strong style={summaryValueStyle}>{displayName.trim()}</strong>
            </div>
            <div>
              <span style={summaryLabelStyle}>{t('login.consent.summary.objective')}</span>
              <strong style={summaryValueStyle}>
                {role ? t('login.profile.objective.' + role) : t('login.consent.summary.notSelected')}
              </strong>
            </div>
            {jobRole.trim() && (
              <div>
                <span style={summaryLabelStyle}>{t('login.consent.summary.role')}</span>
                <strong style={summaryValueStyle}>{jobRole.trim()}</strong>
              </div>
            )}
            {affiliation.trim() && (
              <div>
                <span style={summaryLabelStyle}>{t('login.consent.summary.affiliation')}</span>
                <strong style={summaryValueStyle}>{affiliation.trim()}</strong>
              </div>
            )}
          </div>
          <p style={bodyCopyStyle}>{t('login.consent.body')}</p>
          <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12 }}>
            <GestureHint
              side="left"
              active={intent === 'left'}
              label={t('login.consent.left.label')}
              sub={t('login.consent.left.sub')}
            />
            <GestureHint
              side="right"
              active={intent === 'right'}
              label={t('login.consent.right.label')}
              sub={t('login.consent.right.sub')}
            />
          </div>
        </AuthCard>
      </SwipeGestureFrame>
    </div>
  )
}

function ReturningStep({
  t,
  typedLine,
  showGoogle,
  disabled,
  googleLoading,
  loginLoading,
  onBack,
  onGoogleSuccess,
  onGoogleError,
  onGoogleNonOAuthError,
  onLoginSubmit,
}) {
  const [handle, setHandle]     = useState('')
  const [password, setPassword] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!handle.trim() || !password) return
    onLoginSubmit(handle.trim(), password)
  }

  return (
    <AuthCard ariaLabel={t('login.returning.eyebrow')}>
      <CardHeader
        eyebrow={t('login.returning.eyebrow')}
        title={t('login.returning.title')}
        typedLine={typedLine}
        trailing={<LangToggle />}
      />
      {showGoogle ? (
        <GoogleLoginButton
          onSuccess={onGoogleSuccess}
          onError={onGoogleError}
          onNonOAuthError={onGoogleNonOAuthError}
          disabled={disabled}
          loading={googleLoading}
          label={t('login.returning.google')}
          className="lp-btn"
          style={{ width: '100%', minHeight: 48, borderRadius: 12 }}
        />
      ) : (
        <div role="status" style={noticeStyle}>
          {t('login.returning.googleUnavailable')}
        </div>
      )}

      <div style={dividerRowStyle}>
        <span style={dividerLineStyle} />
        <span style={dividerTextStyle}>{t('login.returning.divider')}</span>
        <span style={dividerLineStyle} />
      </div>

      <form onSubmit={handleSubmit} style={formStyle}>
        <input
          type="text"
          value={handle}
          onChange={e => setHandle(e.target.value)}
          disabled={disabled}
          placeholder={t('login.returning.handle.placeholder')}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          aria-label={t('login.returning.handle.aria')}
          className="lp-input"
          style={inputStyle}
        />
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          disabled={disabled}
          placeholder={t('login.returning.password.placeholder')}
          aria-label={t('login.returning.password.aria')}
          className="lp-input"
          style={inputStyle}
        />
        <button
          type="submit"
          className="lp-cta"
          disabled={disabled || !handle.trim() || !password}
          style={primaryButtonStyle(disabled || !handle.trim() || !password)}
        >
          {loginLoading ? <Spinner /> : t('login.returning.submit')}
        </button>
      </form>

      <button
        type="button"
        className="lp-btn"
        onClick={onBack}
        disabled={disabled}
        style={ghostButtonStyle(disabled)}
      >
        {t('login.common.back')}
      </button>
    </AuthCard>
  )
}

function ProfileStep({
  t,
  typedLine,
  displayName,
  role,
  jobRole,
  affiliation,
  profileReady,
  disabled,
  onDisplayNameChange,
  onRoleChange,
  onJobRoleChange,
  onAffiliationChange,
  onBack,
  onSubmit,
}) {
  const nameReady = isDisplayNameReady(displayName)

  return (
    <AuthCard ariaLabel={t('login.profile.eyebrow')}>
      <CardHeader
        eyebrow={t('login.profile.eyebrow')}
        title={t('login.profile.title')}
        typedLine={typedLine}
        trailing={<LangToggle />}
      />
      <form onSubmit={onSubmit} style={formStyle}>
        <label style={fieldLabelStyle} htmlFor="guest-display-name">
          {t('login.profile.displayName.label')}
        </label>
        <input
          id="guest-display-name"
          autoFocus
          required
          value={displayName}
          onChange={e => onDisplayNameChange(e.target.value)}
          disabled={disabled}
          placeholder={t('login.profile.displayName.placeholder')}
          maxLength={30}
          aria-invalid={displayName.length > 0 && !nameReady ? 'true' : 'false'}
          className="lp-input"
          style={inputStyle}
        />

        <label style={{ ...fieldLabelStyle, marginTop: 12 }} htmlFor="guest-job-role">
          {t('login.profile.jobRole.label')}
        </label>
        <input
          id="guest-job-role"
          type="text"
          value={jobRole}
          onChange={e => onJobRoleChange(e.target.value)}
          disabled={disabled}
          placeholder={t('login.profile.jobRole.placeholder')}
          maxLength={50}
          className="lp-input"
          style={inputStyle}
        />

        <label style={{ ...fieldLabelStyle, marginTop: 12 }} htmlFor="guest-affiliation">
          {t('login.profile.affiliation.label')}
        </label>
        <input
          id="guest-affiliation"
          type="text"
          value={affiliation}
          onChange={e => onAffiliationChange(e.target.value)}
          disabled={disabled}
          placeholder={t('login.profile.affiliation.placeholder')}
          maxLength={100}
          className="lp-input"
          style={inputStyle}
        />

        <div style={roleHeaderStyle}>
          <span style={fieldLabelStyle}>{t('login.profile.objective.label')}</span>
          <span style={captionStyle}>
            {isRoleReady(role)
              ? t('login.profile.objective.selected')
              : t('login.profile.objective.required')}
          </span>
        </div>
        <div
          role="radiogroup"
          aria-label={t('login.profile.objective.aria')}
          aria-required="true"
          style={roleGridStyle}
        >
          {ONBOARDING_ROLES.map(roleOption => (
            <button
              key={roleOption.value}
              type="button"
              role="radio"
              aria-checked={role === roleOption.value}
              onClick={() => onRoleChange(roleOption.value)}
              disabled={disabled}
              className="lp-btn"
              style={roleButtonStyle(disabled, role === roleOption.value)}
            >
              {t('login.profile.objective.' + roleOption.value)}
            </button>
          ))}
        </div>

        <div style={buttonGridStyle}>
          <button
            type="button"
            className="lp-btn"
            onClick={onBack}
            disabled={disabled}
            style={secondaryButtonStyle(disabled)}
          >
            {t('login.common.back')}
          </button>
          <button
            type="submit"
            className="lp-cta"
            disabled={disabled || !profileReady}
            style={primaryButtonStyle(disabled || !profileReady)}
          >
            {t('login.profile.continueBtn')}
          </button>
        </div>
      </form>
    </AuthCard>
  )
}

function RegisterStep({
  t,
  typedLine,
  disabled,
  registerLoading,
  onBack,
  onRegisterSubmit,
}) {
  const [handle, setHandle]           = useState('')
  const [password, setPassword]       = useState('')
  const [displayName, setDisplayName] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!handle.trim() || !password) return
    onRegisterSubmit(handle.trim(), password, displayName)
  }

  const canSubmit = handle.trim().length >= 3 && password.length >= 8

  return (
    <AuthCard ariaLabel={t('login.register.eyebrow')}>
      <CardHeader
        eyebrow={t('login.register.eyebrow')}
        title={t('login.register.title')}
        typedLine={typedLine}
        trailing={<LangToggle />}
      />
      <form onSubmit={handleSubmit} style={formStyle}>
        <label style={fieldLabelStyle} htmlFor="reg-display-name">
          {t('login.register.name.label')}
        </label>
        <input
          id="reg-display-name"
          type="text"
          value={displayName}
          onChange={e => setDisplayName(e.target.value)}
          disabled={disabled}
          placeholder={t('login.register.name.placeholder')}
          maxLength={30}
          className="lp-input"
          style={inputStyle}
        />

        <label style={{ ...fieldLabelStyle, marginTop: 4 }} htmlFor="reg-handle">
          {t('login.register.handle.label')}
        </label>
        <input
          id="reg-handle"
          type="text"
          value={handle}
          onChange={e => setHandle(e.target.value)}
          disabled={disabled}
          placeholder={t('login.register.handle.placeholder')}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          maxLength={30}
          aria-required="true"
          className="lp-input"
          style={inputStyle}
        />

        <label style={{ ...fieldLabelStyle, marginTop: 4 }} htmlFor="reg-password">
          {t('login.register.password.label')}
        </label>
        <input
          id="reg-password"
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          disabled={disabled}
          placeholder={t('login.register.password.placeholder')}
          maxLength={128}
          aria-required="true"
          className="lp-input"
          style={inputStyle}
        />

        <div style={buttonGridStyle}>
          <button
            type="button"
            className="lp-btn"
            onClick={onBack}
            disabled={disabled}
            style={secondaryButtonStyle(disabled)}
          >
            {t('login.common.back')}
          </button>
          <button
            type="submit"
            className="lp-cta"
            disabled={disabled || !canSubmit}
            style={primaryButtonStyle(disabled || !canSubmit)}
          >
            {registerLoading ? <Spinner /> : t('login.register.submit')}
          </button>
        </div>
      </form>
    </AuthCard>
  )
}

function CardHeader({ eyebrow, title, typedLine, trailing }) {
  return (
    <div style={cardHeaderStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
        <p style={eyebrowStyle}>{eyebrow}</p>
        {trailing}
      </div>
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

function IntroOverlay({ t, onDone }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('login.intro.title')}
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
        background: 'rgba(0,0,0,0.55)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
      }}
    >
      <div
        className="lp-card-in"
        style={{
          width: AUTH_STAGE_WIDTH,
          height: AUTH_CARD_HEIGHT,
          boxSizing: 'border-box',
          display: 'flex', flexDirection: 'column', alignItems: 'stretch',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          borderRadius: 20,
          boxShadow: '0 24px 64px rgba(0,0,0,0.45)',
          padding: 24,
          overflowY: 'auto',
        }}
      >
        {/* eyebrow + LangToggle row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
          <p style={eyebrowStyle}>{t('login.intro.eyebrow')}</p>
          <LangToggle />
        </div>

        <h2 style={{ ...titleStyle, marginTop: 10 }}>{t('login.intro.title')}</h2>

        <div style={{ flex: 1 }} />

        {/* swipe demo: synchronized arrows flanking mini card */}
        <div style={{ height: 168, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
          <span
            className="lp-arrow-left"
            aria-hidden="true"
            style={{ fontSize: 26, fontWeight: 700, color: 'var(--color-text-dim)', flexShrink: 0 }}
          >
            &#8592;
          </span>
          <div
            className="lp-swipe-demo"
            style={{
              width: 112, height: 148,
              borderRadius: 12,
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border-soft)',
              boxShadow: '0 8px 24px rgba(0,0,0,0.22)',
              display: 'flex', alignItems: 'flex-start',
              padding: 12,
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.3em', color: 'var(--color-text-muted)' }}>
              ARCHIBE
            </span>
          </div>
          <span
            className="lp-arrow-right"
            aria-hidden="true"
            style={{ fontSize: 26, fontWeight: 700, color: 'var(--color-text-dim)', flexShrink: 0 }}
          >
            &#8594;
          </span>
        </div>

        <p style={{ ...bodyCopyStyle, textAlign: 'center', whiteSpace: 'pre-line', marginTop: 12 }}>
          {t('login.intro.body')}
        </p>

        <div style={{ flex: 1 }} />

        <button
          type="button"
          className="lp-cta"
          onClick={onDone}
          style={{ ...primaryButtonStyle(false), width: '100%', marginTop: 12 }}
        >
          {t('login.intro.cta')}
        </button>
      </div>
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

// ── Style helpers ─────────────────────────────────────────────────────────────

function primaryButtonStyle(disabled) {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
    padding: '14px 16px',
    border: 0,
    borderRadius: 'var(--radius-md)',
    background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
    color: '#fff',
    fontSize: 14,
    fontWeight: 600,
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

// ── Style constants ───────────────────────────────────────────────────────────

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

const captionTextStyle = {
  fontSize: 13,
  color: 'var(--color-text-muted)',
  textAlign: 'center',
  margin: 0,
  lineHeight: 1.5,
  width: '100%',
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
  background: 'color-mix(in srgb, var(--color-surface) 72%, transparent)',
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

const dividerRowStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
}

const dividerLineStyle = {
  flex: 1,
  height: 1,
  background: 'var(--color-border)',
}

const dividerTextStyle = {
  fontSize: 12,
  color: 'var(--color-text-dim)',
  fontWeight: 600,
  whiteSpace: 'nowrap',
}
