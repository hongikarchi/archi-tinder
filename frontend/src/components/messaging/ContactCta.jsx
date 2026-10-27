import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from '../../i18n/index.js'
import { getContactStatus } from '../../api/messaging.js'
import { useMessagingEnabled } from '../../hooks/useMessagingFeature.js'
import GreetingSheet from './GreetingSheet.jsx'
import MessagesSheet from './MessagesSheet.jsx'

/**
 * ContactCta — the "관심 있어요" button on ANOTHER user's profile
 * (FULL-MESSAGING-1). Reflects GET contact-requests/status/:
 *   none + can_request   -> primary button, opens the greeting sheet
 *   none + !can_request:
 *     verify_required    -> enabled button; click fires the global
 *                           'archithon:verify-required' {reason:'messaging'}
 *                           event (VerifyGateModal), no API call
 *     self               -> renders nothing
 *     unavailable/other  -> disabled button + muted hint (blocked / opted-out /
 *                           guest recipient are indistinguishable by design)
 *   sent                 -> disabled "보냄" (an ignored request is
 *                           indistinguishable by design, D10)
 *   connected            -> "메시지 보내기", opens the messages sheet on that
 *                           conversation
 * Status fetch failure -> retry button (one fetch per click, no auto loop).
 * Loading, flag OFF, or `hidden` (I blocked them) -> renders nothing; when OFF
 * it never calls the API. `buttonClassName` lets the host page keep its own CTA styling.
 */
export default function ContactCta({ userId, buttonClassName, hidden = false }) {
  const { t } = useTranslation()
  const enabled = useMessagingEnabled()
  const navigate = useNavigate()
  const [status, setStatus] = useState(null) // null = loading / unknown
  const [loadFailed, setLoadFailed] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [greetingOpen, setGreetingOpen] = useState(false)
  const [sheet, setSheet] = useState(null) // { conversationId } | null

  useEffect(() => {
    if (!enabled || !userId || hidden) return undefined
    let cancelled = false
    getContactStatus(userId)
      .then(data => { if (!cancelled) { setStatus(data); setLoadFailed(false) } })
      .catch(() => { if (!cancelled) { setStatus(null); setLoadFailed(true) } })
    return () => { cancelled = true }
  }, [enabled, userId, hidden, reloadKey])

  // A guest finished verification in place (App.jsx onPromoted) -> the cached
  // 'verify_required' reason is stale; refetch once.
  useEffect(() => {
    if (!enabled || !userId || hidden) return undefined
    const onVerified = () => setReloadKey(k => k + 1)
    window.addEventListener('archithon:verified', onVerified)
    return () => window.removeEventListener('archithon:verified', onVerified)
  }, [enabled, userId, hidden])

  // New profile -> drop the previous user's status (render-time reset, no
  // effect flicker); a hidden toggle keeps the rendered state.
  const [statusUser, setStatusUser] = useState(userId)
  if (statusUser !== userId) {
    setStatusUser(userId)
    setStatus(null)
    setLoadFailed(false)
    setGreetingOpen(false)
    setSheet(null)
  }

  const sheetsOpen = greetingOpen || !!sheet
  if (!enabled || (!status && !loadFailed && !sheetsOpen)) return null

  const { state, can_request: canRequest, reason } = status || {}

  function handleSent(res) {
    setGreetingOpen(false)
    if (res?.status === 'connected') {
      setStatus({ state: 'connected', can_request: false })
      setSheet({ conversationId: res.conversation_id ?? null })
    } else {
      setStatus({ state: 'sent', can_request: false })
    }
  }

  function handleRetry() {
    setLoadFailed(false)
    setReloadKey(k => k + 1)
  }

  function handleVerifyRequired() {
    window.dispatchEvent(new CustomEvent('archithon:verify-required', { detail: { reason: 'messaging' } }))
  }

  let button = null
  if (hidden) {
    button = null // peer blocked: hide the button only; open sheets stay mounted
  } else if (state === 'sent') {
    button = (
      <button type="button" className={buttonClassName} disabled>
        {t('messaging.interestSent')}
      </button>
    )
  } else if (state === 'connected') {
    button = (
      <button type="button" className={buttonClassName} onClick={() => setSheet({ conversationId: null })}>
        {t('messaging.sendMessage')}
      </button>
    )
  } else if (canRequest) {
    button = (
      <button type="button" className={buttonClassName} onClick={() => setGreetingOpen(true)}>
        {t('messaging.interest')}
      </button>
    )
  } else if (!status && loadFailed) {
    button = (
      <button
        type="button"
        className={buttonClassName}
        aria-disabled="true"
        style={{ opacity: 0.55 }}
        onClick={handleRetry}
      >
        {t('messaging.statusLoadFailed')}
      </button>
    )
  } else if (state === 'none' && reason === 'verify_required') {
    button = (
      <button type="button" className={buttonClassName} onClick={handleVerifyRequired}>
        {t('messaging.interest')}
      </button>
    )
  } else if (state === 'none' && reason === 'assessment_required') {
    button = (
      <button type="button" className={buttonClassName} onClick={() => navigate('/assessment')}>
        {t('messaging.assessmentRequiredCta')}
      </button>
    )
  } else if (state === 'none' && reason !== 'self') {
    button = (
      <>
        <button type="button" className={buttonClassName} disabled>
          {t('messaging.interestUnavailable')}
        </button>
        <p style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-muted)', margin: 0, textAlign: 'center' }}>
          {t('messaging.interestUnavailableHint')}
        </p>
      </>
    )
  }

  return (
    <>
      {button}
      {greetingOpen && (
        <GreetingSheet
          recipientId={userId}
          onClose={() => setGreetingOpen(false)}
          onSent={handleSent}
        />
      )}
      {sheet && (
        <MessagesSheet
          initialConversationId={sheet.conversationId}
          initialPeerUserId={userId}
          onClose={() => setSheet(null)}
        />
      )}
    </>
  )
}
