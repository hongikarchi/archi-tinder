import test from 'node:test'
import assert from 'node:assert/strict'
import { createInflight } from './inflight.ts'

function deferred() {
  let resolve
  const promise = new Promise(r => { resolve = r })
  return { promise, resolve }
}

test('concurrent calls for one key share a request', async () => {
  const c = createInflight()
  let calls = 0
  const d = deferred()
  const a = c.run('1', () => { calls += 1; return d.promise })
  const b = c.run('1', () => { calls += 1; return d.promise })
  d.resolve('x')
  assert.equal(await a, 'x')
  assert.equal(await b, 'x')
  assert.equal(calls, 1)
})

test('different keys do not share', async () => {
  const c = createInflight()
  let calls = 0
  await Promise.all([c.run('1', async () => { calls += 1 }), c.run('2', async () => { calls += 1 })])
  assert.equal(calls, 2)
})

test('a settled request is not reused', async () => {
  const c = createInflight()
  let calls = 0
  await c.run('1', async () => { calls += 1 })
  await c.run('1', async () => { calls += 1 })
  assert.equal(calls, 2)
})

test('invalidate starts a fresh request; the old one does not evict it', async () => {
  const c = createInflight()
  const d1 = deferred()
  const d2 = deferred()
  const a = c.run('1', () => d1.promise)
  c.invalidate('1')
  const b = c.run('1', () => d2.promise)
  assert.notEqual(a, b)
  d1.resolve('old')
  await a
  // b is still the shared in-flight request for key '1'
  assert.equal(c.run('1', () => Promise.resolve('new')), b)
  d2.resolve('fresh')
  assert.equal(await b, 'fresh')
})

test('a rejected request is shared and then dropped', async () => {
  const c = createInflight()
  let calls = 0
  const fail = () => { calls += 1; return Promise.reject(new Error('boom')) }
  await assert.rejects(Promise.all([c.run('1', fail), c.run('1', fail)]))
  await assert.rejects(c.run('1', fail))
  assert.equal(calls, 2)
})
