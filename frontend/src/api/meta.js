/**
 * api/meta.js
 * Public metadata endpoints (no auth). SETTINGS-POLISH-1.
 */

import { callApi } from './core.js'
import { ROLES } from '../constants/roles.js'

// Module-level promise memo — fetch once per session (page load).
// On failure resolves to the bundled fallback constant instead of rejecting,
// so callers never need a try/catch around getRoles().
let _rolesPromise = null

/**
 * getRoles() — GET /api/v1/meta/roles/
 * Returns a Promise<Array<{value, label_en, label_ko}>>.
 * Memoized at module scope: the network request fires at most once per
 * session; subsequent calls reuse the same settled promise.
 * Falls back to the bundled ROLES constant on any fetch/parse failure.
 */
export function getRoles() {
  if (!_rolesPromise) {
    _rolesPromise = callApi('GET', '/meta/roles/')
      .then(data => (Array.isArray(data?.roles) && data.roles.length ? data.roles : ROLES))
      .catch(() => ROLES)
  }
  return _rolesPromise
}
