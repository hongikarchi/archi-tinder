/**
 * api/contests.js
 * Real contests (공모전): list / detail, interest toggle.
 * Design: docs/decisions/2026-10-09-contest-real-data.md
 */

import { callApi } from './core.js'
import { VerifyRequiredError } from './projects.js'

/**
 * Same 403 verify_required contract the project write endpoints use: dispatch
 * the global VerifyGateModal event and throw the typed error. Any other error
 * is left for the caller's own catch block.
 */
function throwIfVerifyRequired(err) {
  if (err?.status === 403 && err?.data?.detail === 'verify_required') {
    const reason = err?.data?.reason || 'verify_required'
    window.dispatchEvent(new CustomEvent('archithon:verify-required', { detail: { reason } }))
    throw new VerifyRequiredError(reason)
  }
}

/** GET contests/ → { results: [Contest] } (published, not past submission, soonest first). */
export async function listContests() {
  return await callApi('GET', '/contests/')
}

/** GET contests/<id>/ → Contest. 404 for hidden / pending / missing rows. */
export async function getContest(contestId) {
  return await callApi('GET', `/contests/${encodeURIComponent(contestId)}/`)
}

/** POST contests/<id>/interest/ → { interest_count, interested: true } */
export async function addContestInterest(contestId) {
  try {
    return await callApi('POST', `/contests/${encodeURIComponent(contestId)}/interest/`)
  } catch (err) {
    throwIfVerifyRequired(err)
    throw err
  }
}

/** DELETE contests/<id>/interest/ → 204 (null) */
export async function removeContestInterest(contestId) {
  try {
    return await callApi('DELETE', `/contests/${encodeURIComponent(contestId)}/interest/`)
  } catch (err) {
    throwIfVerifyRequired(err)
    throw err
  }
}
