/**
 * api/messaging.js
 * In-app 1:1 messaging + block / report (FULL-MESSAGING-1, SNS-FOLLOW-1).
 *
 * Backend: apps/messaging, all under /api/v1/, JWT auth. Conversation endpoints
 * return 404 while the MESSAGING_ENABLED backend flag is off — callers gate on
 * `useMessagingEnabled()` (hooks/useMessagingFeature.ts) and never call these
 * when the flag is off. Opening a conversation also needs FOLLOW_ENABLED and
 * that I follow the peer (SNS-FOLLOW-1; the contact-request flow is gone).
 *
 *   POST   /conversations/                     {peer_user_id} -> {id, other, closed}  (201 created / 200 existing)
 *   GET    /conversations/                     -> {results:[{id, other, last_message, last_message_at, unread_count, closed}]}
 *   GET    /conversations/<id>/messages/?after=&limit= -> {results:[message], closed}
 *   POST   /conversations/<id>/messages/       {body} -> message
 *   POST   /conversations/<id>/read/
 *   GET    /messages/unread-count/             -> {count}
 *   POST   /users/<user_id>/block/  | DELETE (unblock)   (MESSAGING or FOLLOW flag)
 *   POST   /reports/                           {target_type, target_id, reason?}
 *
 * Guest writes answer 403 {detail:'verify_required'}: write helpers dispatch
 * the global 'archithon:verify-required' event (VerifyGateModal) and throw
 * VerifyRequiredError — same contract as api/projects.js.
 */
import { callApi } from './core.ts'
import { VerifyRequiredError } from './projects.ts'
import type { OpenConversationResult } from '../types/api.ts'

function throwIfVerifyRequired(err) {
  if (err?.status === 403 && err?.data?.detail === 'verify_required') {
    // Fixed 'messaging' reason (not the backend's) so VerifyGateModal swaps
    // in messaging copy instead of the board-limit text.
    const reason = 'messaging'
    window.dispatchEvent(new CustomEvent('archithon:verify-required', { detail: { reason } }))
    throw new VerifyRequiredError(reason)
  }
}

async function write(method: string, path: string, body?: unknown) {
  try {
    return await callApi(method, path, body)
  } catch (err) {
    throwIfVerifyRequired(err)
    throw err
  }
}

/** Shared guest-gated write (follow reuses it): 403 verify_required -> global gate event + VerifyRequiredError. */
export const verifyGatedWrite = write

// -- Conversations / messages ------------------------------------------------

/** Open (or reopen) the 1:1 conversation with a followed user. */
export async function openConversation(peerUserId: number | string): Promise<OpenConversationResult> {
  const peer = Number(peerUserId)
  if (!Number.isInteger(peer) || peer <= 0) throw new Error('invalid user id')
  return await write('POST', '/conversations/', { peer_user_id: peer })
}

export async function listConversations() {
  return await callApi('GET', '/conversations/')
}

export async function listMessages(conversationId: number | string, { after, limit }: { after?: number | string | null, limit?: number } = {}) {
  const qs = []
  if (after != null) qs.push(`after=${encodeURIComponent(after)}`)
  if (limit != null) qs.push(`limit=${encodeURIComponent(limit)}`)
  const suffix = qs.length ? `?${qs.join('&')}` : ''
  return await callApi('GET', `/conversations/${conversationId}/messages/${suffix}`)
}

export async function sendMessage(conversationId, body) {
  return await write('POST', `/conversations/${conversationId}/messages/`, { body })
}

export async function markConversationRead(conversationId) {
  return await callApi('POST', `/conversations/${conversationId}/read/`)
}

export async function getMessagesUnreadCount() {
  return await callApi('GET', '/messages/unread-count/')
}

// -- Block / report ----------------------------------------------------------

export async function blockUser(userId) {
  return await write('POST', `/users/${userId}/block/`)
}

export async function unblockUser(userId) {
  return await write('DELETE', `/users/${userId}/block/`)
}

export async function reportTarget({ targetType, targetId, reason }: { targetType: string, targetId: number | string, reason?: string }) {
  const body: { target_type: string, target_id: number | string, reason?: string } = { target_type: targetType, target_id: targetId }
  if (reason) body.reason = reason
  return await write('POST', '/reports/', body)
}
