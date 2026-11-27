/**
 * api/social.ts
 * Social graph: user follow (SNS-FOLLOW-1), project reactors and the viewer's
 * liked boards.
 *
 *   GET    /users/<id>/follow/  -> FollowStatus
 *   POST   /users/<id>/follow/  -> FollowStatus (201 created / 200 already following)
 *   DELETE /users/<id>/follow/  -> 204
 *
 * Every follow endpoint answers 404 while the FOLLOW_ENABLED backend flag is
 * off — callers gate on `useFollowEnabled()` (hooks/useMessagingFeature.ts)
 * and never call these when it is off. Guest writes answer 403
 * {detail:'verify_required'}: the write helpers dispatch the global
 * 'archithon:verify-required' event and throw VerifyRequiredError (same
 * contract as api/messaging.ts). A 400 {detail:'unavailable'} (self / blocked
 * either way / guest target / opted-out target) is deliberately identical for
 * all causes. Architect/firm follow is a separate feature in api/architects.ts.
 */

import { callApi } from './core.ts'
import { verifyGatedWrite } from './messaging.ts'
import type { FollowStatus } from '../types/api.ts'
import { followStatusInflight, followStatusKey, withFollowStatusWrite } from './followStatusInflight.ts'

/** Numeric user ids only — the id is interpolated into the URL path. */
function followPath(userId: number | string) {
  const id = Number(userId)
  if (!Number.isInteger(id) || id <= 0) throw new Error('invalid user id')
  return `/users/${id}/follow/`
}

/** Fresh read (never shared); callers capture getBlockSeq() before calling. */
export async function getFollowStatus(userId: number | string): Promise<FollowStatus> {
  return await callApi('GET', followPath(userId))
}

/**
 * Share a pending read for this user, or start one. `meta` is the block-seq
 * token from when the shared read started — pass it to applyServerBlockedByMe.
 */
export function joinFollowStatus(userId: number | string, blockSeq?: number | string) {
  const path = followPath(userId)
  return followStatusInflight.join(followStatusKey(userId), () => callApi('GET', path), blockSeq)
}

export async function followUser(userId: number | string): Promise<FollowStatus> {
  const path = followPath(userId)
  return await withFollowStatusWrite(userId, () => verifyGatedWrite('POST', path))
}

export async function unfollowUser(userId: number | string): Promise<null> {
  const path = followPath(userId)
  return await withFollowStatusWrite(userId, () => verifyGatedWrite('DELETE', path))
}

export async function getProjectReactors(projectId, { page = 1, pageSize = 50 } = {}) {
  return await callApi('GET', `/projects/${projectId}/reactors/?page=${page}&page_size=${pageSize}`)
}

export async function reactToProject(projectId) {
  return await callApi('POST', `/projects/${projectId}/react/`)
}

export async function unreactToProject(projectId) {
  return await callApi('DELETE', `/projects/${projectId}/react/`)
}

/** Own liked boards, newest like first (profile 'Liked' tab). */
export async function getLikedBoards({ page = 1, pageSize = 12 } = {}) {
  return await callApi('GET', `/liked-boards/?page=${page}&page_size=${pageSize}`)
}
