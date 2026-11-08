import test from 'node:test'
import assert from 'node:assert/strict'
import { createSwipeSettler } from './swipeSettle.js'

test('wait resolves immediately at 0 and leaves no waiter', async () => {
  const s = createSwipeSettler({ timeoutMs: 50 })
  await s.wait()
  assert.equal(s.waiterCount, 0)
})

test('wait resolves when the counter hits 0', async () => {
  const s = createSwipeSettler({ timeoutMs: 5000 })
  s.increment(); s.increment()
  let done = false
  const p = s.wait().then(() => { done = true })
  s.decrement()
  await new Promise(r => setTimeout(r, 5))
  assert.equal(done, false)
  s.decrement()
  await p
  assert.equal(done, true)
  assert.equal(s.waiterCount, 0)
})

test('timeout resolves anyway and cleans up', async () => {
  const s = createSwipeSettler({ timeoutMs: 20 })
  s.increment()
  const t0 = Date.now()
  await s.wait()
  assert.ok(Date.now() - t0 >= 15)
  assert.equal(s.waiterCount, 0)
  assert.equal(s.pending, 1)
})

test('multiple waiters all resolve; timers do not leak', async () => {
  const s = createSwipeSettler({ timeoutMs: 60000 })
  s.increment()
  const ps = [s.wait(), s.wait(), s.wait()]
  assert.equal(s.waiterCount, 3)
  s.decrement()
  await Promise.all(ps)
  assert.equal(s.waiterCount, 0)
})

test('decrement never goes below 0', () => {
  const s = createSwipeSettler()
  s.decrement()
  assert.equal(s.pending, 0)
})
