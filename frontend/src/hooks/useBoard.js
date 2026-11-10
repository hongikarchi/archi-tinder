import { useCallback, useEffect, useState } from 'react'
import { getBoardBuildings, getProject } from '../api/projects.js'
import { getResult } from '../api/sessions.js'
import { getRecommendedArchitects } from '../api/architects.js'

export function collectBoardBuildingIds(project) {
  const ids = []
  const seen = new Set()
  const add = item => {
    const id = item?.id
    if (!id || seen.has(id)) return
    seen.add(id)
    ids.push(id)
  }
  for (const item of project?.liked_ids || []) add(item)
  return ids
}

function adaptProjectToBoard(project, buildings) {
  return {
    ...project,
    board_id: project.project_id,
    owner: project.user,
    cover_image_url: buildings[0]?.image_url || '',
    buildings,
  }
}

// The session-result request is owner-only. Recommended architects are fetched for
// the owner and, for viewers, only when the board has a report (the server now
// returns report data + recommendations to non-owners of PUBLIC boards).
// `fetchResult: false` skips the owner-only session-result fetch (the merged
// report page loads recommendations itself via getProjectRecommendations).
// `enabled: false` makes the hook inert (the caller got the board from a parent).
export function useBoard(projectId, { fetchResult = true, enabled = true } = {}) {
  const [board, setBoard] = useState(null)
  const [recommended, setRecommended] = useState([])
  const [recommendedArchitects, setRecommendedArchitects] = useState([])
  const [buildingsLoading, setBuildingsLoading] = useState(true)
  const [resultLoading, setResultLoading] = useState(false)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const reload = useCallback(() => setReloadKey(k => k + 1), [])

  useEffect(() => {
    if (!enabled) return
    if (!projectId) {
      setBoard(null)
      setRecommended([])
      setBuildingsLoading(false)
      setResultLoading(false)
      setError(new Error('No board ID found.'))
      return
    }

    let cancelled = false
    setBuildingsLoading(true)
    setResultLoading(false)
    setRecommended([])
    setRecommendedArchitects([])
    setError(null)
    setBoard(null)

    getProject(projectId, { throwOnError: true })
      .then(project => {
        if (cancelled) return
        if (!project) throw new Error('Board not found.')

        const buildingIds = collectBoardBuildingIds(project)

        // Session result + recommended architects are owner-only endpoints
        // (a non-owner gets 404 and a console error), so only the board owner
        // requests them. Same derivation as BoardDetailPage.
        const viewerId = sessionStorage.getItem('archithon_user')
        const ownerId = project.user?.user_id
        const isOwner = !!viewerId && ownerId != null && String(ownerId) === String(viewerId)

        // Fetch buildings independently — show cards as soon as they arrive.
        // setBoard fires exactly once per board load so the BoardDetailPage
        // useEffect([board]) initializes local state only once.
        getBoardBuildings(buildingIds)
          .then(buildings => {
            if (cancelled) return
            setBoard(adaptProjectToBoard(project, buildings))
            setBuildingsLoading(false)
          })
          .catch(() => {
            if (cancelled) return
            setBoard(adaptProjectToBoard(project, []))
            setBuildingsLoading(false)
          })

        // Fetch result independently — recommended section populates when it arrives.
        // Uses separate `recommended` state so setBoard is never called again.
        if (isOwner && fetchResult && project.latest_session_id) {
          setResultLoading(true)
          getResult({ session_id: project.latest_session_id })
            .then(resultData => {
              if (cancelled) return
              setRecommended(resultData?.predicted_like_images || [])
            })
            .catch(() => { /* leave recommended empty on error */ })
            .finally(() => {
              if (!cancelled) setResultLoading(false)
            })
        }

        // Fetch recommended architects in parallel — graceful degradation on failure.
        // Owner always; a viewer only for a board that carries a report (the
        // endpoint is public for public boards, but report-less boards render the
        // old detail page, which does not show architects to viewers).
        if (isOwner || project.final_report) {
          getRecommendedArchitects(project.project_id)
            .then(architects => {
              if (cancelled) return
              setRecommendedArchitects(architects)
            })
        }
      })
      .catch(err => {
        if (cancelled) return
        setBoard(null)
        setRecommended([])
        setBuildingsLoading(false)
        setResultLoading(false)
        setError(err)
      })

    return () => { cancelled = true }
  }, [projectId, fetchResult, enabled, reloadKey])

  // Expose a combined `loading` alias so existing consumers continue to work.
  const loading = buildingsLoading

  return { board, recommended, recommendedArchitects, loading, buildingsLoading, resultLoading, error, reload }
}

// Owner-only session result (predicted-like images) for a board that was loaded
// elsewhere with `fetchResult: false`. Mirrors the fetch inside useBoard.
export function useBoardSessionResult(board, enabled) {
  const [recommended, setRecommended] = useState([])
  const [resultLoading, setResultLoading] = useState(false)
  const sessionId = board?.latest_session_id || null
  const ownerId = board?.user?.user_id ?? board?.owner?.user_id
  const viewerId = sessionStorage.getItem('archithon_user')
  const isOwner = !!viewerId && ownerId != null && String(ownerId) === String(viewerId)
  const active = enabled && isOwner && !!sessionId
  useEffect(() => {
    setRecommended([])
    if (!active) { setResultLoading(false); return }
    let cancelled = false
    setResultLoading(true)
    getResult({ session_id: sessionId })
      .then(d => { if (!cancelled) setRecommended(d?.predicted_like_images || []) })
      .catch(() => { /* leave empty */ })
      .finally(() => { if (!cancelled) setResultLoading(false) })
    return () => { cancelled = true }
  }, [active, sessionId])
  return { recommended, resultLoading }
}
