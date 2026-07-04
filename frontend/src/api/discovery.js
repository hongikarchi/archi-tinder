import { callApi } from './core.js'
import { normalizeCard } from './images.js'
import { VerifyRequiredError } from './projects.js'

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

export async function discoveryFeedback(canonicalBldId, action, draftId) {
  const body = {
    canonical_bld_id: canonicalBldId,
    action,
    timezone_offset_minutes: new Date().getTimezoneOffset(),
  }
  if (draftId) body.draft_id = draftId
  try {
    const data = await callApi('POST', '/discovery/feedback/', body)
    return {
      draftId: data.draft_id ?? null,
      draftLikeCount: data.draft_like_count ?? 0,
      draftPassCount: data.draft_pass_count ?? 0,
      likeCapReached: data.like_cap_reached ?? false,
    }
  } catch (err) {
    if (err?.status === 403 && err?.data?.detail === 'verify_required') {
      const reason = err?.data?.reason || 'board_limit_reached'
      window.dispatchEvent(new CustomEvent('archithon:verify-required', { detail: { reason } }))
      throw new VerifyRequiredError(reason)
    }
    throw err
  }
}

export async function promoteToTaste(draftId) {
  // Returns the session payload with card fields normalized (image_id set),
  // mirroring startSession in sessions.js so the first Taste swipe sends a
  // valid canonical_bld_id instead of undefined.
  const body = {}
  if (draftId) body.draft_id = draftId
  const result = await callApi('POST', '/discovery/promote-to-taste/', body)
  return {
    ...result,
    next_image:       normalizeCard(result.next_image),
    prefetch_image:   normalizeCard(result.prefetch_image),
    prefetch_image_2: normalizeCard(result.prefetch_image_2),
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
