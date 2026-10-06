/**
 * useAdminSection — loads one admin dashboard endpoint independently.
 *
 * Each section owns its own request so a failing endpoint only shows an
 * inline error in its own card (DESIGN.md 8.9: never blank the whole page).
 * `loading` is derived (result token !== current token) rather than set in
 * the effect, so a key change (e.g. audit-log page) shows the skeleton again.
 */
import { useCallback, useEffect, useState } from 'react'

export function useAdminSection(fetcher, key = '') {
  const [tick, setTick] = useState(0)
  const [result, setResult] = useState({ token: null, data: null, error: null })
  const token = `${key}|${tick}`

  useEffect(() => {
    let cancelled = false
    fetcher()
      .then(data => { if (!cancelled) setResult({ token, data, error: null }) })
      .catch(error => { if (!cancelled) setResult({ token, data: null, error: error || new Error('failed') }) })
    return () => { cancelled = true }
  }, [fetcher, token])

  const reload = useCallback(() => setTick(n => n + 1), [])
  const loading = result.token !== token
  return {
    data: loading ? null : result.data,
    error: loading ? null : result.error,
    loading,
    reload,
  }
}
