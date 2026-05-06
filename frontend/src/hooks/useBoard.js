import { useEffect, useState } from 'react'
import { getBoardBuildings, getProject } from '../api/projects.js'

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
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!projectId) {
      setBoard(null)
      setLoading(false)
      setError(new Error('No board ID found.'))
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    getProject(projectId, { throwOnError: true })
      .then(async project => {
        if (cancelled) return
        if (!project) throw new Error('Board not found.')
        const buildingIds = collectBoardBuildingIds(project)
        const buildings = await getBoardBuildings(buildingIds)
        if (cancelled) return
        setBoard(adaptProjectToBoard(project, buildings))
      })
      .catch(err => {
        if (cancelled) return
        setBoard(null)
        setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [projectId])

  return { board, loading, error }
}
