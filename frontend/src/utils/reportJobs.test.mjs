/**
 * utils/reportJobs.test.mjs
 * In-flight report regeneration store: dedupe + leader-only afterSuccess.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createReportJobs } from './reportJobs.js'

const DATA = { final_report: { persona_type: 'x' }, axis_scores: {} }

test('concurrent regenerate joins the running promise (one POST), afterSuccess once', async () => {
  let calls = 0
  let release
  const gate = new Promise(r => { release = r })
  const jobs = createReportJobs(async (id, o) => { calls++; assert.equal(o.regenerate, true); await gate; return DATA })
  let after = 0
  const a = jobs.regenerate('p1', { afterSuccess: () => { after++ } })
  const b = jobs.regenerate('p1', { afterSuccess: () => { after += 10 } })
  assert.equal(a, b)
  assert.equal(jobs.isRegenerating('p1'), true)
  release()
  assert.equal(await a, DATA)
  assert.equal(calls, 1)
  assert.equal(after, 1)
  assert.equal(jobs.isRegenerating('p1'), false)
})

test('after settling, a new regenerate starts a fresh job', async () => {
  let calls = 0
  const jobs = createReportJobs(async () => { calls++; return DATA })
  await jobs.regenerate('p1')
  await jobs.regenerate('p1')
  assert.equal(calls, 2)
})

test('failure rejects all joiners, clears in-flight, skips afterSuccess; empty report skips it too', async () => {
  let after = 0
  const jobs = createReportJobs(async () => { throw new Error('boom') })
  const a = jobs.regenerate('p1', { afterSuccess: () => { after++ } })
  const b = jobs.regenerate('p1')
  await assert.rejects(a, /boom/)
  await assert.rejects(b, /boom/)
  assert.equal(jobs.isRegenerating('p1'), false)
  const j2 = createReportJobs(async () => ({ final_report: null }))
  await j2.regenerate('p', { afterSuccess: () => { after++ } })
  assert.equal(after, 0)
})

test('afterSuccess throwing does not break the job; missing id rejects', async () => {
  const jobs = createReportJobs(async () => DATA)
  const orig = console.error
  console.error = () => {}
  try {
    assert.equal(await jobs.regenerate('p1', { afterSuccess: () => { throw new Error('x') } }), DATA)
  } finally { console.error = orig }
  await assert.rejects(jobs.regenerate(null))
})
