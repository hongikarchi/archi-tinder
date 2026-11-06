/**
 * contestErrors.js — turn the admin contests 400 body into display strings.
 *
 * Body shape: {"<field>": ["message", ...], "error_codes": {"<field>": ["code", ...]}}
 * (error_codes[field][i] is the code of <field>[i]; non-field errors use the key
 * "non_field_errors"; a bare {detail: '...'} is also handled). `error_codes` is
 * metadata, never a field, so it is skipped by every loop below.
 *
 * Known publish-rule codes are rendered through i18n (`admin.contests.errors.*`)
 * when a `t` function is passed; unknown codes fall back to the server message.
 */

const META_KEY = 'error_codes'
const LOCALIZED_CODES = new Set([
  'source_url_required',
  'source_url_listing_site',
  'invalid_url_scheme',
  'poster_host_blocked',
])

function asMessages(value) {
  if (Array.isArray(value)) return value.map(v => String(v))
  if (value == null) return []
  if (typeof value === 'object') return Object.values(value).flatMap(asMessages)
  return [String(value)]
}

/** Messages for one field, swapping known codes for their i18n copy. */
function fieldMessages(data, key, t) {
  const value = data[key]
  const codes = data[META_KEY]?.[key]
  if (!Array.isArray(value) || !Array.isArray(codes) || typeof t !== 'function') {
    return asMessages(value)
  }
  return value.map((msg, i) => {
    const code = codes[i]
    return LOCALIZED_CODES.has(code) ? t(`admin.contests.errors.${code}`) : String(msg)
  })
}

function bodyKeys(data) {
  return Object.keys(data).filter(k => k !== META_KEY)
}

/** All messages in the body, flat (field names omitted). */
export function flattenApiErrors(data, t) {
  if (typeof data === 'string' && data) return [data]
  if (!data || typeof data !== 'object') return []
  return bodyKeys(data).flatMap(k => fieldMessages(data, k, t))
}

/** { byField: {field: 'msg1 msg2'}, general: [non-field messages] } */
export function fieldErrorMap(data, t) {
  const byField = {}
  const general = []
  for (const key of bodyKeys(data || {})) {
    const messages = fieldMessages(data, key, t)
    if (messages.length === 0) continue
    if (key === 'non_field_errors' || key === 'detail') general.push(...messages)
    else byField[key] = messages.join(' ')
  }
  return { byField, general }
}
