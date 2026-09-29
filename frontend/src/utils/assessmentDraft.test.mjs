/**
 * utils/assessmentDraft.test.mjs
 * Unit tests for assessmentDraft.js using Node's built-in test runner (no extra
 * deps), matching loginFlow.test.mjs.
 * Run with: node --test frontend/src/utils/assessmentDraft.test.mjs
 */
import { test, describe, beforeEach } from 'node:test'
import assert from 'node:assert/strict'

// The module reads window.localStorage. Node has neither, so stand up a minimal
// stub BEFORE importing it (the module only touches it inside functions, but
// keeping the order explicit avoids depending on that).
const store = new Map()
globalThis.window = {
  localStorage: {
    getItem: k => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: k => store.delete(k),
  },
}

const {
  assessmentDraftKey,
  loadAssessmentDraft,
  saveAssessmentDraft,
  clearAssessmentDraft,
} = await import('./assessmentDraft.js')

const TOTAL = 20
const USER = '42'
const KEY = assessmentDraftKey(USER)

function blank() {
  return Array(TOTAL).fill(null)
}
function partial(answeredCount) {
  const r = blank()
  for (let i = 0; i < answeredCount; i++) r[i] = 1
  return r
}

beforeEach(() => store.clear())

describe('saveAssessmentDraft / loadAssessmentDraft round-trip', () => {
  test('mid-assessment progress is restored exactly', () => {
    saveAssessmentDraft(USER, { currentQ: 7, responses: partial(7) })
    const got = loadAssessmentDraft(USER, TOTAL)
    assert.equal(got.currentQ, 7)
    assert.deepEqual(got.responses, partial(7))
  })

  test('negative Likert values survive (reversed questions store -1/-2)', () => {
    const r = blank()
    r[0] = -2
    r[1] = 0
    saveAssessmentDraft(USER, { currentQ: 2, responses: r })
    assert.deepEqual(loadAssessmentDraft(USER, TOTAL).responses.slice(0, 2), [-2, 0])
  })

  test('an untouched assessment is not stored', () => {
    saveAssessmentDraft(USER, { currentQ: 0, responses: blank() })
    assert.equal(store.has(KEY), false)
    assert.equal(loadAssessmentDraft(USER, TOTAL), null)
  })

  test('drafts are scoped per user', () => {
    saveAssessmentDraft(USER, { currentQ: 5, responses: partial(5) })
    assert.equal(loadAssessmentDraft('99', TOTAL), null)
  })
})

describe('a fresh assessment starts at question 1', () => {
  test('no draft → null', () => {
    assert.equal(loadAssessmentDraft(USER, TOTAL), null)
  })

  test('clear() removes the draft so the next run starts over', () => {
    saveAssessmentDraft(USER, { currentQ: 19, responses: partial(20) })
    clearAssessmentDraft(USER)
    assert.equal(loadAssessmentDraft(USER, TOTAL), null)
  })
})

describe('untrusted stored values fall back to a clean start', () => {
  const cases = {
    'unparseable JSON': '{not json',
    'not an object': '"hello"',
    'null payload': 'null',
    'responses missing': JSON.stringify({ currentQ: 3 }),
    'responses not an array': JSON.stringify({ currentQ: 3, responses: 'abc' }),
    'currentQ missing': JSON.stringify({ responses: Array(TOTAL).fill(null) }),
    'currentQ not an integer': JSON.stringify({ currentQ: 1.5, responses: Array(TOTAL).fill(1) }),
    'currentQ negative': JSON.stringify({ currentQ: -1, responses: Array(TOTAL).fill(1) }),
    'currentQ past the end': JSON.stringify({ currentQ: TOTAL, responses: Array(TOTAL).fill(1) }),
    'response value not numeric': JSON.stringify({
      currentQ: 2,
      responses: Array(TOTAL).fill(null).map((v, i) => (i === 0 ? 'x' : v)),
    }),
    // Hand-written JSON: JSON.stringify() turns NaN/Infinity into null, so a
    // non-finite value can only reach storage as a literal like 1e999, which
    // JSON.parse revives as Infinity. This is what Number.isFinite guards.
    'response value non-finite': `{"currentQ":2,"responses":[1e999,${Array(TOTAL - 1).fill('null').join(',')}]}`,
  }
  for (const [label, raw] of Object.entries(cases)) {
    test(label, () => {
      store.set(KEY, raw)
      assert.equal(loadAssessmentDraft(USER, TOTAL), null)
    })
  }

  test('draft from a different question-bank size is discarded', () => {
    // Written when the bank had 20 items; reading with 25 must not resume,
    // because the indices no longer line up.
    saveAssessmentDraft(USER, { currentQ: 7, responses: partial(7) })
    assert.equal(loadAssessmentDraft(USER, 25), null)
  })
})

describe('missing user id is a no-op, never a throw', () => {
  test('load', () => assert.equal(loadAssessmentDraft(null, TOTAL), null))
  test('save', () => {
    saveAssessmentDraft(null, { currentQ: 3, responses: partial(3) })
    assert.equal(store.size, 0)
  })
  test('clear', () => assert.doesNotThrow(() => clearAssessmentDraft(null)))
})

describe('storage failures never break the assessment', () => {
  test('setItem throwing (quota / private mode) is swallowed', () => {
    const original = globalThis.window.localStorage.setItem
    globalThis.window.localStorage.setItem = () => { throw new Error('QuotaExceededError') }
    assert.doesNotThrow(() =>
      saveAssessmentDraft(USER, { currentQ: 3, responses: partial(3) })
    )
    globalThis.window.localStorage.setItem = original
  })

  test('getItem throwing returns null instead of propagating', () => {
    const original = globalThis.window.localStorage.getItem
    globalThis.window.localStorage.getItem = () => { throw new Error('SecurityError') }
    assert.equal(loadAssessmentDraft(USER, TOTAL), null)
    globalThis.window.localStorage.getItem = original
  })
})
