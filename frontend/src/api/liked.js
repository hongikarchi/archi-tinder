/**
 * api/liked.js
 * Liked buildings API — right-swipe likes (Discovery) stored server-side.
 */

import { callApi } from './core.js'
import { VerifyRequiredError } from './projects.js'

/**
 * Record a right-swipe like for a building.
 * On 403 verify_required → throws VerifyRequiredError + dispatches archithon:verify-required for the global VerifyGateModal.
 */
export async function addLikedBuilding(canonicalBldId) {
  try {
    return await callApi('POST', '/liked-buildings/', { canonical_bld_id: canonicalBldId })
  } catch (err) {
    if (err?.status === 403 && err?.data?.detail === 'verify_required') {
      const reason = err?.data?.reason || 'liked_limit_reached'
      window.dispatchEvent(new CustomEvent('archithon:verify-required', { detail: { reason } }))
      window.dispatchEvent(new CustomEvent('archithon:pending-like', { detail: { bldId: canonicalBldId } }))
      throw new VerifyRequiredError(reason)
    }
    throw err
  }
}

/**
 * Fetch a user's liked buildings.
 * @param {number|string} [userId] - when omitted, returns the caller's own
 *   liked list. When provided, returns that user's liked list (design-parity
 *   public-profile tabs — any authenticated caller may view another user's
 *   likes; still requires auth).
 * @returns {Promise<{buildings: Array, total: number}>}
 */
export async function getLikedBuildings(userId) {
  const query = userId != null ? `?user_id=${encodeURIComponent(userId)}` : ''
  return callApi('GET', `/liked-buildings/${query}`)
}
