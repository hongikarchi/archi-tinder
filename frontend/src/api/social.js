/**
 * api/social.js
 * Social graph: follow / unfollow.
 */

import { callApi } from './core.js'

export async function followUser(userId) {
  return await callApi('POST', `/users/${userId}/follow/`)
}

export async function unfollowUser(userId) {
  await callApi('DELETE', `/users/${userId}/follow/`)
}
