/**
 * api/liked.js
 * Liked buildings API — right-swipe likes (Discovery) stored server-side.
 */

import { callApi } from './core.js'

export async function addLikedBuilding(canonicalBldId) {
  return callApi('POST', '/liked-buildings/', { canonical_bld_id: canonicalBldId })
}

export async function getLikedBuildings() {
  return callApi('GET', '/liked-buildings/')
}
