/**
 * AccountScreen — /settings/account
 *
 * Editable: ID/handle (PATCH /api/v1/users/me/), password (POST /auth/set-password/).
 * Read-only display: email + verified status, is_guest (verified status), providers.
 * Email verify: Google auth-code flow → POST /auth/link-email/.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMe, updateMyProfile, setPassword as apiSetPassword } from '../../api/client.js'
import { IconBack } from '../../components/icons.jsx'
import GoogleVerifyButton from '../../components/GoogleVerifyButton.jsx'
import { hasGoogleLogin } from '../../utils/loginFlow.js'
import { useGoogleEmailVerify } from '../../hooks/useGoogleEmailVerify.js'
import { useTranslation } from '../../i18n/index.js'
import btnStyles from '../../components/Button.module.css'
import styles from './AccountScreen.module.css'

const LABEL_STYLE = {
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: '0.06em',
  color: 'var(--color-text-muted)',
  textTransform: 'uppercase',
  display: 'block',
  marginBottom: 6,
}

const HINT_STYLE = {
  fontSize: 12,
  color: 'var(--color-text-dim)',
  marginTop: 6,
  display: 'block',
  lineHeight: 1.5,
}

const READONLY_VALUE_STYLE = {
  fontSize: 15,
  color: 'var(--color-text)',
  fontWeight: 500,
  padding: '10px 0',
}

export default function AccountScreen() {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [me, setMe] = useState(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)

  // Handle draft state
  const [handle, setHandle] = useState('')
  const [handleError, setHandleError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Password section state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState(null)
  const [passwordCurrentError, setPasswordCurrentError] = useState(null)
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordSuccess, setPasswordSuccess] = useState(false)

  // Email verify — shared hook (must stay identical to VerifyGateModal; see useGoogleEmailVerify.js)
  const googleConfigured = hasGoogleLogin(import.meta.env.VITE_GOOGLE_CLIENT_ID)
  const {
    loading: verifyLoading,
    error: verifyError,
    onSuccess: handleVerifySuccess,
    onError: handleVerifyError,
    onNonOAuthError: handleVerifyNonOAuthError,
  } = useGoogleEmailVerify({
    onVerified: (fresh) => setMe(fresh),
  })

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setFetchError(null)
    getMe()
      .then(data => {
        if (cancelled) return
        setMe(data)
        setHandle(data.handle || '')
      })
      .catch(err => {
        if (cancelled) return
        setFetchError(err.message || t('account.profileLoadError'))
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave() {
    if (saving) return
    setHandleError(null)
    setSaveSuccess(false)

    // Client-side format check (backend also validates; this is UX-only)
    const trimmed = handle.trim()
    if (trimmed && !/^[a-z0-9_]{3,30}$/.test(trimmed)) {
      setHandleError(t('account.idHandleFormatError'))
      return
    }

    setSaving(true)
    try {
      const updated = await updateMyProfile({ handle: trimmed || null })
      // PATCH /users/me/ responds with UserProfileSerializer which includes handle.
      // Use ?? trimmed for both so the field never blanks if handle is absent in the response.
      setMe(prev => ({ ...prev, handle: updated.handle ?? trimmed }))
      setHandle(updated.handle ?? trimmed)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) {
      // Backend returns 400 with {handle: ["..."]} or {detail: "..."}
      const data = err?.data
      if (data?.handle) {
        setHandleError(Array.isArray(data.handle) ? data.handle[0] : data.handle)
      } else {
        setHandleError(err.message || t('account.saveFailed'))
      }
    } finally {
      setSaving(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleSave()
  }

  async function handlePasswordSave(e) {
    e.preventDefault()
    if (savingPassword) return
    setPasswordError(null)
    setPasswordCurrentError(null)
    setPasswordSuccess(false)

    if (newPassword.length < 8) {
      setPasswordError(t('account.passwordMin8'))
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError(t('account.passwordMismatch'))
      return
    }
    if (me?.has_password && !currentPassword) {
      setPasswordCurrentError(t('account.currentPasswordRequired'))
      return
    }

    setSavingPassword(true)
    try {
      const updatedUser = await apiSetPassword(
        newPassword,
        me?.has_password ? currentPassword : undefined,
      )
      // Token swap is done inside apiSetPassword — tokens already updated in localStorage.
      // Update local me so the form switches 설정↔변경.
      setMe(prev => ({ ...prev, has_password: true, ...updatedUser }))
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setPasswordSuccess(true)
      setTimeout(() => setPasswordSuccess(false), 3000)
    } catch (err) {
      const data = err?.data
      if (data?.current_password) {
        setPasswordCurrentError(Array.isArray(data.current_password) ? data.current_password[0] : data.current_password)
      } else if (data?.password) {
        setPasswordError(Array.isArray(data.password) ? data.password[0] : data.password)
      } else {
        setPasswordError(err.message || t('account.saveFailed'))
      }
    } finally {
      setSavingPassword(false)
    }
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <ScreenHeader navigate={navigate} t={t} />
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48, color: 'var(--color-text-dim)', fontSize: 14 }}>
          {t('account.loading')}
        </div>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className={styles.page}>
        <ScreenHeader navigate={navigate} t={t} />
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48, color: 'var(--color-destructive)', fontSize: 14 }}>
          {fetchError}
        </div>
      </div>
    )
  }

  const isDirty = handle !== (me?.handle || '')

  return (
    <div className={styles.page}>
      <ScreenHeader navigate={navigate} t={t} />

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>

        {/* Read-only info section */}
        <section style={{ marginBottom: 32 }}>
          <p style={{
            fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
            color: 'var(--color-text-muted)', textTransform: 'uppercase',
            margin: '0 0 16px',
          }}>
            {t('account.infoSection')}
          </p>

          <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
          }}>
            {/* Verified status */}
            <InfoRow
              label={t('account.status')}
              value={me?.is_guest ? t('account.statusGuest') : t('account.statusVerified')}
              valueStyle={{ color: me?.is_guest ? 'var(--accent-3)' : 'var(--accent-1)', fontWeight: 600 }}
            />

            {/* Login method (providers) */}
            <InfoRow
              label={t('account.loginMethod')}
              value={formatProviders(me?.providers)}
            />

            {/* Email */}
            <InfoRow
              label={t('account.email')}
              value={
                me?.email
                  ? me.email_verified_at
                    ? t('account.emailVerified', { email: me.email })
                    : t('account.emailUnverified', { email: me.email })
                  : '—'
              }
              valueStyle={
                me?.email && me?.email_verified_at
                  ? { color: 'var(--accent-1)', fontWeight: 500 }
                  : me?.email
                  ? { color: 'var(--accent-3)', fontWeight: 500 }
                  : {}
              }
              last
            />
          </div>
        </section>

        {/* ID (handle) edit section */}
        <section style={{ marginBottom: 32 }}>
          <p style={{
            fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
            color: 'var(--color-text-muted)', textTransform: 'uppercase',
            margin: '0 0 16px',
          }}>
            {t('account.idSection')}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <label>
              <span style={LABEL_STYLE}>ID</span>
              <input
                type="text"
                value={handle}
                onChange={(e) => {
                  setHandle(e.target.value)
                  setHandleError(null)
                  setSaveSuccess(false)
                }}
                onKeyDown={handleKeyDown}
                placeholder={t('account.idPlaceholder')}
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
                className={`${styles.inputWrapper} ${handleError ? styles.inputError : ''}`}
              />
              {handleError ? (
                <span style={{ ...HINT_STYLE, color: 'var(--color-destructive)' }}>
                  {handleError}
                </span>
              ) : (
                <span style={HINT_STYLE}>
                  {t('account.idHint')}
                </span>
              )}
            </label>

            {saveSuccess && (
              <div style={{
                padding: '10px 14px',
                background: 'color-mix(in srgb, var(--accent-1) 10%, transparent)',
                border: '1px solid var(--accent-1)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 13,
                color: 'var(--accent-1)',
                fontWeight: 500,
              }}>
                {t('account.idSaved')}
              </div>
            )}

            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !isDirty}
              className={btnStyles.cta}
              style={{ alignSelf: 'flex-start', minWidth: 120 }}
            >
              {saving ? t('account.saving') : t('account.save')}
            </button>
          </div>
        </section>

        {/* Password section */}
        <section style={{ marginBottom: 32 }}>
          <p style={{
            fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
            color: 'var(--color-text-muted)', textTransform: 'uppercase',
            margin: '0 0 16px',
          }}>
            {me?.has_password ? t('account.passwordChange') : t('account.passwordSet')}
          </p>

          <form onSubmit={handlePasswordSave} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {me?.has_password && (
              <label>
                <span style={LABEL_STYLE}>{t('account.currentPassword')}</span>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => {
                    setCurrentPassword(e.target.value)
                    setPasswordCurrentError(null)
                  }}
                  placeholder={t('account.currentPassword')}
                  autoComplete="current-password"
                  className={`${styles.inputWrapper} ${passwordCurrentError ? styles.inputError : ''}`}
                />
                {passwordCurrentError && (
                  <span style={{ ...HINT_STYLE, color: 'var(--color-destructive)' }}>
                    {passwordCurrentError}
                  </span>
                )}
              </label>
            )}

            <label>
              <span style={LABEL_STYLE}>{t('account.newPassword')}</span>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => {
                  setNewPassword(e.target.value)
                  setPasswordError(null)
                }}
                placeholder={t('account.newPassword')}
                autoComplete="new-password"
                className={`${styles.inputWrapper} ${passwordError ? styles.inputError : ''}`}
              />
            </label>

            <label>
              <span style={LABEL_STYLE}>{t('account.confirmPassword')}</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value)
                  setPasswordError(null)
                }}
                placeholder={t('account.confirmPassword')}
                autoComplete="new-password"
                className={`${styles.inputWrapper} ${passwordError && confirmPassword !== newPassword ? styles.inputError : ''}`}
              />
              {passwordError && (
                <span style={{ ...HINT_STYLE, color: 'var(--color-destructive)' }}>
                  {passwordError}
                </span>
              )}
            </label>

            {passwordSuccess && (
              <div style={{
                padding: '10px 14px',
                background: 'color-mix(in srgb, var(--accent-1) 10%, transparent)',
                border: '1px solid var(--accent-1)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 13,
                color: 'var(--accent-1)',
                fontWeight: 500,
              }}>
                {me?.has_password ? t('account.passwordChanged') : t('account.passwordSetSuccess')}
              </div>
            )}

            <button
              type="submit"
              disabled={savingPassword || !newPassword}
              className={btnStyles.cta}
              style={{ alignSelf: 'flex-start', minWidth: 160 }}
            >
              {savingPassword ? t('account.saving') : (me?.has_password ? t('account.passwordChange') : t('account.passwordSet'))}
            </button>
          </form>
        </section>

        {/* Email verify section */}
        {!me?.email_verified_at && (
          <section style={{ marginBottom: 32 }}>
            <p style={{
              fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
              color: 'var(--color-text-muted)', textTransform: 'uppercase',
              margin: '0 0 16px',
            }}>
              {t('account.emailVerifySection')}
            </p>

            {verifyError && (
              <div style={{
                padding: '10px 14px',
                background: 'color-mix(in srgb, var(--color-destructive) 8%, transparent)',
                border: '1px solid var(--color-destructive)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 13,
                color: 'var(--color-destructive)',
                fontWeight: 500,
                marginBottom: 12,
              }}>
                {t(verifyError.key, verifyError.params)}
              </div>
            )}

            {googleConfigured ? (
              <GoogleVerifyButton
                onSuccess={handleVerifySuccess}
                onError={handleVerifyError}
                onNonOAuthError={handleVerifyNonOAuthError}
                disabled={verifyLoading}
                loading={verifyLoading}
                label={t('account.verifyWithGoogle')}
              />
            ) : (
              <div role="status" style={{
                padding: '12px 16px',
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 13,
                color: 'var(--color-text-dim)',
              }}>
                {t('account.googleUnavailable')}
              </div>
            )}
          </section>
        )}

      </div>
      <div style={{ height: 24 }} />
    </div>
  )
}

/* ── Internal helpers ────────────────────────────────────────────────── */

function ScreenHeader({ navigate, t }) {
  return (
    <div className={styles.header}>
      <button
        type="button"
        onClick={() => navigate(-1)}
        aria-label="Back"
        className={styles.iconBtn}
      >
        <IconBack width={20} height={20} />
      </button>
      <h2 className={styles.headerTitle}>{t('account.title')}</h2>
      <div style={{ width: 44 }} />
    </div>
  )
}

function InfoRow({ label, value, valueStyle, last }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
      padding: '14px 16px',
      borderBottom: last ? 'none' : '1px solid var(--color-border)',
    }}>
      <span style={{ fontSize: 13, color: 'var(--color-text-muted)', flexShrink: 0 }}>
        {label}
      </span>
      <span style={{ ...READONLY_VALUE_STYLE, textAlign: 'right', ...valueStyle }}>
        {value}
      </span>
    </div>
  )
}

function formatProviders(providers) {
  if (!providers || providers.length === 0) return '—'
  const MAP = { google: 'Google', kakao: 'Kakao', naver: 'Naver' }
  return providers.map(p => MAP[p] || p).join(', ')
}
