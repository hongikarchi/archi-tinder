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
 *
 * LOGIN-REWORK-1 (2026-07-07): real card deck (next card pre-rendered behind
 * the front one) + step-history stack for back-nav; no more IntroOverlay
 * modal — the first `choice` card teaches the swipe itself. See
 * .claude/plans/login-page-concept-rework.md for the full diagnosis.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import styles from './LoginPage.module.css'
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
  loginWordmarkStyle as cardWordmarkStyle,
  baseLabelStyle,
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

// LOGIN-REWORK-1: deterministic "what card is waiting behind" map for the
// linear (non-branching) form steps. `choice` and `consent` branch by swipe
// direction, so their back-card is resolved dynamically from drag intent
// (see ChoiceDeck / ConsentDeck `intent` state) instead of this table.
const LINEAR_NEXT_STEP = {
  [FLOW_STEPS.credentials]: FLOW_STEPS.profile,
  [FLOW_STEPS.profile]:     FLOW_STEPS.consent,
}

// Steps that resolve their own back-card internally from live drag intent
// (branching steps) — the parent deck must not also wrap them in a second
// pre-rendered back layer (see ChoiceDeck / ConsentDeck `renderBackStep`).
const SELF_BACKED_STEPS = new Set([FLOW_STEPS.choice, FLOW_STEPS.consent])

const AUTH_STAGE_WIDTH = `${CARD_WIDTH}px`
const AUTH_CARD_HEIGHT = `${CARD_HEIGHT}px`

