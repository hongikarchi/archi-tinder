/**
 * api/profiles.js
 * User profile fetching.
 */

import { callApi, BASE, getToken } from './core.js'

export async function getUserProfile(userId, { boardsPage, boardsPageSize } = {}) {
  const params = new URLSearchParams()
  if (boardsPage != null) params.set('boards_page', boardsPage)
  if (boardsPageSize != null) params.set('boards_page_size', boardsPageSize)
  const qs = params.toString()
  return await callApi('GET', `/users/${userId}/${qs ? `?${qs}` : ''}`)
}

export async function updateMyProfile(patch) {
  return await callApi('PATCH', '/users/me/', patch)
}

/**
 * uploadAvatar — POST multipart/form-data to /users/me/avatar/
 * Cannot use callApi (JSON-only). Builds FormData and sends with fetch directly.
 * On success returns the updated UserSerializer shape (with new avatar_url).
 * On 401, surfaces session-expired event (consistent with core.js behaviour).
 * Note: single-attempt 401 refresh not wired (deferred for v1).
 */
export async function uploadAvatar(fileOrBlob) {
  const fd = new FormData()
  fd.append('avatar', fileOrBlob, 'avatar.webp')

  const token = getToken()
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  // Do NOT set Content-Type — browser must set it with the multipart boundary.

  const res = await fetch(`${BASE}/users/me/avatar/`, {
    method: 'POST',
    headers,
    body: fd,
  })

  if (res.status === 401) {
    window.dispatchEvent(new CustomEvent('archithon:session-expired'))
    throw Object.assign(new Error('Session expired'), { status: 401 })
  }

  if (!res.ok) {
    let detail = 'Upload failed'
    try {
      const data = await res.json()
      if (data.detail) detail = data.detail
    } catch { /* ignore parse failure */ }
    throw Object.assign(new Error(detail), { status: res.status })
  }

  return res.json()
}
