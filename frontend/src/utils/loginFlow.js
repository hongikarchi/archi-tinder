/**
 * utils/loginFlow.js
 * Guest onboarding utilities.
 * No literal fallback client-id strings anywhere in this file.
 */

import { ROLES } from '../constants/roles.js'

// SETTINGS-POLISH-1: re-exported from constants/roles.js (bundled fallback,
// mirrors backend ONBOARDING_ROLE_CHOICES — 5 entries). Export name kept for
// backward compatibility with existing imports (isRoleReady, tests, etc).
// Live callers should prefer api/meta.js getRoles() to pick up backend-added
// roles without a frontend redeploy; this constant is the fallback + the
// value used for validation (isRoleReady), which only needs the `value` set.
export const ONBOARDING_ROLES = ROLES

export const LOGIN_SWIPE_ACTIONS = { left: 'returning', right: 'new' }

export function getLoginSwipeAction(direction) {
  return LOGIN_SWIPE_ACTIONS[direction] || null
}

/**
 * Client-side mirror of backend unified ID validator.
 * Allowed: Hangul + ASCII letters + digits + underscore.
 * No spaces. 2-20 characters after NFC normalization.
 */
export function isIdFormatValid(value) {
  if (typeof value !== 'string') return false
  const nfc = value.normalize('NFC')
  if (nfc.length < 2 || nfc.length > 20) return false
  // Must stay in sync with backend _HANDLE_RE in serializers.py.
  // Hangul syllables (AC00-D7A3) + Hangul Jamo (1100-11FF)
  // + Hangul Jamo Extended-A (A960-A97F) + Hangul Jamo Extended-B (D7B0-D7FF)
  // + ASCII letters + digits + underscore. No whitespace, no other characters.
  return /^[가-힣ᄀ-ᇿꥠ-꥿ힰ-퟿a-zA-Z0-9_]+$/.test(nfc)
}

// Kept for backward compatibility with test suite.
export function isDisplayNameReady(value) {
  return typeof value === 'string' && value.trim().length > 0
}

export function isRoleReady(value) {
  return ONBOARDING_ROLES.some(role => role.value === value)
}

/**
 * Validate the new unified flow: id must be format-valid, objective required.
 * Affiliation is optional.
 */
export function isGuestProfileReady(profile = {}) {
  // New shape: { id, role } — also accepts legacy { displayName, role } for tests
  const idOk = isIdFormatValid(profile.id) || isDisplayNameReady(profile.displayName)
  return idOk && isRoleReady(profile.role)
}

/**
 * Normalize a user-supplied display name.
 * - Trims whitespace.
 * - Defaults to 'Guest' if blank or non-string.
 * - Caps at 30 characters.
 * Kept for test compatibility.
 */
export function normalizeGuestName(value) {
  if (typeof value !== 'string') return 'Guest'
  const stripped = value.trim()
  if (!stripped) return 'Guest'
  return stripped.slice(0, 30)
}

/**
 * Build the POST /auth/guest/ body.
 * Kept for test compatibility (not called from new flow — new flow uses register()).
 */
export function buildGuestLoginPayload({ displayName, role, jobRole, affiliation }) {
  const payload = {
    display_name: normalizeGuestName(displayName),
    onboarding_role: role || '',
    consent_accepted: true,
    consent_policy_version: '1.0',
  }
  if (jobRole && jobRole.trim()) payload.role = jobRole.trim().slice(0, 50)
  if (affiliation && affiliation.trim()) payload.affiliation = affiliation.trim().slice(0, 100)
  return payload
}

/**
 * Returns true if a Google Client ID is configured, false otherwise.
 * Never returns a literal fallback string — returns null/false on empty input.
 */
export function hasGoogleLogin(clientId) {
  if (!clientId || typeof clientId !== 'string') return false
  return clientId.trim().length > 0
}
