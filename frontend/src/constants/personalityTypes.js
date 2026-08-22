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

export const TYPE_LABELS = {
  CLON: '개념적 협업 리더 — 혁신형',
  CLOT: '개념적 협업 리더 — 전통형',
  CLDN: '개념적 독립 리더 — 혁신형',
  CLDT: '개념적 독립 리더 — 전통형',
  CSON: '개념적 협업 서포터 — 혁신형',
  CSOT: '개념적 협업 서포터 — 전통형',
  CSDN: '개념적 독립 서포터 — 혁신형',
  CSDT: '개념적 독립 서포터 — 전통형',
  RLON: '실무적 협업 리더 — 혁신형',
  RLOT: '실무적 협업 리더 — 전통형',
  RLDN: '실무적 독립 리더 — 혁신형',
  RLDT: '실무적 독립 리더 — 전통형',
  RSON: '실무적 협업 서포터 — 혁신형',
  RSOT: '실무적 협업 서포터 — 전통형',
  RSDN: '실무적 독립 서포터 — 혁신형',
  RSDT: '실무적 독립 서포터 — 전통형',
}

export const AXIS_LABELS = ['작업방식', '역할성향', '협업방식', '접근태도', '결정속도']

/** Derive a type code from a 5-element vector (each -1..+1). */
export function vectorToTypeCode(vector) {
  if (!vector || vector.length < 4) return null
  const c = vector[0] > 0 ? 'C' : 'R'
  const l = vector[1] > 0 ? 'L' : 'S'
  const o = vector[2] > 0 ? 'O' : 'D'
  const n = vector[3] > 0 ? 'N' : 'T'
  return `${c}${l}${o}${n}`
}
