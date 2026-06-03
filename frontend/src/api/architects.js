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
