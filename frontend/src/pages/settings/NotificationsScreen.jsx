/**
 * NotificationsScreen — /settings/notifications
 *
 * Loads notification prefs from GET /auth/me/ (notifications JSONField, self-only).
 * On toggle: PATCH /api/v1/users/me/ with merged dict — one `in_app` toggle per
 * category (NOTIF-INAPP-1). Absent `in_app` defaults to ON. push/email keys
 * (if already stored from a legacy save) are preserved verbatim via merge-PATCH.
 *
 * Toggle `locked` is used for the 'security' category (always on, cannot change).
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMe, updateMyProfile } from '../../api/client.js'
import Toggle from '../../components/Toggle.jsx'
import { IconBack } from '../../components/icons.jsx'
import { useTranslation } from '../../i18n/index.js'
import PageLogoHeader from '../../components/PageLogoHeader.jsx'
import styles from './NotificationsScreen.module.css'

const CATEGORY_KEYS = ['social', 'content', 'security', 'recommend', 'marketing']

export default function NotificationsScreen() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [prefs, setPrefs] = useState(null)   // null = not loaded yet
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)
  // Per-category save status for subtle feedback (key = catKey)
  const [pendingSave, setPendingSave] = useState(new Set())
  const [saveError, setSaveError] = useState(null)

  const categories = CATEGORY_KEYS.map(key => ({
    key,
    label: t(`notifications.settings.categories.${key}.label`),
    hint: t(`notifications.settings.categories.${key}.hint`),
    locked: key === 'security',
  }))

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
        setFetchError(err.message || t('notifications.settings.fetchError'))
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // Mount-only fetch. `t` is intentionally excluded: useTranslation()
    // returns a brand-new `t` function reference on every render (it is a
    // plain inner function, not memoized), so including it would re-run
    // this effect on every render and fire an unbounded stream of
    // GET /auth/me/ requests (one per render triggered by the previous
    // fetch's setState). `t` is only used inside the catch handler for a
    // fallback error string.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleToggle(catKey, next) {
    if (pendingSave.has(catKey)) return

    // Optimistic local update — preserve any existing push/email keys via
    // merge-PATCH (spec: {[cat]: {...existing, in_app: bool}}).
    const existing = prefs?.[catKey] || {}
    const nextPrefs = {
      ...prefs,
      [catKey]: { ...existing, in_app: next },
    }
    setPrefs(nextPrefs)
    setPendingSave(prev => { const s = new Set(prev); s.add(catKey); return s })
    setSaveError(null)

    try {
      await updateMyProfile({ notifications: nextPrefs })
    } catch (err) {
      // Revert on failure
      const reverted = {
        ...nextPrefs,
        [catKey]: { ...existing, in_app: !next },
      }
      setPrefs(reverted)
      setSaveError(err.message || t('notifications.settings.saveError'))
    } finally {
      setPendingSave(prev => { const s = new Set(prev); s.delete(catKey); return s })
    }
  }

  return (
    <div className={styles.page}>
      <PageLogoHeader />

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
        <h2 className={styles.headerTitle}>{t('notifications.title')}</h2>
        <div style={{ width: 44 }} />
      </div>

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>

        {/* Honest hint: email/push delivery not yet implemented */}
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
          {t('notifications.settings.disclaimer')}
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
            {t('notifications.settings.loading')}
          </div>
        )}

        {fetchError && !loading && (
          <div style={{ padding: '48px 0', textAlign: 'center', color: 'var(--color-destructive)', fontSize: 14 }}>
            {fetchError}
          </div>
        )}

        {!loading && !fetchError && prefs !== null && categories.map(cat => {
          // ABSENT in_app defaults to true (ON) per spec.
          const catPrefs = prefs[cat.key] || {}
          const inAppOn = cat.locked ? true : (catPrefs.in_app !== false)

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

              {/* In-app toggle row */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 0',
              }}>
                <span style={{ fontSize: 13, color: 'var(--color-text-2)' }}>
                  {t('notifications.settings.inAppToggle')}
                </span>
                <Toggle
                  checked={inAppOn}
                  onChange={(next) => handleToggle(cat.key, next)}
                  locked={cat.locked}
                  disabled={pendingSave.has(cat.key)}
                  aria-label={`${cat.label} ${t('notifications.settings.inAppToggle')}`}
                />
              </div>

              {cat.locked && (
                <p style={{ marginTop: 10, fontSize: 11, color: 'var(--color-text-dim)', lineHeight: 1.5 }}>
                  {t('notifications.settings.categories.security.lockedHint')}
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
