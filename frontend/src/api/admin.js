/**
 * api/admin.js
 * ADMIN-DASH-1 — operator dashboard API (GET) + ADMIN-DASH-2a provider note (PATCH). Gated
 * server-side by IsAdminOperator (401 anon / 403 non-admin). The frontend
 * `is_admin` redirect is UX only; the backend is the real gate.
 */

import { callApi } from './core.js'

const BASE_PATH = '/admin/dashboard'

/** @returns {Promise<{backend: object, github: object}>} */
export async function getAdminVersion() {
  return callApi('GET', `${BASE_PATH}/version/`)
}

/** @returns {Promise<{count: number, unapplied: string[]}>} */
export async function getAdminMigrations() {
  return callApi('GET', `${BASE_PATH}/migrations/`)
}

/** @returns {Promise<{flags: Array<{key: string, label_ko: string, description_ko: string, value: boolean|string}>}>} */
export async function getAdminFlags() {
  return callApi('GET', `${BASE_PATH}/flags/`)
}

/** @returns {Promise<{users: object|null, works: object|null, reports: object|null, sessions: object|null, buildings: object|null}>} */
export async function getAdminStats() {
  return callApi('GET', `${BASE_PATH}/stats/`)
}

/**
 * @param {{ page?: number, pageSize?: number }} opts
 * @returns {Promise<{results: object[], count: number}>}
 */
export async function getAdminAuditLog({ page = 1, pageSize = 50 } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  return callApi('GET', `${BASE_PATH}/audit-log/?${params.toString()}`)
}

/**
 * ADMIN-DASH-2a — external service status / usage / login memo.
 * Server caches the external part (10 min); `refresh` appends ?refresh=1 to bust it.
 * @param {{ refresh?: boolean }} opts
 * @returns {Promise<{services: object[], fetched_at: string}>}
 */
export async function getAdminServices({ refresh = false } = {}) {
  return callApi('GET', `${BASE_PATH}/services/${refresh ? '?refresh=1' : ''}`)
}

/**
 * Update the operator's free-text login memo for one provider (max 200 chars).
 * @param {string} slug
 * @param {string} loginNote
 * @returns {Promise<{slug: string, login_note: string, updated_at: string}>}
 */
export async function updateProviderNote(slug, loginNote) {
  return callApi('PATCH', `${BASE_PATH}/services/${encodeURIComponent(slug)}/note/`, { login_note: loginNote })
}
