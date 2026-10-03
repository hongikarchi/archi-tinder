/**
 * useUnreadMessages — shared unread count for the messaging badge (profile
 * message pill) and the TabBar profile dot (FULL-MESSAGING-1, D6/D8).
 *
 * Same contract as useUnreadNotifications: fetch on mount + on document
 * visibilitychange (tab becomes visible) + on route change. Deliberately NO
 * setInterval (NOTIF-INAPP-1 §3 — no background polling). The only timed
 * polling in messaging lives inside an OPEN conversation view.
 *
 * The count lives in a tiny module-level store so every consumer agrees;
 * concurrent non-forced refreshes share one in-flight request, so TabBar and
 * the profile pill mounting together cost a single GET.
 *
 * Feature flag OFF => the hook returns 0 and never touches the network.
 */
import { useEffect, useSyncExternalStore } from 'react'
import { useLocation } from 'react-router-dom'
import { getMessagesUnreadCount } from '../api/messaging.js'
import { isMessagingEnabled, useMessagingEnabled } from './useMessagingFeature.js'

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
  const promise = getMessagesUnreadCount()
    .then(data => {
      if (myEpoch === epoch) setCount(data?.count ?? 0)
    })
    .catch(() => { /* best-effort — keep last-known count */ })
    .finally(() => {
      // A reset may have replaced/cleared `inflight`; only clear our own.
      if (inflight !== promise) return
      inflight = null
      if (rerunQueued) {
        rerunQueued = false
        if (isMessagingEnabled()) runFetch()
      }
    })
  inflight = promise
  return promise
}

/**
 * Refresh the shared count. `force` (after a mutation such as read/accept)
 * guarantees one more request starts after any in-flight one; a plain call
 * joins the in-flight request instead of duplicating it.
 */
export function refreshUnreadMessages({ force = false } = {}) {
  if (!isMessagingEnabled()) return Promise.resolve()
  if (inflight) {
    if (force) rerunQueued = true
    return inflight
  }
  return runFetch()
}

/** Logout / user switch — drop the previous user's count and in-flight result. */
export function resetUnreadMessages() {
  epoch += 1
  rerunQueued = false
  inflight = null // stale request must not be joined; its result is epoch-discarded
  setCount(0)
}

export function useUnreadMessages() {
  const enabled = useMessagingEnabled()
  const count = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
  const { pathname } = useLocation()

  // mount + route change
  useEffect(() => {
    if (enabled) refreshUnreadMessages()
  }, [enabled, pathname])

  // tab becomes visible again
  useEffect(() => {
    if (!enabled) return undefined
    function onVisibilityChange() {
      if (document.visibilityState === 'visible') refreshUnreadMessages()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [enabled])

  return { count: enabled ? count : 0, refresh: refreshUnreadMessages }
}
