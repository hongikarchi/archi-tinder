/**
 * useMessagingFeature — app-wide messaging feature flag (FULL-MESSAGING-1, D12).
 *
 * Source of truth is the backend (`features.messaging` on GET /auth/me/), read
 * once per login by App.jsx via loadMessagingFeature(). Tiny module-level
 * store (not a context) so TabBar, the profile page and non-component code
 * (the unread store) all agree without a provider.
 *
 * Default is OFF: until /auth/me/ answers — or if it fails, or the field is
 * absent — every messaging surface renders nothing and no messaging endpoint
 * is called.
 */
import { useSyncExternalStore } from 'react'
import { getMe } from '../api/auth.js'

let messagingEnabled = false
let generation = 0
const listeners = new Set()

function setEnabled(next) {
  if (messagingEnabled === next) return
  messagingEnabled = next
  listeners.forEach(fn => fn())
}

function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function isMessagingEnabled() {
  return messagingEnabled
}

/** Fetch /auth/me/ and publish `features.messaging`. Stale responses are dropped. */
export async function loadMessagingFeature() {
  const mine = ++generation
  try {
    const me = await getMe()
    if (mine !== generation) return
    setEnabled(me?.features?.messaging === true)
  } catch {
    if (mine !== generation) return
    setEnabled(false)
  }
}

/** Logout / no session — flag back to OFF and invalidate any in-flight load. */
export function resetMessagingFeature() {
  generation += 1
  setEnabled(false)
}

export function useMessagingEnabled() {
  return useSyncExternalStore(subscribe, isMessagingEnabled, isMessagingEnabled)
}
