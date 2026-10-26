import test from 'node:test'
import assert from 'node:assert/strict'
import { throttleRetryDelayMs, DEFAULT_RETRY_MS, MAX_RETRY_MS } from './throttleRetry.js'

test('defaults to ~8s plus jitter', () => {
  assert.equal(throttleRetryDelayMs(undefined, 0), DEFAULT_RETRY_MS)
  assert.equal(throttleRetryDelayMs(NaN, 0.5), DEFAULT_RETRY_MS + 500)
})

test('uses Retry-After seconds', () => {
  assert.equal(throttleRetryDelayMs(3, 0), 3000)
})

test('ignores non-positive and caps large values', () => {
  assert.equal(throttleRetryDelayMs(0, 0), DEFAULT_RETRY_MS)
  assert.equal(throttleRetryDelayMs(600, 0.9), MAX_RETRY_MS)
})
