/**
 * utils/axisScores.test.mjs
 * Unit tests for axisScores.js using Node's built-in test runner (no extra deps).
 * Run with: node --test frontend/src/utils/axisScores.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { isLegacyAxisScores } from './axisScores.js'

describe('isLegacyAxisScores', () => {
  test('null/undefined axisScores is not legacy', () => {
    assert.equal(isLegacyAxisScores(null), false)
    assert.equal(isLegacyAxisScores(undefined), false)
  })

  test('non-object axisScores is not legacy', () => {
    assert.equal(isLegacyAxisScores('nope'), false)
    assert.equal(isLegacyAxisScores(42), false)
  })

  test('legacy: flat numbers per axis', () => {
    assert.equal(isLegacyAxisScores({ materiality: 0.4, scale: -0.2, energy: null, tradition: 0.1 }), true)
  })

  test('legacy: presence of a form key, even with current-shape siblings', () => {
    assert.equal(isLegacyAxisScores({
      form: 0.3,
      materiality: { score: 0.4, dots: [0.1, 0.5], n: 4, iqr: 0.2, confidence: 0.6 },
      scale: null,
      energy: null,
      tradition: null,
    }), true)
  })

  test('legacy: all-null axes but with a form key present', () => {
    assert.equal(isLegacyAxisScores({ form: null, materiality: null, scale: null, energy: null, tradition: null }), true)
  })

  test('current shape: every present axis is a dict with dots', () => {
    assert.equal(isLegacyAxisScores({
      materiality: { score: 0.4, dots: [0.1, 0.5], n: 4, iqr: 0.2, confidence: 0.6 },
      scale: { score: -0.1, dots: [], n: 1, iqr: 0, confidence: 0.2 },
      energy: null,
      tradition: null,
    }), false)
  })

  test('all-null axis object without a form key is NOT legacy (no-evidence, not legacy)', () => {
    assert.equal(isLegacyAxisScores({ materiality: null, scale: null, energy: null, tradition: null }), false)
  })

  test('empty object is not legacy', () => {
    assert.equal(isLegacyAxisScores({}), false)
  })
})
