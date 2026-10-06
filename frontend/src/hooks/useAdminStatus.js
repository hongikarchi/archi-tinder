/**
 * useAdminStatus — app-wide `is_admin` flag (ADMIN-DASH-1).
 *
 * Source of truth is the backend (`is_admin` on GET /auth/me/), published by
 * useMessagingFeature's loadMessagingFeature() so the app issues ONE /auth/me/
 * call per login. Tri-state: null = not known yet, true / false = answered.
 * UX only — the backend IsAdminOperator permission is the real gate.
 */
import { useSyncExternalStore } from 'react'

let adminStatus = null
const listeners = new Set()

export function setAdminStatus(next) {
  if (adminStatus === next) return
  adminStatus = next
  listeners.forEach(fn => fn())
}

function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

function getSnapshot() {
  return adminStatus
}

/** @returns {boolean|null} null while /auth/me/ has not answered yet. */
export function useAdminStatus() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}
