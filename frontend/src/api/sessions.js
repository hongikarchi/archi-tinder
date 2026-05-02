/**
 * api/sessions.js
 * Analysis session lifecycle: start, resume, swipe, query parse, results.
 */

import { callApi } from './core.js'
import { normalizeCard } from './images.js'

/**
 * Start an analysis session.
 * params.filter_priority and params.seed_ids are forwarded to the backend
 * for weighted scoring pool creation.
 * params.visual_description -- Topic 03 HyDE V_initial seed (English text from parse_query);
 *   ignored by backend when hyde_vinitial_enabled flag is OFF.
 */
export async function startSession(params) {
  const result = await callApi('POST', '/analysis/sessions/', {
    project_id:      params.project_id,
    filters:         params.filters || {},
    filter_priority: params.filter_priority || [],
    seed_ids:        params.seed_ids || [],
    ...(params.visual_description ? { visual_description: params.visual_description } : {}),
  })
  return {
    ...result,
    next_image:      normalizeCard(result.next_image),
    prefetch_image:  normalizeCard(result.prefetch_image),
    prefetch_image_2: normalizeCard(result.prefetch_image_2),
  }
}

/**
 * Fetch the current resumable state of an active session.
 * Used on page refresh to continue a swipe session where the user left off,
 * instead of creating a brand-new session (which would reset progress).
 * The optional `currentHint` is the building_id of the card the frontend was
 * actively displaying (via instant-swap buffering). The backend uses it as a
 * hint to return the same card the user was looking at, so refresh is seamless.
 * Throws on 404 (session not found) or other API errors.
 */
export async function getSessionState(sessionId, currentHint = null) {
  const query = currentHint ? `?current=${encodeURIComponent(currentHint)}` : ''
  const result = await callApi('GET', `/analysis/sessions/${sessionId}/state/${query}`)
  return {
    ...result,
    next_image:      normalizeCard(result.next_image),
    prefetch_image:  normalizeCard(result.prefetch_image),
    prefetch_image_2: normalizeCard(result.prefetch_image_2),
  }
}

/**
 * Record a swipe action -> receive next_image.
 * client_buffer_ids is an array of building_ids the frontend has prefetched
 * in its visible queue (not yet swiped). The backend merges these into
 * session.exposed_ids before card selection so the same card is never shown twice.
 */
export async function recordSwipe({ session_id, image_id, action, client_buffer_ids = [] }) {
  const result = await callApi('POST', `/analysis/sessions/${session_id}/swipes/`, {
    building_id:       image_id,
    action,
    idempotency_key:   `swp_${session_id}_${image_id}`,
    client_buffer_ids: client_buffer_ids,
  })
  return {
    ...result,
    next_image:      normalizeCard(result.next_image),
    prefetch_image:  normalizeCard(result.prefetch_image),
    prefetch_image_2: normalizeCard(result.prefetch_image_2),
  }
}

/**
 * Parse a natural-language query using Gemini on the backend.
 * Backwards-compatible:
 *   parseQuery('hello')                     -> POST { query: 'hello' }               (legacy single-turn)
 *   parseQuery([{role:'user', text:'..'}])  -> POST { conversation_history: [...] }  (multi-turn)
 *
 * Response (probe_needed=true):  { probe_needed: true, probe_question, reply, results: [] }
 * Response (probe_needed=false): { reply, structured_filters, filter_priority, suggestions, results: [ImageCard] }
 */
export async function parseQuery(input) {
  const body = typeof input === 'string'
    ? { query: input }
    : { conversation_history: input }
  const result = await callApi('POST', '/parse-query/', body)
  return {
    ...result,
    results: (result.results || []).map(normalizeCard),
  }
}

/**
 * Fetch final session results.
 */
export async function getResult({ session_id }) {
  const result = await callApi('GET', `/analysis/sessions/${session_id}/result/`)
  return {
    ...result,
    liked_images:           (result.liked_images || []).map(normalizeCard),
    predicted_like_images:  (result.predicted_images || []).map(normalizeCard),
  }
}
