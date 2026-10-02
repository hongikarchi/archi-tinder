/**
 * Small pure helpers shared by the messaging components (FULL-MESSAGING-1).
 */

/** Today -> clock time, otherwise a short date. `language` is 'ko' | 'en'. */
export function formatMessageTime(iso, language) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const locale = language === 'en' ? 'en-US' : 'ko-KR'
  if (d.toDateString() === new Date().toDateString()) {
    return d.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' })
  }
  return d.toLocaleDateString(locale, { month: 'short', day: 'numeric' })
}

export function isConnectedSystem(message) {
  return message?.kind === 'system' && message?.system_type === 'connected'
}

/** Inbox row preview. System "connected" renders the i18n caption, not DB text. */
export function previewText(lastMessage, t) {
  if (!lastMessage) return ''
  if (lastMessage.kind === 'system') {
    return isConnectedSystem(lastMessage) ? t('messaging.connectedText') : ''
  }
  return lastMessage.body || ''
}

export function maxMessageId(messages, floor = 0) {
  return messages.reduce((acc, m) => (m.id > acc ? m.id : acc), floor)
}

export function badgeLabel(count) {
  return count > 99 ? '99+' : String(count)
}