export default function LoginPage({ onLogin }) {
  const { t, language } = useTranslation()
  const { setLanguage } = useLanguage()

  const [step, setStep]                         = useState(FLOW_STEPS.choice)
  // LOGIN-REWORK-1: step-history stack — advancing pushes the step being LEFT
  // onto history; 'back' pops it so the previous card returns to the deck top.
  // A ref (not state) is correct here: the stack itself is never rendered —
  // only `step` (derived via setStep) drives the UI.
  const historyRef = useRef([])

  // New-profile state: lifted to parent so consent step can access all fields.
  const [id, setId]                             = useState('')
  const [password, setPassword]                 = useState('')
  const [affiliation, setAffiliation]           = useState('')
  const [role, setRole]                         = useState('')

  const [consentGiven, setConsentGiven]         = useState(false)
  const [consentResetTick, setConsentResetTick] = useState(0)
  const [loading, setLoading]                   = useState(null)
  const [error, setError]                       = useState(null)

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

  // Push the current step onto history, then advance to `nextStep`.
  const advanceStep = useCallback((nextStep) => {
    historyRef.current = [...historyRef.current, step]
    setStep(nextStep)
  }, [step])

  // Pop history — previous card returns to the top of the deck. No-op if
  // history is empty (shouldn't happen since `choice` never pushes a back).
  const goBack = useCallback(() => {
    const prev = historyRef.current
    if (prev.length === 0) return
    historyRef.current = prev.slice(0, -1)
    setStep(prev[prev.length - 1])
  }, [])

  // Stable callbacks — setState setters are stable, module constants are stable.
  const handleChoiceAction = useCallback((action) => {
    setError(null)
    setConsentGiven(false)
    advanceStep(action === LOGIN_SWIPE_ACTIONS.left ? FLOW_STEPS.returning : FLOW_STEPS.credentials)
  }, [advanceStep])

  const handleConsentAction = useCallback((action) => {
    if (action === 'back') {
      setConsentGiven(false)
      setError(null)
      goBack()
    } else {
      setConsentGiven(true)
      registerSubmitRef.current()
    }
  }, [goBack])

  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)
  const isBusy           = loading !== null
  const errorText        = error && (error.key ? t(error.key, error.params) : error.text)

  function moveToStep(nextStep) {
    setError(null)
    advanceStep(nextStep)
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
      // FRONT-FLOW-1: newly registered accounts see the swipe tutorial on their
      // first Discovery entry. Set BEFORE onLogin (which may navigate/unmount).
      localStorage.setItem('archithon_show_tutorial', '1')
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

  // LOGIN-REWORK-1: renders any step's card body by key. Used both for the
  // interactive FRONT card (isActive=true) and for pre-rendering the inert
  // BACK card (isActive=false — no autoFocus, no typed line, no interaction)
  // so the deck's "next card" already exists in the tree before it surfaces.
  function renderStep(stepKey, { isActive = true, key } = {}) {
    const line = isActive ? typedLine : ''
    switch (stepKey) {
      case FLOW_STEPS.choice:
        return (
          <ChoiceDeck
            key={key}
            t={t}
            typedLine={line}
            disabled={isBusy || !isActive}
            onAction={handleChoiceAction}
            renderBackStep={isActive ? (backKey) => renderStep(backKey, { isActive: false, key: `back-${backKey}` }) : undefined}
          />
        )
      case FLOW_STEPS.returning:
        return (
          <ReturningStep
            key={key}
            t={t}
            typedLine={line}
            isActive={isActive}
            showGoogle={googleConfigured}
            disabled={isBusy || !isActive}
            googleLoading={loading === 'google'}
            loginLoading={loading === 'login'}
            onBack={goBack}
            onGoogleSuccess={handleGoogleSuccess}
            onGoogleError={handleGoogleError}
            onGoogleNonOAuthError={handleGoogleNonOAuthError}
            onLoginSubmit={handleLoginSubmit}
          />
        )
      case FLOW_STEPS.credentials:
        return (
          <CredentialsStep
            key={key}
            t={t}
            typedLine={line}
            isActive={isActive}
            disabled={isBusy || !isActive}
            onBack={goBack}
            onContinue={handleCredentialsContinue}
          />
        )
      case FLOW_STEPS.profile:
        return (
          <ProfileStep
            key={key}
            t={t}
            typedLine={line}
            isActive={isActive}
            role={role}
            roles={roles}
            language={language}
            affiliation={affiliation}
            disabled={isBusy || !isActive}
            onRoleChange={(value) => {
              setRole(value)
              setError(null)
              setConsentGiven(false)
            }}
            onAffiliationChange={(value) => {
              setAffiliation(value)
              setConsentGiven(false)
            }}
            onBack={goBack}
            onSubmit={handleProfileContinue}
          />
        )
      case FLOW_STEPS.consent:
        return (
          <ConsentDeck
            key={key ?? `consent-${consentResetTick}`}
            t={t}
            typedLine={line}
            id={id}
            role={role}
            roles={roles}
            language={language}
            affiliation={affiliation}
            profileReady={isIdFormatValid(id) && isRoleReady(role)}
            disabled={isBusy || !isActive}
            onAction={handleConsentAction}
            renderBackStep={isActive ? () => renderStep(FLOW_STEPS.profile, { isActive: false, key: 'back-profile' }) : undefined}
          />
        )
      default:
        return null
    }
  }

  // The step a bare (non-branching) advance would land on next — pre-rendered
  // behind the front card so the deck feels like it was already waiting.
  const linearNextStep = SELF_BACKED_STEPS.has(step) ? null : (LINEAR_NEXT_STEP[step] || null)

  // FIX (LOGIN-REWORK-1 review finding, high): the front-card key must force a
  // fresh mount on a failed register() from the consent card. react-tinder-card
  // has no restore-after-completed-swipe path in handleSwipeReleased (only
  // restoreCard()/remount reset the spring) — so after a swiped-away consent
  // card whose register() call fails server-side (duplicate id / weak password
  // / consent_required retry), the card stays flown off-screen forever unless
  // remounted. `step` alone never changes on that failure path (only
  // consentResetTick increments — see handleRegisterSubmit catch), so folding
  // the tick into the key here (not the dead `key ?? ...` fallback at the
  // consent case in renderStep, which never fires since callers always pass a
  // truthy key) is what actually forces the remount. The back-card pre-render
  // (`key: 'back-consent'`) is intentionally unaffected — it never swipes.
  const frontCardKey = step === FLOW_STEPS.consent ? `consent-${consentResetTick}` : step

  return (
    <div className={styles.page} style={pageStyle}>
      <main style={mainStyle}>
        <div style={stageStyle}>
          <div style={deckStackStyle}>
            {linearNextStep && (
              <div aria-hidden="true" style={backCardWrapStyle}>
                {renderStep(linearNextStep, { isActive: false, key: `back-${linearNextStep}` })}
              </div>
            )}
            <div key={frontCardKey} className={styles.cardIn} style={frontCardWrapStyle}>
              {renderStep(step, { key: frontCardKey })}
            </div>
          </div>
        </div>

        {import.meta.env.DEV && (
          <button
            type="button"
            className={styles.btn}
            onClick={handleDevClick}
            disabled={isBusy}
            style={inkGhostStyle(isBusy)}
          >
            {loading === 'dev' ? <Spinner /> : t('login.dev.button')}
          </button>
        )}

        {/* Fixed-height slot — reserved even when empty so error text never
            shifts the deck (LOGIN-REWORK-1 issue: floating error caused layout jump). */}
        <p role="alert" style={errorStyle}>
          {errorText || ''}
        </p>
      </main>
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
  const { t } = useTranslation()
  const stop = (e) => e.stopPropagation()
  const langs = [{ id: 'ko', labelKey: 'login.common.langKo' }, { id: 'en', labelKey: 'login.common.langEn' }]

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
            {t(l.labelKey)}
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
      <span style={{ fontFamily: 'var(--font-family)', fontSize: 11, fontWeight: 500, color: INK.dim }}>
        {sub}
      </span>
    </div>
  )
}

