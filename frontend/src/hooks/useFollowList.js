/**
 * useFollowList — reusable hook for fetching followers/following with pagination.
 *
 * @param {string|number} userId
 * @param {'followers'|'following'} mode
 * @returns {{ users, loading, error, hasMore, loadMore, retry }}
 *
 * The consumer owns the IntersectionObserver sentinel and calls loadMore().
 */
import { useState, useEffect, useCallback } from 'react'
import { getFollowers, getFollowing } from '../api/social.js'

export default function useFollowList(userId, mode) {
  const [users, setUsers] = useState([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchPage = useCallback(async (pageNum, append = false) => {
    if (!userId) return
    setLoading(true)
    setError(null)
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

  const retry = useCallback(() => {
    fetchPage(1, false)
  }, [fetchPage])

  return { users, loading, error, hasMore, loadMore, retry }
}
