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
        setFetchError(err.message || '프로필을 불러올 수 없습니다.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  async function handleSave() {
    if (saving) return
    setHandleError(null)
    setSaveSuccess(false)

    // Client-side format check (backend also validates; this is UX-only)
    const trimmed = handle.trim()
    if (trimmed && !/^[a-z0-9_]{3,30}$/.test(trimmed)) {
      setHandleError('핸들은 영소문자·숫자·_만, 3-30자.')
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
        setHandleError(err.message || '저장에 실패했습니다.')
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
      setPasswordError('비밀번호는 8자 이상이어야 합니다.')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('비밀번호가 일치하지 않습니다.')
      return
    }
    if (me?.has_password && !currentPassword) {
      setPasswordCurrentError('현재 비밀번호를 입력해 주세요.')
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
        setPasswordError(err.message || '저장에 실패했습니다.')
      }
    } finally {
      setSavingPassword(false)
    }
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <ScreenHeader navigate={navigate} />
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48, color: 'var(--color-text-dim)', fontSize: 14 }}>
          불러오는 중...
        </div>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className={styles.page}>
        <ScreenHeader navigate={navigate} />
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48, color: 'var(--color-destructive)', fontSize: 14 }}>
          {fetchError}
        </div>
      </div>
    )
  }

  const isDirty = handle !== (me?.handle || '')

  return (
    <div className={styles.page}>
      <ScreenHeader navigate={navigate} />

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>

        {/* Read-only info section */}
        <section style={{ marginBottom: 32 }}>
          <p style={{
            fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
            color: 'var(--color-text-muted)', textTransform: 'uppercase',
            margin: '0 0 16px',
          }}>
            계정 정보
          </p>

          <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
          }}>
            {/* Verified status */}
            <InfoRow
              label="계정 상태"
              value={me?.is_guest ? '미인증 (게스트)' : '인증된 계정'}
              valueStyle={{ color: me?.is_guest ? 'var(--accent-3)' : 'var(--accent-1)', fontWeight: 600 }}
            />

            {/* Login method (providers) */}
            <InfoRow
              label="로그인 방식"
              value={formatProviders(me?.providers)}
            />

            {/* Email */}
            <InfoRow
              label="이메일"
              value={
                me?.email
                  ? `${me.email}${me.email_verified_at ? ' · 인증됨' : ' · 미인증'}`
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
            ID 설정
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
                placeholder="예: dain_architect"
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
                  로그인 ID이자 공개 @아이디입니다. 영소문자·숫자·_ 만 사용, 3-30자.
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
                ID가 저장되었습니다.
              </div>
            )}

            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !isDirty}
              className={btnStyles.cta}
              style={{ alignSelf: 'flex-start', minWidth: 120 }}
            >
              {saving ? '저장 중…' : '저장'}
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
            {me?.has_password ? '비밀번호 변경' : '비밀번호 설정'}
          </p>

          <form onSubmit={handlePasswordSave} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {me?.has_password && (
              <label>
                <span style={LABEL_STYLE}>현재 비밀번호</span>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => {
                    setCurrentPassword(e.target.value)
                    setPasswordCurrentError(null)
                  }}
                  placeholder="현재 비밀번호"
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
              <span style={LABEL_STYLE}>새 비밀번호 (8자 이상)</span>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => {
                  setNewPassword(e.target.value)
                  setPasswordError(null)
                }}
                placeholder="새 비밀번호"
                autoComplete="new-password"
                className={`${styles.inputWrapper} ${passwordError ? styles.inputError : ''}`}
              />
            </label>

            <label>
              <span style={LABEL_STYLE}>비밀번호 확인</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value)
                  setPasswordError(null)
                }}
                placeholder="비밀번호 재입력"
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
                {me?.has_password ? '비밀번호가 변경되었습니다.' : '비밀번호가 설정되었습니다.'}
              </div>
            )}

            <button
              type="submit"
              disabled={savingPassword || !newPassword}
              className={btnStyles.cta}
              style={{ alignSelf: 'flex-start', minWidth: 160 }}
            >
              {savingPassword ? '저장 중…' : (me?.has_password ? '비밀번호 변경' : '비밀번호 설정')}
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
              이메일 인증
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
                {verifyError}
              </div>
            )}

            {googleConfigured ? (
              <GoogleVerifyButton
                onSuccess={handleVerifySuccess}
                onError={handleVerifyError}
                onNonOAuthError={handleVerifyNonOAuthError}
                disabled={verifyLoading}
                loading={verifyLoading}
                label="구글로 이메일 인증"
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
                Google 인증을 사용할 수 없는 환경입니다.
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

function ScreenHeader({ navigate }) {
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
      <h2 className={styles.headerTitle}>계정</h2>
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
