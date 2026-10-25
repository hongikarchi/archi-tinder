import { test } from 'node:test'
import assert from 'node:assert/strict'
import { postUntilReady } from './postUntilReady.js'

const OK = { final_report: { a: 1 } }

test('returns a normal body without waiting', async () => {
  let n = 0
  assert.equal(await postUntilReady(async () => { n++; return OK }, { wait: async () => { throw new Error('no wait') } }), OK)
  assert.equal(n, 1)
})

test('202 in_progress waits retry_after then re-POSTs', async () => {
  const rs = [{ status: 'in_progress', retry_after: 7 }, { status: 'in_progress' }, OK]
  const waits = []
  const res = await postUntilReady(async () => rs.shift(), { wait: async ms => { waits.push(ms) } })
  assert.equal(res, OK)
  assert.deepEqual(waits, [7000, 5000])
})

test('gives up after 4 retries with a normal Error', async () => {
  let n = 0
  await assert.rejects(postUntilReady(async () => { n++; return { status: 'in_progress' } }, { wait: async () => {} }), /in progress/)
  assert.equal(n, 5)
})

test('a body with final_report is never treated as in progress; errors propagate', async () => {
  const b = { status: 'in_progress', final_report: { x: 1 } }
  assert.equal(await postUntilReady(async () => b), b)
  await assert.rejects(postUntilReady(async () => { throw Object.assign(new Error('x'), { status: 429 }) }), /x/)
})

test('202 with based_on passes { basedOn } to the next post(); first call gets undefined', async () => {
  const seen = []
  const rs = [{ status: 'in_progress', based_on: 'g1' }, OK]
  await postUntilReady(async ctx => { seen.push(ctx); return rs.shift() }, { wait: async () => {} })
  assert.deepEqual(seen, [undefined, { basedOn: 'g1' }])
})

test('202 without based_on key leaves ctx undefined', async () => {
  const seen = []
  const rs = [{ status: 'in_progress' }, OK]
  await postUntilReady(async ctx => { seen.push(ctx); return rs.shift() }, { wait: async () => {} })
  assert.deepEqual(seen, [undefined, undefined])
})

test('202 with based_on null passes { basedOn: null }', async () => {
  const seen = []
  const rs = [{ status: 'in_progress', based_on: null }, OK]
  await postUntilReady(async ctx => { seen.push(ctx); return rs.shift() }, { wait: async () => {} })
  assert.deepEqual(seen, [undefined, { basedOn: null }])
})
