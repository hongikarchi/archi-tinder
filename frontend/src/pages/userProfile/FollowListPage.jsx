/**
 * FollowListPage.jsx — /user/:userId/followers + /user/:userId/following
 *
 * Props:
 *   mode — 'followers' | 'following'
 *
 * Reads :userId from useParams.
 * Infinite scroll via IntersectionObserver (same pattern as UserProfilePage).
 * onOpenUser → navigate to /user/{user_id}.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getFollowers, getFollowing } from '../../api/social.js'
import FollowList from '../../components/profile/FollowList.jsx'
import { IconBack } from '../../components/icons.jsx'

export default function FollowListPage({ mode }) {
  const { userId } = useParams()
  const navigate = useNavigate()

  const [users, setUsers] = useState([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const sentinelRef = useRef(null)

  const title = mode === 'followers' ? '팔로워' : '팔로잉'
  const emptyMessage = mode === 'followers' ? '팔로워가 없습니다.' : '팔로잉하는 사람이 없습니다.'

  const fetchPage = useCallback(async (pageNum, append = false) => {
    if (!userId) return
    setLoading(true)
    try {
      const fetcher = mode === 'followers' ? getFollowers : getFollowing
      const data = await fetcher(userId, pageNum)
      const results = data.results || []
      setUsers(prev => append ? [...prev, ...results] : results)
      setHasMore(data.has_more ?? false)
      setPage(pageNum)
    } catch (err) {
      setError(err.message || 'Failed to load.')
    } finally {
      setLoading(false)
    }
  }, [userId, mode])

  // Initial load
  useEffect(() => {
    setUsers([])
    setPage(1)
    setHasMore(false)
    setError(null)
    fetchPage(1, false)
  }, [fetchPage])

  const loadMore = useCallback(() => {
    if (loading || !hasMore) return
    fetchPage(page + 1, true)
  }, [loading, hasMore, page, fetchPage])

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

  function handleOpenUser(user) {
    navigate(`/user/${user.user_id}`)
  }

  return (
    <div style={{
      maxWidth: 600,
      margin: '0 auto',
      padding: '0 16px',
      height: 'calc(100vh - 64px)',
      overflowY: 'auto',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '16px 0 12px',
        position: 'sticky',
        top: 0,
        background: 'var(--color-bg)',
        zIndex: 10,
        borderBottom: '1px solid var(--color-border)',
        marginBottom: 16,
      }}>
        <button
          type="button"
          onClick={() => navigate(-1)}
          aria-label="Back"
          style={{
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-text)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 8,
            minWidth: 36,
            minHeight: 36,
            borderRadius: 'var(--radius-md)',
          }}
        >
          <IconBack width={20} height={20} />
        </button>
        <h2 style={{
          margin: 0,
          fontSize: 18,
          fontWeight: 600,
          color: 'var(--color-text)',
        }}>
          {title}
        </h2>
      </div>

      {/* Initial-load error (no items loaded yet) */}
      {error && !loading && users.length === 0 && (
        <div style={{
          padding: '24px 14px',
          textAlign: 'center',
          fontSize: 13,
          color: 'var(--color-destructive)',
        }}>
          {error}
          <br />
          <button
            type="button"
            onClick={() => fetchPage(1, false)}
            style={{
              marginTop: 8,
              background: 'transparent',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              padding: '6px 14px',
              cursor: 'pointer',
              fontSize: 13,
              color: 'var(--color-text)',
              fontFamily: 'inherit',
            }}
          >
            다시 시도
          </button>
        </div>
      )}

      {/* Empty state (initial load complete, no results, no error) */}
      {!loading && !error && users.length === 0 && (
        <div style={{ padding: '24px 14px', textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
          {emptyMessage}
        </div>
      )}

      {/* List — always rendered when we have data, even if a later page failed */}
      {users.length > 0 && (
        <FollowList
          users={users}
          onOpenUser={handleOpenUser}
          emptyMessage={emptyMessage}
        />
      )}

      {/* Pagination error (items already loaded — show inline retry below list) */}
      {error && users.length > 0 && !loading && (
        <div style={{
          padding: '12px 14px',
          textAlign: 'center',
          fontSize: 13,
          color: 'var(--color-text-dim)',
        }}>
          추가 로딩 실패.{' '}
          <button
            type="button"
            onClick={() => fetchPage(page + 1, true)}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              fontSize: 13,
              color: 'var(--accent-1)',
              fontFamily: 'inherit',
              padding: 0,
              textDecoration: 'underline',
            }}
          >
            다시 시도
          </button>
        </div>
      )}

      {/* Loading indicator */}
      {loading && (
        <div style={{
          padding: '20px',
          textAlign: 'center',
          fontSize: 13,
          color: 'var(--color-text-dim)',
        }}>
          불러오는 중...
        </div>
      )}

      {/* Infinite scroll sentinel */}
      <div ref={sentinelRef} style={{ height: 1 }} />

      {/* Bottom padding for TabBar */}
      <div style={{ height: 24 }} />
    </div>
  )
}
