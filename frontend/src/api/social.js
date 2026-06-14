/**
 * api/social.js
 * Social graph: project reactors.
 *
 * User-to-user follow/unfollow (followUser, unfollowUser, getFollowers,
 * getFollowing) has been removed. Architect/firm follow is in api/architects.js.
 */

import { callApi } from './core.js'

export async function getProjectReactors(projectId, { page = 1, pageSize = 50 } = {}) {
  return await callApi('GET', `/projects/${projectId}/reactors/?page=${page}&page_size=${pageSize}`)
}

export async function reactToProject(projectId) {
  return await callApi('POST', `/projects/${projectId}/react/`)
}

export async function unreactToProject(projectId) {
  return await callApi('DELETE', `/projects/${projectId}/react/`)
}
