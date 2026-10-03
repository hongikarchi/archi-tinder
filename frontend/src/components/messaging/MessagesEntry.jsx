import { useState } from 'react'
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
 */
export default function MessagesEntry() {
  const { t } = useTranslation()
  const enabled = useMessagingEnabled()
  const { count } = useUnreadMessages()
  const [open, setOpen] = useState(false)

  if (!enabled) return null

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '-12px 0 12px' }}>
        <button
          type="button"
          className={styles.pill}
          onClick={() => setOpen(true)}
          aria-label={count > 0 ? t('messaging.openWithCount', { n: count }) : t('messaging.open')}
          title={t('messaging.label')}
          aria-haspopup="dialog"
        >
          <MessageIcon size={26} />
          {count > 0 && <span className={styles.badge} aria-hidden="true">{badgeLabel(count)}</span>}
        </button>
      </div>
      {open && <MessagesSheet onClose={() => setOpen(false)} />}
    </>
  )
}
