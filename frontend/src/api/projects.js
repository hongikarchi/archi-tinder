/**
 * api/projects.js
 * Project (board) CRUD, building batch-fetch, bookmark, and report generation.
 */

import { callApi } from './core.js'
import { normalizeCard } from './images.js'

/**
 * Typed error thrown when the backend returns 403 with reason=board_limit_reached.
 * Callers catch this to mount VerifyGateModal instead of showing a generic error.
 */
export class VerifyRequiredError extends Error {
  constructor(reason) {
    super('verify_required')
    this.name = 'VerifyRequiredError'
    this.reason = reason
  }
}

/**
 * Create a new project (board).
 * On 403 verify_required → throws VerifyRequiredError (caller must handle).
 * Also dispatches 'archithon:verify-required' event for the global VerifyGateModal.
 */
export async function createProject(body) {
  try {
    return await callApi('POST', '/projects/', body)
  } catch (err) {
    if (err?.status === 403 && err?.data?.detail === 'verify_required') {
      const reason = err?.data?.reason || 'board_limit_reached'
      const verifyErr = new VerifyRequiredError(reason)
      window.dispatchEvent(new CustomEvent('archithon:verify-required', {
        detail: { reason },
      }))
      throw verifyErr
    }
    throw err
  }
}

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

export async function generateReport(projectId, { regenerate = false } = {}) {
  return callApi('POST', `/projects/${projectId}/report/generate/`, regenerate ? { regenerate: true } : undefined)
}

export async function generateReportImage(projectId, { regenerate = false } = {}) {
  return callApi('POST', `/projects/${projectId}/report/generate-image/`, regenerate ? { regenerate: true } : undefined)
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

/**
 * Fetch a board's persona report image.
 *
 * Split from the board list on purpose: Project.report_image is base64 TEXT
 * (~200KB each) and the profile's board page holds up to 50, so the list ships
 * a `report_image_url` pointer and each card resolves it lazily. Same split the
 * /people feed uses (see api/people.js getPersonReportImage).
 *
 * Returns { image_data, mime_type }, or null when the board has none / is not
 * visible to the caller (backend answers 404). Callers must treat null as "no
 * image" and fall back — do not retry.
 */
export async function getProjectReportImage(projectId) {
    try {
        return await callApi('GET', `/projects/${projectId}/report-image/`)
    } catch {
        return null
    }
}
