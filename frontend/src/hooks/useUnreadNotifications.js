/**
 * useUnreadNotifications — self-only unread notification count.
 *
 * Fetches on mount + on document visibilitychange (tab becomes visible).
 * Deliberately NO setInterval polling (spec NOTIF-INAPP-1 §3).
 *
 * `enabled` (default true) lets a caller mount the hook unconditionally
 * (Rules of Hooks) while skipping the fetch entirely when not applicable —
 * e.g. ProfileHeader only wants this on the viewer's OWN profile (isMe),
 * not when viewing someone else's.
 *
 * Kept minimal / component-local (no global store) — the inbox screen
 * calls markRead() itself; callers that need the badge to clear after a
 * visit to /notifications can call refresh() again on route return.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { getUnreadCount } from '../api/notifications.js'

export function useUnreadNotifications(enabled = true) {
  const [count, setCount] = useState(0)
  const cancelledRef = useRef(false)

  const refresh = useCallback(() => {
    if (!enabled) return
    getUnreadCount()
      .then(data => {
        if (cancelledRef.current) return
        setCount(data?.count ?? 0)
      })
      .catch(() => { /* best-effort — leave last-known count */ })
  }, [enabled])

  useEffect(() => {
    if (!enabled) return undefined
    cancelledRef.current = false
    refresh()

    function onVisibilityChange() {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      cancelledRef.current = true
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [refresh, enabled])

  return { count, refresh }
}
