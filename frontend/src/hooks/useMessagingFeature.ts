/**
 * useMessagingFeature — app-wide messaging + follow feature flags
 * (FULL-MESSAGING-1 D12, SNS-FOLLOW-1).
 *
 * Source of truth is the backend (`features.messaging` / `features.follow` on
 * GET /auth/me/), read once per login by App.jsx via loadMessagingFeature().
 * Tiny module-level store (not a context) so TabBar, the profile page and
 * non-component code (the unread store) all agree without a provider.
 *
 * Both flags default to OFF: until /auth/me/ answers — or if it fails, or the
 * field is absent — every messaging / follow surface renders nothing and no
 * endpoint of that feature is called.
 */
import { useSyncExternalStore } from 'react'
import { getMe } from '../api/auth.ts'
import { setAdminStatus } from './useAdminStatus.ts'

let messagingEnabled = false
let followEnabled = false
let generation = 0
const listeners = new Set<() => void>()

function setFlags(messaging: boolean, follow: boolean) {
  if (messagingEnabled === messaging && followEnabled === follow) return
  messagingEnabled = messaging
  followEnabled = follow
  listeners.forEach(fn => fn())
}

function subscribe(fn: () => void) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function isMessagingEnabled() {
  return messagingEnabled
}

export function isFollowEnabled() {
  return followEnabled
}

/** Fetch /auth/me/ and publish `features.messaging` / `features.follow`. Stale responses are dropped. */
export async function loadMessagingFeature() {
  const mine = ++generation
  try {
    const me = await getMe()
    if (mine !== generation) return
    setFlags(me?.features?.messaging === true, me?.features?.follow === true)
    // ADMIN-DASH-1: same /auth/me/ answer also carries `is_admin` (UX gate only).
    setAdminStatus(me?.is_admin === true)
  } catch {
    if (mine !== generation) return
    setFlags(false, false)
    setAdminStatus(false)
  }
}

/** Logout / no session — flag back to OFF and invalidate any in-flight load. */
export function resetMessagingFeature() {
  generation += 1
  setFlags(false, false)
  setAdminStatus(null)
}

export function useMessagingEnabled() {
  return useSyncExternalStore(subscribe, isMessagingEnabled, isMessagingEnabled)
}

export function useFollowEnabled() {
  return useSyncExternalStore(subscribe, isFollowEnabled, isFollowEnabled)
}