// LOGIN-REWORK-1: choice is the FIRST card — it teaches the swipe itself
// (typed question + animated L/R gesture hints), no separate intro modal.
// The card waiting behind it is resolved live from drag `intent`: dragging
// left surfaces "returning" behind, dragging right surfaces "credentials"
// behind; idle defaults to "credentials" (the primary new-profile path).
function ChoiceDeck({ t, typedLine, disabled, onAction, renderBackStep }) {
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
  const backStepKey = intent === 'left' ? FLOW_STEPS.returning : FLOW_STEPS.credentials

  return (
    <div style={{ position: 'relative', width: '100%', height: AUTH_CARD_HEIGHT }}>
      {renderBackStep && (
        <div aria-hidden="true" style={backCardWrapStyle}>
          {renderBackStep(backStepKey)}
        </div>
      )}
      <SwipeGestureFrame
        className={styles.tinder}
        onSwipe={handleSwipe}
        onCardLeftScreen={handleLeftScreen}
        onSwipeRequirementFulfilled={handleFulfilled}
        onSwipeRequirementUnfulfilled={handleUnfulfilled}
        preventSwipe={preventSwipe}
      >
        <AuthCard absolute ariaLabel={t('login.choice.eyebrow')}>
          <CardHeader
            title={t('login.choice.title')}
            typedLine={typedLine}
            trailing={<LangToggle />}
          />
          <SwipeTutorial intent={intent} />
          <p style={bodyCopyStyle}>{t('login.choice.body')}</p>
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

// LOGIN-REWORK-1: debounce delay before auto-checking ID availability.
const ID_CHECK_DEBOUNCE_MS = 450

function CredentialsStep({ t, typedLine, isActive = true, disabled, onBack, onContinue }) {
  const [localId, setLocalId]             = useState('')
  const [localPassword, setLocalPassword] = useState('')
  const [checkState, setCheckState]       = useState(CHECK_IDLE)
  const [confirmedId, setConfirmedId]     = useState('')  // the id that was confirmed available
  const [checkError, setCheckError]       = useState(null)

  // IME composition guard — Korean (and other IME) input fires onChange per
  // jamo/keystroke while composing; checkHandle must only fire on committed text.
  const isComposingRef = useRef(false)
  // Debounce timer + a request token so a stale in-flight response for an
  // older id value can never overwrite a newer id's state.
  const debounceRef = useRef(null)
  const requestTokenRef = useRef(0)

  const idNfc         = localId.normalize('NFC')
  const idFormatValid = isIdFormatValid(localId)
  const passwordValid = localPassword.length >= 8

  const runCheck = useCallback((value) => {
    const nfc = value.normalize('NFC')
    if (!isIdFormatValid(value)) {
      setCheckState(CHECK_IDLE)
      setCheckError(null)
      return
    }
    const token = ++requestTokenRef.current
    setCheckState(CHECK_CHECKING)
    setCheckError(null)
    checkHandle(value)
      .then((result) => {
        if (requestTokenRef.current !== token) return  // stale response, ignore
        if (result.available) {
          setCheckState(CHECK_AVAILABLE)
          setConfirmedId(nfc)
          setCheckError(null)
        } else {
          setCheckState(CHECK_TAKEN)
          setConfirmedId('')
          setCheckError(result.reason || t('login.credentials.id.taken'))
        }
      })
      .catch(() => {
        if (requestTokenRef.current !== token) return
        setCheckState(CHECK_IDLE)
        setCheckError(t('login.error.idInvalid'))
      })
  }, [t])

  // Debounced auto-check on typing. Skips entirely while an IME composition
  // is in progress (isComposingRef) — compositionend re-triggers explicitly.
  function handleIdChange(value) {
    setLocalId(value)
    setCheckError(null)
    setCheckState(CHECK_IDLE)
    setConfirmedId('')
    // Invalidate any in-flight/pending check for the previous value.
    requestTokenRef.current += 1
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
    if (isComposingRef.current) return
    debounceRef.current = window.setTimeout(() => runCheck(value), ID_CHECK_DEBOUNCE_MS)
  }

  function handleCompositionStart() {
    isComposingRef.current = true
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
  }

  function handleCompositionEnd(e) {
    isComposingRef.current = false
    const value = e.target.value
    setLocalId(value)
    requestTokenRef.current += 1
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => runCheck(value), ID_CHECK_DEBOUNCE_MS)
  }

  // Cleanup pending debounce on unmount.
  useEffect(() => () => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
  }, [])

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
        title={t('login.credentials.title')}
        typedLine={typedLine}
        trailing={<LangToggle />}
      />
      <form onSubmit={handleSubmit} style={formStyle}>
        <label style={baseLabelStyle} htmlFor="cred-id">
          {t('login.credentials.id.label')}
        </label>
        <input
          id="cred-id"
          autoFocus={isActive}
          type="text"
          value={localId}
          onChange={e => handleIdChange(e.target.value)}
          onCompositionStart={handleCompositionStart}
          onCompositionEnd={handleCompositionEnd}
          disabled={disabled}
          placeholder={t('login.credentials.id.placeholder')}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          maxLength={20}
          aria-label={t('login.credentials.id.aria')}
          aria-invalid={localId.length > 0 && !idFormatValid ? 'true' : 'false'}
          className={styles.input}
          style={paperInputStyle}
        />
        <p aria-live="polite" style={{ margin: 0, minHeight: 16, fontSize: 12, fontWeight: 600, color: checkHintColor, lineHeight: 1.4, display: 'flex', alignItems: 'center', gap: 6 }}>
          {checkState === CHECK_CHECKING && <Spinner small />}
          {checkHintText}
        </p>

        <label style={{ ...baseLabelStyle, marginTop: 4 }} htmlFor="cred-password">
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
          className={styles.input}
          style={paperInputStyle}
        />

        <div style={buttonGridStyle}>
          <button
            type="button"
            className={styles.btn}
            onClick={onBack}
            disabled={disabled}
            style={inkSecondaryStyle(disabled)}
          >
            {t('login.common.back')}
          </button>
          <button
            type="submit"
            className={styles.cta}
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
  t, typedLine, id, role, roles, language, affiliation, profileReady, disabled, onAction, renderBackStep,
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
      {renderBackStep && (
        <div aria-hidden="true" style={backCardWrapStyle}>
          {renderBackStep()}
        </div>
      )}
      <SwipeGestureFrame
        className={styles.tinder}
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
          {/* Canvas design port (login family): name/role sizing overridden
              inline here only — cardNameStyle/cardRoleStyle are
              ConsentDeck-exclusive (verified: SwipePage/DiscoveryTriggerCard
              consume cardMetaStyle and monoLabelStyle only, not these two),
              so this is safe to adjust without a cross-page effect. */}
          <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ ...cardNameStyle, fontSize: 30, lineHeight: 1.15, textTransform: 'none' }}>{id}</div>
            {role && (
              <div style={{ ...cardRoleStyle, fontSize: 14, fontWeight: 600, color: 'var(--color-text-2)' }}>
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
          {/* monoLabelStyle is shared with SwipePage/DiscoveryTriggerCard —
              overridden inline here only, never edited in cardLanguage.js. */}
          <footer style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 14 }}>
            <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ ...monoRowStyle, letterSpacing: '0.06em' }}>@{id}</div>
              <div style={{ ...monoLabelStyle, fontSize: 10, textTransform: 'none', letterSpacing: '0.1em', color: 'var(--color-text-dim)' }}>JOINED {new Date().getFullYear()}</div>
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
  isActive = true,
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
          className={styles.btn}
          style={{
            width: '100%',
            minHeight: 48,
            borderRadius: 12,
            border: '1px solid var(--accent-1)',
            background: 'var(--accent-1)',
            color: '#fff',
            fontWeight: 700,
          }}
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
          autoFocus={isActive && !showGoogle}
          value={handle}
          onChange={e => setHandle(e.target.value)}
          disabled={disabled}
          placeholder={t('login.returning.id.placeholder')}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          aria-label={t('login.returning.id.aria')}
          className={styles.input}
          style={paperInputStyle}
        />
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          disabled={disabled}
          placeholder={t('login.returning.password.placeholder')}
          aria-label={t('login.returning.password.aria')}
          className={styles.input}
          style={paperInputStyle}
        />
        <button
          type="submit"
          className={styles.cta}
          disabled={disabled || !handle.trim() || !password}
          style={inkPrimaryStyle(disabled || !handle.trim() || !password)}
        >
          {loginLoading ? <Spinner /> : t('login.returning.submit')}
        </button>
      </form>

      <button
        type="button"
        className={styles.btn}
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
  isActive = true,
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
        title={t('login.profile.title')}
        typedLine={typedLine}
        trailing={<LangToggle />}
      />
      <form onSubmit={onSubmit} style={formStyle}>
        <label style={baseLabelStyle} htmlFor="guest-affiliation">
          {t('login.profile.affiliation.label')}
        </label>
        <input
          id="guest-affiliation"
          autoFocus={isActive}
          type="text"
          value={affiliation}
          onChange={e => onAffiliationChange(e.target.value)}
          disabled={disabled}
          placeholder={t('login.profile.affiliation.placeholder')}
          maxLength={100}
          className={styles.input}
          style={paperInputStyle}
        />

        <div style={roleHeaderStyle}>
          <span style={baseLabelStyle}>{t('login.profile.objective.label')}</span>
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
              className={styles.btn}
              style={roleButtonStyle(disabled, role === roleOption.value)}
            >
              {roleLabel(roleOption, language)}
            </button>
          ))}
        </div>

        <div style={buttonGridStyle}>
          <button
            type="button"
            className={styles.btn}
            onClick={onBack}
            disabled={disabled}
            style={inkSecondaryStyle(disabled)}
          >
            {t('login.common.back')}
          </button>
          <button
            type="submit"
            className={styles.cta}
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
      {/* LOGIN-REWORK-1: eyebrow only renders when it adds orientation the
          typed question doesn't already give (issue 5 — remove noise copy). */}
      {eyebrow && <p style={baseLabelStyle}>{eyebrow}</p>}
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

