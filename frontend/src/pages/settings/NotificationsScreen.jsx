/**
 * NotificationsScreen — /settings/notifications
 *
 * Loads notification prefs from GET /auth/me/ (notifications JSONField, self-only).
 * On toggle: PATCH /api/v1/users/me/ with merged dict.
 * PATCH response does NOT echo notifications → local state is authoritative after save.
 *
 * Toggle `locked` is used for the 'security' category (always on, cannot change).
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMe, updateMyProfile } from '../../api/client.js'
import Toggle from '../../components/Toggle.jsx'
import { IconBack } from '../../components/icons.jsx'
import styles from './NotificationsScreen.module.css'

const CATEGORIES = [
  {
    key: 'social',
    label: '소셜 활동',
    hint: '팔로우 · 좋아요 · 댓글 · 멘션',
  },
  {
    key: 'content',
    label: '내 보드 · 프로젝트',
    hint: '저장 · 공유 · 추천 노출',
  },
  {
    key: 'security',
    label: '계정 보안',
    hint: '새 기기 로그인 · 비밀번호 변경',
    locked: true,
  },
  {
    key: 'recommend',
    label: '추천 · 트렌드',
    hint: '개인화 추천 · 주간 다이제스트',
  },
  {
    key: 'marketing',
    label: '마케팅 · 이벤트',
    hint: '프로모션 안내',
  },
]

const DEFAULT_CHANNEL = { push: false, email: false }

export default function NotificationsScreen() {
  const navigate = useNavigate()
  const [prefs, setPrefs] = useState(null)   // null = not loaded yet
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)
  // Per-channel save status for subtle feedback (key = 'catKey.push' | 'catKey.email')
  const [pendingSave, setPendingSave] = useState(new Set())
  const [saveError, setSaveError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setFetchError(null)
    getMe()
      .then(data => {
        if (cancelled) return
        setPrefs(data.notifications || {})
      })
      .catch(err => {
        if (cancelled) return
        setFetchError(err.message || '알림 설정을 불러올 수 없습니다.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  async function handleToggle(catKey, channel, next) {
    const saveKey = `${catKey}.${channel}`
    if (pendingSave.has(saveKey)) return

    // Optimistic local update
    const nextPrefs = {
      ...prefs,
      [catKey]: { ...(prefs?.[catKey] || DEFAULT_CHANNEL), [channel]: next },
    }
    setPrefs(nextPrefs)
    setPendingSave(prev => { const s = new Set(prev); s.add(saveKey); return s })
    setSaveError(null)

    try {
      await updateMyProfile({ notifications: nextPrefs })
    } catch (err) {
      // Revert on failure
      const reverted = {
        ...nextPrefs,
        [catKey]: { ...(nextPrefs[catKey] || DEFAULT_CHANNEL), [channel]: !next },
      }
      setPrefs(reverted)
      setSaveError(err.message || '저장에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setPendingSave(prev => { const s = new Set(prev); s.delete(saveKey); return s })
    }
  }

  return (
    <div className={styles.page}>
      {/* Glassmorphic sticky header */}
      <div className={styles.header}>
        <button
          type="button"
          onClick={() => navigate(-1)}
          aria-label="Back"
          className={styles.iconBtn}
        >
          <IconBack width={20} height={20} />
        </button>
        <h2 className={styles.headerTitle}>알림</h2>
        <div style={{ width: 44 }} />
      </div>

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>

        {/* Honest hint: delivery not yet implemented */}
        <div style={{
          padding: '10px 14px',
          marginBottom: 20,
          background: 'color-mix(in srgb, var(--color-surface-2) 80%, transparent)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)',
          fontSize: 12,
          color: 'var(--color-text-muted)',
          lineHeight: 1.6,
        }}>
          설정은 저장됩니다 · 알림 발송은 준비 중입니다
        </div>

        {saveError && (
          <div style={{
            padding: '10px 14px',
            marginBottom: 16,
            background: 'color-mix(in srgb, var(--color-destructive) 8%, transparent)',
            border: '1px solid var(--color-destructive)',
            borderRadius: 'var(--radius-sm)',
            fontSize: 13,
            color: 'var(--color-destructive)',
            fontWeight: 500,
          }}>
            {saveError}
          </div>
        )}

        {loading && (
          <div style={{ padding: '48px 0', textAlign: 'center', color: 'var(--color-text-dim)', fontSize: 14 }}>
            불러오는 중...
          </div>
        )}

        {fetchError && !loading && (
          <div style={{ padding: '48px 0', textAlign: 'center', color: 'var(--color-destructive)', fontSize: 14 }}>
            {fetchError}
          </div>
        )}

        {!loading && !fetchError && prefs !== null && CATEGORIES.map(cat => {
          const catPrefs = prefs[cat.key] || DEFAULT_CHANNEL
          const pushKey = `${cat.key}.push`
          const emailKey = `${cat.key}.email`

          return (
            <div key={cat.key} className={styles.categoryBlock}>
              {/* Category header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)' }}>
                  {cat.label}
                </span>
                {cat.locked && (
                  <svg
                    width="12" height="12"
                    viewBox="0 0 24 24" fill="none" stroke="var(--color-text-dim)"
                    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                )}
              </div>
              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', margin: '0 0 12px', lineHeight: 1.5 }}>
                {cat.hint}
              </p>

              {/* Push toggle row */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 0',
              }}>
                <span style={{ fontSize: 13, color: 'var(--color-text-2)' }}>푸시</span>
                <Toggle
                  checked={cat.locked ? true : !!catPrefs.push}
                  onChange={(next) => handleToggle(cat.key, 'push', next)}
                  locked={cat.locked}
                  disabled={pendingSave.has(pushKey)}
                  aria-label={`${cat.label} 푸시 알림`}
                />
              </div>

              {/* Email toggle row */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 0',
              }}>
                <span style={{ fontSize: 13, color: 'var(--color-text-2)' }}>이메일</span>
                <Toggle
                  checked={cat.locked ? true : !!catPrefs.email}
                  onChange={(next) => handleToggle(cat.key, 'email', next)}
                  locked={cat.locked}
                  disabled={pendingSave.has(emailKey)}
                  aria-label={`${cat.label} 이메일 알림`}
                />
              </div>

              {cat.locked && (
                <p style={{ marginTop: 10, fontSize: 11, color: 'var(--color-text-dim)', lineHeight: 1.5 }}>
                  보안 알림은 계정 보호를 위해 항상 켜집니다.
                </p>
              )}
            </div>
          )
        })}

      </div>
      <div style={{ height: 24 }} />
    </div>
  )
}
