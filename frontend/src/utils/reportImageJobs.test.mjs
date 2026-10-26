/**
 * utils/reportImageJobs.test.mjs
 * FULL-REPORT-IMG-1: persona-image job store state machine.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createReportImageJobs } from './reportImageJobs.js'

const noWait = { wait: async () => {} }
const IMG = { image_data: 'AAAA', mime_type: 'image/png', prompt: null }

test('generating -> done, notifies subscribers, dedupes concurrent start()', async () => {
  let calls = 0
  const jobs = createReportImageJobs(async () => { calls++; return IMG }, noWait)
  const seen = []
  jobs.subscribe(() => seen.push(jobs.get('p1').status))
  const a = jobs.start('p1')
  const b = jobs.start('p1')
  assert.equal(jobs.get('p1').status, 'generating')
  assert.equal(a, b)
  await a
  assert.equal(calls, 1)
  assert.deepEqual(seen, ['generating', 'done'])
  assert.equal(jobs.get('p1').image, 'AAAA')
  assert.equal(jobs.get('p1').mime, 'image/png')
  assert.equal(jobs.get('other').status, 'idle')
})

test('202 in_progress re-POSTs after retry_after, then resolves', async () => {
  const responses = [{ status: 'in_progress', retry_after: 5 }, IMG]
  const waits = []
  const jobs = createReportImageJobs(async () => responses.shift(), { wait: async (ms) => { waits.push(ms) } })
  await jobs.start('p1')
  assert.equal(jobs.get('p1').status, 'done')
  assert.deepEqual(waits, [5000])
})

test('persistent 202 gives up as error (bounded POSTs)', async () => {
  let calls = 0
  const jobs = createReportImageJobs(async () => { calls++; return { status: 'in_progress', retry_after: 5 } }, noWait)
  await jobs.start('p1')
  assert.equal(jobs.get('p1').status, 'error')
  assert.equal(calls, 3)
})

test('transient failure gets one silent retry', async () => {
  let calls = 0
  const jobs = createReportImageJobs(async () => {
    calls++
    if (calls === 1) throw Object.assign(new Error('boom'), { status: 500 })
    return IMG
  }, noWait)
  await jobs.start('p1')
  assert.equal(calls, 2)
  assert.equal(jobs.get('p1').status, 'done')
})

test('two failures -> error; 429/400/404 are not retried', async () => {
  let calls = 0
  const jobs = createReportImageJobs(async () => { calls++; throw Object.assign(new Error('x'), { status: 500 }) }, noWait)
  assert.equal(await jobs.start('p1'), null)
  assert.equal(calls, 2)
  assert.equal(jobs.get('p1').status, 'error')

  for (const status of [429, 400, 404]) {
    let n = 0
    const j = createReportImageJobs(async () => { n++; throw Object.assign(new Error('x'), { status }) }, noWait)
    await j.start('p')
    assert.equal(n, 1, `status ${status}`)
    assert.equal(j.get('p').status, 'error')
  }
})

test('start() without id is a no-op; reset() clears state', async () => {
  const jobs = createReportImageJobs(async () => IMG, noWait)
  assert.equal(await jobs.start(null), null)
  await jobs.start('p1')
  jobs.reset()
  assert.equal(jobs.get('p1').status, 'idle')
})

test('total POSTs per job capped at 3 across 202 re-POSTs and error retries', async () => {
  // 500, then 202, then 202 -> 3 POSTs total, no 4th despite remaining attempt/loop budget
  const responses = [
    () => { throw Object.assign(new Error('boom'), { status: 500 }) },
    () => ({ status: 'in_progress', retry_after: 5 }),
    () => ({ status: 'in_progress', retry_after: 5 }),
    () => IMG,
  ]
  let calls = 0
  const jobs = createReportImageJobs(async () => responses[calls++](), noWait)
  await jobs.start('p1')
  assert.equal(calls, 3)
  assert.equal(jobs.get('p1').status, 'error')

  // two 500s: one silent retry only, then error
  let n = 0
  const j = createReportImageJobs(async () => {
    n++
    if (n < 3) throw Object.assign(new Error('x'), { status: 500 })
    return IMG
  }, noWait)
  await j.start('p')
  assert.equal(n, 2)
  assert.equal(j.get('p').status, 'error')
})

test('start() on a done job short-circuits without POST', async () => {
  let calls = 0
  const jobs = createReportImageJobs(async () => { calls++; return IMG }, noWait)
  await jobs.start('p1')
  const again = await jobs.start('p1')
  assert.equal(calls, 1)
  assert.equal(again.image_data, 'AAAA')
  assert.equal(jobs.get('p1').status, 'done')
})

test('regenerate: previous image kept while generating, replaced on success, first POST only carries regenerate', async () => {
  const opts = []
  const NEW = { image_data: 'BBBB', mime_type: 'image/jpeg' }
  const jobs = createReportImageJobs(async (id, o) => { opts.push(o.regenerate); return opts.length === 1 ? IMG : NEW }, noWait)
  await jobs.start('p1')
  const seen = []
  jobs.subscribe(() => { const j = jobs.get('p1'); seen.push([j.status, j.image, j.regen]) })
  const a = jobs.regenerate('p1')
  assert.equal(jobs.regenerate('p1'), a)   // joins in-flight, no second request
  assert.deepEqual(jobs.get('p1'), { status: 'generating', image: 'AAAA', mime: 'image/png', regen: true, regenFailed: false })
  await a
  assert.deepEqual(opts, [false, true])
  assert.deepEqual(seen, [['generating', 'AAAA', true], ['done', 'BBBB', false]])
  assert.equal(jobs.get('p1').mime, 'image/jpeg')
})

test('regenerate failure keeps the previous image and flags regenFailed; next attempt clears it', async () => {
  let fail = true
  const jobs = createReportImageJobs(async () => {
    if (fail) throw Object.assign(new Error('x'), { status: 429 })
    return { image_data: 'CCCC', mime_type: 'image/png' }
  }, noWait)
  fail = false
  await jobs.start('p1')
  fail = true
  assert.equal(await jobs.regenerate('p1'), null)
  const j = jobs.get('p1')
  assert.equal(j.status, 'done')
  assert.equal(j.image, 'CCCC')
  assert.equal(j.regen, false)
  assert.equal(j.regenFailed, true)
  fail = false
  const p = jobs.regenerate('p1')
  assert.equal(jobs.get('p1').regenFailed, false)
  await p
  assert.equal(jobs.get('p1').regenFailed, false)
})

test('regenerate: 202 in_progress re-POSTs WITH regenerate:true; first-generation 202 re-POSTs without it', async () => {
  const calls = []
  const responses = [IMG, { status: 'in_progress', retry_after: 5 }, { image_data: 'DDDD', mime_type: 'image/png' }]
  const waits = []
  const jobs = createReportImageJobs(async (id, o) => { calls.push(o.regenerate); return responses.shift() }, { wait: async ms => { waits.push(ms) } })
  await jobs.start('p1')
  await jobs.regenerate('p1')
  assert.deepEqual(calls, [false, true, true])
  assert.deepEqual(waits, [5000])
  assert.equal(jobs.get('p1').image, 'DDDD')
  assert.equal(jobs.get('p1').regenFailed, false)

  const c2 = []
  const r2 = [{ status: 'in_progress', retry_after: 5 }, IMG]
  const j2 = createReportImageJobs(async (id, o) => { c2.push(o.regenerate); return r2.shift() }, noWait)
  await j2.start('p2')
  assert.deepEqual(c2, [false, false])
})

test('regenerate with no previous entry (image came from the board) fails back to idle + regenFailed', async () => {
  const jobs = createReportImageJobs(async () => { throw Object.assign(new Error('x'), { status: 400 }) }, noWait)
  await jobs.regenerate('p1')
  assert.deepEqual(jobs.get('p1'), { status: 'idle', image: null, mime: null, regen: false, regenFailed: true })
})
