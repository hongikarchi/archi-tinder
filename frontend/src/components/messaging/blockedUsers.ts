import { useSyncExternalStore } from 'react'

/**
 * Session-local cache of users the viewer blocked (FULL-MESSAGING-1).
 *
 * The server status (`blocked_by_me` on contact-requests/status/, #372) is
 * authoritative and is applied both ways (true adds, false removes) via
 * applyServerBlockedByMe. Local block/unblock actions update the cache
 * immediately. A status response issued before a local action may be stale, so
 * callers capture getBlockSeq() before the request and the response is dropped if
 * a local action bumped the counter meanwhile. Module-level (not component
 * state) so every UserActionsMenu instance — the conversation header (remounted
 * whenever a conversation is opened on the /messages tab) and the profile menu —
 * agrees and offers "Unblock".
 */
type UserId = number | string | null | undefined

const blocked = new Set<string>()
const listeners = new Set<() => void>()
let seq = 0 // bumped on local user actions only

function key(userId: UserId): string | null {
  return userId == null ? null : String(userId)
}

function emit() {
  listeners.forEach(l => l())
}

export function getBlockSeq() {
  return seq
}

export function markBlocked(userId: UserId) {
  seq += 1
  const k = key(userId)
  if (k == null || blocked.has(k)) return
  blocked.add(k)
  emit()
}

export function markUnblocked(userId: UserId) {
  seq += 1
  const k = key(userId)
  if (k == null || !blocked.delete(k)) return
  emit()
}

export function applyServerBlockedByMe(userId: UserId, blockedByMe?: boolean | null, seqAtRequest?: number) {
  if (seqAtRequest !== undefined && seqAtRequest !== seq) return
  const k = key(userId)
  if (k == null) return
  if (blockedByMe === true) {
    if (blocked.has(k)) return
    blocked.add(k)
    emit()
  } else if (blockedByMe === false) {
    if (!blocked.delete(k)) return
    emit()
  }
}

export function clearBlocked() {
  seq += 1
  if (blocked.size === 0) return
  blocked.clear()
  emit()
}

export function isBlockedLocally(userId: UserId) {
  const k = key(userId)
  return k != null && blocked.has(k)
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function useBlockedUser(userId: UserId) {
  return useSyncExternalStore(subscribe, () => isBlockedLocally(userId), () => false)
}
