/**
 * utils/socialFeed.js — pure logic for the /people board feed.
 * Kept DOM-free so it can be unit-tested with node:test.
 */

/** Index of the first tile in the grid row that contains `index`. */
export function rowStartIndex(index, cols) {
  const c = Math.max(1, Math.floor(cols) || 1)
  return Math.floor(index / c) * c
}

/**
 * Display order while a card is expanded: the expanded card is inserted at the
 * START of its own row (its left siblings drop below it, in order). Returns a
 * new array; the input is never mutated. No-op when nothing is expanded, the id
 * is unknown, or the card already starts its row.
 */
export function reorderForExpanded(list, expandedId, cols) {
  if (expandedId == null) return list
  const i = list.findIndex(b => b.board_id === expandedId)
  if (i < 0) return list
  const rs = rowStartIndex(i, cols)
  if (i === rs) return list
  const next = list.slice()
  const [item] = next.splice(i, 1)
  next.splice(rs, 0, item)
  return next
}

/** Append a page, dropping boards already present (keyed by board_id). */
export function mergePages(prev, incoming) {
  const seen = new Set(prev.map(b => b.board_id))
  const out = prev.slice()
  for (const b of incoming || []) {
    if (!b || seen.has(b.board_id)) continue
    seen.add(b.board_id)
    out.push(b)
  }
  return out
}

/** Immutable patch of one board's reaction state. */
export function patchReaction(list, boardId, patch) {
  return list.map(b => (b.board_id === boardId ? { ...b, ...patch } : b))
}

/** Optimistic like toggle result for a board (count never goes below 0). */
export function toggledReaction(board) {
  const reacted = !board.is_reacted
  const base = Number(board.reaction_count) || 0
  return {
    is_reacted: reacted,
    reaction_count: Math.max(0, base + (reacted ? 1 : -1)),
  }
}
