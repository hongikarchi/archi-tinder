/**
 * utils/reportStale.js
 * FULL-REPORT-UI-1: deleting liked buildings no longer regenerates the persona
 * report on the spot. The server flags the board `report_stale`; the owner's
 * next open of the report page regenerates it once.
 */

/** Stale flag from the board payload (server always sends a boolean; undefined = false). */
export function isReportStale(board) {
  if (!board) return false
  return board.report_stale === true
}

/**
 * Owner opens a board whose EXISTING report is stale and which still has liked
 * buildings. Never for a first generation: a report produced in this visit
 * (`hasLocalReport`) or one that arrived with the swipe-end save flow
 * (`freshlySaved`, report generated seconds ago for this very liked set) is fresh
 * by definition, so the "regenerating because of changes" flow must not run.
 */
export function shouldRegenerateOnOpen({ isOwner, board, hasLocalReport = false, freshlySaved = false }) {
  if (hasLocalReport || freshlySaved) return false
  return !!(isOwner && board && board.final_report && isReportStale(board) && board.liked_ids?.length > 0)
}

/**
 * Swipe session just completed (incl. a board resumed via "continue exploring").
 * Regenerate the persona report (+ image) only when a report ALREADY existed for
 * the board and the liked set grew during this session. A first generation
 * (`hadReport` false) keeps the normal non-regenerate path.
 *  - reportStale: `board.report_stale` re-fetched after the swipes (true = server
 *    says the liked set no longer matches the report). null/undefined = unknown.
 *  - newLikes: likes recorded since the session was resumed (local fallback; also
 *    covers legacy reports without a signature, which the server never flags stale).
 */
export function shouldRegenerateAfterSession({ hadReport, newLikes = 0, reportStale = null }) {
  if (!hadReport) return false
  return reportStale === true || newLikes > 0
}
