import test from 'node:test'
import assert from 'node:assert/strict'
import { planEditSave } from './boardEditPlan.js'

test('name only: dirty draft is trimmed, selection is not deleted', () => {
  const p = planEditSave({ draft: ' New ', baseline: 'Old', selectedIds: new Set(['a']), deleting: false })
  assert.deepEqual(p, { name: 'New', deleteIds: [], noop: false, blank: false })
})

test('delete with dirty name sends both', () => {
  const p = planEditSave({ draft: 'New', baseline: 'Old', selectedIds: new Set(['a', 'b']), deleting: true })
  assert.equal(p.name, 'New')
  assert.deepEqual(p.deleteIds, ['a', 'b'])
})

test('delete with clean name sends only ids', () => {
  const p = planEditSave({ draft: 'Old', baseline: 'Old', selectedIds: new Set(['a']), deleting: true })
  assert.equal(p.name, null)
  assert.deepEqual(p.deleteIds, ['a'])
  assert.equal(p.noop, false)
})

test('blank draft is never saved; unchanged draft is a noop', () => {
  assert.equal(planEditSave({ draft: '  ', baseline: 'Old', selectedIds: new Set(), deleting: false }).blank, true)
  assert.equal(planEditSave({ draft: '  ', baseline: 'Old', selectedIds: new Set(), deleting: false }).noop, true)
  const same = planEditSave({ draft: 'Old', baseline: 'Old', selectedIds: new Set(), deleting: false })
  assert.equal(same.noop, true)
  assert.equal(same.blank, false)
})

test('after the name is saved the new baseline is not re-sent on retry', () => {
  const p = planEditSave({ draft: 'New', baseline: 'New', selectedIds: new Set(['a']), deleting: true })
  assert.equal(p.name, null)
  assert.deepEqual(p.deleteIds, ['a'])
})
