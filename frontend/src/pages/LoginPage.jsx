/**
 * pages/LoginPage.jsx
 * Conversational swipe onboarding — unified ID+password signup.
 *
 * New 3-step new-profile flow:
 *   choice → credentials (ID+password) → profile (affiliation+objective) → consent
 *
 * Google = verification only, not a signup path.
 *
 * Visual language: business-card ("paper card") — see components/cardLanguage.js.
 * Theme-adaptive (paper = --color-surface, ink = --color-text family), unlike
 * BusinessCard.jsx's intentionally hardcoded white-paper-always printed artifact.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { login as apiLogin, register as apiRegister, checkHandle } from '../api/auth.js'
import * as api from '../api/client.js'
import { getRoles } from '../api/meta.js'
import GoogleLoginButton from '../components/GoogleLoginButton.jsx'
import { CARD_HEIGHT, CARD_WIDTH } from '../components/SwipeCard.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'
import { SWIPE_PREVENT_ALL, SWIPE_PREVENT_VERTICAL } from '../components/swipeGestureConfig.js'
import {
  LOGIN_SWIPE_ACTIONS,
  ONBOARDING_ROLES,
  getLoginSwipeAction,
  hasGoogleLogin,
  isIdFormatValid,
  isRoleReady,
} from '../utils/loginFlow.js'
import { useTranslation } from '../i18n/index.js'
import { useLanguage } from '../hooks/useLanguage.js'
import {
  MONO,
  INK,
  paperFaceStyle,
  wordmarkStyle as cardWordmarkStyle,
  monoLabelStyle,
  monoRowStyle,
  finePrintStyle,
  cardNameStyle,
  cardRoleStyle,
  cardMetaStyle,
  inkPrimaryStyle,
  inkSecondaryStyle,
  inkGhostStyle,
  paperInputStyle,
} from '../components/cardLanguage.js'

const FLOW_STEPS = {
  choice:      'choice',
  returning:   'returning',
  credentials: 'credentials',
  profile:     'profile',
  consent:     'consent',
}

const INTRO_DISMISS_KEY = 'archithon_login_intro_dismissed'
const INTRO_SHOW_ONCE   = false

const AUTH_STAGE_WIDTH = `${CARD_WIDTH}px`
const AUTH_CARD_HEIGHT = `${CARD_HEIGHT}px`

export default function LoginPage({ onLogin }) {
  const { t, language } = useTranslation()
  const { setLanguage } = useLanguage()

  const [step, setStep]                         = useState(FLOW_STEPS.choice)

  // New-profile state: lifted to parent so consent step can access all fields.
  const [id, setId]                             = useState('')
  const [password, setPassword]                 = useState('')
  const [affiliation, setAffiliation]           = useState('')
  const [role, setRole]                         = useState('')

  const [consentGiven, setConsentGiven]         = useState(false)
  const [consentResetTick, setConsentResetTick] = useState(0)
  const [loading, setLoading]                   = useState(null)
  const [error, setError]                       = useState(null)
  const [showIntro, setShowIntro]               = useState(
    () => INTRO_SHOW_ONCE ? !localStorage.getItem(INTRO_DISMISS_KEY) : true,
  )

  // SETTINGS-POLISH-1: role list — bundled fallback first paint, then the
  // live backend list once getRoles() resolves (adds new roles with no
  // frontend redeploy).
  const [roles, setRoles] = useState(ONBOARDING_ROLES)
  useEffect(() => {
    let cancelled = false
    getRoles().then(list => { if (!cancelled) setRoles(list) })
    return () => { cancelled = true }
  }, [])

  const typedLine = useTypedLine(t('login.prompt.' + step))

  // Latest-ref: stable identity for handleConsentAction while capturing fresh
  // handleRegisterSubmit closure every render.
  const registerSubmitRef = useRef(() => {})
  registerSubmitRef.current = () => handleRegisterSubmit({ consentConfirmed: true })

  // Stable callbacks — setState setters are stable, module constants are stable.
  const handleChoiceAction = useCallback((action) => {
    setError(null)
    setConsentGiven(false)
    setStep(action === LOGIN_SWIPE_ACTIONS.left ? FLOW_STEPS.returning : FLOW_STEPS.credentials)
  }, [])

  const handleConsentAction = useCallback((action) => {
    if (action === 'back') {
      setConsentGiven(false)
      setError(null)
      setStep(FLOW_STEPS.profile)
    } else {
      setConsentGiven(true)
      registerSubmitRef.current()
    }
  }, [])

  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)
  const isBusy           = loading !== null
  const errorText        = error && (error.key ? t(error.key, error.params) : error.text)

  function dismissIntro() {
    if (INTRO_SHOW_ONCE) localStorage.setItem(INTRO_DISMISS_KEY, 'true')
    setShowIntro(false)
  }

  function moveToStep(nextStep) {
    setError(null)
    setStep(nextStep)
  }

  // -- Google login (returning / verify only) --------------------------------
  async function handleGoogleSuccess(codeResponse) {
    setLoading('google')
    setError(null)
    try {
      const user = await api.socialLogin('google', null, codeResponse.code)
      onLogin(user)
    } catch (err) {
      // Backend returns 404/400 { detail: 'signup_required' } for new Google users.
      const detail = err?.data?.detail || err?.message || 'Unknown error'
      if (detail === 'signup_required') {
        setError({ key: 'login.error.googleSignupRequired' })
      } else {
        setError({ key: 'login.error.googleFailed', params: { detail } })
      }
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

  // -- ID+password login (returning) ----------------------------------------
  async function handleLoginSubmit(handle, pass) {
    if (isBusy) return
    setError(null)
    setLoading('login')
    try {
      const user = await apiLogin(handle, pass)
      onLogin(user)
    } catch (err) {
      setError(err.message ? { text: err.message } : { key: 'login.error.loginFailed' })
    } finally {
      setLoading(null)
    }
  }

  // -- Credentials step → advance to profile step ---------------------------
  function handleCredentialsContinue(credId, credPassword) {
    setId(credId)
    setPassword(credPassword)
    setError(null)
    moveToStep(FLOW_STEPS.profile)
  }

  // -- Profile step → advance to consent ------------------------------------
  function handleProfileContinue(event) {
    event.preventDefault()
    setError(null)
    if (!isRoleReady(role)) {
      setError({ key: 'login.error.objectiveRequired' })
      return
    }
    setConsentGiven(false)
    moveToStep(FLOW_STEPS.consent)
  }

  // -- Final submit: register() called once on consent ----------------------
  async function handleRegisterSubmit({ consentConfirmed = consentGiven } = {}) {
    if (isBusy) return
    setError(null)

    if (!isIdFormatValid(id)) {
      setError({ key: 'login.error.idInvalid' })
      setStep(FLOW_STEPS.credentials)
      return
    }
    if (!password || password.length < 8) {
      setStep(FLOW_STEPS.credentials)
      return
    }
    if (!isRoleReady(role)) {
      setError({ key: 'login.error.profileIncomplete' })
      setStep(FLOW_STEPS.profile)
      return
    }
    if (!consentConfirmed) {
      setError({ key: 'login.error.consentRequired' })
      return
    }

    setLoading('register')
    try {
      const payload = {
        id: id.normalize('NFC'),
        password,
        onboarding_role: role,
        consent_accepted: true,
        consent_policy_version: '1.0',
      }
      if (affiliation && affiliation.trim()) payload.affiliation = affiliation.trim().slice(0, 100)
      const user = await apiRegister(payload)
      await onLogin(user)
      setLanguage(language)
    } catch (err) {
      const data = err?.data
      if (data?.id) {
        const msg = Array.isArray(data.id) ? data.id[0] : data.id
        setError({ text: msg })
      } else if (data?.handle) {
        // Legacy field name fallback
        const msg = Array.isArray(data.handle) ? data.handle[0] : data.handle
        setError({ text: msg })
      } else if (data?.password) {
        const msg = Array.isArray(data.password) ? data.password[0] : data.password
        setError({ text: msg })
      } else if (data?.detail === 'consent_required') {
        setError({ key: 'login.error.consentRetry' })
        setConsentGiven(false)
      } else {
        setError(err.message ? { text: err.message } : { key: 'login.error.registerFailed' })
      }
      setConsentResetTick(prev => prev + 1)
    } finally {
      setLoading(null)
    }
  }

  // -- Dev login ------------------------------------------------------------
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

          {step === FLOW_STEPS.credentials && (
            <CredentialsStep
              t={t}
              typedLine={typedLine}
              disabled={isBusy}
              onBack={() => moveToStep(FLOW_STEPS.choice)}
              onContinue={handleCredentialsContinue}
            />
          )}

          {step === FLOW_STEPS.profile && (
            <ProfileStep
              t={t}
              typedLine={typedLine}
              role={role}
              roles={roles}
              language={language}
              affiliation={affiliation}
              disabled={isBusy}
              onRoleChange={(value) => {
                setRole(value)
                setError(null)
                setConsentGiven(false)
              }}
              onAffiliationChange={(value) => {
                setAffiliation(value)
                setConsentGiven(false)
              }}
              onBack={() => moveToStep(FLOW_STEPS.credentials)}
              onSubmit={handleProfileContinue}
            />
          )}

          {step === FLOW_STEPS.consent && (
            <ConsentDeck
              key={`consent-${consentResetTick}`}
              t={t}
              typedLine={typedLine}
              id={id}
              role={role}
              roles={roles}
              language={language}
              affiliation={affiliation}
              profileReady={isIdFormatValid(id) && isRoleReady(role)}
              disabled={isBusy}
              onAction={handleConsentAction}
            />
          )}
        </div>

        {import.meta.env.DEV && (
          <button
            type="button"
            className="lp-btn"
            onClick={handleDevClick}
            disabled={isBusy}
            style={inkSecondaryStyle(isBusy)}
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
        color: active ? INK.strong : INK.dim,
        transition: `color var(--motion-fast) var(--motion-ease)`,
      }}>
        {isLeft ? `← ${label}` : `${label} →`}
      </span>
      <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 500, color: INK.dim }}>
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
          {/* Static faint placeholder rows — seeds the skeleton language */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div className="lp-skel" style={{ opacity: 0.35, animation: 'none', height: 22, width: '60%' }} />
            <div className="lp-skel" style={{ opacity: 0.35, animation: 'none', height: 12, width: '40%' }} />
            <div className="lp-skel" style={{ opacity: 0.35, animation: 'none', height: 12, width: '50%' }} />
          </div>
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

