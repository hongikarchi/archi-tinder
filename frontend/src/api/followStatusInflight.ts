/**
 * Shared in-flight GET /users/<id>/follow/ (#493). The profile page mounts
 * FollowCta and UserActionsMenu together and both read the status; they now
 * share one request. Writes that change the answer (follow / unfollow / block /
 * unblock) invalidate first so a later read is never served a pre-write answer.
 * Its own module so api/social.ts and api/messaging.ts can both use it without
 * an import cycle.
 */
import { createInflight } from '../utils/inflight.ts'
import type { FollowStatus } from '../types/api.ts'

export const followStatusInflight = createInflight<FollowStatus>()

export function invalidateFollowStatus(userId?: number | string) {
  followStatusInflight.invalidate(userId === undefined ? undefined : String(Number(userId)))
}
