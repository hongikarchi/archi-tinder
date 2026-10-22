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

/** Owner opens a board whose report is stale and which still has liked buildings. */
export function shouldRegenerateOnOpen({ isOwner, board }) {
  return !!(isOwner && board && board.final_report && isReportStale(board) && board.liked_ids?.length > 0)
}