// Handle-check state machine
const CHECK_IDLE      = 'idle'
const CHECK_CHECKING  = 'checking'
const CHECK_AVAILABLE = 'available'
const CHECK_TAKEN     = 'taken'

function CredentialsStep({ t, typedLine, disabled, onBack, onContinue }) {
  const [localId, setLocalId]           = useState('')
  const [localPassword, setLocalPassword] = useState('')
  const [checkState, setCheckState]     = useState(CHECK_IDLE)
  const [confirmedId, setConfirmedId]   = useState('')  // the id that was confirmed available
  const [checkError, setCheckError]     = useState(null)

  const idNfc         = localId.normalize('NFC')
  const idFormatValid = isIdFormatValid(localId)
  const passwordValid = localPassword.length >= 8

  // Reset availability when id changes after confirmation
  function handleIdChange(value) {
    setLocalId(value)
    setCheckError(null)
    if (checkState !== CHECK_IDLE) {
      setCheckState(CHECK_IDLE)
      setConfirmedId('')
    }
  }

  async function handleCheckAvailability() {
    if (!idFormatValid) {
      setCheckError(t('login.error.idInvalid'))
      return
    }
    setCheckState(CHECK_CHECKING)
    setCheckError(null)
    try {
      const result = await checkHandle(localId)
      if (result.available) {
        setCheckState(CHECK_AVAILABLE)
        setConfirmedId(idNfc)
      } else {
        setCheckState(CHECK_TAKEN)
        setConfirmedId('')
        setCheckError(result.reason || t('login.credentials.id.taken'))
      }
    } catch {
      setCheckState(CHECK_IDLE)
      setCheckError(t('login.error.idInvalid'))
    }
  }

  // Continue enabled when: format valid, check result is available (for current id), password >= 8
  const idConfirmed = checkState === CHECK_AVAILABLE && confirmedId === idNfc
  const canContinue = idConfirmed && passwordValid && !disabled

  function handleSubmit(e) {
    e.preventDefault()
    if (!canContinue) return
    onContinue(idNfc, localPassword)
  }

  // Inline check-state hint color
  const checkHintColor =
    checkState === CHECK_AVAILABLE ? 'var(--accent-1)' :
    checkState === CHECK_TAKEN     ? 'var(--color-destructive)' :
    'var(--color-text-dim)'

  const checkHintText =
    checkState === CHECK_CHECKING  ? t('login.credentials.id.checking') :
    checkState === CHECK_AVAILABLE ? t('login.credentials.id.available') :
    checkState === CHECK_TAKEN     ? (checkError || t('login.credentials.id.taken')) :
    checkError || ''

  return (
    <AuthCard ariaLabel={t('login.credentials.eyebrow')}>
      <CardHeader
        eyebrow={t('login.credentials.eyebrow')}
        title={t('login.credentials.title')}
        typedLine={typedLine}
        trailing={<LangToggle />}
      />
      <form onSubmit={handleSubmit} style={formStyle}>
        <label style={monoLabelStyle} htmlFor="cred-id">
          {t('login.credentials.id.label')}
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            id="cred-id"
            autoFocus
            type="text"
            value={localId}
            onChange={e => handleIdChange(e.target.value)}
            disabled={disabled}
            placeholder={t('login.credentials.id.placeholder')}
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            maxLength={20}
            aria-label={t('login.credentials.id.aria')}
            aria-invalid={localId.length > 0 && !idFormatValid ? 'true' : 'false'}
            className="lp-input"
            style={{ ...paperInputStyle, flex: 1 }}
          />
          <button
            type="button"
            className="lp-btn"
            onClick={handleCheckAvailability}
            disabled={disabled || !idFormatValid || checkState === CHECK_CHECKING}
            style={inkSecondaryStyle(disabled || !idFormatValid || checkState === CHECK_CHECKING)}
          >
            {checkState === CHECK_CHECKING ? <Spinner /> : t('login.credentials.checkBtn')}
          </button>
        </div>
        {checkHintText && (
          <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: checkHintColor, lineHeight: 1.4 }}>
            {checkHintText}
          </p>
        )}

        <label style={{ ...monoLabelStyle, marginTop: 4 }} htmlFor="cred-password">
          {t('login.credentials.password.label')}
        </label>
        <input
          id="cred-password"
          type="password"
          value={localPassword}
          onChange={e => setLocalPassword(e.target.value)}
          disabled={disabled}
          placeholder={t('login.credentials.password.placeholder')}
          aria-label={t('login.credentials.password.aria')}
          maxLength={128}
          aria-required="true"
          className="lp-input"
          style={paperInputStyle}
        />

        <div style={buttonGridStyle}>
          <button
            type="button"
            className="lp-btn"
            onClick={onBack}
            disabled={disabled}
            style={inkSecondaryStyle(disabled)}
          >
            {t('login.common.back')}
          </button>
          <button
            type="submit"
            className="lp-cta"
            disabled={!canContinue}
            style={inkPrimaryStyle(!canContinue)}
          >
            {t('login.credentials.continueBtn')}
          </button>
        </div>
      </form>
    </AuthCard>
  )
}

