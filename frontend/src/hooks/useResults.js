import { useEffect, useMemo, useState } from 'react'
import { bookmarkBuilding, getResult } from '../api/client.js'

function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(value || ''))
}

function getCardId(card) {
  return card?.image_id || card?.building_id || null
}

export function useResults(sessionId, projects, setProjects) {
  const validSessionId = isUuid(sessionId) ? sessionId : null
  const project = useMemo(
    () => projects.find(p => p.sessionId === validSessionId) || null,
    [projects, validSessionId]
  )
  const [cards, setCards] = useState(project?.predictedLikes || [])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(!!validSessionId && !project?.predictedLikes?.length)
  const [error, setError] = useState(null)
  const [pendingIds, setPendingIds] = useState(() => new Set())

  useEffect(() => {
    setCards(project?.predictedLikes || [])
  }, [project?.predictedLikes])

  useEffect(() => {
    if (!validSessionId) {
      setError('Invalid session ID.')
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    getResult({ session_id: validSessionId })
      .then(data => {
        if (cancelled) return
        const predicted = data.predicted_like_images || []
        setResult(data)
        setCards(predicted)
        if (setProjects) {
          setProjects(prev => prev.map(p => (
            p.sessionId === validSessionId
              ? { ...p, predictedLikes: predicted }
              : p
          )))
        }
      })
      .catch(err => {
        if (cancelled) return
        setError(err.message || 'Failed to load results.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [validSessionId, setProjects])

  async function toggleBookmark(card, rank) {
    const cardId = getCardId(card)
    const backendId = project?.backendId || (project?.id?.includes('-') ? project.id : null)
    if (!cardId || !backendId || pendingIds.has(cardId)) return

    const wasSaved = (project?.savedIds || []).includes(cardId)
    const action = wasSaved ? 'unsave' : 'save'
    setPendingIds(prev => new Set(prev).add(cardId))

    setProjects(prev => prev.map(p => {
      if (p.id !== project.id) return p
      const current = p.savedIds || []
      const next = wasSaved
        ? current.filter(id => id !== cardId)
        : [...new Set([...current, cardId])]
      return { ...p, savedIds: next }
    }))

    try {
      await bookmarkBuilding(backendId, cardId, action, rank, validSessionId)
    } catch {
      setProjects(prev => prev.map(p => {
        if (p.id !== project.id) return p
        const current = p.savedIds || []
        const reverted = wasSaved
          ? [...new Set([...current, cardId])]
          : current.filter(id => id !== cardId)
        return { ...p, savedIds: reverted }
      }))
    } finally {
      setPendingIds(prev => {
        const next = new Set(prev)
        next.delete(cardId)
        return next
      })
    }
  }

  return {
    cards,
    error,
    loading,
    pendingIds,
    project,
    result,
    toggleBookmark,
    validSessionId,
  }
}
