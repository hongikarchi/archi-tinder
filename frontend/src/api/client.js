/**
 * api/client.js
 * Calls the real backend API, falls back to localSession if backend is unreachable.
 * Base URL: VITE_API_BASE_URL (default: http://localhost:8001/api/v1)
 */
import * as local from './localSession.js'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1'

const isLocalSession = id => id?.startsWith('sess_local_')

async function callApi(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw Object.assign(new Error(err.message || 'API error'), { status: res.status, data: err })
  }
  return res.json()
}

// ── Analysis Sessions ────────────────────────────────────────────────────────

/**
 * Start an analysis session.
 * If preloaded_images are provided, use local session directly.
 * Falls back to localSession on network error.
 */
export async function startSession(params) {
  if (params.preloaded_images?.length > 0) {
    return local.startSession(params)
  }
  try {
    return await callApi('POST', '/analysis/sessions', {
      user_id: params.user_id,
      project_id: params.project_id,
      is_new_project: params.is_new_project,
      filter_mode: params.filter_mode || 'keep',
      analysis_options: params.analysis_options,
    })
  } catch (err) {
    console.error('[api/client] startSession failed, using local fallback:', err)
    return local.startSession(params)
  }
}

/**
 * Record a swipe action → receive next_image.
 * Uses localSession for local sessions.
 */
export async function recordSwipe({ session_id, user_id, project_id, image_id, action, swiped_image_ids }) {
  if (isLocalSession(session_id)) {
    return local.recordSwipe({ session_id, image_id, action })
  }
  try {
    return await callApi('POST', `/analysis/sessions/${session_id}/swipes`, {
      user_id,
      project_id,
      image_id,
      action,
      swiped_image_ids,
      timestamp: new Date().toISOString(),
      idempotency_key: `swp_${Date.now()}`,
    })
  } catch (err) {
    console.error('[api/client] recordSwipe failed, using local fallback:', err)
    return local.recordSwipe({ session_id, image_id, action })
  }
}

/**
 * Fetch final session results.
 */
export async function getResult({ session_id, user_id, project_id }) {
  if (isLocalSession(session_id)) {
    return local.getResult({ session_id })
  }
  try {
    const params = new URLSearchParams({ user_id, project_id })
    return await callApi('GET', `/analysis/sessions/${session_id}/result?${params}`)
  } catch (err) {
    console.error('[api/client] getResult failed, using local fallback:', err)
    return local.getResult({ session_id })
  }
}