// LOGIN-REWORK-1: the animated mini-card + arrows tutorial, formerly inside
// the (now-removed) IntroOverlay modal. Lives directly in ChoiceDeck's card
// body — the first card teaches the swipe itself, no separate modal.
function SwipeTutorial({ intent }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
      <span
        className={styles.arrowLeft}
        aria-hidden="true"
        style={{
          fontSize: 22, fontWeight: 700, flexShrink: 0,
          color: intent === 'left' ? 'var(--color-text)' : 'var(--color-text-dim)',
        }}
      >
        &#8592;
      </span>
      <div
        className={styles.swipeDemo}
        aria-hidden="true"
        style={{
          width: 84, height: 112,
          borderRadius: 10,
          background: 'var(--color-surface-2)',
          border: '1px solid var(--color-border-soft)',
          boxShadow: '0 6px 18px rgba(0,0,0,0.18)',
          display: 'flex', alignItems: 'flex-start',
          padding: 10,
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 7, fontWeight: 700, letterSpacing: '0.28em', color: 'var(--color-text-muted)' }}>
          ARCHIBE
        </span>
      </div>
      <span
        className={styles.arrowRight}
        aria-hidden="true"
        style={{
          fontSize: 22, fontWeight: 700, flexShrink: 0,
          color: intent === 'right' ? 'var(--color-text)' : 'var(--color-text-dim)',
        }}
      >
        &#8594;
      </span>
    </div>
  )
}

