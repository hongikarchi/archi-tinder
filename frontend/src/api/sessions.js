/**
 * api/sessions.js
 * Analysis session lifecycle: start, resume, swipe, query parse, results.
 */

import { callApi, getToken, BASE } from './core.js'
import { createSseParser } from './sse.js'
import { normalizeCard } from './images.js'
import { VerifyRequiredError } from './projects.js'

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
  try {
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
  } catch (err) {
    if (err?.status === 403 && err?.data?.detail === 'verify_required') {
      const reason = err?.data?.reason || 'board_limit_reached'
      window.dispatchEvent(new CustomEvent('archithon:verify-required', { detail: { reason } }))
      throw new VerifyRequiredError(reason)
    }
    throw err
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
 */
export async function recordSwipe({ session_id, image_id, action, client_buffer_ids = [], extend = false }) {
  const result = await callApi('POST', `/analysis/sessions/${session_id}/swipes/`, {
    canonical_bld_id:  image_id,
    action,
    idempotency_key:   `swp_${session_id}_${image_id}`,
    client_buffer_ids: client_buffer_ids,
    ...(extend ? { extend: true } : {}),
  })
  return {
    ...result,
    next_image:       normalizeCard(result.next_image),
    prefetch_image:   normalizeCard(result.prefetch_image),
    prefetch_image_2: normalizeCard(result.prefetch_image_2),
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
export async function parseQuery(input, opts = {}) {
  const body = _buildParseQueryBody(input, opts)
  const result = await callApi('POST', '/parse-query/', body, true, PARSE_QUERY_TIMEOUT_MS)
  return _normalizeParsed(result)
}

function _buildParseQueryBody(input, { prior_filters, priority_axis, raw_query } = {}) {
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
  return body
}

function _normalizeParsed(result) {
  return {
    ...result,
    results: (result.results || []).map(normalizeCard),
  }
}

function _safeCall(fn, arg) {
  if (typeof fn !== 'function') return
  try { fn(arg) } catch { /* UI callback errors must never break the stream */ }
}

// Marker for stream failures where retrying via the blocking endpoint is safe
// (no LLM result was lost / the blocking path owns the recovery flow).
class StreamFallbackError extends Error {}

/**
 * Consume POST /parse-query/stream/ (SSE over fetch + ReadableStream).
 * Resolves with the raw `final` payload.
 *
 * Failure handling (the caller falls back to the blocking parseQuery() ONLY for
 * StreamFallbackError, so the LLM is never run twice for a result we already
 * paid for):
 *   - 401                                   -> StreamFallbackError (blocking call runs the token refresh flow)
 *   - fetch/network failure before a response, missing stream support,
 *     network break / EOF before `final`   -> StreamFallbackError
 *   - 400 / 403 / 429 / other non-200       -> same error shape as callApi (`status`, `data`)
 *   - server `error` event / bad payload    -> Error with `status` 500, `data`
 *   - timeout (abort)                       -> the AbortError, like the blocking call
 */
async function _streamParseQuery(body, { onReply, onFilters, onResults } = {}) {
  const token = getToken()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), PARSE_QUERY_TIMEOUT_MS)
  let reader = null
  try {
    let res
    try {
      res = await fetch(`${BASE}/parse-query/stream/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
    } catch (err) {
      if (controller.signal.aborted) throw err // timeout: surface, do not re-run
      throw new StreamFallbackError('stream network failure')
    }

    if (res.status === 401) throw new StreamFallbackError('stream 401')
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw Object.assign(new Error(data.detail || data.message || 'API error'), { status: res.status, data })
    }
    if (!res.body || typeof res.body.getReader !== 'function') {
      throw new StreamFallbackError('stream unsupported')
    }

    let final = null
    let serverError = null
    const parser = createSseParser((event, data) => {
      let payload
      try { payload = JSON.parse(data) } catch {
        serverError = { detail: 'Malformed stream payload' }
        return
      }
      if (event === 'reply') _safeCall(onReply, payload?.text || '')
      else if (event === 'filters') _safeCall(onFilters, payload)
      else if (event === 'results') {
        // Speculative early cards (OpenAI streaming path only); `final.results`
        // stays authoritative. Normalized exactly like the final payload.
        _safeCall(onResults, {
          results: (payload?.results || []).map(normalizeCard),
          is_fallback: Boolean(payload?.is_fallback),
          fallback_note: payload?.fallback_note || '',
        })
      }
      else if (event === 'final') final = payload
      else if (event === 'error') serverError = payload || {}
    })

    reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    try {
      while (!final && !serverError) {
        const { done, value } = await reader.read()
        if (done) break
        parser.push(decoder.decode(value, { stream: true }))
      }
      if (!final && !serverError) {
        parser.push(decoder.decode())
        parser.flush()
      }
    } catch (err) {
      if (controller.signal.aborted) throw err // timeout: surface, do not re-run
      throw new StreamFallbackError('stream broke before final')
    }

    if (final) return final
    if (serverError) {
      throw Object.assign(
        new Error(serverError.detail || 'Search stream failed'),
        { status: 500, data: serverError },
      )
    }
    throw new StreamFallbackError('stream ended without final')
  } finally {
    clearTimeout(timer)
    if (reader) reader.cancel().catch(() => {})
  }
}

/**
 * Streaming variant of parseQuery. Same input/options and SAME resolved shape
 * as parseQuery(); additionally reports progress through callbacks:
 *   onReply(textDelta)   -- incremental reply text (concatenation == final.reply)
 *   onFilters({structured_filters, filter_priority}) -- once, before `final`
 *   onResults({results, is_fallback, fallback_note}) -- at most once, right after
 *                           `filters` and before any reply text (OpenAI stream path
 *                           only). SPECULATIVE: the resolved `final.results` is
 *                           authoritative and may differ.
 *   onFallback()         -- the blocking parse-query call is about to run, so the
 *                           caller should discard any partially streamed text
 * Falls back to parseQuery() only on 401 (token refresh), network failure /
 * missing stream support, or a network break before `final`. HTTP errors
 * (400/403/429/...), server `error` events and timeouts are thrown with the same
 * shape as parseQuery() errors, without a second LLM call. Priority-axis
 * re-rank requests (single `final`, no LLM) skip streaming entirely.
 */
export async function parseQueryStream(input, opts = {}, callbacks = {}) {
  const canStream = !opts.priority_axis
    && typeof fetch === 'function'
    && typeof ReadableStream !== 'undefined'
    && typeof TextDecoder !== 'undefined'
  if (canStream) {
    try {
      const final = await _streamParseQuery(_buildParseQueryBody(input, opts), callbacks)
      return _normalizeParsed(final)
    } catch (err) {
      if (!(err instanceof StreamFallbackError)) throw err
      _safeCall(callbacks.onFallback)
    }
  }
  return parseQuery(input, opts)
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
