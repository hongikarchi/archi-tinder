/**
 * pages/OnboardingPage.jsx
 * First-login profile step: ID (suggested from the social profile), optional
 * affiliation, objective, and required consent. Backend: POST /auth/onboarding/.
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import styles from './LoginPage.module.css'
import { getMe, checkHandle, completeOnboarding } from '../api/auth.js'
import { getRoles } from '../api/meta.js'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import { ONBOARDING_ROLES, isIdFormatValid } from '../utils/loginFlow.js'
import { ONBOARDING_FLAG_KEY } from '../utils/onboardingFlag.js'
import { useTranslation } from '../i18n/index.js'
import {
  paperFaceStyle, baseLabelStyle, paperInputStyle, inkPrimaryStyle,
} from '../components/cardLanguage.js'

const ID_CHECK_DEBOUNCE_MS = 450

function roleLabel(role, language) {
  return language === 'ko'
    ? (role.label_ko || role.label_en || role.value)
    : (role.label_en || role.label_ko || role.value)
}

export default function OnboardingPage() {
  const { t, language } = useTranslation()
  const navigate = useNavigate()

  const [ready, setReady]             = useState(false)
  const [suggestion, setSuggestion]   = useState('')
  const [value, setValue]             = useState('')
  const [checkState, setCheckState]   = useState('idle') // idle | checking | available | taken
  const [checkReason, setCheckReason] = useState('')
  const [affiliation, setAffiliation] = useState('')
  const [role, setRole]               = useState('')
  const [consent, setConsent]         = useState(false)
  const [roles, setRoles]             = useState(ONBOARDING_ROLES)
  const [submitting, setSubmitting]   = useState(false)
  const [error, setError]             = useState('')

  const composingRef = useRef(false)
  const debounceRef  = useRef(null)
  const tokenRef     = useRef(0)

  useEffect(() => {
    let cancelled = false
    getRoles().then(list => { if (!cancelled && list?.length) setRoles(list) }).catch(() => {})
    getMe()
      .then(me => {
        if (cancelled) return
        if (me && me.onboarding_required === false) {
          sessionStorage.removeItem(ONBOARDING_FLAG_KEY)
          navigate('/discovery', { replace: true })
          return
        }
        const h = me?.handle || ''
        setSuggestion(h)
        setValue(h)
        setReady(true)
      })
      .catch(() => { if (!cancelled) setReady(true) })
    return () => { cancelled = true }
  }, [navigate])

  useEffect(() => () => { if (debounceRef.current) window.clearTimeout(debounceRef.current) }, [])

  function scheduleCheck(next) {
    tokenRef.current += 1
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
    setCheckReason('')
    setCheckState('idle')
    if (!next || next === suggestion) return
    if (composingRef.current) return
    debounceRef.current = window.setTimeout(() => {
      if (!isIdFormatValid(next)) return
      const token = ++tokenRef.current
      setCheckState('checking')
      checkHandle(next)
        .then(res => {
          if (tokenRef.current !== token) return
          setCheckState(res.available ? 'available' : 'taken')
          setCheckReason(res.available ? '' : (res.reason || ''))
        })
        .catch(() => { if (tokenRef.current === token) setCheckState('idle') })
    }, ID_CHECK_DEBOUNCE_MS)
  }

  function handleChange(next) {
    setValue(next)
    scheduleCheck(next)
  }

  function handleFocus() {
    if (value === suggestion) setValue('')
  }

  function handleBlur() {
    if (value === '') {
      setValue(suggestion)
      scheduleCheck(suggestion)
    }
  }

  const handle      = (value === '' ? suggestion : value).normalize('NFC')
  const isSuggested = handle === suggestion
  const handleValid = isSuggested ? !!suggestion : (isIdFormatValid(handle) && checkState === 'available')
  const canSubmit   = !!role && consent && handleValid && !submitting

  async function handleSubmit(e) {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError('')
    try {
      await completeOnboarding({
        handle,
        affiliation: affiliation.trim().slice(0, 100),
        onboarding_role: role,
        consent_accepted: true,
        consent_policy_version: '1.0',
      })
      sessionStorage.removeItem(ONBOARDING_FLAG_KEY)
      localStorage.setItem('archithon_show_tutorial', '1')
      navigate('/discovery', { replace: true })
    } catch (err) {
      const d = err?.data
      if (d?.detail === 'already_onboarded') {
        sessionStorage.removeItem(ONBOARDING_FLAG_KEY)
        navigate('/discovery', { replace: true })
        return
      }
      setError(d?.message || err?.message || t('onboarding.failed'))
    } finally {
      setSubmitting(false)
    }
  }

  const formatBad = !isSuggested && handle && !isIdFormatValid(handle)
  const hintText =
    checkState === 'checking'  ? t('onboarding.checking') :
    checkState === 'available' ? t('onboarding.available') :
    checkState === 'taken'     ? (checkReason || t('onboarding.taken')) :
    formatBad                  ? t('login.error.idInvalid') : ''
  const hintColor =
    checkState === 'available' ? 'var(--accent-1)' :
    (checkState === 'taken' || formatBad) ? 'var(--color-destructive)' :
    'var(--color-text-dim)'

  return (
    <div className={styles.page} style={pageStyle}>
      <PageTopControls />
      <PageLogoHeader style={{ position: 'absolute', top: 0, left: 0 }} />
      <main style={mainStyle}>
        <form onSubmit={handleSubmit} className={styles.cardIn} style={cardStyle}>
          <h1 style={titleStyle}>{t('onboarding.title')}</h1>
          <p style={subtitleStyle}>{t('onboarding.subtitle')}</p>

          <label style={baseLabelStyle} htmlFor="onb-id">{t('onboarding.idLabel')}</label>
          <input
            id="onb-id"
            type="text"
            value={value}
            placeholder={suggestion}
            onChange={e => handleChange(e.target.value)}
            onFocus={handleFocus}
            onBlur={handleBlur}
            onCompositionStart={() => {
              composingRef.current = true
              if (debounceRef.current) window.clearTimeout(debounceRef.current)
            }}
            onCompositionEnd={e => {
              composingRef.current = false
              handleChange(e.target.value)
            }}
            disabled={!ready || submitting}
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            maxLength={20}
            aria-label={t('onboarding.idAria')}
            className={styles.input}
            style={paperInputStyle}
          />
          <p aria-live="polite" style={{ margin: 0, minHeight: 16, fontSize: 12, fontWeight: 600, color: hintColor }}>
            {hintText}
          </p>

          <label style={baseLabelStyle} htmlFor="onb-aff">{t('onboarding.affiliationLabel')}</label>
          <input
            id="onb-aff"
            type="text"
            value={affiliation}
            onChange={e => setAffiliation(e.target.value)}
            maxLength={100}
            placeholder={t('onboarding.affiliationPlaceholder')}
            disabled={submitting}
            className={styles.input}
            style={paperInputStyle}
          />

          <span style={baseLabelStyle}>{t('onboarding.roleLabel')}</span>
          <div role="radiogroup" aria-label={t('onboarding.roleAria')} aria-required="true" style={{ display: 'grid', gap: 8 }}>
            {roles.map(r => (
              <button
                key={r.value}
                type="button"
                role="radio"
                aria-checked={role === r.value}
                onClick={() => setRole(r.value)}
                disabled={submitting}
                className={styles.btn}
                style={roleButtonStyle(role === r.value)}
              >
                {roleLabel(r, language)}
              </button>
            ))}
          </div>

          <label style={consentStyle}>
            <input
              type="checkbox"
              checked={consent}
              onChange={e => setConsent(e.target.checked)}
              disabled={submitting}
            />
            <span>{t('onboarding.consent')}</span>
          </label>

          <button type="submit" className={styles.cta} disabled={!canSubmit} style={inkPrimaryStyle(!canSubmit)}>
            {t('onboarding.submit')}
          </button>
          <p role="alert" style={errorStyle}>{error}</p>
        </form>
      </main>
    </div>
  )
}

function roleButtonStyle(active) {
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
    cursor: 'pointer',
  }
}

const pageStyle = {
  height: '100vh',
  overflowY: 'auto',
  display: 'flex',
  justifyContent: 'center',
  padding: '64px 16px 24px',
  boxSizing: 'border-box',
}

const mainStyle = { width: '100%', maxWidth: 420, margin: 'auto 0' }

const cardStyle = {
  ...paperFaceStyle({ radius: 20 }),
  padding: '32px 28px',
  gap: 10,
}

const titleStyle = {
  margin: 0,
  color: 'var(--color-text)',
  fontSize: 26,
  fontWeight: 700,
  letterSpacing: '-0.01em',
}

const subtitleStyle = {
  margin: '0 0 6px',
  color: 'var(--color-text-2)',
  fontSize: 14,
  fontWeight: 500,
}

const consentStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 8,
  marginTop: 6,
  color: 'var(--color-text-2)',
  fontSize: 13,
  lineHeight: 1.45,
}

const errorStyle = {
  margin: 0,
  minHeight: 18,
  color: 'var(--color-destructive, #D73A49)',
  fontSize: 12,
  fontWeight: 500,
  textAlign: 'center',
}
