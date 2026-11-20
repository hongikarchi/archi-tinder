import test from 'node:test'
import assert from 'node:assert/strict'
import {
  markBlocked, clearBlocked, isBlockedLocally, getBlockSeq, applyServerBlockedByMe,
} from './blockedUsers.ts'

test('block, unblock elsewhere, refetch -> unblocked', () => {
  clearBlocked()
  markBlocked(7)
  applyServerBlockedByMe(7, false, getBlockSeq())
  assert.equal(isBlockedLocally(7), false)
})

test('server true seeds the store', () => {
  clearBlocked()
  applyServerBlockedByMe(8, true, getBlockSeq())
  assert.equal(isBlockedLocally(8), true)
})

test('missing field is a no-op', () => {
  clearBlocked()
  markBlocked(9)
  applyServerBlockedByMe(9, undefined, getBlockSeq())
  assert.equal(isBlockedLocally(9), true)
})

test('stale response (local action after request) is ignored', () => {
  clearBlocked()
  const s = getBlockSeq()
  markBlocked(10)
  applyServerBlockedByMe(10, false, s)
  assert.equal(isBlockedLocally(10), true)
})

test('ids are normalized to strings', () => {
  clearBlocked()
  applyServerBlockedByMe('11', true, getBlockSeq())
  assert.equal(isBlockedLocally(11), true)
})
