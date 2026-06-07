/**
 * AccountScreen — /settings/account
 *
 * Editable: @handle (PATCH /api/v1/users/me/)
 * Read-only display: display_name, is_guest (verified status), providers (login method).
 *
 * Deliberately OMITTED (not in UserSerializer / auth/me response):
 *   - email (not exposed by serializer — field absent from response)
 *   - join_date / created_at (not in UserSerializer)
 *   - password change (not applicable — OAuth-only accounts; no backend endpoint)
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMe, updateMyProfile } from '../../api/client.js'
import { IconBack } from '../../components/icons.jsx'
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
            {/* Display name (read-only) */}
            <InfoRow label="이름" value={me?.display_name || '—'} />

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
              last
            />
          </div>
        </section>

        {/* Handle edit section */}
        <section>
          <p style={{
            fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
            color: 'var(--color-text-muted)', textTransform: 'uppercase',
            margin: '0 0 16px',
          }}>
            핸들 설정
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <label>
              <span style={LABEL_STYLE}>@핸들 (Handle)</span>
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
                  영소문자, 숫자, _ 만 사용 · 3-30자 · 다른 사용자가 나를 찾을 때 씁니다.
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
                핸들이 저장되었습니다.
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
