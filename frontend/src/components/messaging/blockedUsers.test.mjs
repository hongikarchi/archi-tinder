import test from 'node:test'
import assert from 'node:assert/strict'
import {
  markBlocked, markUnblocked, clearBlocked, isBlockedLocally, getBlockSeq, applyServerBlockedByMe,
} from './blockedUsers.ts'

test('block, unblock elsewhere, refetch -> unblocked', () => {
  clearBlocked()
  markBlocked(7)
  applyServerBlockedByMe(7, false, getBlockSeq(7))
  assert.equal(isBlockedLocally(7), false)
})

test('server true seeds the store', () => {
  clearBlocked()
  applyServerBlockedByMe(8, true, getBlockSeq(8))
  assert.equal(isBlockedLocally(8), true)
})

test('missing field is a no-op', () => {
  clearBlocked()
  markBlocked(9)
  applyServerBlockedByMe(9, undefined, getBlockSeq(9))
  assert.equal(isBlockedLocally(9), true)
})

test('stale response (local action after request) is ignored', () => {
  clearBlocked()
  const s = getBlockSeq(10)
  markBlocked(10)
  applyServerBlockedByMe(10, false, s)
  assert.equal(isBlockedLocally(10), true)
})

test('ids are normalized to strings', () => {
  clearBlocked()
  applyServerBlockedByMe('11', true, getBlockSeq('11'))
  assert.equal(isBlockedLocally(11), true)
})

test('local action on another user does not drop a valid response (#500)', () => {
  clearBlocked()
  const s = getBlockSeq(12)
  markBlocked(13)
  applyServerBlockedByMe(12, true, s)
  assert.equal(isBlockedLocally(12), true)
})

test('no-op unblock of another user does not drop a valid response (#500)', () => {
  clearBlocked()
  markBlocked(14)
  const s = getBlockSeq(14)
  markUnblocked(15)
  applyServerBlockedByMe(14, false, s)
  assert.equal(isBlockedLocally(14), false)
})

test('clearBlocked (logout) drops every in-flight response', () => {
  clearBlocked()
  const s = getBlockSeq(16)
  clearBlocked()
  applyServerBlockedByMe(16, true, s)
  assert.equal(isBlockedLocally(16), false)
})
