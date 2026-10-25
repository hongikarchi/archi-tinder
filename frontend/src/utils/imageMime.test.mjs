/**
 * utils/imageMime.test.mjs — node --test src/utils/imageMime.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { safeImageMime, imageExtension } from './imageMime.js'

describe('safeImageMime', () => {
  test('keeps allowlisted types', () => {
    assert.equal(safeImageMime('image/png'), 'image/png')
    assert.equal(safeImageMime('image/jpeg'), 'image/jpeg')
    assert.equal(safeImageMime('IMAGE/WEBP'), 'image/webp')
  })
  test('falls back to png for anything else', () => {
    assert.equal(safeImageMime('image/svg+xml'), 'image/png')
    assert.equal(safeImageMime('text/html'), 'image/png')
    assert.equal(safeImageMime('image/png;base64,x'), 'image/png')
    assert.equal(safeImageMime(null), 'image/png')
    assert.equal(safeImageMime(undefined), 'image/png')
  })
  test('imageExtension follows the safe mime', () => {
    assert.equal(imageExtension('image/jpeg'), 'jpeg')
    assert.equal(imageExtension('image/svg+xml'), 'png')
  })
})
