import test from 'node:test'
import assert from 'node:assert/strict'
import { isReportStale, shouldRegenerateOnOpen } from './reportStale.js'

const board = (over = {}) => ({ final_report: { persona_type: 'x' }, liked_ids: ['a'], ...over })

test('isReportStale: undefined is false, boolean is returned as-is', () => {
  assert.equal(isReportStale(board()), false)
  assert.equal(isReportStale(board({ report_stale: true })), true)
  assert.equal(isReportStale(board({ report_stale: false })), false)
  assert.equal(isReportStale(null), false)
})

test('shouldRegenerateOnOpen: owner + stale + liked only', () => {
  assert.equal(shouldRegenerateOnOpen({ isOwner: true, board: board({ report_stale: true }) }), true)
  assert.equal(shouldRegenerateOnOpen({ isOwner: false, board: board({ report_stale: true }) }), false)
  assert.equal(shouldRegenerateOnOpen({ isOwner: true, board: board({ report_stale: false }) }), false)
  assert.equal(shouldRegenerateOnOpen({ isOwner: true, board: board({ report_stale: true, liked_ids: [] }) }), false)
  assert.equal(shouldRegenerateOnOpen({ isOwner: true, board: board({ report_stale: true, final_report: null }) }), false)
})
