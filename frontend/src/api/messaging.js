/**
 * api/messaging.js
 * Contact requests + in-app 1:1 messaging (FULL-MESSAGING-1).
 *
 * Backend: apps/messaging, all under /api/v1/, JWT auth. Every endpoint
 * returns 404 while the MESSAGING_ENABLED backend flag is off — callers gate
 * on `useMessagingEnabled()` (hooks/useMessagingFeature.js) and never call
 * these when the flag is off.
 *
 *   POST   /contact-requests/                  {recipient_id, greeting?} -> {status:'sent'} | {status:'connected', conversation_id}
 *   GET    /contact-requests/received/         -> {results:[{id, sender, greeting, created_at}]}
 *   GET    /contact-requests/status/?user_id=  -> {state:'none'|'sent'|'connected', can_request}
 *   POST   /contact-requests/<id>/accept/      -> {status:'accepted', conversation_id}
 *   POST   /contact-requests/<id>/ignore/      -> {status:'ignored'}
 *   GET    /conversations/                     -> {results:[{id, other, last_message, last_message_at, unread_count, closed}]}
 *   GET    /conversations/<id>/messages/?after=&limit= -> {results:[message], closed}
 *   POST   /conversations/<id>/messages/       {body} -> message
 *   POST   /conversations/<id>/read/
 *   GET    /messages/unread-count/             -> {count}
 *   POST   /users/<user_id>/block/  | DELETE (unblock)
 *   POST   /reports/                           {target_type, target_id, reason?}
 *
 * Guest writes answer 403 {detail:'verify_required'}: write helpers dispatch
 * the global 'archithon:verify-required' event (VerifyGateModal) and throw
 * VerifyRequiredError — same contract as api/projects.js.
 */
import { callApi } from './core.js'
import { VerifyRequiredError } from './projects.js'

function throwIfVerifyRequired(err) {
  if (err?.status === 403 && err?.data?.detail === 'verify_required') {
    // Fixed 'messaging' reason (not the backend's) so VerifyGateModal swaps
    // in messaging copy instead of the board-limit text.
    const reason = 'messaging'
    window.dispatchEvent(new CustomEvent('archithon:verify-required', { detail: { reason } }))
    throw new VerifyRequiredError(reason)
  }
}

async function write(method, path, body) {
  try {
    return await callApi(method, path, body)
  } catch (err) {
    throwIfVerifyRequired(err)
    throw err
  }
}

// -- Contact requests --------------------------------------------------------

export async function sendContactRequest(recipientId, greeting) {
  const body = { recipient_id: recipientId }
  if (greeting) body.greeting = greeting
  return await write('POST', '/contact-requests/', body)
}

export async function listReceivedRequests() {
  return await callApi('GET', '/contact-requests/received/')
}

export async function getContactStatus(userId) {
  return await callApi('GET', `/contact-requests/status/?user_id=${encodeURIComponent(userId)}`)
}

export async function acceptContactRequest(requestId) {
  return await write('POST', `/contact-requests/${requestId}/accept/`)
}

export async function ignoreContactRequest(requestId) {
  return await write('POST', `/contact-requests/${requestId}/ignore/`)
}

// -- Conversations / messages ------------------------------------------------

export async function listConversations() {
  return await callApi('GET', '/conversations/')
}

export async function listMessages(conversationId, { after, limit } = {}) {
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

export async function reportTarget({ targetType, targetId, reason }) {
  const body = { target_type: targetType, target_id: targetId }
  if (reason) body.reason = reason
  return await write('POST', '/reports/', body)
}
