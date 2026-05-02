/**
 * api/profiles.js
 * Office (firm) and user profile fetching.
 */

import { callApi } from './core.js'

export async function getOffice(officeId) {
  return await callApi('GET', `/offices/${officeId}/`)
}

export async function getUserProfile(userId) {
  return await callApi('GET', `/users/${userId}/`)
}
