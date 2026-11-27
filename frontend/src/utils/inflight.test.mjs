import test from 'node:test'
import assert from 'node:assert/strict'
import { createInflight } from './inflight.ts'

function deferred() {
  let resolve
  const promise = new Promise(r => { resolve = r })
  return { promise, resolve }
}

test('join shares a pending request and its start meta', async () => {
  const c = createInflight()
  let calls = 0
  const d = deferred()
  const a = c.start('1', () => { calls += 1; return d.promise }, 'seq-at-start')
  const b = c.join('1', () => { calls += 1; return d.promise }, 'seq-now')
  assert.equal(b, a)
  assert.equal(b.meta, 'seq-at-start')
  d.resolve('x')
  assert.equal(await b.promise, 'x')
  assert.equal(calls, 1)
})

test('start always sends a fresh request', async () => {
  const c = createInflight()
  let calls = 0
  const d = deferred()
  c.start('1', () => { calls += 1; return d.promise })
  const b = c.start('1', async () => { calls += 1; return 'fresh' })
  assert.equal(await b.promise, 'fresh')
  assert.equal(calls, 2)
})

test('join with nothing pending starts one; different keys do not share', async () => {
  const c = createInflight()
  let calls = 0
  await Promise.all([
    c.join('1', async () => { calls += 1 }).promise,
    c.join('2', async () => { calls += 1 }).promise,
  ])
  assert.equal(calls, 2)
})

test('a settled request is not reused', async () => {
  const c = createInflight()
  let calls = 0
  await c.join('1', async () => { calls += 1 }).promise
  await c.join('1', async () => { calls += 1 }).promise
  assert.equal(calls, 2)
})

test('invalidate: next join is fresh; the old request does not evict the new one', async () => {
  const c = createInflight()
  const d1 = deferred()
  const d2 = deferred()
  const a = c.join('1', () => d1.promise)
  c.invalidate('1')
  const b = c.join('1', () => d2.promise)
  assert.notEqual(a, b)
  d1.resolve('old')
  await a.promise
  assert.equal(c.join('1', () => Promise.resolve('new')), b)
  d2.resolve('fresh')
  assert.equal(await b.promise, 'fresh')
})

test('a rejected request is shared and then dropped', async () => {
  const c = createInflight()
  let calls = 0
  const fail = () => { calls += 1; return Promise.reject(new Error('boom')) }
  const a = c.join('1', fail)
  const b = c.join('1', fail)
  await assert.rejects(a.promise)
  await assert.rejects(b.promise)
  await assert.rejects(c.join('1', fail).promise)
  assert.equal(calls, 2)
})
