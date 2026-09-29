/**
 * utils/reportText.test.mjs
 * Unit tests for reportText.js using Node's built-in test runner (no extra deps).
 * Run with: node --test frontend/src/utils/reportText.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { localizeReport } from './reportText.js'

describe('localizeReport', () => {
  test('per-field fallback: uses i18n[language] field when present, falls back to top-level field when a field is missing from the block', () => {
    const report = {
      persona_type: 'TOP-LEVEL TYPE',
      one_liner: 'TOP-LEVEL LINE',
      pattern_paragraph: 'TOP-LEVEL PATTERN',
      description: 'TOP-LEVEL DESC',
      dominant_programs: ['museum'],
      i18n: {
        ko: {
          persona_type: 'KO TYPE',
          one_liner: 'KO LINE',
          // pattern_paragraph intentionally omitted — should fall back to top-level
          description: 'KO DESC',
        },
        en: {
          persona_type: 'EN TYPE',
          one_liner: 'EN LINE',
          pattern_paragraph: 'EN PATTERN',
          description: 'EN DESC',
        },
      },
    }

    const ko = localizeReport(report, 'ko')
    assert.equal(ko.persona_type, 'KO TYPE')
    assert.equal(ko.one_liner, 'KO LINE')
    assert.equal(ko.pattern_paragraph, 'TOP-LEVEL PATTERN') // fallback: missing from ko block
    assert.equal(ko.description, 'KO DESC')
    // dominant_* untouched
    assert.deepEqual(ko.dominant_programs, ['museum'])

    const en = localizeReport(report, 'en')
    assert.equal(en.persona_type, 'EN TYPE')
    assert.equal(en.one_liner, 'EN LINE')
    assert.equal(en.pattern_paragraph, 'EN PATTERN')
    assert.equal(en.description, 'EN DESC')
  })

  test('missing i18n block entirely: returns the report unchanged (old flat-model reports)', () => {
    const report = {
      persona_type: 'Old School',
      one_liner: 'a legacy one-liner',
      pattern_paragraph: 'legacy pattern',
      description: 'legacy description',
    }
    const result = localizeReport(report, 'en')
    assert.deepEqual(result, report)
  })

  test('missing language in i18n block: falls back to top-level fields for every text field', () => {
    const report = {
      persona_type: 'TOP TYPE',
      one_liner: 'TOP LINE',
      pattern_paragraph: 'TOP PATTERN',
      description: 'TOP DESC',
      i18n: {
        ko: { persona_type: 'KO TYPE', one_liner: 'KO LINE', pattern_paragraph: 'KO PATTERN', description: 'KO DESC' },
        // no 'en' block
      },
    }
    const result = localizeReport(report, 'en')
    assert.equal(result.persona_type, 'TOP TYPE')
    assert.equal(result.one_liner, 'TOP LINE')
    assert.equal(result.pattern_paragraph, 'TOP PATTERN')
    assert.equal(result.description, 'TOP DESC')
  })

  test('empty pattern_paragraph string in i18n block is honored (not treated as missing)', () => {
    const report = {
      pattern_paragraph: 'TOP PATTERN',
      i18n: { ko: { pattern_paragraph: '' } },
    }
    const result = localizeReport(report, 'ko')
    assert.equal(result.pattern_paragraph, '')
  })

  test('does not mutate the input report', () => {
    const report = {
      persona_type: 'TOP TYPE',
      i18n: { ko: { persona_type: 'KO TYPE' } },
    }
    const snapshot = JSON.stringify(report)
    localizeReport(report, 'ko')
    assert.equal(JSON.stringify(report), snapshot)
  })

  test('handles null/undefined report gracefully', () => {
    assert.equal(localizeReport(null, 'ko'), null)
    assert.equal(localizeReport(undefined, 'en'), undefined)
  })

  test('non-object report is returned unchanged', () => {
    assert.equal(localizeReport('not an object', 'ko'), 'not an object')
  })
})
