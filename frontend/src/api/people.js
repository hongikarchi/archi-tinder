/**
 * api/people.js
 * People discovery feed endpoints.
 */

import { callApi } from './core.js'

export async function getPeopleDiscovery({ filter, axis } = {}) {
  const qs = new URLSearchParams()
  if (filter) qs.set('filter', filter)
  if (axis !== undefined && axis !== null) qs.set('axis', String(axis))
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return await callApi('GET', `/people/${query}`)
}

/**
 * Fetch one person's taste-report image.
 *
 * Split off the feed response because the image is base64 TEXT in the DB —
 * inlining ~15 of them would make a single feed payload megabytes wide. Cards
 * call this lazily.
 *
 * Returns { image_data, mime_type }, or null when the user has no public
 * report image (backend answers 404). Callers must treat null as "no image"
 * and stop — do not retry.
 */
export async function getPersonReportImage(userId) {
  try {
    return await callApi('GET', `/people/${userId}/report-image/`)
  } catch {
    return null
  }
}
