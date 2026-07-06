/**
 * api/notifications.js
 * In-app notifications (NOTIF-INAPP-1).
 *
 * Backend: apps/notifications (self-only, JWT auth).
 *   GET  /api/v1/notifications/               -> {results, page, page_size, has_more, total}
 *   GET  /api/v1/notifications/unread-count/  -> {count}
 *   POST /api/v1/notifications/mark-read/     -> {ids: [...]} or {all: true} -> {updated}
 */
import { callApi } from './core.js'

export async function listNotifications({ page = 1, pageSize = 20 } = {}) {
  return await callApi('GET', `/notifications/?page=${page}&page_size=${pageSize}`)
}

export async function getUnreadCount() {
  return await callApi('GET', '/notifications/unread-count/')
}

export async function markRead({ ids, all } = {}) {
  const body = all ? { all: true } : { ids: ids || [] }
  return await callApi('POST', '/notifications/mark-read/', body)
}
