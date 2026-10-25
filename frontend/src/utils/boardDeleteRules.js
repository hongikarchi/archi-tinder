/**
 * utils/boardDeleteRules.js
 * FULL-REPORT-UI-1: a board's persona report is built from its LIKED buildings,
 * so the last remaining liked building can never be deleted (the server rejects
 * it with 400 `last_liked_building`). Saved-only buildings are never restricted.
 */

const idOf = item => String(item?.id ?? item)

/** Server error body detail for the rule above. */
export const LAST_LIKED_DETAIL = 'last_liked_building'

/** True when `err` (callApi error: { status, data }) is the server's last-liked-building rejection. */
export function isLastLikedError(err) {
  return err?.status === 400 && (err?.data?.detail === LAST_LIKED_DETAIL || err?.message === LAST_LIKED_DETAIL)
}

/**
 * May `candidateId` be added to the delete selection?
 *   likedIds     board liked ids (strings or {id})
 *   deletedIds   liked ids already deleted this session (iterable)
 *   selectedIds  currently selected ids (iterable)
 *   candidateId  tile being toggled ON
 * Refused only when selecting it would select ALL remaining liked buildings.
 */
export function canSelectForDelete({ likedIds = [], deletedIds = [], selectedIds = [], candidateId }) {
  const deleted = new Set([...deletedIds].map(idOf))
  const remaining = new Set([...likedIds].map(idOf).filter(id => !deleted.has(id)))
  const cand = idOf(candidateId)
  if (!remaining.has(cand)) return true                 // saved-only (or already gone): unrestricted
  const selectedLiked = new Set([...selectedIds].map(idOf).filter(id => remaining.has(id)))
  selectedLiked.add(cand)
  return selectedLiked.size < remaining.size
}
