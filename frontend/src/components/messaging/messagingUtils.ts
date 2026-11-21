/**
 * Small pure helpers shared by the messaging components (FULL-MESSAGING-1).
 */

/** Today -> clock time, otherwise a short date. `language` is 'ko' | 'en'. */
export function formatMessageTime(iso?: string | null, language?: string) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const locale = language === 'en' ? 'en-US' : 'ko-KR'
  if (d.toDateString() === new Date().toDateString()) {
    return d.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' })
  }
  return d.toLocaleDateString(locale, { month: 'short', day: 'numeric' })
}

/**
 * Inbox row preview. System messages (legacy 'connected' rows from the removed
 * contact-request flow stay in the DB) have no preview text.
 */
export function previewText(lastMessage: { kind?: string, body?: string } | null | undefined) {
  if (!lastMessage || lastMessage.kind === 'system') return ''
  return lastMessage.body || ''
}

export function maxMessageId(messages: { id: number }[], floor = 0) {
  return messages.reduce((acc, m) => (m.id > acc ? m.id : acc), floor)
}

export function badgeLabel(count: number) {
  return count > 99 ? '99+' : String(count)
}
