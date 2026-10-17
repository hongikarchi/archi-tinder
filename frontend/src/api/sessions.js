/**
 * api/sessions.js
 * Analysis session lifecycle: start, resume, swipe, results.
 */

import { callApi } from './core.js'
import { normalizeCard } from './images.js'
import { VerifyRequiredError } from './projects.js'

const SESSION_CREATE_TIMEOUT_MS = 30000 // Cold pool path: execute_pool_sql ~14.7s, total backend time can exceed 15s default

/**
 * Start an analysis session.
 */
export async function startSession(params) {
  try {
    const result = await callApi('POST', '/analysis/sessions/', {
      project_id:      params.project_id,
      name:            params.name || 'Untitled',
      filters:         params.filters || {},
      raw_query:       params.raw_query || '',
      ...(params.force_new ? { force_new: true } : {}),
      // Taste-start v2 body: tags are sent back exactly as the server returned them.
      ...(params.taste_tags ? { taste_tags: params.taste_tags } : {}),
      ...(params.start_ids?.length ? { start_ids: params.start_ids } : {}),
      ...(params.exclude_ids?.length ? { exclude_ids: params.exclude_ids } : {}),
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
// PERF-MISC-1(f): the result endpoint is hit by goToResults (App.jsx) AND the
// useResults mount effect (plus StrictMode's double effect) for one arrival, and
// the backend persists provenance fields on every call. Share one in-flight
// request per session id, and keep the settled promise a few seconds so a lazy
// ResultsPage chunk that mounts just after goToResults resolved reuses it too.
// Failures are evicted immediately so retries re-fetch.
const _RESULT_REUSE_MS = 4000
const _resultInflight = new Map()

export function _resetResultCache() { _resultInflight.clear() }

async function _fetchResult(session_id) {
  const result = await callApi('GET', `/analysis/sessions/${session_id}/result/`)
  return {
    ...result,
    liked_images:           (result.liked_images || []).map(normalizeCard),
    predicted_like_images:  (result.predicted_images || []).map(normalizeCard),
  }
}

/**
 * Fetch final session results (deduped per session id, see above).
 */
export function getResult({ session_id }) {
  const hit = _resultInflight.get(session_id)
  if (hit) return hit.promise
  const promise = _fetchResult(session_id)
  const entry = { promise }
  _resultInflight.set(session_id, entry)
  promise.then(
    () => {
      setTimeout(() => {
        if (_resultInflight.get(session_id) === entry) _resultInflight.delete(session_id)
      }, _RESULT_REUSE_MS)
    },
    () => {
      if (_resultInflight.get(session_id) === entry) _resultInflight.delete(session_id)
    },
  )
  return promise
}
