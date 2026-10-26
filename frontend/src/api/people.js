/**
 * api/people.js
 * Social board feed endpoints (/people).
 */

import { callApi } from './core.js'

/**
 * One page of the public-board feed.
 * filter: absent (all) | 'inspired' | 'opposite' | a 4-letter type code.
 * Resolves { results, has_more, next_cursor }; 403 { detail: 'assessment_required' }
 * is thrown (err.status / err.data) so the page can show its CTA.
 */
export async function getPeopleDiscovery({ filter, cursor, pageSize } = {}) {
  const qs = new URLSearchParams()
  if (filter && filter !== 'all') qs.set('filter', filter)
  if (cursor) qs.set('cursor', cursor)
  if (pageSize) qs.set('page_size', String(pageSize))
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return await callApi('GET', `/people/${query}`)
}

/**
 * Fetch one board's report image for the feed card.
 *
 * Split off the feed response because the image is base64 TEXT in the DB —
 * inlining a page of them would make one feed payload megabytes wide. Cards
 * call this lazily.
 *
 * Returns { image_data, mime_type }, or null when the board has no public
 * report image (backend answers 404). Callers must treat null as "no image"
 * and stop — do not retry.
 */
export async function getBoardReportImage(boardId) {
  try {
    return await callApi('GET', `/people/boards/${boardId}/report-image/`)
  } catch {
    return null
  }
}
