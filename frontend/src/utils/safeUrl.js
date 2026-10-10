/**
 * safeUrl.js — render-time guards for API-supplied links.
 *
 * The backend already validates, but every href / src that originates in the
 * API still passes through these at render time (defense in depth). A null
 * result means "do not render this link / image".
 */

// eslint-disable-next-line no-control-regex
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/

/** Normalized absolute URL (parsed.href) only for well-formed http(s)://host URLs without credentials. */
export function safeHttpUrl(value) {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  if (!trimmed || CONTROL_CHARS.test(trimmed)) return null
  // Require the literal "scheme://" first: 'https:example.com' parses as http(s)
  // yet would resolve as a same-origin relative path when used as href/src.
  if (!/^https?:\/\//i.test(trimmed)) return null
  let parsed
  try {
    parsed = new URL(trimmed)   // no base: relative and protocol-relative throw
  } catch {
    return null
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null
  if (!parsed.hostname) return null
  if (parsed.username || parsed.password) return null   // no userinfo
  return parsed.href
}
