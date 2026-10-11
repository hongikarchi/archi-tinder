/**
 * utils/contestDeadline.test.mjs — node --test src/utils/contestDeadline.test.mjs
 * D-day is a KST calendar-date difference, independent of the device timezone.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  nextDeadline,
  ddayKst,
  isClosed,
  formatKstDateTime,
  formatKstDate,
} from './contestDeadline.js'

const d = s => new Date(s)

describe('ddayKst — KST calendar-date based', () => {
  const deadline = d('2026-10-14T17:00:00+09:00')

  test('KST 10/13 23:59 -> 1', () => {
    assert.equal(ddayKst(deadline, d('2026-10-13T14:59:00Z')), 1)
  })
  test('KST 10/14 00:00 -> 0 (midnight boundary)', () => {
    assert.equal(ddayKst(deadline, d('2026-10-13T15:00:00Z')), 0)
  })
  test('KST 10/14 16:59 -> 0 (same day, before the deadline)', () => {
    assert.equal(ddayKst(deadline, d('2026-10-14T07:59:00Z')), 0)
  })
  test('KST 10/15 00:00 -> -1', () => {
    assert.equal(ddayKst(deadline, d('2026-10-14T15:00:00Z')), -1)
  })
  test('UTC date and KST date differ on both sides -> 0', () => {
    // deadline 18:00 KST = 09:00Z (same UTC date); now = 16:00Z on 10/27 = KST 10/28 01:00
    assert.equal(ddayKst(d('2026-10-28T18:00:00+09:00'), d('2026-10-27T16:00:00Z')), 0)
    // deadline 01:00 KST 10/28 = 16:00Z on 10/27 (UTC date earlier); now 10/27 20:00Z = KST 10/28 05:00
    assert.equal(ddayKst(d('2026-10-28T01:00:00+09:00'), d('2026-10-27T20:00:00Z')), 0)
  })
  test('invalid input -> null', () => {
    assert.equal(ddayKst('nope', new Date()), null)
  })
})

describe('정림 row — apply -> submission switch', () => {
  const junglim = {
    apply_deadline: '2027-01-04T23:59:00+09:00',
    submission_deadline: '2027-01-11T23:59:00+09:00',
  }
  const at = now => {
    const nd = nextDeadline(junglim, d(now))
    return { kind: nd.kind, dday: ddayKst(nd.at, d(now)), closed: isClosed(junglim, d(now)) }
  }

  test('well before -> apply', () => {
    assert.equal(at('2026-12-01T12:00:00+09:00').kind, 'apply')
  })
  test('01/04 23:58 -> apply, D-day 0', () => {
    const r = at('2027-01-04T23:58:00+09:00')
    assert.equal(r.kind, 'apply')
    assert.equal(r.dday, 0)
    assert.equal(r.closed, false)
  })
  test('01/05 00:00 -> submission, D-6', () => {
    const r = at('2027-01-05T00:00:00+09:00')
    assert.equal(r.kind, 'submission')
    assert.equal(r.dday, 6)
    assert.equal(r.closed, false)
  })
  test('01/12 00:00 -> submission, -1, closed', () => {
    const r = at('2027-01-12T00:00:00+09:00')
    assert.equal(r.kind, 'submission')
    assert.equal(r.dday, -1)
    assert.equal(r.closed, true)
  })
})

describe('nextDeadline — no apply deadline', () => {
  test('apply_deadline null -> submission', () => {
    const c = { apply_deadline: null, submission_deadline: '2026-12-28T18:00:00+09:00' }
    const nd = nextDeadline(c, d('2026-10-10T00:00:00Z'))
    assert.equal(nd.kind, 'submission')
    assert.equal(nd.at.toISOString(), '2026-12-28T09:00:00.000Z')
  })
  test('missing submission -> null', () => {
    assert.equal(nextDeadline({}, new Date()), null)
  })
})

describe('isClosed', () => {
  const c = { submission_deadline: '2026-10-14T17:00:00+09:00' }
  test('open before, closed at and after the instant', () => {
    assert.equal(isClosed(c, d('2026-10-14T07:59:59Z')), false)
    assert.equal(isClosed(c, d('2026-10-14T08:00:00Z')), true)
    assert.equal(isClosed(c, d('2026-10-15T00:00:00Z')), true)
  })
})

describe('formatting — always KST', () => {
  test('ko / en date-time', () => {
    assert.equal(formatKstDateTime('2026-10-28T09:00:00Z', 'ko'), '2026.10.28 (수) 18:00')
    assert.equal(formatKstDateTime('2026-10-28T09:00:00Z', 'en'), 'Wed, Oct 28, 2026, 18:00 KST')
  })
  test('crosses the date line into the next KST day', () => {
    assert.equal(formatKstDateTime('2026-10-27T16:00:00Z', 'ko'), '2026.10.28 (수) 01:00')
  })
  test('date-only strings are KST calendar dates', () => {
    assert.equal(formatKstDate('2026-11-02', 'ko'), '2026.11.02 (월)')
    assert.equal(formatKstDate('2026-11-02', 'en'), 'Mon, Nov 2, 2026')
  })
  test('invalid -> empty string', () => {
    assert.equal(formatKstDateTime('garbage', 'ko'), '')
    assert.equal(formatKstDate(null, 'ko'), '')
  })
})

describe('device timezone independence', () => {
  const original = process.env.TZ
  const run = () => {
    const c = {
      apply_deadline: '2027-01-04T23:59:00+09:00',
      submission_deadline: '2027-01-11T23:59:00+09:00',
    }
    const out = []
    for (const now of [
      '2026-10-13T14:59:00Z', '2026-10-13T15:00:00Z', '2026-10-14T07:59:00Z', '2026-10-14T15:00:00Z',
      '2027-01-04T23:58:00+09:00', '2027-01-05T00:00:00+09:00', '2027-01-12T00:00:00+09:00',
    ]) {
      const nd = nextDeadline(c, d(now))
      out.push([nd.kind, ddayKst(nd.at, d(now)), isClosed(c, d(now))])
    }
    out.push(ddayKst(d('2026-10-14T17:00:00+09:00'), d('2026-10-13T14:59:00Z')))
    out.push(ddayKst(d('2026-10-28T18:00:00+09:00'), d('2026-10-27T16:00:00Z')))
    out.push(formatKstDateTime('2026-10-27T16:00:00Z', 'ko'))
    out.push(formatKstDate('2026-11-02', 'en'))
    return JSON.stringify(out)
  }

  test('identical results under America/Los_Angeles, Asia/Seoul, UTC, Pacific/Kiritimati', () => {
    try {
      const results = ['America/Los_Angeles', 'Asia/Seoul', 'UTC', 'Pacific/Kiritimati'].map(tz => {
        process.env.TZ = tz
        return run()
      })
      for (const r of results) assert.equal(r, results[0])
    } finally {
      if (original === undefined) delete process.env.TZ
      else process.env.TZ = original
    }
  })
})
