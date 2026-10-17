import test from 'node:test'
import assert from 'node:assert/strict'
import { clampIndex, stepIndex, tagMatches, buildChips, isTypingTarget } from './tasteStart.js'

test('stack navigation clamps at both ends', () => {
  assert.equal(stepIndex(0, -1, 3), 0)
  assert.equal(stepIndex(0, 1, 3), 1)
  assert.equal(stepIndex(2, 1, 3), 2)
  assert.equal(stepIndex(2, -1, 3), 1)
  assert.equal(clampIndex(5, 2), 1)
  assert.equal(clampIndex(0, 0), 0)
})

test('chips: exclude hidden, matched flag from front card keys', () => {
  const tags = [
    { axis: 'country', value: 'Japan', polarity: 'want' },
    { axis: 'material', value: 'wood', polarity: 'want' },
    { axis: 'material', value: 'brick', polarity: 'exclude' },
  ]
  const chips = buildChips(tags, [['country', 'Japan']])
  assert.equal(chips.length, 2)
  assert.equal(chips[0].matched, true)
  assert.equal(chips[1].matched, false)
  assert.equal(tagMatches(tags[1], undefined), false)
})

test('typing target detection', () => {
  assert.equal(isTypingTarget({ tagName: 'TEXTAREA' }), true)
  assert.equal(isTypingTarget({ tagName: 'BUTTON' }), false)
  assert.equal(isTypingTarget(null), false)
})

test('array-valued year tags match structurally, incl. null bounds', () => {
  const decade = { axis: 'year', value: [2010, 2019], polarity: 'want' }
  const since = { axis: 'year', value: [2021, null], polarity: 'want' }
  assert.equal(tagMatches(decade, [['year', [2010, 2019]]]), true)
  assert.equal(tagMatches(since, [['year', [2021, null]]]), true)
  assert.equal(tagMatches(since, [['year', [2021, 2030]]]), false)
  assert.equal(tagMatches(decade, [['year', [2000, 2009]]]), false)
})
