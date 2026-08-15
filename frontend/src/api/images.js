/**
 * api/images.js
 * Image URL classification, telemetry, and card normalization.
 */

import { BASE } from './core.js'
import { rightSizeImageUrl, buildCardSrcSet, buildLqipUrl } from './rightSizeImageUrl.js'

// -- Image telemetry helpers -----------------------------------------------

/**
 * getImageSource — classify image URL by CDN/host origin.
 * Uses URL(url, origin) to handle both absolute and relative URLs.
 * Returns: 'divisare' | 'metalocus' | 'archello' | 'imgix' | 'architizer'
 *        | 'archdaily' | 'dezeen' | 'external' | 'unknown'
 *
 * 'imgix' covers *.imgix.net (e.g. architizer-prod.imgix.net).
 * 'architizer' covers architizer.com (non-imgix direct URLs).
 *
 * Canonical v2 schema serves full source-CDN URLs (R2 composition retired).
 * Buckets listed above are the dominant hosts in canonical_v2_buildings.source_refs.
 */
export function getImageSource(url) {
  if (!url || typeof url !== 'string') return 'unknown'
  try {
    const u = new URL(url, window.location.origin)
    const host = u.hostname.toLowerCase()
    const isHost = (h) => host === h || host.endsWith('.' + h)
    if (isHost('divisare.com')) return 'divisare'
    if (isHost('metalocus.es')) return 'metalocus'
    if (isHost('archello.com')) return 'archello'
    if (isHost('imgix.net'))      return 'imgix'
    if (isHost('architizer.com')) return 'architizer'
    if (isHost('archdaily.com') || isHost('archdaily.net')) return 'archdaily'
    if (isHost('dezeen.com')) return 'dezeen'
    return 'external'
  } catch {
    return 'unknown'
  }
}

/**
 * emitImageLoadEvent — fire-and-forget telemetry beacon.
 * Uses sendBeacon when available (reliable on page unload), falls back to fetch.
 * Errors are swallowed — telemetry must never throw or affect UI.
 */
export function emitImageLoadEvent({ url, outcome, canonical_bld_id, context, load_ms, session_id }) {
  if (!url || !outcome) return
  const body = JSON.stringify({ url, outcome, canonical_bld_id, context, load_ms, session_id })
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(`${BASE}/telemetry/image-load/`, new Blob([body], { type: 'application/json' }))
    } else {
      fetch(`${BASE}/telemetry/image-load/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      }).catch(() => {})  // swallow errors; telemetry must never throw
    }
  } catch { /* swallow; telemetry must never throw */ }
}

// -- ImageCard normalizer --------------------------------------------------
// Maps backend field names (spec) -> frontend field names used in components.
// Components use: image_id, image_title, image_url, gallery, metadata.*

export function normalizeCard(card) {
  if (!card) return null

  // Backend now emits `canonical_bld_id`; tolerate legacy `building_id` for
  // one rollout cycle.
  const bld = card.canonical_bld_id || card.building_id || null

  // Handle action cards
  if (bld === '__action_card__' || card.card_type === 'action') {
    return {
      image_id: '__action_card__',
      card_type: 'action',
      action_card_message: card.action_card_message || 'Your taste profile is ready!',
      action_card_subtitle: card.action_card_subtitle || null,
      image_title: card.name || card.name_en || 'Analysis Complete',
      image_url: '',
      source_url: null,
      gallery: [],
      covers_by_type: {},
      metadata: {},
    }
  }

  // Already normalized
  if (card.image_id) return card

  return {
    image_id:    bld,
    card_type:   'building',
    // canonical_v2 collapses name_en + project_name into a single `name`.
    image_title: card.name || card.name_en || card.project_name || '',
    image_url:   rightSizeImageUrl(card.image_url),
    image_srcset: buildCardSrcSet(card.image_url),
    lqip_url:    buildLqipUrl(card.image_url),
    // cover_full_url: raw un-resized URL passthrough (no transformation).
    // Consumers that need full resolution (lightbox, download) use this field.
    cover_full_url: card.image_url || null,
    // image_focus / image_kind: passthrough so SwipeCard's isDrawingKind check
    // (drawing-vs-photo background/fit) actually has data to read.
    image_focus: card.image_focus ?? null,
    image_kind:  card.image_kind ?? null,
    source_url:  card.url || null,
    // FRONT-UX-14: gallery images render full-bleed at CARD_WIDTH — right-size
    // to the same 840px default as the cover so the gallery face doesn't pull
    // full-resolution source images. rightSizeImageUrl is idempotent for
    // already-sized URLs and a no-op passthrough for non-CDN hosts.
    gallery:     (card.gallery || []).map(u => rightSizeImageUrl(u)),
    gallery_meta: card.gallery_meta || [],
    gallery_drawing_start: card.gallery_drawing_start ?? card.metadata?.gallery_drawing_start ?? null,
    // covers_by_type: jsonb dict {exterior, interior, drawing, aerial, detail}
    // passthrough so UI can render a focus selector (S2 image_focus feature).
    covers_by_type: card.covers_by_type || {},
    metadata: {
      axis_typology:        card.metadata?.axis_typology        ?? card.program          ?? null,
      axis_architects:      card.metadata?.axis_architects      ?? null,
      axis_country:         card.metadata?.axis_country         ?? card.location_country ?? null,
      axis_city:            card.metadata?.axis_city            ?? card.location_city    ?? null,
      axis_year:            card.metadata?.axis_year            ?? card.project_year     ?? null,
      axis_style:           card.metadata?.axis_style           ?? card.style            ?? null,
      axis_atmosphere:      card.metadata?.axis_atmosphere      ?? card.atmosphere       ?? null,
      axis_color_tone:      card.metadata?.axis_color_tone      ?? card.color_tone       ?? null,
      axis_material_visual: card.metadata?.axis_material_visual ?? card.material_visual  ?? [],
      visual_description:   card.metadata?.visual_description   ?? card.visual_description ?? null,
    },
  }
}
