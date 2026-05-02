/**
 * api/auth.js
 * Authentication: social login, dev login, logout.
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
