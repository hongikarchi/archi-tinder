import { classifyApiError } from '../utils/apiError.js'

// Classify a failed Discovery -> Taste promote call into a reason key + short
// technical code, so the UI can say WHICH error happened.
export function describePromoteError(err) {
  const { kind, code } = classifyApiError(err)
  if (kind === 'notFound') return { reason: 'no_buildings', code }
  if (kind === 'forbidden') {
    return { reason: err?.data?.detail === 'verify_required' ? 'verify_required' : 'unknown', code }
  }
  return { reason: kind, code }
}

// Localized message + " (code)" suffix. Falls back to the generic key.
export function promoteErrorText(t, info) {
  const reason = info?.reason || 'unknown'
  const base = reason === 'unknown'
    ? t('discovery.toastAnalysisFailed')
    : t(`discovery.promoteError_${reason}`)
  return info?.code ? `${base} (${info.code})` : base
}
