import { useEffect, useState } from 'react'
import { useTranslation } from '../../i18n/index.js'
import { getContactStatus } from '../../api/messaging.js'
import { useMessagingEnabled } from '../../hooks/useMessagingFeature.js'
import GreetingSheet from './GreetingSheet.jsx'
import MessagesSheet from './MessagesSheet.jsx'

/**
 * ContactCta — the "관심 있어요" button on ANOTHER user's profile
 * (FULL-MESSAGING-1). Reflects GET contact-requests/status/:
 *   none + can_request   -> primary button, opens the greeting sheet
 *   none + !can_request  -> renders nothing
 *   sent                 -> disabled "보냄" (an ignored request is
 *                           indistinguishable by design, D10)
 *   connected            -> "메시지 보내기", opens the messages sheet on that
 *                           conversation
 * Flag OFF (or a failed status call) -> renders nothing and, when OFF, never
 * calls the API. `buttonClassName` lets the host page keep its own CTA styling.
 */
export default function ContactCta({ userId, buttonClassName, hidden = false }) {
  const { t } = useTranslation()
  const enabled = useMessagingEnabled()
  const [status, setStatus] = useState(null) // null = loading / unknown
  const [greetingOpen, setGreetingOpen] = useState(false)
  const [sheet, setSheet] = useState(null) // { conversationId } | null

  useEffect(() => {
    if (!enabled || !userId || hidden) return undefined
    let cancelled = false
    getContactStatus(userId)
      .then(data => { if (!cancelled) setStatus(data) })
      .catch(() => { if (!cancelled) setStatus(null) })
    return () => { cancelled = true }
  }, [enabled, userId, hidden])

  // New profile -> drop the previous user's status (render-time reset, no
  // effect flicker); a hidden toggle keeps the rendered state.
  const [statusUser, setStatusUser] = useState(userId)
  if (statusUser !== userId) {
    setStatusUser(userId)
    setStatus(null)
    setGreetingOpen(false)
    setSheet(null)
  }

  const sheetsOpen = greetingOpen || !!sheet
  if (!enabled || (!status && !sheetsOpen)) return null

  const { state, can_request: canRequest } = status || {}

  function handleSent(res) {
    setGreetingOpen(false)
    if (res?.status === 'connected') {
      setStatus({ state: 'connected', can_request: false })
      setSheet({ conversationId: res.conversation_id ?? null })
    } else {
      setStatus({ state: 'sent', can_request: false })
    }
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
