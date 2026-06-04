import { callApi } from './core.js'
import { normalizeCard } from './images.js'

const DISCOVERY_TIMEOUT_MS = 30000      // discovery feed can be slow on cold backend (~8s+)

export async function fetchDiscoveryFeed(bufferIds = []) {
  const queryParam = bufferIds.length > 0 ? `?buffer=${bufferIds.join(',')}` : ''
  const data = await callApi('GET', `/discovery/${queryParam}`, undefined, true, DISCOVERY_TIMEOUT_MS)
  return {
    cards: (data.cards || []).map(normalizeCard),
    tier: data.tier ?? null,
    tasteState: data.taste_state || 'cold',
  }
}

export async function discoveryFeedback(canonicalBldId, action) {
  const data = await callApi('POST', '/discovery/feedback/', { canonical_bld_id: canonicalBldId, action })
  return {
    draftLikeCount: data.draft_like_count ?? 0,
    draftPassCount: data.draft_pass_count ?? 0,
  }
}

export async function promoteToTaste() {
  // Returns the raw session payload (same shape as POST /analysis/sessions/).
  // App.jsx's applySessionResponse + custom event handler consume this directly.
  return callApi('POST', '/discovery/promote-to-taste/', {})
}

export async function fetchBoardSurprise() {
  const data = await callApi('GET', '/recommendations/board-surprise/')
  return {
    cards: (data.cards || []).map(normalizeCard),
    title: data.title || 'Curated for you',
    rationale: data.rationale || '',
  }
}
