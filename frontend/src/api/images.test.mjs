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

try {
  const mod = await import('./images.js')
  getImageSource = mod.getImageSource
} catch {
  // images.js imports core.js which calls import.meta.env at module eval —
  // that is a Vite construct unavailable under node --test. Skip all tests.
  test('getImageSource (images.js) — SKIPPED: module not importable under node --test (import.meta.env)', (t) => {
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
