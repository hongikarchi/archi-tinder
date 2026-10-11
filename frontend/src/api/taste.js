/**
 * api/taste.js
 * Taste-start: tag recognition + top-3 card lookup (docs/decisions/2026-10-11-taste-start-redesign.md).
 * Tags are sent back EXACTLY as received — the server rebuilds them.
 */

import { callApi } from './core.js'
import { normalizeCard } from './images.js'

function normalizeCards(list) {
  return (list || []).map(c => ({
    card: normalizeCard(c.card),
    matched_keys: c.matched_keys || [],
    hit: c.hit ?? 0,
    total: c.total ?? 0,
  })).filter(c => c.card)
}

/** POST /taste/recognize/ -> { source, tags, cards } (throttled 10/min -> status 429). */
export async function recognizeTaste({ text, prevTags = [], excludeIds = [] }) {
  const res = await callApi('POST', '/taste/recognize/', {
    text,
    prev_tags: prevTags,
    exclude_ids: excludeIds.slice(0, 100),
  }, true, 20000)
  return { source: res.source, tags: res.tags || [], cards: normalizeCards(res.cards) }
}

/** POST /taste/cards/ -> next 3 cards for the same tags ("다시 찾기"). */
export async function findTasteCards({ tags, excludeIds = [] }) {
  const res = await callApi('POST', '/taste/cards/', {
    tags,
    exclude_ids: excludeIds.slice(0, 100),
  }, true, 20000)
  return normalizeCards(res.cards)
}
