import test from 'node:test'
import assert from 'node:assert/strict'
import { exitDirectionForRaw, rawFromStored } from './assessmentDirection.js'

test('exit direction follows raw value', () => {
  assert.equal(exitDirectionForRaw(2), 'right')
  assert.equal(exitDirectionForRaw(1), 'right')
  assert.equal(exitDirectionForRaw(0), 'right')
  assert.equal(exitDirectionForRaw(-1), 'left')
  assert.equal(exitDirectionForRaw(-2), 'left')
})

test('rawFromStored undoes reversal', () => {
  assert.equal(rawFromStored(2, true), -2)
  assert.equal(rawFromStored(2, false), 2)
  assert.equal(rawFromStored(0, true) + 0, 0)
})