function Spinner({ small = false } = {}) {
  const size = small ? 12 : 18
  return (
    <span aria-hidden="true" style={{
      width: size,
      height: size,
      border: '2px solid currentColor',
      borderTopColor: 'transparent',
      borderRadius: '50%',
      display: 'inline-block',
      flexShrink: 0,
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

// LOGIN-REWORK-1: deck stack — the back card (pre-rendered, inert) sits
// absolutely behind the front card so advancing surfaces a card that was
// already waiting rather than mounting fresh. `position:relative` container
// sized to the card so both layers align.
const deckStackStyle = {
  position: 'relative',
  width: AUTH_STAGE_WIDTH,
  height: AUTH_CARD_HEIGHT,
}

const backCardWrapStyle = {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  pointerEvents: 'none',
  userSelect: 'none',
  transform: 'translateY(10px) scale(0.96)',
  opacity: 0.55,
  transition: `transform var(--motion-normal) var(--motion-ease), opacity var(--motion-normal) var(--motion-ease)`,
}

const frontCardWrapStyle = {
  position: 'relative',
  width: '100%',
  height: '100%',
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

// LOGIN-REWORK-1: the typed question is what tells the user what to do —
// base font family per DESIGN.md §2.5a (MONO reserved for @id / JOINED meta).
const typedLineStyle = {
  minHeight: 44,
  margin: 0,
  fontFamily: 'var(--font-family)',
  color: INK.mid,
  fontSize: 15,
  fontWeight: 500,
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

// LOGIN-REWORK-1: error text is instructional (tells the user what went
// wrong / what to fix) — base font, not MONO, per DESIGN.md §2.5a.
// FRONT-DESIGN-B1: fixed minHeight (~2 lines @ 12px/1.45) + always-rendered
// node (see JSX) — reserves the slot so the deck never jumps when an error
// appears/clears.
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
