/**
 * utils/axisScores.js
 * Detects whether a persona report's axis_scores object was produced by the
 * legacy (pre-taste-spectrum) shape rather than the current shape.
 *
 * Legacy shape:  { form?, materiality, scale, energy, tradition: number|null }
 *                (flat numbers per axis, may include a 'form' key)
 * Current shape: { materiality|scale|energy|tradition: null | { score, dots,
 *                 n, iqr, confidence } }
 *
 * User decision (2026-09-28): the backend does not recompute old reports'
 * axis_scores — legacy stored shapes are shown as-is in the UI, with a small
 * notice rather than a re-derivation attempt.
 */

/**
 * @param {object|null|undefined} axisScores
 * @returns {boolean} true if axisScores is present and uses the legacy shape
 *   — i.e. it has a 'form' key, or any axis value is a plain number (rather
 *   than every present value being a { score, dots, ... } dict).
 */
export function isLegacyAxisScores(axisScores) {
  if (!axisScores || typeof axisScores !== 'object') return false
  if ('form' in axisScores) return true
  return Object.values(axisScores).some(v => typeof v === 'number')
}
