import { useState, useEffect, useCallback } from 'react'
import { getProjectReactors } from '../api/social.js'

/**
 * useProjectReactors — fetch and paginate the reactor list for a project.
 *
 * Returns:
 *   reactors    — accumulated list of reactor user objects across loaded pages
 *   loading     — true while fetching the next page
 *   error       — Error or null
 *   hasMore     — true if more pages exist on the server
 *   total       — total reactor count from latest response (or null before first load)
 *   loadMore()  — fetch the next page
 *   reset()     — clear state (use when projectId changes; effect calls this automatically)
 *
 * Usage:
 *   const { reactors, hasMore, loadMore } = useProjectReactors(projectId)
 *   <button onClick={loadMore} disabled={!hasMore}>Load more</button>
 *
 * No automatic refetch on focus or interval — caller decides when to loadMore.
 * 403 responses surface as `error.message === 'Forbidden'` (or whatever message
 * callApi propagates); the hook does not branch on status code.
 */
export function useProjectReactors(projectId, { pageSize = 50 } = {}) {
  const [reactors, setReactors] = useState([])
  const [page, setPage] = useState(0)         // 0 = nothing loaded yet
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hasMore, setHasMore] = useState(true)
  const [total, setTotal] = useState(null)

  const reset = useCallback(() => {
    setReactors([])
    setPage(0)
    setError(null)
    setHasMore(true)
    setTotal(null)
  }, [])

  const loadMore = useCallback(async () => {
    if (loading || !hasMore || !projectId) return
    const nextPage = page + 1
    setLoading(true)
    setError(null)
    try {
      const resp = await getProjectReactors(projectId, { page: nextPage, pageSize })
      setReactors(prev => [...prev, ...(resp.results || [])])
      setPage(nextPage)
      setHasMore(!!resp.has_more)
      setTotal(resp.total ?? null)
    } catch (err) {
      setError(err)
      setHasMore(false)
    } finally {
      setLoading(false)
    }
  }, [projectId, page, pageSize, loading, hasMore])

  // Reset when projectId changes (don't auto-fetch — caller decides)
  useEffect(() => {
    reset()
  }, [projectId, reset])

  return { reactors, loading, error, hasMore, total, loadMore, reset }
}
