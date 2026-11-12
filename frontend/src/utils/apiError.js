// Shared classifier for failed callApi() requests (see api/core.js error shape:
// AbortError = timeout, TypeError = network, err.status / err.data for HTTP).
// Pure — no i18n, no side effects. Callers map `kind` onto their own copy.
//
// kind: 'timeout' | 'network' | 'server' | 'notFound' | 'unauthorized'
//       | 'forbidden' | 'unknown'
// code: short technical suffix shown to the user ('timeout', 'network',
//       'HTTP 500', or err.name / 'error' when there is no status).
export function classifyApiError(err) {
  const status = err?.status
  if (err?.name === 'AbortError') return { kind: 'timeout', code: 'timeout' }
  if (err instanceof TypeError) return { kind: 'network', code: 'network' }
  if (typeof status === 'number') {
    const code = `HTTP ${status}`
    if (status >= 500) return { kind: 'server', code }
    if (status === 404) return { kind: 'notFound', code }
    if (status === 403) return { kind: 'forbidden', code }
    if (status === 401) return { kind: 'unauthorized', code }
    return { kind: 'unknown', code }
  }
  return { kind: 'unknown', code: err?.name || 'error' }
}

// Board save failure -> { reason, code }; reason keys match
// i18n `board.saveError_<reason>` (unknown uses plain `board.saveError`).
export function describeSaveError(err) {
  const { kind, code } = classifyApiError(err)
  return { reason: kind === 'forbidden' ? 'unknown' : kind, code }
}
