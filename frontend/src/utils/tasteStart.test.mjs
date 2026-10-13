import test from 'node:test'
import assert from 'node:assert/strict'
import {
  clampIndex, stepIndex, tagMatches, buildChips, isTypingTarget,
  tagKey, keptCards, buildStartDeck, cardZIndex,
} from './tasteStart.js'

const mkCards = ids => ids.map(id => ({ card: { image_id: id } }))

test('start deck: no reports keeps all three, excludes the rest of shown', () => {
  const { startIds, excludeIds } = buildStartDeck({
    cards: mkCards(['a', 'b', 'c']), shown: ['x', 'a', 'b', 'c'], reports: {},
  })
  assert.deepEqual(startIds, ['a', 'b', 'c'])
  assert.deepEqual(excludeIds, ['x'])
})

test('start deck: reported card leaves startIds and stays excluded', () => {
  const cards = mkCards(['a', 'b', 'c'])
  const { startIds, excludeIds } = buildStartDeck({
    cards, shown: ['x', 'a', 'b', 'c'], reports: { b: { reason: 'tag' } },
  })
  assert.deepEqual(startIds, ['a', 'c'])
  assert.deepEqual(excludeIds, ['x', 'b'])
  assert.equal(keptCards(cards, { b: {}, c: {} }).length, 1)
  assert.equal(keptCards(cards, undefined).length, 3)
})

test('start deck: reported ids survive the exclude cap', () => {
  const shown = Array.from({ length: 150 }, (_, i) => `s${i}`)
  shown.unshift('b', 'a', 'c')
  const { excludeIds } = buildStartDeck({
    cards: mkCards(['a', 'b', 'c']), shown, reports: { b: {} }, max: 100,
  })
  assert.equal(excludeIds.length, 100)
  assert.equal(excludeIds[excludeIds.length - 1], 'b')
})

test('front card is always on top of departed and behind cards', () => {
  assert.ok(cardZIndex(0) > cardZIndex(1))
  assert.ok(cardZIndex(1) > cardZIndex(2))
  assert.ok(cardZIndex(2) > cardZIndex(-1))
  assert.ok(cardZIndex(0) > cardZIndex(-2))
})

test('tagKey is stable for list-valued year tags', () => {
  assert.equal(tagKey({ axis: 'year', value: [2010, 2019] }), 'year:[2010,2019]')
  assert.equal(tagKey({ axis: 'country', value: 'Japan' }), 'country:"Japan"')
})

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
