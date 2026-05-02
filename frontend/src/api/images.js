/**
 * api/images.js
 * Image URL classification, telemetry, and card normalization.
 */

import { BASE } from './core.js'

// -- Image telemetry helpers -----------------------------------------------

/**
 * getImageSource — classify image URL by CDN/host origin.
 * Uses URL(url, origin) to handle both absolute and relative URLs.
 * Returns: 'divisare' | 'metalocus' | 'r2' | 'external' | 'unknown'
 */
export function getImageSource(url) {
  if (!url || typeof url !== 'string') return 'unknown'
  try {
    const u = new URL(url, window.location.origin)
    const host = u.hostname.toLowerCase()
    const isHost = (h) => host === h || host.endsWith('.' + h)
    if (isHost('divisare.com')) return 'divisare'
    if (isHost('metalocus.es')) return 'metalocus'
    if (isHost('cloudflarestorage.com') || isHost('r2.dev')) return 'r2'
    // Same-origin: backend-proxied R2 images
    if (host === window.location.hostname) return 'r2'
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
export function emitImageLoadEvent({ url, outcome, building_id, context, load_ms, session_id }) {
  if (!url || !outcome) return
  const body = JSON.stringify({ url, outcome, building_id, context, load_ms, session_id })
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

  // Handle action cards
  if (card.building_id === '__action_card__' || card.card_type === 'action') {
    return {
      image_id: '__action_card__',
      card_type: 'action',
      action_card_message: card.action_card_message || 'Your taste profile is ready!',
      action_card_subtitle: card.action_card_subtitle || null,
      image_title: card.name_en || 'Analysis Complete',
      image_url: '',
      source_url: null,
      gallery: [],
      metadata: {},
    }
  }

  // Already normalized
  if (card.image_id) return card

  return {
    image_id:    card.building_id,
    card_type:   'building',
    image_title: card.name_en || card.project_name,
    image_url:   card.image_url,
    source_url:  card.url || null,
    gallery:     card.gallery || [],
    gallery_drawing_start: card.gallery_drawing_start ?? card.metadata?.gallery_drawing_start ?? null,
    metadata: {
      axis_typology:   card.metadata?.axis_typology   ?? card.program   ?? null,
      axis_architects: card.metadata?.axis_architects ?? card.architect  ?? null,
      axis_country:    card.metadata?.axis_country    ?? card.location_country ?? null,
      axis_area_m2:    card.metadata?.axis_area_m2    ?? card.area_sqm  ?? null,
      axis_year:       card.metadata?.axis_year       ?? card.year      ?? null,
      axis_style:          card.metadata?.axis_style          ?? card.style          ?? null,
      axis_atmosphere:     card.metadata?.axis_atmosphere     ?? card.atmosphere     ?? null,
      axis_color_tone:     card.metadata?.axis_color_tone     ?? card.color_tone     ?? null,
      axis_material_visual: card.metadata?.axis_material_visual ?? card.material_visual ?? [],
      axis_material:   card.metadata?.axis_material   ?? card.material  ?? null,
      axis_tags:       card.metadata?.axis_tags       ?? card.tags      ?? [],
    },
  }
}
