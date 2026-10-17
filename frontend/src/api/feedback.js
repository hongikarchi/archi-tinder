/**
 * api/feedback.js
 * Taste-start feedback: per-card reports and per-round (query) reports.
 * Tags are sent exactly as received from /taste/recognize/ (incl. prob).
 */

import { callApi } from './core.js'

/** POST /feedback/card-reports/ — create or edit the report for (round_key, canonical_bld_id). */
export function submitCardReport(payload) {
  return callApi('POST', '/feedback/card-reports/', payload)
}

/** POST /feedback/card-reports/cancel/ -> 204. */
export function cancelCardReport({ round_key, canonical_bld_id }) {
  return callApi('POST', '/feedback/card-reports/cancel/', { round_key, canonical_bld_id })
}

/** POST /feedback/query-reports/ — one report per round, edited in place. */
export function submitQueryReport(payload) {
  return callApi('POST', '/feedback/query-reports/', payload)
}

/** POST /feedback/query-reports/cancel/ -> 204. */
export function cancelQueryReport({ round_key }) {
  return callApi('POST', '/feedback/query-reports/cancel/', { round_key })
}
