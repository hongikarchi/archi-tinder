/**
 * api/rightSizeImageUrl.js
 *
 * PR1 cover right-sizing — RESIZE ONLY (no format conversion, srcset, decode, or LQIP).
 *
 * Divisare (Cloudinary FETCH CDN):
 *   Replaces the `w_auto` token inside the `/images/<transform>/` segment with
 *   `w_<targetWidth>,c_limit`. Keeps `f_auto,q_auto` and the literal `//images`
 *   double-slash intact. URLs without `w_auto` (already-sized covers, gallery
 *   siblings like `/image/upload/c_fit,f_jpg,q_80,w_1200/...`) are left unchanged
 *   — the replacement is idempotent.
 *
 * imgix:
 *   Sets (or overrides) `w=<targetWidth>` and `fit=max` query params.
 *   `fit=max` preserves aspect ratio and never upscales. All other params
 *   (q, auto, cs, etc.) are kept as-is.
 *
 * All other hosts (archello, archdaily, dezeen, external, unknown), malformed
 * URLs, relative paths, and empty/null values are returned unchanged.
 *
 * Pure function — no side effects, no imports, node --test compatible.
 */

/**
 * @param {string|null|undefined} url   - Source image URL from the backend card.
 * @param {number} [targetWidth=840]    - Target display width in CSS pixels (1x).
 * @returns {string|null|undefined}     - Right-sized URL, or the original if no
 *                                        transformation applies.
 */
export function rightSizeImageUrl(url, targetWidth = 840) {
  if (!url || typeof url !== 'string') return url
  let host
  try { host = new URL(url).hostname.toLowerCase() } catch { return url }   // malformed/relative -> unchanged
  const isDivisare = host === 'divisare.com' || host.endsWith('.divisare.com')
  const isImgix    = host === 'imgix.net'    || host.endsWith('.imgix.net')
  if (isDivisare) {
    // Cloudinary FETCH: replace only the w_auto token inside the /images/<transform>/ segment,
    // keep f_auto,q_auto and the literal `//images` double-slash. No w_auto -> no-op (idempotent),
    // which also leaves the already-capped /image/upload/...,w_1200/ gallery sibling untouched.
    return url.replace(/(\/images\/[^/]*?)\bw_auto\b/, `$1w_${targetWidth},c_limit`)
  }
  if (isImgix) {
    try {
      const u = new URL(url)
      u.searchParams.set('w', String(targetWidth))   // override existing w=
      u.searchParams.set('fit', 'max')               // preserve aspect, never upscale
      // URLSearchParams serializes ',' as %2C; imgix's canonical params use literal
      // commas (auto=format,compress). Restore them so the emitted URL matches the
      // CDN's canonical cache-key form rather than a percent-encoded variant.
      u.search = u.searchParams.toString().replace(/%2C/gi, ',')
      return u.toString()
    } catch { return url }
  }
  return url   // archello / archdaily / dezeen / external / unknown -> unchanged
}
