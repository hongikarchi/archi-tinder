/**
 * contestErrors.js — turn a DRF-style 400 body ({field: [msg, ...]} or
 * {detail: '...'}) into display strings for the admin contests UI.
 */

function asMessages(value) {
  if (Array.isArray(value)) return value.map(v => String(v))
  if (value == null) return []
  if (typeof value === 'object') return Object.values(value).flatMap(asMessages)
  return [String(value)]
}

/** All messages in the body, flat (field names omitted). */
export function flattenApiErrors(data) {
  if (typeof data === 'string' && data) return [data]
  if (!data || typeof data !== 'object') return []
  return Object.values(data).flatMap(asMessages)
}

/** { byField: {field: 'msg1 msg2'}, general: [non-field messages] } */
export function fieldErrorMap(data) {
  const byField = {}
  const general = []
  for (const [key, value] of Object.entries(data || {})) {
    const messages = asMessages(value)
    if (messages.length === 0) continue
    if (key === 'non_field_errors' || key === 'detail') general.push(...messages)
    else byField[key] = messages.join(' ')
  }
  return { byField, general }
}
