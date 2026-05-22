import { callApi } from './core.js'
import { normalizeCard } from './images.js'

const DISCOVERY_TIMEOUT_MS = 30000      // discovery feed can be slow on cold backend (~8s+)

export async function fetchDiscoveryFeed(cursor = 0, limit = 12) {
  const data = await callApi('GET', `/discovery/?cursor=${cursor}&limit=${limit}`, undefined, true, DISCOVERY_TIMEOUT_MS)
  return {
    cards: (data.cards || []).map(normalizeCard),
    nextCursor: data.next_cursor,
    hasMore: !!data.has_more,
    tasteState: data.taste_state || 'cold',
  }
}

export async function fetchBoardSurprise() {
  const data = await callApi('GET', '/recommendations/board-surprise/')
  return {
    cards: (data.cards || []).map(normalizeCard),
    title: data.title || 'Curated for you',
    rationale: data.rationale || '',
  }
}
