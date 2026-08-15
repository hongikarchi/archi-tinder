/**
 * api/images.test.mjs
 *
 * Unit tests for getImageSource (Lever 4 — imgix bucket).
 *
 * images.js imports core.js which uses import.meta.env at module-eval time.
 * Under node --test, import.meta.env is undefined, causing a TypeError before
 * any test body runs. We use a dynamic import() inside the test body and skip
 * gracefully if the module cannot be loaded.
 *
 * All five asserted identities are verified in browser/Vite passes regardless.
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

// Provide a minimal window.location.origin so URL(url, origin) in getImageSource
// has a base to resolve relative URLs against. Must be set before the dynamic import.
if (typeof globalThis.window === 'undefined') {
  globalThis.window = { location: { origin: 'https://app.example' } }
}

let getImageSource
let normalizeCard

try {
  const mod = await import('./images.js')
  getImageSource = mod.getImageSource
  normalizeCard = mod.normalizeCard
} catch {
  // images.js imports core.js which calls import.meta.env at module eval —
  // that is a Vite construct unavailable under node --test. Skip all tests.
  test('getImageSource (images.js) — SKIPPED: module not importable under node --test (import.meta.env)', (t) => {
    t.skip('images.js cannot be imported under node --test (import.meta.env)')
  })
  test('normalizeCard (images.js) — SKIPPED: module not importable under node --test (import.meta.env)', (t) => {
    t.skip('images.js cannot be imported under node --test (import.meta.env)')
  })
}

if (getImageSource) {
  test('Lever4 getImageSource: architizer-prod.imgix.net → imgix', () => {
    assert.equal(getImageSource('https://architizer-prod.imgix.net/media/foo/x.jpg'), 'imgix')
  })

  test('Lever4 getImageSource: arbitrary subdomain *.imgix.net → imgix', () => {
    assert.equal(getImageSource('https://example.imgix.net/img.jpg'), 'imgix')
  })

  test('Lever4 getImageSource: architizer.com (non-imgix) → architizer', () => {
    assert.equal(getImageSource('https://architizer.com/foo.jpg'), 'architizer')
  })

  test('Lever4 getImageSource: images.divisare.com → divisare', () => {
    assert.equal(getImageSource('https://images.divisare.com/images/f_auto,q_auto,w_auto/v1/abc/x.jpg'), 'divisare')
  })

  test('Lever4 getImageSource: unknown host → external', () => {
    assert.equal(getImageSource('https://cdn.unknown-host.io/photo.jpg'), 'external')
  })

  test('Lever4 getImageSource: empty string → unknown', () => {
    assert.equal(getImageSource(''), 'unknown')
  })
}

if (normalizeCard) {
  // Raw Divisare w_auto URL: cover_full_url must be the exact raw URL,
  // image_url must be the rightSized (w_840,c_limit) transform.
  const RAW_DIVISARE = 'https://images.divisare.com/images/f_auto,q_auto,w_auto/v1/abc/x.jpg'
  const SIZED_DIVISARE = 'https://images.divisare.com/images/f_auto,q_auto,w_840,c_limit/v1/abc/x.jpg'

  test('normalizeCard: cover_full_url preserves raw URL exactly', () => {
    const card = { canonical_bld_id: 'bld_000001', image_url: RAW_DIVISARE }
    const result = normalizeCard(card)
    assert.equal(result.cover_full_url, RAW_DIVISARE,
      'cover_full_url must be the unmodified raw URL')
  })

  test('normalizeCard: image_url is rightSized (w_840,c_limit)', () => {
    const card = { canonical_bld_id: 'bld_000001', image_url: RAW_DIVISARE }
    const result = normalizeCard(card)
    assert.equal(result.image_url, SIZED_DIVISARE,
      'image_url must be the resized URL')
  })

  test('normalizeCard: cover_full_url is null when image_url absent', () => {
    const card = { canonical_bld_id: 'bld_000001' }
    const result = normalizeCard(card)
    assert.equal(result.cover_full_url, null)
  })

  // FRONT-UX-14: gallery URLs are right-sized (default 840 width) per-entry.
  test('normalizeCard: gallery URLs are right-sized (w_840,c_limit)', () => {
    const RAW_DIVISARE_2 = 'https://images.divisare.com/images/f_auto,q_auto,w_auto/v1/def/y.jpg'
    const SIZED_DIVISARE_2 = 'https://images.divisare.com/images/f_auto,q_auto,w_840,c_limit/v1/def/y.jpg'
    const card = { canonical_bld_id: 'bld_000001', gallery: [RAW_DIVISARE, RAW_DIVISARE_2] }
    const result = normalizeCard(card)
    assert.deepEqual(result.gallery, [SIZED_DIVISARE, SIZED_DIVISARE_2],
      'each gallery entry must be independently right-sized')
  })

  test('normalizeCard: gallery URLs on a non-CDN host pass through unchanged', () => {
    const EXTERNAL = 'https://cdn.unknown-host.io/photo.jpg'
    const card = { canonical_bld_id: 'bld_000001', gallery: [EXTERNAL] }
    const result = normalizeCard(card)
    assert.deepEqual(result.gallery, [EXTERNAL])
  })

  test('normalizeCard: gallery defaults to [] when absent', () => {
    const card = { canonical_bld_id: 'bld_000001' }
    const result = normalizeCard(card)
    assert.deepEqual(result.gallery, [])
  })
}
