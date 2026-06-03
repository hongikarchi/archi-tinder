/**
 * api/architects.js
 * Architect recommendation and profile fetching.
 */

import { callApi } from './core.js'

export async function getRecommendedArchitects(projectId) {
  try {
    const data = await callApi('GET', `/projects/${projectId}/recommended_architects/`)
    return Array.isArray(data) ? data : []
  } catch {
    return []  // graceful degradation — board load must not be blocked
  }
}

export async function getArchitectProfile(architectId) {
  try {
    const data = await callApi('GET', `/architects/${architectId}/`)
    return data
  } catch (err) {
    if (err?.status === 404) return null
    throw err
  }
}

export async function followArchitect(architectId) {
  return callApi('POST', `/architects/${architectId}/follow/`)
}

export async function unfollowArchitect(architectId) {
  try {
    return await callApi('DELETE', `/architects/${architectId}/follow/`)
  } catch (err) {
    if (err?.status === 404) return {}
    throw err
  }
}

export async function getUserSavedStudios(userId) {
  return callApi('GET', `/users/${userId}/saved_studios/`)
}
