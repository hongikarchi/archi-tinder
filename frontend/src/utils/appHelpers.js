export function normalizeFilters(filters) {
  if (!filters) return {}
  const out = {}
  // Structured filters from LLM parse-query -- pass through
  if (filters.program) out.program = filters.program
  if (filters.location_country) out.location_country = filters.location_country
  if (filters.material) out.material = filters.material
  if (filters.style) out.style = filters.style
  if (filters.year_min != null) out.year_min = filters.year_min
  if (filters.year_max != null) out.year_max = filters.year_max
  return out
}

/**
 * Classify a swipe/extend error into { message, kind }.
 * kind: 'network' | 'auth' | 'client' | 'server'
 * message: Korean user-facing string, or null for auth (navigate handles it).
 */
export function classifySwipeError(e) {
  const status = e?.status
  if (!status || e instanceof TypeError || e?.message?.includes('Network')) {
    return { kind: 'network', message: '네트워크 연결을 확인해주세요. 다시 시도합니다…' }
  }
  if (status === 401 || status === 403) {
    return { kind: 'auth', message: null }
  }
  if (status >= 500) {
    return { kind: 'server', message: `서버 오류 — 잠시 후 다시 시도해주세요. (${status})` }
  }
  return { kind: 'client', message: `잘못된 요청입니다. (${status})` }
}

// Action cards have image_url = '' and don't need image preload.
// Treat them as "always instant-swappable" so they advance the queue smoothly.
export function isActionCard(card) {
  return !!card && (card.card_type === 'action' || card.image_id === '__action_card__')
}

// Backend changed Project.liked_ids shape: list[str] -> list[{id, intensity}].
// This helper accepts either shape and returns plain id strings, so older sessions
// (pre-migration data still in browser cache) and new responses both work.
export function extractLikedIds(rawLikedIds) {
  if (!Array.isArray(rawLikedIds)) return []
  return rawLikedIds
    .map(entry => (typeof entry === 'string' ? entry : entry?.id))
    .filter(Boolean)
}

// Backend saved_ids shape: list[{id: str, saved_at: datetime}].
// Returns plain id strings.
export function extractSavedIds(rawSavedIds) {
  if (!Array.isArray(rawSavedIds)) return []
  return rawSavedIds
    .map(entry => (typeof entry === 'string' ? entry : entry?.id))
    .filter(Boolean)
}
