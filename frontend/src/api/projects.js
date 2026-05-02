/**
 * api/projects.js
 * Project (board) CRUD, building batch-fetch, bookmark, and report generation.
 */

import { callApi } from './core.js'
import { normalizeCard } from './images.js'

export async function listProjects(page = 1, pageSize = 50) {
  try {
    const data = await callApi('GET', `/projects/?page=${page}&page_size=${pageSize}`)
    // Support both paginated {results, has_more} and legacy plain array
    if (Array.isArray(data)) return { results: data, has_more: false, total: data.length }
    return data
  } catch (err) {
    console.error('[api/client] listProjects failed:', err)
    return { results: [], has_more: false, total: 0 }
  }
}

export async function deleteProject(projectId) {
  try {
    await callApi('DELETE', `/projects/${projectId}/`)
  } catch (err) {
    console.error('[api/client] deleteProject failed:', err)
  }
}

export async function generateReport(projectId) {
  return callApi('POST', `/projects/${projectId}/report/generate/`)
}

export async function generateReportImage(projectId) {
  return callApi('POST', `/projects/${projectId}/report/generate-image/`)
}

/**
 * Batch-fetch building cards by IDs.
 * Returns list of normalized ImageCard objects.
 */
export async function getBuildings(buildingIds) {
  if (!buildingIds?.length) return []
  try {
    const result = await callApi('POST', '/images/batch/', { building_ids: buildingIds })
    return (result || []).map(normalizeCard)
  } catch (err) {
    console.error('[api/client] getBuildings failed:', err)
    return []
  }
}

/**
 * Toggle bookmark (⭐) on a result-page card.
 * @param {string} projectId - backend project UUID
 * @param {string} cardId - building_id
 * @param {'save'|'unsave'} action
 * @param {number} rank - 1-indexed position in result page (1-50)
 * @param {string|null} sessionId - optional, for event association
 * @returns {Promise<{saved_ids: string[], count: number}>}
 */
export async function bookmarkBuilding(projectId, cardId, action, rank, sessionId = null) {
  return callApi('POST', `/projects/${projectId}/bookmark/`, {
    card_id: cardId,
    action,
    rank,
    ...(sessionId ? { session_id: sessionId } : {}),
  })
}
