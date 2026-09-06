/**
 * NotificationInboxScreen — /notifications
 *
 * Full-screen inbox, glassmorphic sticky header (same pattern as the
 * /settings/* sub-screens). Lists self notifications (GET /api/v1/notifications/),
 * marks everything read on first page load (POST mark-read {all:true}),
 * supports '더 보기' load-more pagination.
 *
 * Tap-through targets (verified against frontend/src/App.jsx router):
 *   - reaction  -> /board/{payload.project_id}  (board/:boardId uses boardId
 *                  AS the project_id -- see BoardDetailPage.jsx react/unreact
 *                  calls which pass `board.project_id` straight through)
 *   - password_changed / new_login (category 'security') -> /settings/account
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { listNotifications, markRead } from '../../api/notifications.js'
import { useTranslation } from '../../i18n/index.js'
import { formatTimeAgo } from '../../utils/timeAgo.js'
import Avatar from '../../components/Avatar.jsx'
import PageLogoHeader from '../../components/PageLogoHeader.jsx'
import PageTopControls from '../../components/PageTopControls.jsx'
import PageBackButton from '../../components/PageBackButton.jsx'
import styles from './NotificationInboxScreen.module.css'

const PAGE_SIZE = 20

function sentenceFor(n, t) {
  const name = n.actor?.display_name || ''
  switch (n.type) {
    case 'reaction':
      return t('notifications.sentence.reaction', { name })
    case 'password_changed':
      return t('notifications.sentence.passwordChanged')
    case 'new_login':
      return t('notifications.sentence.newLogin')
    default:
      return ''
  }
}

function RowSkeleton() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: 14 }}>
      <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--color-surface-2)', flexShrink: 0 }} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 4 }}>
        <div style={{ width: '80%', height: 14, borderRadius: 'var(--radius-sm)', background: 'var(--color-surface-2)' }} />
        <div style={{ width: '40%', height: 11, borderRadius: 'var(--radius-sm)', background: 'var(--color-surface-2)' }} />
      </div>
    </div>
  )
}

export default function NotificationInboxScreen({ onLogout }) {
  const navigate = useNavigate()
  const { t, language } = useTranslation()

  const [items, setItems] = useState([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [fetchError, setFetchError] = useState(null)
  const markedAllRef = useRef(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setFetchError(null)
    listNotifications({ page: 1, pageSize: PAGE_SIZE })
      .then(data => {
        if (cancelled) return
        setItems(data.results || [])
        setPage(data.page || 1)
        setHasMore(!!data.has_more)
        // Mark everything read once the first page has landed (v1 simple:
        // clears the badge on open, regardless of what's on-screen).
        if (!markedAllRef.current) {
          markedAllRef.current = true
          markRead({ all: true }).catch(() => { /* best-effort */ })
        }
      })
      .catch(err => {
        if (cancelled) return
        setFetchError(err.message || t('notifications.fetchError'))
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // Mount-only fetch. `t` is intentionally excluded: useTranslation()
    // returns a brand-new `t` function reference on every render (it is a
    // plain inner function, not memoized), so including it would re-run
    // this effect on every render and fire an unbounded stream of
    // GET /api/v1/notifications/ requests (one per render triggered by the
    // previous fetch's setState). `t` is only used inside the catch handler
    // for a fallback error string.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleLoadMore = useCallback(() => {
    if (loadingMore) return
    setLoadingMore(true)
    const nextPage = page + 1
    listNotifications({ page: nextPage, pageSize: PAGE_SIZE })
      .then(data => {
        setItems(prev => [...prev, ...(data.results || [])])
        setPage(data.page || nextPage)
        setHasMore(!!data.has_more)
      })
      .catch(() => { /* leave hasMore as-is; user can retry */ })
      .finally(() => setLoadingMore(false))
  }, [loadingMore, page])

  function handleRowClick(n) {
    if (n.category === 'security') {
      navigate('/settings/account')
      return
    }
    if (n.type === 'reaction' && n.payload?.project_id) {
      navigate(`/board/${n.payload.project_id}`)
    }
  }

  return (
    <div className={styles.page}>
      <PageBackButton onClick={() => navigate(-1)} />
      <PageLogoHeader />
      <PageTopControls onLogout={onLogout} />

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '8px 12px 24px' }}>
        <h2 className={styles.headerTitle}>{t('notifications.title')}</h2>

        {loading && (
          <div>
            {Array.from({ length: 5 }).map((_, i) => <RowSkeleton key={i} />)}
          </div>
        )}

        {fetchError && !loading && (
          <div style={{ padding: '48px 0', textAlign: 'center', color: 'var(--color-destructive)', fontSize: 14 }}>
            {fetchError}
          </div>
        )}

        {!loading && !fetchError && items.length === 0 && (
          <div style={{ padding: '64px 0', textAlign: 'center', color: 'var(--color-text-dim)', fontSize: 14 }}>
            {t('notifications.empty')}
          </div>
        )}

        {!loading && !fetchError && items.length > 0 && (
          <div>
            {items.map(n => {
              const isUnread = !n.read_at
              const sentence = sentenceFor(n, t)
              const secondaryLine = n.type === 'reaction' ? (n.payload?.project_title || '') : ''
              return (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleRowClick(n)}
                  className={`${styles.row} ${isUnread ? styles.rowUnread : ''}`}
                >
                  <Avatar src={n.actor?.avatar_url} name={n.actor?.display_name} size={40} />
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                      {isUnread && (
                        <span
                          aria-label={t('notifications.unreadAriaSuffix')}
                          style={{
                            width: 7, height: 7, borderRadius: '50%',
                            background: 'var(--accent-1)', flexShrink: 0, marginTop: 6,
                          }}
                        />
                      )}
                      <span style={{
                        fontSize: 14,
                        fontWeight: isUnread ? 600 : 500,
                        color: 'var(--color-text)',
                        lineHeight: 1.4,
                      }}>
                        {sentence}
                      </span>
                    </div>
                    {secondaryLine && (
                      <span style={{
                        fontSize: 12,
                        color: 'var(--color-text-muted)',
                        lineHeight: 1.3,
                        marginLeft: isUnread ? 13 : 0,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}>
                        {secondaryLine}
                      </span>
                    )}
                    <span style={{
                      fontSize: 11,
                      color: 'var(--color-text-dim)',
                      marginLeft: isUnread ? 13 : 0,
                    }}>
                      {formatTimeAgo(n.created_at, language)}
                    </span>
                  </div>
                </button>
              )
            })}

            {hasMore && (
              <button
                type="button"
                onClick={handleLoadMore}
                disabled={loadingMore}
                className={styles.loadMoreBtn}
              >
                {loadingMore ? '…' : t('notifications.loadMore')}
              </button>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
