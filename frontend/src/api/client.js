/**
 * api/client.js
 * Calls the real backend API with JWT auth.
 * Base URL: VITE_API_BASE_URL (default: http://localhost:8001/api/v1)
 */

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1'

const FETCH_TIMEOUT_MS = 10000          // 10-second timeout for all fetch calls
const MAX_NETWORK_RETRIES = 2           // retry count for network failures
const BACKOFF_BASE_MS = 300             // exponential backoff base (300ms, 900ms)

// -- API call tracker (for DebugOverlay) -----------------------------------

let _lastCall = null
export function getLastCall() { return _lastCall }

// -- JWT token storage -----------------------------------------------------

export function getToken()         { return localStorage.getItem('archithon_access') }
export function setTokens(access, refresh) {
  localStorage.setItem('archithon_access',  access)
  localStorage.setItem('archithon_refresh', refresh)
}
export function clearTokens() {
  localStorage.removeItem('archithon_access')
  localStorage.removeItem('archithon_refresh')
}

// -- Network error detection -----------------------------------------------

function _isNetworkError(err) {
  if (err instanceof TypeError) return true                // fetch network failure
  if (err.name === 'AbortError') return true               // timeout abort
  return false
}

// -- Fetch with timeout ----------------------------------------------------

function _fetchWithTimeout(url, options, timeoutMs = FETCH_TIMEOUT_MS) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(timer))
}

// -- Core fetch helper -----------------------------------------------------

async function callApi(method, path, body, retry = true) {
  const t0 = Date.now()
  const token = getToken()
  const fetchOptions = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  }

  let res
  let lastNetworkErr

  // Attempt fetch with network-level retries (not for HTTP error responses)
  for (let attempt = 0; attempt <= MAX_NETWORK_RETRIES; attempt++) {
    try {
      res = await _fetchWithTimeout(`${BASE}${path}`, fetchOptions)
      lastNetworkErr = null
      break
    } catch (err) {
      if (_isNetworkError(err) && attempt < MAX_NETWORK_RETRIES) {
        lastNetworkErr = err
        const delay = BACKOFF_BASE_MS * Math.pow(3, attempt)  // 300ms, 900ms
        await new Promise(r => setTimeout(r, delay))
        continue
      }
      // Non-network error or exhausted retries
      _lastCall = { method, url: path, status: 0, ms: Date.now() - t0 }
      throw err
    }
  }

  // If all retries failed with network errors, throw the last one
  if (!res) {
    _lastCall = { method, url: path, status: 0, ms: Date.now() - t0 }
    throw lastNetworkErr
  }

  _lastCall = { method, url: path, status: res.status, ms: Date.now() - t0 }

  // Auto-refresh on 401 (once)
  if (res.status === 401 && retry) {
    const refreshed = await _tryRefresh()
    if (refreshed) return callApi(method, path, body, false)
    clearTokens()
    // Notify App to log out -- avoids circular imports
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
    const res = await _fetchWithTimeout(`${BASE}/auth/token/refresh/`, {
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

// -- ImageCard normalizer --------------------------------------------------
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
      action_card_subtitle: card.action_card_subtitle || null,
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
    gallery_drawing_start: card.gallery_drawing_start ?? card.metadata?.gallery_drawing_start ?? null,
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

// -- Auth ------------------------------------------------------------------

/**
 * Exchange a provider access_token (or auth code) for a backend JWT.
 * provider: 'google' | 'kakao' | 'naver'
 * accessToken: OAuth access_token (implicit flow) -- may be null for auth-code flow
 * code: authorization code (auth-code flow) -- used when accessToken is null
 * Returns: { access, refresh, user }
 */
export async function socialLogin(provider, accessToken, code) {
  clearTokens()  // Remove stale tokens so callApi doesn't send an invalid Authorization header
  const body = {}
  if (accessToken) body.access_token = accessToken
  if (code) body.code = code
  const data = await callApi('POST', `/auth/social/${provider}/`, body, false)
  setTokens(data.access, data.refresh)
  return data.user
}

export async function devLogin(secret) {
  const res = await _fetchWithTimeout(`${BASE}/auth/dev-login/`, {
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

// -- Analysis Sessions -----------------------------------------------------

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

// -- Projects --------------------------------------------------------------

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

export async function generateReportImage(projectId) {
  return callApi('POST', `/projects/${projectId}/report/generate-image/`)
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
    predicted_like_images:  (result.predicted_images || []).map(normalizeCard),
  }
}

/**
 * Toggle bookmark (⭐) on a result-page card.
 * @param {string} projectId - backend project UUID
 * @param {string} cardId - building_id
 * @param {'save'|'unsave'} action
 * @param {number} rank - 1-indexed position in result page (1-50)
 * @param {string|null} sessionId - optional, for event association
 * @returns {Promise<{saved_ids: string[], count: number}>}
 */
export async function bookmarkBuilding(projectId, cardId, action, rank, sessionId = null) {
  return callApi('POST', `/projects/${projectId}/bookmark/`, {
    card_id: cardId,
    action,
    rank,
    ...(sessionId ? { session_id: sessionId } : {}),
  })
}

// -- Profiles --------------------------------------------------------------

export async function getOffice(officeId) {
  return await callApi('GET', `/offices/${officeId}/`)
}

export async function getUserProfile(userId) {
  return await callApi('GET', `/users/${userId}/`)
}
