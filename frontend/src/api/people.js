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
