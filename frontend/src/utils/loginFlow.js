/**
 * utils/loginFlow.js
 * Guest onboarding utilities.
 * No literal fallback client-id strings anywhere in this file.
 */

export const ONBOARDING_ROLES = [
  { value: 'student',     label: 'Student' },
  { value: 'architect',   label: 'Architect' },
  { value: 'other',       label: 'Just exploring' },
]

export const LOGIN_SWIPE_ACTIONS = { left: 'returning', right: 'new' }

export function getLoginSwipeAction(direction) {
  return LOGIN_SWIPE_ACTIONS[direction] || null
}

export function isDisplayNameReady(value) {
  return typeof value === 'string' && value.trim().length > 0
}

export function isRoleReady(value) {
  return ONBOARDING_ROLES.some(role => role.value === value)
}

export function isGuestProfileReady(profile = {}) {
  return isDisplayNameReady(profile.displayName) && isRoleReady(profile.role)
}

/**
 * Normalize a user-supplied display name.
 * - Trims whitespace.
 * - Defaults to 'Guest' if blank or non-string.
 * - Caps at 30 characters.
 */
export function normalizeGuestName(value) {
  if (typeof value !== 'string') return 'Guest'
  const stripped = value.trim()
  if (!stripped) return 'Guest'
  return stripped.slice(0, 30)
}

/**
 * Build the POST /auth/guest/ body.
 * Always includes consent_accepted: true (wizard flow structurally guarantees
 * the user has clicked "동의합니다" before this function is called).
 */
export function buildGuestLoginPayload({ displayName, role }) {
  return {
    display_name: normalizeGuestName(displayName),
    onboarding_role: role || '',
    consent_accepted: true,
    consent_policy_version: '1.0',
  }
}

/**
 * Returns true if a Google Client ID is configured, false otherwise.
 * Never returns a literal fallback string — returns null/false on empty input.
 */
export function hasGoogleLogin(clientId) {
  if (!clientId || typeof clientId !== 'string') return false
  return clientId.trim().length > 0
}
