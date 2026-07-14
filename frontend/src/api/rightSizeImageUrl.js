/**
 * api/rightSizeImageUrl.js
 *
 * PR2 — per-DPR srcset helpers built on the PR1 resize primitive.
 *
 * rightSizeImageUrl(url, targetWidth, quality):
 *   PR1 cover right-sizing + optional quality param (imgix only).
 *
 * buildCardSrcSet(url, { width1x, width2x }):
 *   Builds a `1x, 2x` srcset string from the RAW source URL (Divisare /
 *   imgix), or returns null for non-CDN/non-transformable URLs.
 *
 * Divisare (Cloudinary FETCH CDN):
 *   Replaces the `w_auto` token inside the `/images/<transform>/` segment with
 *   `w_<targetWidth>,c_limit`. Keeps `f_auto,q_auto` and the literal `//images`
 *   double-slash intact. URLs without `w_auto` (already-sized covers, gallery
 *   siblings like `/image/upload/c_fit,f_jpg,q_80,w_1200/...`) are left unchanged
 *   — the replacement is idempotent. quality param is intentionally ignored
 *   (q_auto handles quality for Divisare).
 *
 * imgix:
 *   Sets (or overrides) `w=<targetWidth>`, `fit=max`, and optionally `q=<quality>`
 *   query params. `fit=max` preserves aspect ratio and never upscales. All other
 *   params (auto, cs, etc.) are kept as-is.
 *
 * All other hosts (archello, archdaily, dezeen, external, unknown), malformed
 * URLs, relative paths, and empty/null values are returned unchanged.
 *
 * Pure functions — no side effects, no imports, node --test compatible.
 */

/**
 * @param {string|null|undefined} url   - Source image URL from the backend card.
 * @param {number} [targetWidth=840]    - Target display width in CSS pixels (1x).
 * @param {number} [quality]            - Optional quality param (imgix only; Divisare ignores it).
 * @returns {string|null|undefined}     - Right-sized URL, or the original if no
 *                                        transformation applies.
 */
export function rightSizeImageUrl(url, targetWidth = 840, quality) {
  if (!url || typeof url !== 'string') return url
  let host
  try { host = new URL(url).hostname.toLowerCase() } catch { return url }   // malformed/relative -> unchanged
  const isDivisare = host === 'divisare.com' || host.endsWith('.divisare.com')
  const isImgix    = host === 'imgix.net'    || host.endsWith('.imgix.net')
  if (isDivisare) {
    // Cloudinary FETCH: replace only the w_auto token inside the /images/<transform>/ segment,
    // keep f_auto,q_auto and the literal `//images` double-slash. No w_auto -> no-op (idempotent),
    // which also leaves the already-capped /image/upload/...,w_1200/ gallery sibling untouched.
    // quality is intentionally NOT applied to Divisare — q_auto handles it.
    return url.replace(/(\/images\/[^/]*?)\bw_auto\b/, `$1w_${targetWidth},c_limit`)
  }
  if (isImgix) {
    try {
      const u = new URL(url)
      u.searchParams.set('w', String(targetWidth))   // override existing w=
      u.searchParams.set('fit', 'max')               // preserve aspect, never upscale
      if (quality != null) u.searchParams.set('q', String(quality))   // optional per-DPR quality
      // URLSearchParams serializes ',' as %2C; imgix's canonical params use literal
      // commas (auto=format,compress). Restore them so the emitted URL matches the
      // CDN's canonical cache-key form rather than a percent-encoded variant.
      u.search = u.searchParams.toString().replace(/%2C/gi, ',')
      return u.toString()
    } catch { return url }
  }
  return url   // archello / archdaily / dezeen / external / unknown -> unchanged
}

/**
 * buildLqipUrl — build a tiny (20px-wide) LQIP (Low-Quality Image Placeholder)
 * URL for a card cover image, used as a blurred hint layer while the full
 * image loads.
 *
 * Delegates to rightSizeImageUrl(url, 20) but returns null whenever
 * right-sizing is a no-op for this URL (non-CDN host, malformed/relative
 * URL, or a Divisare URL without a `w_auto` token). A LQIP that resolves to
 * the SAME URL as the full-size image would just download the full image
 * twice — worse than no placeholder at all.
 *
 * @param {string|null|undefined} url  - Raw source URL (before right-sizing).
 * @returns {string|null}              - 20px-wide variant, or null if a
 *                                        distinct right-sized URL cannot be produced.
 */
export function buildLqipUrl(url) {
  const u = rightSizeImageUrl(url, 20)
  return u && u !== url ? u : null
}

/**
 * buildCardSrcSet — produce a `1x, 2x` srcset string for a card cover image.
 *
 * MUST be called with the RAW source URL (before rightSizeImageUrl), because
 * Divisare's w_auto regex only matches the original w_auto token.
 *
 * Per-DPR quality laddering for imgix (per spec A4):
 *   1x: q=80 (full perceived quality at 1x)
 *   2x: q=40 (retina pixels are tiny; lower q is visually lossless at 2x density)
 *
 * Divisare uses q_auto on both descriptors (quality param is intentionally ignored).
 *
 * @param {string|null|undefined} url         - Raw source URL (not yet right-sized).
 * @param {{ width1x?: number, width2x?: number }} [opts]
 * @returns {string|null}  srcset string, or null if not transformable.
 */
export function buildCardSrcSet(url, { width1x = 420, width2x = 840 } = {}) {
  if (!url || typeof url !== 'string') return null
  // A srcset is whitespace-delimited: a literal space in the URL would terminate the URL
  // token and let anything after it parse as an extra candidate (CDN-allowlist bypass /
  // attacker-controlled fetch). Reject any whitespace → degrade to the plain <img src>
  // (which the browser URL-encodes safely). The imgix branch re-serializes via new URL()
  // so it is space-safe anyway; this guard makes the Divisare string-replace path safe too.
  if (/\s/.test(url)) return null
  let host
  try { host = new URL(url).hostname.toLowerCase() } catch { return null }
  const isDivisare = host === 'divisare.com' || host.endsWith('.divisare.com')
  const isImgix    = host === 'imgix.net'    || host.endsWith('.imgix.net')
  if (isDivisare) {
    const u1 = rightSizeImageUrl(url, width1x)
    const u2 = rightSizeImageUrl(url, width2x)
    if (u1 === url && u2 === url) return null   // no w_auto (gallery sibling/already-sized) -> degrade to src
    return `${u1} 1x, ${u2} 2x`
  }
  if (isImgix) {
    const u1 = rightSizeImageUrl(url, width1x, 80)   // q80 @1x — full perceived quality
    const u2 = rightSizeImageUrl(url, width2x, 40)   // q40 @2x — retina pixels; visually lossless
    return `${u1} 1x, ${u2} 2x`
  }
  return null   // non-CDN -> no srcset
}
