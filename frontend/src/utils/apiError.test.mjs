/**
 * utils/apiError.test.mjs — node --test src/utils/apiError.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { classifyApiError, describeSaveError } from './apiError.js'
import { describePromoteError } from '../components/promoteError.js'

const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
const http = (status, data) => Object.assign(new Error('x'), { status, data })

describe('classifyApiError', () => {
  test('timeout / network', () => {
    assert.deepEqual(classifyApiError(abort), { kind: 'timeout', code: 'timeout' })
    assert.deepEqual(classifyApiError(new TypeError('Failed to fetch')), { kind: 'network', code: 'network' })
  })
  test('http statuses', () => {
    assert.deepEqual(classifyApiError(http(500)), { kind: 'server', code: 'HTTP 500' })
    assert.deepEqual(classifyApiError(http(503)), { kind: 'server', code: 'HTTP 503' })
    assert.deepEqual(classifyApiError(http(404)), { kind: 'notFound', code: 'HTTP 404' })
    assert.deepEqual(classifyApiError(http(401)), { kind: 'unauthorized', code: 'HTTP 401' })
    assert.deepEqual(classifyApiError(http(403)), { kind: 'forbidden', code: 'HTTP 403' })
    assert.deepEqual(classifyApiError(http(400)), { kind: 'unknown', code: 'HTTP 400' })
  })
  test('no status', () => {
    assert.deepEqual(classifyApiError(new Error('boom')), { kind: 'unknown', code: 'Error' })
    assert.deepEqual(classifyApiError(null), { kind: 'unknown', code: 'error' })
  })
})

describe('describeSaveError', () => {
  test('maps kinds to save reasons', () => {
    assert.deepEqual(describeSaveError(abort), { reason: 'timeout', code: 'timeout' })
    assert.deepEqual(describeSaveError(new TypeError('x')), { reason: 'network', code: 'network' })
    assert.deepEqual(describeSaveError(http(502)), { reason: 'server', code: 'HTTP 502' })
    assert.deepEqual(describeSaveError(http(404)), { reason: 'notFound', code: 'HTTP 404' })
    assert.deepEqual(describeSaveError(http(401)), { reason: 'unauthorized', code: 'HTTP 401' })
    assert.deepEqual(describeSaveError(http(400)), { reason: 'unknown', code: 'HTTP 400' })
    assert.deepEqual(describeSaveError(http(403)), { reason: 'unknown', code: 'HTTP 403' })
  })
})

describe('describePromoteError (behaviour unchanged)', () => {
  test('all reasons', () => {
    assert.deepEqual(describePromoteError(abort), { reason: 'timeout', code: 'timeout' })
    assert.deepEqual(describePromoteError(new TypeError('x')), { reason: 'network', code: 'network' })
    assert.deepEqual(describePromoteError(http(500)), { reason: 'server', code: 'HTTP 500' })
    assert.deepEqual(describePromoteError(http(404)), { reason: 'no_buildings', code: 'HTTP 404' })
    assert.deepEqual(describePromoteError(http(403, { detail: 'verify_required' })), { reason: 'verify_required', code: 'HTTP 403' })
    assert.deepEqual(describePromoteError(http(403, { detail: 'other' })), { reason: 'unknown', code: 'HTTP 403' })
    assert.deepEqual(describePromoteError(http(401)), { reason: 'unauthorized', code: 'HTTP 401' })
    assert.deepEqual(describePromoteError(http(400)), { reason: 'unknown', code: 'HTTP 400' })
    assert.deepEqual(describePromoteError(new Error('boom')), { reason: 'unknown', code: 'Error' })
    assert.deepEqual(describePromoteError(undefined), { reason: 'unknown', code: 'error' })
  })
})
