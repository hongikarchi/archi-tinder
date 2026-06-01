import { useEffect, useState } from 'react'
import { getBoardBuildings, getProject } from '../api/projects.js'
import { getResult } from '../api/sessions.js'
import { getRecommendedArchitects } from '../api/architects.js'

function collectBoardBuildingIds(project) {
  const ids = []
  const seen = new Set()
  const add = item => {
    const id = item?.id
    if (!id || seen.has(id)) return
    seen.add(id)
    ids.push(id)
  }
  for (const item of project?.liked_ids || []) add(item)
  for (const item of project?.saved_ids || []) add(item)
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

export function useBoard(projectId) {
  const [board, setBoard] = useState(null)
  const [recommended, setRecommended] = useState([])
  const [recommendedArchitects, setRecommendedArchitects] = useState([])
  const [buildingsLoading, setBuildingsLoading] = useState(true)
  const [resultLoading, setResultLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
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
        if (project.latest_session_id) {
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
        getRecommendedArchitects(project.project_id)
          .then(architects => {
            if (cancelled) return
            setRecommendedArchitects(architects)
          })
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
  }, [projectId])

  // Expose a combined `loading` alias so existing consumers continue to work.
  const loading = buildingsLoading

  return { board, recommended, recommendedArchitects, loading, buildingsLoading, resultLoading, error }
}
