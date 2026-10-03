/**
 * api/getResult.test.mjs
 * PERF-MISC-1(f): concurrent / near-simultaneous getResult calls for one
 * session share a single GET; failures are not cached.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

if (typeof globalThis.window === 'undefined') {
  globalThis.window = { location: { origin: 'https://app.example' } }
}
if (typeof globalThis.localStorage === 'undefined') {
  globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} }
}

const calls = []
let failNext = false
globalThis.fetch = async (url) => {
  calls.push(String(url))
  await new Promise(r => setTimeout(r, 5))
  if (failNext) {
    failNext = false
    return { ok: false, status: 500, json: async () => ({ detail: 'boom' }) }
  }
  return {
    ok: true, status: 200,
    json: async () => ({ liked_images: [], predicted_images: [] }),
  }
}

const { getResult, _resetResultCache } = await import('./sessions.js')

test('concurrent getResult calls share one request', async () => {
  _resetResultCache(); calls.length = 0
  const [a, b, c] = await Promise.all([
    getResult({ session_id: 's1' }),
    getResult({ session_id: 's1' }),
    getResult({ session_id: 's1' }),
  ])
  assert.equal(calls.length, 1)
  assert.equal(a, b)
  assert.equal(b, c)
})

test('a call just after settle reuses the result', async () => {
  _resetResultCache(); calls.length = 0
  await getResult({ session_id: 's2' })
  await getResult({ session_id: 's2' })
  assert.equal(calls.length, 1)
})

test('different sessions fetch separately', async () => {
  _resetResultCache(); calls.length = 0
  await Promise.all([getResult({ session_id: 'a' }), getResult({ session_id: 'b' })])
  assert.equal(calls.length, 2)
})

test('failure is not cached', async () => {
  _resetResultCache(); calls.length = 0
  failNext = true
  await assert.rejects(getResult({ session_id: 's3' }))
  await getResult({ session_id: 's3' })
  assert.equal(calls.length, 2)
})

// pending reuse timers would keep node alive for 4s; exit explicitly.
test.after(() => { setTimeout(() => process.exit(process.exitCode || 0), 50).unref?.() })
