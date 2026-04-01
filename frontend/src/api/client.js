/**
 * api/client.js
 * Calls the real backend API with JWT auth.
 * Base URL: VITE_API_BASE_URL (default: http://localhost:8001/api/v1)
 */

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1'

// ── API call tracker (for DebugOverlay) ───────────────────────────────────────

let _lastCall = null
export function getLastCall() { return _lastCall }

// ── JWT token storage ─────────────────────────────────────────────────────────

export function getToken()         { return localStorage.getItem('archithon_access') }
export function setTokens(access, refresh) {
  localStorage.setItem('archithon_access',  access)
  localStorage.setItem('archithon_refresh', refresh)
}
export function clearTokens() {
  localStorage.removeItem('archithon_access')
  localStorage.removeItem('archithon_refresh')
}

// ── Core fetch helper ─────────────────────────────────────────────────────────

async function callApi(method, path, body, retry = true) {
  const t0 = Date.now()
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })

  _lastCall = { method, url: path, status: res.status, ms: Date.now() - t0 }

  // Auto-refresh on 401 (once)
  if (res.status === 401 && retry) {
    const refreshed = await _tryRefresh()
    if (refreshed) return callApi(method, path, body, false)
    clearTokens()
    // Notify App to log out — avoids circular imports
    window.dispatchEvent(new CustomEvent('archithon:session-expired'))
    throw Object.assign(new Error('Session expired'), { status: 401 })
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw Object.assign(new Error(err.detail || err.message || 'API error'), { status: res.status, data: err })
  }
  if (res.status === 204) return null
  return res.json()
}

async function _tryRefresh() {
  const refresh = localStorage.getItem('archithon_refresh')
  if (!refresh) return false
  try {
    const res = await fetch(`${BASE}/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })
    if (!res.ok) return false
    const data = await res.json()
    localStorage.setItem('archithon_access', data.access)
    if (data.refresh) {
      localStorage.setItem('archithon_refresh', data.refresh)
    }
    return true
  } catch {
    return false
  }
}

// ── ImageCard normalizer ──────────────────────────────────────────────────────
// Maps backend field names (spec) -> frontend field names used in components.
// Components use: image_id, image_title, image_url, gallery, metadata.*

export function normalizeCard(card) {
  if (!card) return null

  // Handle action cards
  if (card.building_id === '__action_card__' || card.card_type === 'action') {
    return {
      image_id: '__action_card__',
      card_type: 'action',
      action_card_message: card.action_card_message || 'Your taste profile is ready!',
      image_title: card.name_en || 'Analysis Complete',
      image_url: '',
      source_url: null,
      gallery: [],
      metadata: {},
    }
  }

  // Already normalized
  if (card.image_id) return card

  return {
    image_id:    card.building_id,
    card_type:   'building',
    image_title: card.name_en || card.project_name,
    image_url:   card.image_url,
    source_url:  card.url || null,
    gallery:     card.gallery || [],
    metadata: {
      axis_typology:   card.metadata?.axis_typology   ?? card.program   ?? null,
      axis_architects: card.metadata?.axis_architects ?? card.architect  ?? null,
      axis_country:    card.metadata?.axis_country    ?? card.location_country ?? null,
      axis_area_m2:    card.metadata?.axis_area_m2    ?? card.area_sqm  ?? null,
      axis_year:       card.metadata?.axis_year       ?? card.year      ?? null,
      axis_style:          card.metadata?.axis_style          ?? card.style          ?? null,
      axis_atmosphere:     card.metadata?.axis_atmosphere     ?? card.atmosphere     ?? null,
      axis_color_tone:     card.metadata?.axis_color_tone     ?? card.color_tone     ?? null,
      axis_material_visual: card.metadata?.axis_material_visual ?? card.material_visual ?? [],
      axis_material:   card.metadata?.axis_material   ?? card.material  ?? null,
      axis_tags:       card.metadata?.axis_tags       ?? card.tags      ?? [],
    },
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────

/**
 * Exchange a provider access_token for a backend JWT.
 * provider: 'google' | 'kakao' | 'naver'
 * Returns: { access, refresh, user }
 */
export async function socialLogin(provider, accessToken) {
  const data = await callApi('POST', `/auth/social/${provider}/`, { access_token: accessToken }, false)
  setTokens(data.access, data.refresh)
  return data.user
}

export async function devLogin(secret) {
  const res = await fetch(`${BASE}/auth/dev-login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ secret }),
  })
  if (!res.ok) throw new Error(`Dev login failed: ${res.status}`)
  const data = await res.json()
  setTokens(data.access, data.refresh)
  return data.user
}

export async function logout(refreshToken) {
  try {
    await callApi('POST', '/auth/logout/', { refresh: refreshToken }, false)
  } catch (err) {
    console.error('[api/client] logout error (ignoring):', err)
  }
  clearTokens()
}

// ── Analysis Sessions ────────────────────────────────────────────────────────

/**
 * Start an analysis session.
 * params.filter_priority and params.seed_ids are forwarded to the backend
 * for weighted scoring pool creation.
 */
export async function startSession(params) {
  const result = await callApi('POST', '/analysis/sessions/', {
    project_id:      params.project_id,
    filters:         params.filters || {},
    filter_priority: params.filter_priority || [],
    seed_ids:        params.seed_ids || [],
  })
  return {
    ...result,
    next_image:     normalizeCard(result.next_image),
    prefetch_image: normalizeCard(result.prefetch_image),
  }
}

/**
 * Record a swipe action -> receive next_image.
 */
export async function recordSwipe({ session_id, image_id, action }) {
  const result = await callApi('POST', `/analysis/sessions/${session_id}/swipes/`, {
    building_id:      image_id,
    action,
    idempotency_key:  `swp_${session_id}_${image_id}`,
  })
  return {
    ...result,
    next_image:     normalizeCard(result.next_image),
    prefetch_image: normalizeCard(result.prefetch_image),
  }
}

/**
 * Parse a natural-language query using Gemini on the backend.
 * Returns { reply, structured_filters, filter_priority, suggestions, results: [ImageCard] }
 */
export async function parseQuery(query) {
  const result = await callApi('POST', '/parse-query/', { query })
  return {
    ...result,
    results: (result.results || []).map(normalizeCard),
  }
}

// ── Projects ──────────────────────────────────────────────────────────────────

export async function listProjects(page = 1, pageSize = 50) {
  try {
    const data = await callApi('GET', `/projects/?page=${page}&page_size=${pageSize}`)
    // Support both paginated {results, has_more} and legacy plain array
    if (Array.isArray(data)) return { results: data, has_more: false, total: data.length }
    return data
  } catch (err) {
    console.error('[api/client] listProjects failed:', err)
    return { results: [], has_more: false, total: 0 }
  }
}

export async function deleteProject(projectId) {
  try {
    await callApi('DELETE', `/projects/${projectId}/`)
  } catch (err) {
    console.error('[api/client] deleteProject failed:', err)
  }
}

export async function generateReport(projectId) {
  return callApi('POST', `/projects/${projectId}/report/generate/`)
}

/**
 * Batch-fetch building cards by IDs.
 * Returns list of normalized ImageCard objects.
 */
export async function getBuildings(buildingIds) {
  if (!buildingIds?.length) return []
  try {
    const result = await callApi('POST', '/images/batch/', { building_ids: buildingIds })
    return (result || []).map(normalizeCard)
  } catch (err) {
    console.error('[api/client] getBuildings failed:', err)
    return []
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
    predicted_like_images:  (result.predicted_images || result.predicted_like_images || []).map(normalizeCard),
  }
}
