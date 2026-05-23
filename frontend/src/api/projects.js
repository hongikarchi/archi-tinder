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

export async function getProject(projectId, { throwOnError = false } = {}) {
  try {
    return await callApi('GET', `/projects/${projectId}/`)
  } catch (err) {
    console.error('[api/client] getProject failed:', err)
    if (throwOnError) throw err
    return null
  }
}

export async function updateProject(projectId, fields) {
  try {
    return await callApi('PATCH', `/projects/${projectId}/`, fields)
  } catch (err) {
    console.error('[api/client] updateProject failed:', err)
    throw err
  }
}

export async function deleteProject(projectId) {
  try {
    await callApi('DELETE', `/projects/${projectId}/`)
  } catch (err) {
    console.error('[api/client] deleteProject failed:', err)
    throw err
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
 * Splits into chunks of 200 to respect the backend limit.
 */
export async function getBuildings(buildingIds) {
  if (!buildingIds?.length) return []
  const CHUNK = 200
  const chunks = []
  for (let i = 0; i < buildingIds.length; i += CHUNK) {
    chunks.push(buildingIds.slice(i, i + CHUNK))
  }
  try {
    const results = await Promise.all(
      chunks.map(chunk => callApi('POST', '/images/batch/', { canonical_bld_ids: chunk }))
    )
    return results.flat().map(normalizeCard)
  } catch (err) {
    console.error('[api/client] getBuildings failed:', err)
    return []
  }
}

/**
 * Batch-fetch building cards for board detail.
 * Returns normalized ImageCard objects (same shape as swipe cards).
 * Preserves input order via Map lookup before normalizing.
 */
export async function getBoardBuildings(buildingIds) {
  if (!buildingIds?.length) return []
  try {
    const result = await callApi('POST', '/images/batch/', { canonical_bld_ids: buildingIds })
    const byId = new Map(
      (result || []).map(card => [String(card.canonical_bld_id ?? card.building_id ?? card.id), card])
    )
    return buildingIds
      .map(id => byId.get(String(id)))
      .filter(Boolean)
      .map(normalizeCard)
  } catch (err) {
    console.error('[api/client] getBoardBuildings failed:', err)
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
