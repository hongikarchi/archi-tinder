import test from 'node:test'
import assert from 'node:assert/strict'
import { isReportStale, shouldRegenerateOnOpen, shouldRegenerateAfterSession, shouldFetchBoardBeforeReport, pickServerBoardName } from './reportStale.js'

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

test('shouldRegenerateOnOpen: first generation / fresh save never counts as stale', () => {
  const stale = board({ report_stale: true })
  assert.equal(shouldRegenerateOnOpen({ isOwner: true, board: stale, hasLocalReport: true }), false)
  assert.equal(shouldRegenerateOnOpen({ isOwner: true, board: stale, freshlySaved: true }), false)
  assert.equal(shouldRegenerateOnOpen({ isOwner: true, board: board({ final_report: null, report_stale: true }) }), false)
})

test('shouldRegenerateAfterSession: only an existing report with new likes / server-stale', () => {
  assert.equal(shouldRegenerateAfterSession({ hadReport: false, newLikes: 3, reportStale: true }), false)
  assert.equal(shouldRegenerateAfterSession({ hadReport: true, newLikes: 0, reportStale: false }), false)
  assert.equal(shouldRegenerateAfterSession({ hadReport: true, newLikes: 0 }), false)
  assert.equal(shouldRegenerateAfterSession({ hadReport: true, newLikes: 0, reportStale: true }), true)
  assert.equal(shouldRegenerateAfterSession({ hadReport: true, newLikes: 1, reportStale: false }), true)
  assert.equal(shouldRegenerateAfterSession({ hadReport: true, newLikes: 2, reportStale: null }), true)
  // signed report: the server flag beats the local counter; legacy (unsigned) keeps the counter
  assert.equal(shouldRegenerateAfterSession({ hadReport: true, newLikes: 5, reportStale: false, reportSigned: true }), false)
  assert.equal(shouldRegenerateAfterSession({ hadReport: true, newLikes: 5, reportStale: false, reportSigned: false }), true)
  assert.equal(shouldRegenerateAfterSession({ hadReport: true, newLikes: 0, reportStale: true, reportSigned: true }), true)
})

test('shouldFetchBoardBeforeReport: only a fresh temp board skips the fetch', () => {
  assert.equal(shouldFetchBoardBeforeReport({ isTemp: true }), false)
  assert.equal(shouldFetchBoardBeforeReport({ isTemp: true, finalReport: {} }), true)
  assert.equal(shouldFetchBoardBeforeReport({ isTemp: true, reportImage: 'x' }), true)
  assert.equal(shouldFetchBoardBeforeReport({ isTemp: false }), true)
  assert.equal(shouldFetchBoardBeforeReport({}), true)
  assert.equal(shouldFetchBoardBeforeReport(null), false)
})
test('pickServerBoardName: server name or null', () => {
  assert.equal(pickServerBoardName({ name: ' New ' }), 'New')
  assert.equal(pickServerBoardName({ name: '' }), null)
  assert.equal(pickServerBoardName(null), null)
  assert.equal(pickServerBoardName({}), null)
})
