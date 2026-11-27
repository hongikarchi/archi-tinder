/**
 * Shared in-flight GET /users/<id>/follow/ (#493). The profile page mounts
 * FollowCta and UserActionsMenu together and both read the status.
 *
 * FollowCta always sends a fresh read (it refetches right after its own writes)
 * and publishes it here; UserActionsMenu only joins a pending read, using the
 * block-seq token captured when that read STARTED, so a read issued before a
 * local block/unblock is still dropped by applyServerBlockedByMe.
 * Writes that change the answer invalidate at start and again when they settle.
 * Its own module so api/social.ts and api/messaging.ts share it without a cycle.
 */
import { createInflight } from '../utils/inflight.ts'
import type { FollowStatus } from '../types/api.ts'

export const followStatusInflight = createInflight<FollowStatus, number | string | undefined>()

export function followStatusKey(userId: number | string) {
  return String(Number(userId))
}

export function invalidateFollowStatus(userId?: number | string) {
  followStatusInflight.invalidate(userId === undefined ? undefined : followStatusKey(userId))
}

/** Run a write that changes the follow status; invalidate before and after. */
export async function withFollowStatusWrite<T>(userId: number | string, write: () => Promise<T>): Promise<T> {
  invalidateFollowStatus(userId)
  try {
    return await write()
  } finally {
    invalidateFollowStatus(userId)
  }
}
