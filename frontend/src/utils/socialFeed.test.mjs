import test from 'node:test'
import assert from 'node:assert/strict'
import {
  rowStartIndex, reorderForExpanded, mergePages, patchReaction, toggledReaction,
} from './socialFeed.js'

const mk = ids => ids.map(id => ({ board_id: id }))
const ids = l => l.map(b => b.board_id)

test('rowStartIndex: 2 and 3 columns', () => {
  assert.equal(rowStartIndex(0, 2), 0)
  assert.equal(rowStartIndex(1, 2), 0)
  assert.equal(rowStartIndex(5, 2), 4)
  assert.equal(rowStartIndex(5, 3), 3)
  assert.equal(rowStartIndex(7, 0), 7)
})

test('reorderForExpanded: right-column card moves before its left sibling', () => {
  assert.deepEqual(ids(reorderForExpanded(mk([1, 2, 3, 4]), 4, 2)), [1, 2, 4, 3])
  assert.deepEqual(ids(reorderForExpanded(mk([1, 2, 3, 4]), 2, 2)), [2, 1, 3, 4])
})

test('reorderForExpanded: 3 columns pulls to row start', () => {
  assert.deepEqual(ids(reorderForExpanded(mk([1, 2, 3, 4, 5, 6]), 6, 3)), [1, 2, 3, 6, 4, 5])
})

test('reorderForExpanded: no-ops and no mutation', () => {
  const l = mk([1, 2, 3])
  assert.equal(reorderForExpanded(l, null, 2), l)
  assert.equal(reorderForExpanded(l, 99, 2), l)
  assert.equal(reorderForExpanded(l, 3, 2), l) // already row start
  reorderForExpanded(l, 2, 2)
  assert.deepEqual(ids(l), [1, 2, 3])
})

test('mergePages: appends and dedups by board_id', () => {
  const merged = mergePages(mk([1, 2]), mk([2, 3, 3, 4]))
  assert.deepEqual(ids(merged), [1, 2, 3, 4])
  assert.deepEqual(ids(mergePages(mk([1]), undefined)), [1])
})

test('patchReaction: patches only the target', () => {
  const l = [{ board_id: 1, is_reacted: false }, { board_id: 2, is_reacted: false }]
  const out = patchReaction(l, 2, { is_reacted: true })
  assert.equal(out[0].is_reacted, false)
  assert.equal(out[1].is_reacted, true)
  assert.equal(l[1].is_reacted, false)
})

test('toggledReaction: flips state and adjusts count', () => {
  assert.deepEqual(toggledReaction({ is_reacted: false, reaction_count: 2 }), { is_reacted: true, reaction_count: 3 })
  assert.deepEqual(toggledReaction({ is_reacted: true, reaction_count: 0 }), { is_reacted: false, reaction_count: 0 })
  assert.deepEqual(toggledReaction({}), { is_reacted: true, reaction_count: 1 })
})
