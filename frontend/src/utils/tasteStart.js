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

/** Ignore arrow keys while typing. */
export function isTypingTarget(el) {
  if (!el) return false
  const tag = (el.tagName || '').toLowerCase()
  return tag === 'input' || tag === 'textarea' || el.isContentEditable === true
}
