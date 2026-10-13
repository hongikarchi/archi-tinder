/** Pure helpers for the taste-start page (unit-tested in tasteStart.test.mjs). */

/** Clamp card index to [0, count-1] — no wrap-around. */
export function clampIndex(i, count) {
  if (!count || count < 1) return 0
  return Math.max(0, Math.min(count - 1, i))
}

/** dir: +1 = next (1->3), -1 = previous (3->1). */
export function stepIndex(i, dir, count) {
  return clampIndex(i + dir, count)
}

/** Does the card's matched_keys contain this tag's [axis, value]? */
export function tagMatches(tag, matchedKeys) {
  const want = JSON.stringify(tag.value)
  return (matchedKeys || []).some(k => k && k[0] === tag.axis && JSON.stringify(k[1]) === want)
}

/** Chips shown for a round: want-polarity tags only, each with matched flag. */
export function buildChips(tags, matchedKeys) {
  return (tags || [])
    .filter(t => t.polarity !== 'exclude')
    .map(t => ({ tag: t, matched: tagMatches(t, matchedKeys) }))
}

/** Stable identity of a tag (value may be a list for year tags). */
export function tagKey(tag) {
  return `${tag.axis}:${JSON.stringify(tag.value)}`
}

/** Cards of a round that are not reported (the deck the user starts swiping with). */
export function keptCards(cards, reports) {
  const r = reports || {}
  return (cards || []).filter(c => !r[c.card.image_id])
}

/**
 * Start-swiping payload. startIds = non-reported round cards in order;
 * excludeIds = shown minus startIds, capped to the last `max`, with reported
 * ids placed last so they always survive the cap.
 */
export function buildStartDeck({ cards, shown, reports, max = 100 }) {
  const r = reports || {}
  const startIds = keptCards(cards, r).map(c => c.card.image_id)
  const startSet = new Set(startIds)
  const reportedSet = new Set(Object.keys(r))
  const rest = (shown || []).filter(id => !startSet.has(id) && !reportedSet.has(id))
  const reported = [...new Set([
    ...(shown || []).filter(id => reportedSet.has(id) && !startSet.has(id)),
    ...[...reportedSet].filter(id => !startSet.has(id)),
  ])]
  return { startIds, excludeIds: [...rest, ...reported].slice(-max) }
}

/** Ignore arrow keys while typing. */
export function isTypingTarget(el) {
  if (!el) return false
  const tag = (el.tagName || '').toLowerCase()
  return tag === 'input' || tag === 'textarea' || el.isContentEditable === true
}
