/**
 * utils/boardDeleteRules.test.mjs — node --test src/utils/boardDeleteRules.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { canSelectForDelete, isLastLikedError } from './boardDeleteRules.js'

describe('canSelectForDelete', () => {
  test('single liked building is refused', () => {
    assert.equal(canSelectForDelete({ likedIds: [{ id: 'a' }], candidateId: 'a' }), false)
  })
  test('selecting all remaining liked is refused, one fewer is allowed', () => {
    const likedIds = ['a', 'b', 'c']
    assert.equal(canSelectForDelete({ likedIds, selectedIds: [], candidateId: 'a' }), true)
    assert.equal(canSelectForDelete({ likedIds, selectedIds: ['a'], candidateId: 'b' }), true)
    assert.equal(canSelectForDelete({ likedIds, selectedIds: ['a', 'b'], candidateId: 'c' }), false)
  })
  test('saved-only buildings are never restricted', () => {
    assert.equal(canSelectForDelete({ likedIds: ['a'], selectedIds: [], candidateId: 'saved1' }), true)
    assert.equal(canSelectForDelete({ likedIds: ['a', 'b'], selectedIds: ['a', 'saved1'], candidateId: 'saved2' }), true)
  })
  test('saved selections do not count toward the liked total', () => {
    assert.equal(canSelectForDelete({ likedIds: ['a', 'b'], selectedIds: ['s1', 's2', 'a'], candidateId: 'b' }), false)
  })
  test('already deleted liked ids shrink the remaining set', () => {
    assert.equal(canSelectForDelete({ likedIds: ['a', 'b'], deletedIds: ['a'], candidateId: 'b' }), false)
  })
})

describe('canSelectForDelete with hidden liked ids', () => {
  test('caller filters liked ids to rendered ones: last visible liked is refused', () => {
    const all = ['a', 'b', 'x']          // x = non-publishable, not rendered
    const rendered = new Set(['a', 'b'])
    const likedIds = all.filter(id => rendered.has(id))
    assert.equal(canSelectForDelete({ likedIds, selectedIds: ['a'], candidateId: 'b' }), false)
    // unfiltered list would wrongly allow it
    assert.equal(canSelectForDelete({ likedIds: all, selectedIds: ['a'], candidateId: 'b' }), true)
  })
})

describe('isLastLikedError', () => {
  test('detects the 400 body', () => {
    assert.equal(isLastLikedError({ status: 400, data: { detail: 'last_liked_building' } }), true)
    assert.equal(isLastLikedError({ status: 400, message: 'last_liked_building' }), true)
  })
  test('ignores other errors', () => {
    assert.equal(isLastLikedError({ status: 500, data: { detail: 'last_liked_building' } }), false)
    assert.equal(isLastLikedError({ status: 400, data: { detail: 'x' } }), false)
    assert.equal(isLastLikedError(null), false)
  })
})
