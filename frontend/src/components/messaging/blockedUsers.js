import { useSyncExternalStore } from 'react'

/**
 * Session-local record of users the viewer blocked (FULL-MESSAGING-1).
 *
 * The API has no block-status read, so after a block action the menus must
 * remember it themselves. Module-level (not component state) so every
 * UserActionsMenu instance — the conversation header (remounted whenever the
 * sheet reopens) and the profile menu — agrees and offers "Unblock".
 */
const blocked = new Set()
const listeners = new Set()

function key(userId) {
  return userId == null ? null : String(userId)
}

function emit() {
  listeners.forEach(l => l())
}

export function markBlocked(userId) {
  const k = key(userId)
  if (k == null || blocked.has(k)) return
  blocked.add(k)
  emit()
}

export function markUnblocked(userId) {
  const k = key(userId)
  if (k == null || !blocked.delete(k)) return
  emit()
}

export function isBlockedLocally(userId) {
  const k = key(userId)
  return k != null && blocked.has(k)
}

function subscribe(listener) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function useBlockedUser(userId) {
  return useSyncExternalStore(subscribe, () => isBlockedLocally(userId), () => false)
}
