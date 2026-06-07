/**
 * api/auth.js
 * Authentication: social login, guest login, promote, dev login, logout.
 */

import { callApi, clearTokens, setTokens, _fetchWithTimeout, BASE } from './core.js'

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

/**
 * Create a guest (unverified) account.
 * payload: { display_name, onboarding_role, consent_accepted: true, consent_policy_version }
 * Returns: user object (same shape as socialLogin)
 */
export async function guestLogin(payload) {
  clearTokens()
  const data = await callApi('POST', '/auth/guest/', payload, false)
  setTokens(data.access, data.refresh)
  return data.user
}

/**
 * Promote a guest account to a verified account via Google OAuth.
 * Must be called with a valid guest JWT already in localStorage.
 *
 * Body sent: { code } — the Google authorization code from the OAuth auth-code flow.
 * The 'provider' field defaults to 'google' on the backend; no need to send it.
 *
 * Returns: { access, refresh, user, promoted: true, merged: bool }
 *   merged: true  → guest deleted, tokens now belong to the existing verified account.
 *   merged: false → guest user in-place promoted (user_id preserved, is_guest: false).
 *
 * Error cases:
 *   400 + detail:'not_a_guest' → the account is already promoted (e.g. another tab
 *                                 completed the flow). Caller should treat as success.
 */
export async function promoteAccount(code) {
  // callApi automatically attaches the current access token as Authorization header
  const data = await callApi('POST', '/auth/promote/', { code }, false)
  // Swap to the new tokens issued for the (now-verified) user
  setTokens(data.access, data.refresh)
  return data
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

/**
 * Fetch the authenticated user's own profile (includes notifications, handle, etc.).
 * Returns the same UserSerializer shape as the login response.
 */
export async function getMe() {
  return await callApi('GET', '/auth/me/')
}

/**
 * Log in with handle + password.
 * Returns: user object (same shape as socialLogin).
 */
export async function login(handle, password) {
  clearTokens()
  const data = await callApi('POST', '/auth/login/', { handle, password }, false)
  setTokens(data.access, data.refresh)
  return data.user
}

/**
 * Register a new account with handle + password (+ optional display_name).
 * Returns: user object.
 */
export async function register(handle, password, displayName) {
  clearTokens()
  const body = { handle, password }
  if (displayName && displayName.trim()) body.display_name = displayName.trim()
  const data = await callApi('POST', '/auth/register/', body, false)
  setTokens(data.access, data.refresh)
  return data.user
}

/**
 * Set or change password (authenticated).
 * On success, the backend issues a NEW token pair (old sessions blacklisted).
 * ⚠️ MUST replace stored tokens from this response, else next refresh = silent logout.
 * Returns: user object.
 */
export async function setPassword(password, currentPassword) {
  const body = { password }
  if (currentPassword !== undefined && currentPassword !== null) {
    body.current_password = currentPassword
  }
  const data = await callApi('POST', '/auth/set-password/', body)
  // Token swap is mandatory — backend blacklists old refresh tokens.
  setTokens(data.access, data.refresh)
  return data.user
}

/**
 * Link a Google account to the current user (email verification).
 * provider: 'google', code: authorization code from auth-code flow.
 * Returns: UserSerializer object (no token pair — user stays logged in).
 */
export async function linkEmail(code) {
  return await callApi('POST', '/auth/link-email/', { provider: 'google', code })
}
