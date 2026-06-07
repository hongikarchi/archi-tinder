/**
 * FollowListModal.jsx — Instagram-style popup for followers / following lists.
 *
 * Props:
 *   userId   — user whose followers/following to show
 *   mode     — 'followers' | 'following'
 *   onClose  — called to dismiss the modal
 */
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import useFollowList from '../../hooks/useFollowList.js'
import FollowList from './FollowList.jsx'

export default function FollowListModal({ userId, mode, onClose }) {
  const navigate = useNavigate()
  const { users, loading, error, loadMore, retry } = useFollowList(userId, mode)
  const sentinelRef = useRef(null)

  const title = mode === 'followers' ? '팔로워' : '팔로잉'
  const emptyMessage = mode === 'followers' ? '팔로워가 없습니다.' : '팔로잉하는 사람이 없습니다.'

  // Esc key → close
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  // IntersectionObserver sentinel for infinite scroll
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      entries => { if (entries[0].isIntersecting) loadMore() },
      { rootMargin: '200px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loadMore])

  function handleOpenUser(u) {
    navigate('/user/' + u.user_id)
    onClose()
  }

  return (
    /* Backdrop */
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '0 16px',
      }}
    >
      {/* Panel — stop propagation so clicks inside don't close */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 420, maxHeight: '70vh',
          background: 'var(--color-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border)',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header row */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px',
          borderBottom: '1px solid var(--color-border)',
          flexShrink: 0,
        }}>
          <h2 style={{
            margin: 0, fontSize: 16, fontWeight: 700,
            color: 'var(--color-text)', letterSpacing: '-0.01em',
          }}>
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            style={{
              width: 32, height: 32,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'transparent', border: 'none',
              borderRadius: 8, cursor: 'pointer',
              color: 'var(--color-text-dim)',
              transition: 'color 0.18s cubic-bezier(0.4, 0, 0.2, 1), background 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--color-text)'
              e.currentTarget.style.background = 'var(--color-surface-2)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--color-text-dim)'
              e.currentTarget.style.background = 'transparent'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Scrollable body */}
        <div style={{ overflowY: 'auto', flex: 1, padding: '12px 16px' }}>

          {/* Initial-load error (no items yet) */}
          {error && !loading && users.length === 0 && (
            <div style={{
              padding: '24px 14px', textAlign: 'center',
              fontSize: 13, color: 'var(--color-destructive)',
            }}>
              {error}
              <br />
              <button
                type="button"
                onClick={retry}
                style={{
                  marginTop: 8, background: 'transparent',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '6px 14px', cursor: 'pointer',
                  fontSize: 13, color: 'var(--color-text)', fontFamily: 'inherit',
                }}
              >
                다시 시도
              </button>
            </div>
          )}

          {/* Empty state */}
          {!loading && !error && users.length === 0 && (
            <div style={{ padding: '24px 14px', textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
              {emptyMessage}
            </div>
          )}

          {/* List */}
          {users.length > 0 && (
            <FollowList users={users} onOpenUser={handleOpenUser} emptyMessage={emptyMessage} />
          )}

          {/* Pagination error (items already loaded) */}
          {error && users.length > 0 && !loading && (
            <div style={{
              padding: '12px 14px', textAlign: 'center',
              fontSize: 13, color: 'var(--color-text-dim)',
            }}>
              추가 로딩 실패.{' '}
              <button
                type="button"
                onClick={loadMore}
                style={{
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  fontSize: 13, color: 'var(--accent-1)', fontFamily: 'inherit',
                  padding: 0, textDecoration: 'underline',
                }}
              >
                다시 시도
              </button>
            </div>
          )}

          {/* Loading indicator */}
          {loading && (
            <div style={{
              padding: '20px', textAlign: 'center',
              fontSize: 13, color: 'var(--color-text-dim)',
            }}>
              불러오는 중...
            </div>
          )}

          {/* Infinite scroll sentinel */}
          <div ref={sentinelRef} style={{ height: 1 }} />

        </div>
      </div>
    </div>
  )
}
