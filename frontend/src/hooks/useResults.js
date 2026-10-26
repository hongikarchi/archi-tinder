import { useEffect, useMemo, useState } from 'react'
import { getResult } from '../api/client.js'

function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(value || ''))
}

export function useResults(sessionId, projects, setProjects) {
  const validSessionId = isUuid(sessionId) ? sessionId : null
  const project = useMemo(
    () => projects.find(p => p.sessionId === validSessionId) || null,
    [projects, validSessionId]
  )
  const [loading, setLoading] = useState(!!validSessionId && !project?.predictedLikes?.length)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!validSessionId) {
      // Stable code (not a display string) — ResultsPage translates it via
      // t('results.invalidSession') at the display site.
      setError('invalid_session_id')
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

  return {
    error,
    loading,
    project,
  }
}
