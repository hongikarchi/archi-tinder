import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from '../../i18n/index.js'
import { useMessagingEnabled } from '../../hooks/useMessagingFeature.js'
import { useUnreadMessages } from '../../hooks/useUnreadMessages.js'
import MessageIcon from './MessageIcon.jsx'
import MessagesSheet from './MessagesSheet.jsx'
import { badgeLabel } from './messagingUtils.js'
import styles from './Messaging.module.css'

/**
 * MessagesEntry — the message pill on MY profile (FULL-MESSAGING-1, D4/D5):
 * icon-only 3D chat bubble + numeric unread badge, >=44px, rendered IN the content
 * flow (never position:fixed) so it cannot collide with the fixed
 * PageTopControls / isMe cluster. Opens the inbox sheet. Flag OFF -> nothing.
 *
 * Deep link (FULL-NOTIF-CONTACT-1): `?messages=inbox` opens the sheet on the
 * inbox view, `?messages=<positive int>` opens that conversation. The param is
 * consumed once (removed with `replace`) so back/refresh don't reopen it.
 */
function parseMessagesParam(raw) {
  if (raw === 'inbox') return { conversationId: null }
  if (raw && /^[1-9]\d*$/.test(raw)) return { conversationId: Number(raw) }
  return null
}

export default function MessagesEntry() {
  const { t } = useTranslation()
  const enabled = useMessagingEnabled()
  const { count } = useUnreadMessages()
  const [open, setOpen] = useState(false)
  const [initialConversationId, setInitialConversationId] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const messagesParam = searchParams.get('messages')

  useEffect(() => {
    if (!enabled || messagesParam == null) return
    const target = parseMessagesParam(messagesParam)
    if (target) {
      setInitialConversationId(target.conversationId)
      setOpen(true)
    }
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('messages')
      return next
    }, { replace: true })
  }, [enabled, messagesParam, setSearchParams])

  if (!enabled) return null

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '-12px 0 12px' }}>
        <button
          type="button"
          className={styles.pill}
          onClick={() => { setInitialConversationId(null); setOpen(true) }}
          aria-label={count > 0 ? t('messaging.openWithCount', { n: count }) : t('messaging.open')}
          title={t('messaging.label')}
          aria-haspopup="dialog"
        >
          <MessageIcon size={26} />
          {count > 0 && <span className={styles.badge} aria-hidden="true">{badgeLabel(count)}</span>}
        </button>
      </div>
      {open && (
        <MessagesSheet
          onClose={() => setOpen(false)}
          initialConversationId={initialConversationId}
        />
      )}
    </>
  )
}
