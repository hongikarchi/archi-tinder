/**
 * api/sessions.js
 * Analysis session lifecycle: start, resume, swipe, query parse, results.
 */

import { callApi } from './core.js'
import { normalizeCard } from './images.js'

const PARSE_QUERY_TIMEOUT_MS = 60000    // Gemini LLM generation can take 10-30s
const SESSION_CREATE_TIMEOUT_MS = 30000 // Cold pool path: execute_pool_sql ~14.7s, total backend time can exceed 15s default

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
    name:            params.name || 'Untitled',
    filters:         params.filters || {},
    filter_priority: params.filter_priority || [],
    seed_ids:        params.seed_ids || [],
    raw_query:       params.raw_query || '',
    ...(params.visual_description ? { visual_description: params.visual_description } : {}),
    ...(params.image_focus ? { image_focus: params.image_focus } : {}),
    ...(params.force_new ? { force_new: true } : {}),
  }, true, SESSION_CREATE_TIMEOUT_MS)
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
 * The optional `currentHint` is the canonical_bld_id of the card the frontend
 * was actively displaying (via instant-swap buffering). The backend uses it as
 * a hint to return the same card the user was looking at, so refresh is seamless.
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
 * client_buffer_ids is an array of canonical_bld_ids the frontend has
 * prefetched in its visible queue (not yet swiped). The backend merges these
 * into session.exposed_ids before card selection so the same card is never
 * shown twice.
 * latency_ms (optional) is the number of milliseconds between the card
 * becoming visible and the user swiping it. The backend uses this for
 * hyper-positive / mindless-fast-swipe detection (Phase 3). Ignored if absent.
 */
export async function recordSwipe({ session_id, image_id, action, client_buffer_ids = [], extend = false, latency_ms }) {
  const result = await callApi('POST', `/analysis/sessions/${session_id}/swipes/`, {
    canonical_bld_id:  image_id,
    action,
    idempotency_key:   `swp_${session_id}_${image_id}`,
    client_buffer_ids: client_buffer_ids,
    ...(extend ? { extend: true } : {}),
    ...(latency_ms != null ? { latency_ms } : {}),
  })
  return {
    ...result,
    next_image:       normalizeCard(result.next_image),
    prefetch_image:   normalizeCard(result.prefetch_image),
    prefetch_image_2: normalizeCard(result.prefetch_image_2),
    question_trigger: result.question_trigger ?? null,
  }
}

/**
 * Parse a natural-language query using Gemini on the backend.
 * Backwards-compatible:
 *   parseQuery('hello')                     -> POST { query: 'hello' }               (legacy single-turn)
 *   parseQuery([{role:'user', text:'..'}])  -> POST { conversation_history: [...] }  (multi-turn)
 *
 * Optional second argument (options object):
 *   prior_filters   {object}  — merged into the current parse so context is not lost
 *   priority_axis   {string}  — when present, triggers a deterministic re-rank (no LLM)
 *                               that boosts the given axis to rank 0 while keeping prior_filters
 *   raw_query       {string}  — original user query string forwarded to the re-rank path
 *
 * Response (probe_needed=true):  { probe_needed: true, probe_question, reply, results: [] }
 * Response (probe_needed=false): { reply, structured_filters, filter_priority, suggestions, results: [ImageCard] }
 * Response (priority_axis set):  deterministic re-rank — { results, structured_filters, suggested_quick_replies, ... }
 */
export async function parseQuery(input, { prior_filters, priority_axis, raw_query } = {}) {
  const body = typeof input === 'string'
    ? { query: input }
    : { conversation_history: input }

  if (prior_filters && Object.keys(prior_filters).length > 0) {
    body.prior_filters = prior_filters
  }
  if (priority_axis) {
    body.priority_axis = priority_axis
  }
  if (raw_query) {
    body.raw_query = raw_query
  }

  const result = await callApi('POST', '/parse-query/', body, true, PARSE_QUERY_TIMEOUT_MS)
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

/**
 * Submit a user's response to an in-session question card.
 * option: "A" | "B" | "skip"
 * keyword: the keyword field from the question_trigger (or null)
 *
 * On flush_prefetch=true the response includes next_image / prefetch_image /
 * prefetch_image_2 which are normalized so callers can update the deck directly.
 */
export async function submitQuestionResponse({ session_id, question_type, axis, keyword, selected_option }) {
  const result = await callApi('POST', `/analysis/sessions/${session_id}/question-responses/`, {
    question_type,
    axis,
    keyword: keyword ?? null,
    selected_option,
  })
  return {
    ...result,
    next_image:       normalizeCard(result.next_image),
    prefetch_image:   normalizeCard(result.prefetch_image),
    prefetch_image_2: normalizeCard(result.prefetch_image_2),
  }
}
