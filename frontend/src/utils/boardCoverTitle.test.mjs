import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveCoverTitle, isNameDirty } from './boardCoverTitle.js'

test('resolveCoverTitle: board name wins over persona type', () => {
  assert.equal(resolveCoverTitle({ boardName: 'My board', personaType: 'Persona', defaultName: 'Def' }), 'My board')
})

test('resolveCoverTitle: falls back to persona type then default name', () => {
  assert.equal(resolveCoverTitle({ boardName: '', personaType: 'Persona', defaultName: 'Def' }), 'Persona')
  assert.equal(resolveCoverTitle({ boardName: '  ', personaType: undefined, defaultName: 'Def' }), 'Def')
  assert.equal(resolveCoverTitle({}), '')
})

test('isNameDirty: only a non-empty draft that differs from the saved title', () => {
  assert.equal(isNameDirty('New', 'Old'), true)
  assert.equal(isNameDirty('  Old ', 'Old'), false)
  assert.equal(isNameDirty('   ', 'Old'), false)
  assert.equal(isNameDirty('', ''), false)
  assert.equal(isNameDirty('A', ''), true)
})
