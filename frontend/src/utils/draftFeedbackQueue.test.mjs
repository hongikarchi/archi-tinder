import test from 'node:test'
import assert from 'node:assert/strict'
import { createDraftFeedbackQueue } from './draftFeedbackQueue.js'

test('second back-to-back call receives the draft id from the first', async () => {
  const q = createDraftFeedbackQueue(null)
  const seen = []
  let resolveFirst
  const first = q.send(id => { seen.push(id); return new Promise(r => { resolveFirst = r }) })
  const second = q.send(async id => { seen.push(id); return { draftId: id } })
  await new Promise(r => setTimeout(r, 5))
  assert.deepEqual(seen, [null])
  resolveFirst({ draftId: 'd1' })
  await first
  await second
  assert.deepEqual(seen, [null, 'd1'])
  assert.equal(q.getDraftId(), 'd1')
})

test('failing first call does not hang the second', async () => {
  const q = createDraftFeedbackQueue(null)
  const first = q.send(() => Promise.reject(new Error('boom')))
  const second = q.send(async id => ({ draftId: 'd2', got: id }))
  await assert.rejects(first)
  const res = await second
  assert.equal(res.got, null)
  assert.equal(q.getDraftId(), 'd2')
})

test('known draft id sends immediately without waiting', async () => {
  const q = createDraftFeedbackQueue('d0')
  const seen = []
  q.send(() => { seen.push('a'); return new Promise(() => {}) })
  await q.send(async id => { seen.push(id); return {} })
  assert.deepEqual(seen, ['a', 'd0'])
})