function ConsentDeck({
  t, typedLine, id, role, roles, language, affiliation, profileReady, disabled, onAction,
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

  const monogram = id ? Array.from(id)[0].toUpperCase() : ''
  const affiliationTrimmed = affiliation && affiliation.trim() ? affiliation.trim() : ''

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
            typedLine={typedLine}
            trailing={<LangToggle />}
          />

          {/* Middle: filled card preview — id / objective / affiliation */}
          <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={cardNameStyle}>{id}</div>
            {role && (
              <div style={cardRoleStyle}>
                {roleLabel(
                  (roles && roles.length ? roles : ONBOARDING_ROLES).find(r => r.value === role) || { value: role, label_en: role, label_ko: role },
                  language,
                )}
              </div>
            )}
            {affiliationTrimmed && (
              <div style={cardMetaStyle}>{affiliationTrimmed}</div>
            )}
          </section>

          {/* Footer: @id + JOINED year left, monogram stamp right */}
          <footer style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 14 }}>
            <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={monoRowStyle}>@{id}</div>
              <div style={monoLabelStyle}>JOINED {new Date().getFullYear()}</div>
            </div>
            <div style={{
              flexShrink: 0,
              width: 72,
              height: 72,
              border: '1px solid var(--color-border-soft)',
              borderRadius: 4,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
            }}>
              <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--color-text)', lineHeight: 1 }}>
                {monogram}
              </span>
              <span style={{ fontFamily: MONO, fontSize: 7, fontWeight: 500, color: INK.dim, letterSpacing: '0.1em' }}>
                ARCHIBE
              </span>
            </div>
          </footer>

          <p style={finePrintStyle}>{t('login.consent.finePrint')}</p>

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
          placeholder={t('login.returning.id.placeholder')}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          aria-label={t('login.returning.id.aria')}
          className="lp-input"
          style={paperInputStyle}
        />
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          disabled={disabled}
          placeholder={t('login.returning.password.placeholder')}
          aria-label={t('login.returning.password.aria')}
          className="lp-input"
          style={paperInputStyle}
        />
        <button
          type="submit"
          className="lp-cta"
          disabled={disabled || !handle.trim() || !password}
          style={inkPrimaryStyle(disabled || !handle.trim() || !password)}
        >
          {loginLoading ? <Spinner /> : t('login.returning.submit')}
        </button>
      </form>

      <button
        type="button"
        className="lp-btn"
        onClick={onBack}
        disabled={disabled}
        style={inkGhostStyle(disabled)}
      >
        {t('login.common.back')}
      </button>
    </AuthCard>
  )
}

