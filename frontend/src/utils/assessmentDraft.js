/**
 * assessmentDraft.js — resume state for the 20-question personality assessment.
 *
 * Storage choice follows this repo's existing split (see App.jsx):
 *   - localStorage `archithon_<thing>_${userId}`  → durable per-user progress
 *     (`archithon_projects_`, `archithon_activeId_`, `archithon_currentCard_`)
 *   - sessionStorage                              → transient per-tab deck state
 *     (`discovery_deck_v2`, `discovery_seen_ids`, …)
 *
 * A half-finished assessment is durable per-user progress, so it goes in
 * localStorage keyed by user. sessionStorage would survive a refresh but not a
 * closed tab, and the whole point of this is that people finish the assessment.
 *
 * The draft is written while answering and REMOVED on successful submit, so a
 * fresh assessment always starts at question 1 — a completed run leaves nothing
 * behind to resume.
 *
 * No TTL, matching `archithon_currentCard_*`: an abandoned draft resuming weeks
 * later is the desired behaviour ("이어서 진행"), not a staleness bug.
 */

const PREFIX = 'archithon_assessment_'

export function assessmentDraftKey(userId) {
  return `${PREFIX}${userId}`
}

/**
 * Read a resumable draft. Returns null whenever the stored value cannot be
 * trusted, so the caller falls back to a clean start rather than throwing or
 * restoring a half-valid state.
 *
 * `total` is the current question count; a draft written against a different
 * question bank is discarded (indices and the response array would no longer
 * line up after the bank changes).
 */
export function loadAssessmentDraft(userId, total) {
  if (!userId || typeof window === 'undefined') return null
  let parsed
  try {
    const raw = window.localStorage.getItem(assessmentDraftKey(userId))
    if (!raw) return null
    parsed = JSON.parse(raw)
  } catch {
    return null // unparseable → treat as no draft
  }
  if (!parsed || typeof parsed !== 'object') return null

  const { currentQ, responses } = parsed
  if (!Array.isArray(responses) || responses.length !== total) return null
  const responsesValid = responses.every(
    v => v === null || (typeof v === 'number' && Number.isFinite(v))
  )
  if (!responsesValid) return null
  if (!Number.isInteger(currentQ) || currentQ < 0 || currentQ >= total) return null

  // Nothing actually answered and sitting on the first card is not a resume —
  // report it as absent so the caller does not show "이어서 진행" for a no-op.
  if (currentQ === 0 && responses.every(v => v === null)) return null

  return { currentQ, responses }
}

/**
 * Persist progress. Writes only when there is something to resume; an untouched
 * assessment clears the slot instead of storing an empty draft.
 */
export function saveAssessmentDraft(userId, { currentQ, responses }) {
  if (!userId || typeof window === 'undefined') return
  const key = assessmentDraftKey(userId)
  const nothingToResume = currentQ === 0 && responses.every(v => v === null)
  try {
    if (nothingToResume) {
      window.localStorage.removeItem(key)
    } else {
      window.localStorage.setItem(key, JSON.stringify({ currentQ, responses }))
    }
  } catch {
    // Quota or private-mode failures must never break the assessment; losing
    // resume is acceptable, blocking the user is not.
  }
}

/** Drop the draft — called once the assessment is submitted successfully. */
export function clearAssessmentDraft(userId) {
  if (!userId || typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(assessmentDraftKey(userId))
  } catch {
    // ignore — see saveAssessmentDraft
  }
}
