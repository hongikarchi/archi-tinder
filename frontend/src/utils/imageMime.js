/**
 * Allowlist for the mime type of a stored base64 persona image. Anything else
 * (e.g. `image/svg+xml`, `text/html`, garbage) falls back to PNG so a `data:`
 * URL is never built from an attacker-controlled mime string.
 */
const ALLOWED = new Set(['image/png', 'image/jpeg', 'image/webp'])

export function safeImageMime(mime) {
  const m = typeof mime === 'string' ? mime.trim().toLowerCase() : ''
  return ALLOWED.has(m) ? m : 'image/png'
}

export function imageExtension(mime) {
  return safeImageMime(mime).split('/')[1]
}