function ProfileStep({
  t,
  typedLine,
  role,
  roles,
  language,
  affiliation,
  disabled,
  onRoleChange,
  onAffiliationChange,
  onBack,
  onSubmit,
}) {
  const profileReady = isRoleReady(role)
  const roleList = roles && roles.length ? roles : ONBOARDING_ROLES

  return (
    <AuthCard ariaLabel={t('login.profile.eyebrow')}>
      <CardHeader
        eyebrow={t('login.profile.eyebrow')}
        title={t('login.profile.title')}
        typedLine={typedLine}
        trailing={<LangToggle />}
      />
      <form onSubmit={onSubmit} style={formStyle}>
        <label style={monoLabelStyle} htmlFor="guest-affiliation">
          {t('login.profile.affiliation.label')}
        </label>
        <input
          id="guest-affiliation"
          autoFocus
          type="text"
          value={affiliation}
          onChange={e => onAffiliationChange(e.target.value)}
          disabled={disabled}
          placeholder={t('login.profile.affiliation.placeholder')}
          maxLength={100}
          className="lp-input"
          style={paperInputStyle}
        />

        <div style={roleHeaderStyle}>
          <span style={monoLabelStyle}>{t('login.profile.objective.label')}</span>
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
          {roleList.map(roleOption => (
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
              {roleLabel(roleOption, language)}
            </button>
          ))}
        </div>

        <div style={buttonGridStyle}>
          <button
            type="button"
            className="lp-btn"
            onClick={onBack}
            disabled={disabled}
            style={inkSecondaryStyle(disabled)}
          >
            {t('login.common.back')}
          </button>
          <button
            type="submit"
            className="lp-cta"
            disabled={disabled || !profileReady}
            style={inkPrimaryStyle(disabled || !profileReady)}
          >
            {t('login.profile.continueBtn')}
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
        <span style={cardWordmarkStyle}>ARCHIBE</span>
        {trailing}
      </div>
      <p style={monoLabelStyle}>{eyebrow}</p>
      {title && <h2 style={titleStyle}>{title}</h2>}
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
          ...paperFaceStyle({ radius: 20 }),
          width: AUTH_STAGE_WIDTH,
          height: AUTH_CARD_HEIGHT,
          alignItems: 'stretch',
          overflowY: 'auto',
        }}
      >
        {/* wordmark + eyebrow + LangToggle row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
          <span style={cardWordmarkStyle}>ARCHIBE</span>
          <LangToggle />
        </div>
        <p style={{ ...monoLabelStyle, marginTop: 10 }}>{t('login.intro.eyebrow')}</p>

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
          style={{ ...inkPrimaryStyle(false), width: '100%', marginTop: 12 }}
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

// SETTINGS-POLISH-1: label picked by current language — ko → label_ko, else
// label_en. Roles come from getRoles() (api/meta.js), shape {value,
// label_en, label_ko}.
function roleLabel(roleOption, language) {
  if (!roleOption) return ''
  return language === 'ko'
    ? (roleOption.label_ko || roleOption.label_en || roleOption.value)
    : (roleOption.label_en || roleOption.label_ko || roleOption.value)
}

function roleButtonStyle(disabled, active) {
  return {
    minHeight: 42,
    borderRadius: 12,
    border: active ? '1px solid var(--color-text)' : '1px solid var(--color-border)',
    background: active ? 'color-mix(in srgb, var(--color-text) 8%, transparent)' : 'var(--color-bg)',
    color: 'var(--color-text)',
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

const stageStyle = {
  width: AUTH_STAGE_WIDTH,
}

const authCardStyle = {
  ...paperFaceStyle({ radius: 20 }),
  gap: 16,
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

const titleStyle = {
  margin: 0,
  color: 'var(--color-text)',
  fontSize: 26,
  fontWeight: 700,
  lineHeight: 1.16,
  letterSpacing: '-0.01em',
}

const typedLineStyle = {
  minHeight: 44,
  margin: 0,
  fontFamily: MONO,
  color: INK.muted,
  fontSize: 13,
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
  border: '1px solid var(--color-border-soft)',
  background: 'transparent',
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

const errorStyle = {
  color: 'var(--color-destructive, #D73A49)',
  fontSize: 12,
  fontFamily: MONO,
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
