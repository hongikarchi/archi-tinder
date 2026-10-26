/**
 * utils/userIdentity.js
 * One source for a user's visible identity. Product rule (FULL-AUTH-4): the
 * visible name IS the ID (handle); backend keeps display_name == handle.
 * Handle first, display_name as fallback for older payloads.
 */

/** Plain identity string (no '@'). Empty string when unknown. */
export function userHandle(u) {
  if (!u || typeof u !== 'object') return ''
  return u.handle || u.display_name || ''
}

/** '@id' label. Empty string when unknown (never a bare '@'). */
export function atHandle(u) {
  const h = userHandle(u)
  return h ? `@${h}` : ''
}
