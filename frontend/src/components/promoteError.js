// Classify a failed Discovery -> Taste promote call into a reason key + short
// technical code, so the UI can say WHICH error happened.
export function describePromoteError(err) {
  const status = err?.status
  if (err?.name === 'AbortError') return { reason: 'timeout', code: 'timeout' }
  if (err instanceof TypeError) return { reason: 'network', code: 'network' }
  if (typeof status === 'number') {
    const code = `HTTP ${status}`
    if (status >= 500) return { reason: 'server', code }
    if (status === 404) return { reason: 'no_buildings', code }
    if (status === 403 && err?.data?.detail === 'verify_required') return { reason: 'verify_required', code }
    if (status === 401) return { reason: 'unauthorized', code }
    return { reason: 'unknown', code }
  }
  return { reason: 'unknown', code: err?.name || 'error' }
}

// Localized message + " (code)" suffix. Falls back to the generic key.
export function promoteErrorText(t, info) {
  const reason = info?.reason || 'unknown'
  const base = reason === 'unknown'
    ? t('discovery.toastAnalysisFailed')
    : t(`discovery.promoteError_${reason}`)
  return info?.code ? `${base} (${info.code})` : base
}
