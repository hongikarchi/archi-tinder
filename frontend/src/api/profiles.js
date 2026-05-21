/**
 * api/profiles.js
 * Office (firm) and user profile fetching.
 */

import { callApi } from './core.js'

export async function getOffice(officeId) {
  return await callApi('GET', `/offices/${officeId}/`)
}

export async function getUserProfile(userId, { boardsPage, boardsPageSize } = {}) {
  const params = new URLSearchParams()
  if (boardsPage != null) params.set('boards_page', boardsPage)
  if (boardsPageSize != null) params.set('boards_page_size', boardsPageSize)
  const qs = params.toString()
  return await callApi('GET', `/users/${userId}/${qs ? `?${qs}` : ''}`)
}

export async function updateMyProfile(patch) {
  return await callApi('PATCH', '/users/me/', patch)
}
