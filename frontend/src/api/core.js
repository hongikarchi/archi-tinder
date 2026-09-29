/**
 * api/core.js
 * Core JWT token management, fetch infrastructure, and callApi.
 * All other api/* modules import callApi + token helpers from here.
 */

// Optional chain: import.meta.env is always defined under Vite (identical
// behavior), but undefined under plain Node ESM (node --test) — lets test
// files import this module instead of skip-guarding (FRONT-UX-14-FIX).
export const BASE = import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8001/api/v1'

const FETCH_TIMEOUT_MS = 15000          // 15-second default timeout (per-call override available via callApi 5th param)
const MAX_NETWORK_RETRIES = 2           // retry count for network failures
const BACKOFF_BASE_MS = 300             // exponential backoff base (300ms, 900ms)

// -- Idempotency check -------------------------------------------------------
// Only GET/HEAD/OPTIONS are safe to retry on network failure. POST/PATCH/DELETE
// may trigger server-side side effects; retrying risks duplicates (P0 origin:
// /analysis/sessions/ POST timeout → retry → duplicate Project+Session+Board,
// Codex retest 2026-05-26).
const _IDEMPOTENT_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

// -- API call tracker (for DebugOverlay) -----------------------------------

const _CALL_HISTORY_SIZE = 8
const _callHistory = []
function _recordCall(entry) {
  _callHistory.push(entry)
  if (_callHistory.length > _CALL_HISTORY_SIZE) _callHistory.shift()
}
export function getLastCall() { return _callHistory[_callHistory.length - 1] || null }
export function getCallHistory() { return _callHistory.slice() }

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

// Single-flight refresh: concurrent 401s share one refresh call.
// Backend rotates+blacklists refresh tokens, so only one in-flight refresh is safe.
let _refreshPromise = null
let _sessionExpiredDispatched = false

async function _doRefresh() {
  // Reset the once-guard at the start of each new refresh cycle
  _sessionExpiredDispatched = false
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

// _tryRefresh is intentionally NOT async — no await before the assignment so
// concurrent callers all grab the same Promise before it settles.
function _tryRefresh() {
  if (_refreshPromise) return _refreshPromise
  _refreshPromise = _doRefresh().finally(() => { _refreshPromise = null })
  return _refreshPromise
}

// -- Core fetch helper -----------------------------------------------------

export async function callApi(method, path, body, retry = true, timeoutMs = FETCH_TIMEOUT_MS) {
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
      res = await _fetchWithTimeout(`${BASE}${path}`, fetchOptions, timeoutMs)
      lastNetworkErr = null
      break
    } catch (err) {
      // Only retry network errors on idempotent methods. POST/PATCH/DELETE may
      // have triggered a side effect on the server (the timeout aborts the
      // client wait but not the server work), and a retry causes duplicates.
      const canRetry = _IDEMPOTENT_METHODS.has(method) && _isNetworkError(err) && attempt < MAX_NETWORK_RETRIES
      if (canRetry) {
        lastNetworkErr = err
        const delay = BACKOFF_BASE_MS * Math.pow(3, attempt)  // 300ms, 900ms
        await new Promise(r => setTimeout(r, delay))
        continue
      }
      // Non-network error, exhausted retries, OR non-idempotent method
      _recordCall({ method, url: path, status: 0, ms: Date.now() - t0 })
      throw err
    }
  }

  // If all retries failed with network errors, throw the last one
  if (!res) {
    _recordCall({ method, url: path, status: 0, ms: Date.now() - t0 })
    throw lastNetworkErr
  }

  _recordCall({ method, url: path, status: res.status, ms: Date.now() - t0 })

  // Auto-refresh on 401 (once)
  if (res.status === 401 && retry) {
    const refreshed = await _tryRefresh()
    if (refreshed) return callApi(method, path, body, false, timeoutMs)
    clearTokens()
    // Notify App to log out -- avoids circular imports.
    // Once-guard: all concurrent callers share the same _tryRefresh() result;
    // dispatch session-expired exactly once per failed-refresh cycle.
    if (!_sessionExpiredDispatched) {
      _sessionExpiredDispatched = true
      window.dispatchEvent(new CustomEvent('archithon:session-expired'))
    }
    throw Object.assign(new Error('Session expired'), { status: 401 })
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw Object.assign(new Error(err.detail || err.message || 'API error'), { status: res.status, data: err })
  }
  if (res.status === 204) return null
  return res.json()
}
