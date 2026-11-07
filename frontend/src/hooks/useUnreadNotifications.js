/**
 * useUnreadNotifications — self-only unread notification count.
 *
 * Fetches on mount + on document visibilitychange (tab becomes visible).
 * Deliberately NO setInterval polling (spec NOTIF-INAPP-1 §3).
 *
 * The count lives in a tiny module-level store (same pattern as
 * useUnreadMessages) so the own-profile bell badge and the TabBar profile dot
 * agree, and concurrent non-forced refreshes share ONE in-flight request.
 *
 * `enabled` (default true) lets a caller mount the hook unconditionally
 * (Rules of Hooks) while skipping the fetch entirely when not applicable —
 * e.g. UserProfilePage only wants this on the viewer's OWN profile (isMe),
 * not when viewing someone else's. A disabled caller still reads the shared
 * count (it just never triggers a fetch itself).
 *
 * The inbox screen calls markRead() itself and then
 * refreshUnreadNotifications({ force: true }) so the badge / dot clear.
 */
import { useEffect, useSyncExternalStore, useCallback } from 'react'
import { getUnreadCount } from '../api/notifications.js'

let unreadCount = 0
let epoch = 0
let inflight = null
let rerunQueued = false
const listeners = new Set()

function setCount(next) {
  if (unreadCount === next) return
  unreadCount = next
  listeners.forEach(fn => fn())
}

function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

function getSnapshot() {
  return unreadCount
}

function runFetch() {
  const myEpoch = epoch
  const promise = getUnreadCount()
    .then(data => {
      if (myEpoch === epoch) setCount(data?.count ?? 0)
    })
    .catch(() => { /* best-effort — leave last-known count */ })
    .finally(() => {
      // A reset may have replaced/cleared `inflight`; only clear our own.
      if (inflight !== promise) return
      inflight = null
      if (rerunQueued) {
        rerunQueued = false
        runFetch()
      }
    })
  inflight = promise
  return promise
}

/**
 * Refresh the shared count. `force` (after a mutation such as mark-read)
 * guarantees one more request starts after any in-flight one; a plain call
 * joins the in-flight request instead of duplicating it.
 */
export function refreshUnreadNotifications({ force = false } = {}) {
  if (inflight) {
    if (force) rerunQueued = true
    return inflight
  }
  return runFetch()
}

/** Logout / user switch — drop the previous user's count and in-flight result. */
export function resetUnreadNotifications() {
  epoch += 1
  rerunQueued = false
  inflight = null // stale request must not be joined; its result is epoch-discarded
  setCount(0)
}

export function useUnreadNotifications(enabled = true) {
  const count = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)

  const refresh = useCallback(() => {
    if (!enabled) return
    refreshUnreadNotifications()
  }, [enabled])

  useEffect(() => {
    if (!enabled) return undefined
    refreshUnreadNotifications()

    function onVisibilityChange() {
      if (document.visibilityState === 'visible') refreshUnreadNotifications()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [enabled])

  return { count, refresh }
}
