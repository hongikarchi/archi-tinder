/**
 * personalityTypes.js
 * 16-type personality code system for ArchiTinder.
 * {C,R} × {L,S} × {O,D} × {N,T} = 16 combinations
 * C=개념적, R=실무적, L=리더, S=서포터, O=협업, D=독립, N=혁신, T=전통
 */

export const TYPE_CODES = [
  'CLON', 'CLOT', 'CLDN', 'CLDT',
  'CSON', 'CSOT', 'CSDN', 'CSDT',
  'RLON', 'RLOT', 'RLDN', 'RLDT',
  'RSON', 'RSOT', 'RSDN', 'RSDT',
]

// TYPE_LABELS (Korean-literal map) is retired — its sole consumer
// (AssessmentPage.jsx result screen) now resolves display text via i18n key
// `personality.types.<code>` (frontend/src/i18n/locales.js), gated by
// TYPE_CODES.includes(code) with `personality.typeFallback` as the fallback.

// Localized at render sites via i18n key `personality.axis.<key>`
// (frontend/src/i18n/locales.js). AXIS_LABELS (Korean literals) is retired —
// PentagonChart.jsx now maps AXIS_KEYS through useTranslation()'s t().
export const AXIS_KEYS = ['workStyle', 'role', 'collaboration', 'approach', 'decisionSpeed']

/** Derive a type code from a 5-element vector (each -1..+1). */
export function vectorToTypeCode(vector) {
  if (!vector || vector.length < 4) return null
  const c = vector[0] > 0 ? 'C' : 'R'
  const l = vector[1] > 0 ? 'L' : 'S'
  const o = vector[2] > 0 ? 'O' : 'D'
  const n = vector[3] > 0 ? 'N' : 'T'
  return `${c}${l}${o}${n}`
}
