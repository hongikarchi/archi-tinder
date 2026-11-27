import { useSyncExternalStore } from 'react'

/**
 * Session-local cache of users the viewer blocked (FULL-MESSAGING-1).
 *
 * The server status (`blocked_by_me` on users/<id>/follow/, #372) is
 * authoritative and is applied both ways (true adds, false removes) via
 * applyServerBlockedByMe. Local block/unblock actions update the cache
 * immediately. A status response issued before a local action may be stale, so
 * callers capture getBlockSeq(userId) before the request and the response is
 * dropped if a local action on that same user (or clearBlocked) happened
 * meanwhile. Actions on other users never invalidate it (#500). Module-level
 * (not component state) so every UserActionsMenu instance — the conversation header (remounted
 * whenever a conversation is opened on the /messages tab) and the profile menu —
 * agrees and offers "Unblock".
 */
type UserId = number | string | null | undefined

const blocked = new Set<string>()
const listeners = new Set<() => void>()
// Per-user counters, bumped on local actions for that user only; `epoch` is
// bumped by clearBlocked (logout) and invalidates every in-flight request.
const seqs = new Map<string, number>()
let epoch = 0

function key(userId: UserId): string | null {
  return userId == null ? null : String(userId)
}

function emit() {
  listeners.forEach(l => l())
}

function bump(k: string) {
  seqs.set(k, (seqs.get(k) ?? 0) + 1)
}

export function getBlockSeq(userId: UserId): string {
  const k = key(userId)
  return `${epoch}:${k == null ? 0 : seqs.get(k) ?? 0}`
}

export function markBlocked(userId: UserId) {
  const k = key(userId)
  if (k == null) return
  // Bumped even when already cached: the server state just changed, so an older
  // in-flight status for this user is stale either way.
  bump(k)
  if (blocked.has(k)) return
  blocked.add(k)
  emit()
}

export function markUnblocked(userId: UserId) {
  const k = key(userId)
  if (k == null) return
  bump(k)
  if (!blocked.delete(k)) return
  emit()
}

export function applyServerBlockedByMe(userId: UserId, blockedByMe?: boolean | null, seqAtRequest?: string) {
  if (seqAtRequest !== undefined && seqAtRequest !== getBlockSeq(userId)) return
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
  epoch += 1
  seqs.clear()
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
