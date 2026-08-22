/**
 * api/personality.js
 * Personality assessment + profile endpoints.
 */

import { callApi } from './core.js'

export async function submitAssessment(responses) {
  return await callApi('POST', '/personality/assessment/', { responses })
}

export async function getMyPersonality() {
  return await callApi('GET', '/personality/me/')
}
