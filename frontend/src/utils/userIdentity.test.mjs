import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { userHandle, atHandle } from './userIdentity.js'

describe('userHandle', () => {
  test('prefers handle', () => {
    assert.equal(userHandle({ handle: 'abc', display_name: 'Old' }), 'abc')
  })
  test('falls back to display_name', () => {
    assert.equal(userHandle({ display_name: 'Old' }), 'Old')
    assert.equal(userHandle({ handle: '', display_name: 'Old' }), 'Old')
  })
  test('empty for nullish / non-object / no fields', () => {
    assert.equal(userHandle(null), '')
    assert.equal(userHandle(undefined), '')
    assert.equal(userHandle('str'), '')
    assert.equal(userHandle({}), '')
  })
})

describe('atHandle', () => {
  test('prefixes @', () => {
    assert.equal(atHandle({ handle: 'abc' }), '@abc')
    assert.equal(atHandle({ display_name: 'Old' }), '@Old')
  })
  test('never a bare @', () => {
    assert.equal(atHandle(null), '')
    assert.equal(atHandle({}), '')
  })
})
