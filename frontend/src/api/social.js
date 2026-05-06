/**
 * api/social.js
 * Social graph: follow / unfollow + project reactors.
 */

import { callApi } from './core.js'

export async function followUser(userId) {
  return await callApi('POST', `/users/${userId}/follow/`)
}

export async function unfollowUser(userId) {
  await callApi('DELETE', `/users/${userId}/follow/`)
}

export async function followOffice(officeId) {
  return await callApi('POST', `/offices/${officeId}/follow/`)
}

export async function unfollowOffice(officeId) {
  await callApi('DELETE', `/offices/${officeId}/follow/`)
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
