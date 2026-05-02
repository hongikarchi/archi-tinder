/**
 * api/core.js
 * Core JWT token management, fetch infrastructure, and callApi.
 * All other api/* modules import callApi + token helpers from here.
 */

export const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1'

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

export function _fetchWithTimeout(url, options, timeoutMs = FETCH_TIMEOUT_MS) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(timer))
}

// -- Token refresh (internal) ----------------------------------------------

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

// -- Core fetch helper -----------------------------------------------------

export async function callApi(method, path, body, retry = true) {
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
