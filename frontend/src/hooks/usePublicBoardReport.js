/**
 * usePublicBoardReport — read-only persona-report data for ANOTHER user's public
 * board (the /people feed's expanded card).
 *
 * Fetches on demand for `boardId` (null = nothing to load): the board detail
 * (GET /projects/{id}/), its liked buildings, the public recommendations and the
 * recommended architects. Only 'ready' results are cached per board id for the
 * lifetime of the hook (= the page); 'gone'/'error' refetch on re-open.
 *
 * Returns { status, data, retry }
 *   status  'idle' | 'loading' | 'ready' | 'gone' | 'error'
 *             gone  = 401/403/404, not public any more, or no report (board turned
 *                     private / deleted since the feed loaded)
 *             error = any other failure (network, 5xx) -> retry()
 *   data    { board, finalReport, axisScores, reportImage, reportImageMime,
 *             likedBuildings, recommendations, architects, ownerId } | null
 *   retry   () => void  re-fetch the current board after an 'error'
 *
 * Recommendations / architects degrade to [] on failure (the sections hide).
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { getProject, getBoardBuildings, getProjectRecommendations } from '../api/projects.js'
import { getRecommendedArchitects } from '../api/architects.js'
import { collectBoardBuildingIds } from './useBoard.js'

const GONE_STATUSES = new Set([401, 403, 404])

async function fetchPublicReport(boardId) {
  let project
  try {
    project = await getProject(boardId, { throwOnError: true })
  } catch (err) {
    if (GONE_STATUSES.has(err?.status)) return { status: 'gone', data: null }
    throw err
  }
  if (!project || project.visibility !== 'public' || !project.final_report) {
    return { status: 'gone', data: null }
  }
  const [buildings, recommendations, architects] = await Promise.all([
    getBoardBuildings(collectBoardBuildingIds(project)).catch(() => []),
    getProjectRecommendations(boardId).catch(() => []),
    getRecommendedArchitects(boardId),
  ])
  return {
    status: 'ready',
    data: {
      board: project,
      finalReport: project.final_report,
      axisScores: project.axis_scores || null,
      reportImage: project.report_image || null,
      reportImageMime: project.report_image_mime || null,
      likedBuildings: buildings,
      recommendations,
      architects,
      ownerId: project.user?.user_id ?? null,
    },
  }
}

export function usePublicBoardReport(boardId) {
  const cacheRef = useRef(new Map()) // id -> { status, data }
  const aliveRef = useRef(true)
  const [, bump] = useState(0)

  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false }
  }, [])

  const load = useCallback(id => {
    cacheRef.current.set(id, { status: 'loading', data: null })
    bump(n => n + 1)
    fetchPublicReport(id)
      .then(entry => cacheRef.current.set(id, entry))
      .catch(() => cacheRef.current.set(id, { status: 'error', data: null }))
      .finally(() => { if (aliveRef.current) bump(n => n + 1) })
  }, [])

  useEffect(() => {
    if (!boardId) return
    // Only 'ready' entries (and in-flight loads) are reused; a 'gone'/'error'
    // entry is refetched on re-open (board may be public now / transient failure).
    const st = cacheRef.current.get(boardId)?.status
    if (st !== 'ready' && st !== 'loading') load(boardId)
  }, [boardId, load])

  const retry = useCallback(() => { if (boardId) load(boardId) }, [boardId, load])

  if (!boardId) return { status: 'idle', data: null, retry }
  const entry = cacheRef.current.get(boardId)
  return { status: entry?.status ?? 'loading', data: entry?.data ?? null, retry }
}
