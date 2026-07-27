/**
 * api/inspect.js
 * ADMIN-DBCHECK-1 — internal DB-quality inspection API (dev-build only page).
 * Three read-only IsAuthenticated endpoints consumed by /db-check.
 */

import { callApi } from './core.js'

/**
 * getInspectBuildings — keyset-paginated browse-all grid page.
 * @param {{ after?: string|null, pageSize?: number }} opts
 * @returns {Promise<{ results: object[], next_after: string|null, total: number }>}
 */
export async function getInspectBuildings({ after, pageSize } = {}) {
  const params = new URLSearchParams()
  if (after) params.set('after', after)
  if (pageSize) params.set('page_size', String(pageSize))
  const qs = params.toString()
  return callApi('GET', `/inspect/buildings/${qs ? `?${qs}` : ''}`)
}

/**
 * getInspectBuilding — full DB row for one canonical_bld_id (minus raw embedding).
 * @param {string} id
 */
export async function getInspectBuilding(id) {
  return callApi('GET', `/inspect/buildings/${id}/`)
}

/**
 * inspectSearch — natural-language search through the real service parser,
 * returns up to 100 scored results + the parsed structured filters.
 * @param {string} query
 */
export async function inspectSearch(query) {
  return callApi('POST', '/inspect/search/', { query, limit: 100 })
}
