import { useTranslation } from '../../i18n/index.ts'
import Avatar from '../Avatar.tsx'
import Skeleton from '../Skeleton.tsx'
import EmptyState from '../EmptyState.tsx'
import { badgeLabel, formatMessageTime, previewText } from './messagingUtils.ts'
import styles from './Messaging.module.css'
import type { ConversationItem } from '../../types/api.ts'
import { userHandle } from '../../utils/userIdentity.ts'

/**
 * InboxView — the /messages inbox: the conversation list. Handles loading,
 * error and empty states. Purely presentational; MessagesPage owns the data.
 */
interface InboxViewProps {
  loadState: 'loading' | 'ready' | 'error' | string
  conversations: ConversationItem[]
  onRetry: () => void
  onOpenConversation: (conv: ConversationItem) => void
}

export default function InboxView({
  loadState, conversations, onRetry, onOpenConversation,
}: InboxViewProps) {
  const { t, language } = useTranslation()

  if (loadState === 'loading') {
    return (
      <div className={styles.scroll} aria-busy="true">
        {[0, 1, 2].map(i => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 8px' }}>
            <Skeleton circle height={40} />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Skeleton width="40%" height={14} />
              <Skeleton width="70%" height={12} />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (loadState === 'error') {
    return (
      <div className={styles.scroll}>
        <div className={styles.errorBox} role="alert">
          <span>{t('messaging.loadError')}</span>
          <button type="button" className={`${styles.btn} ${styles.btnSecondary}`} onClick={onRetry}>
            {t('messaging.retry')}
          </button>
        </div>
      </div>
    )
  }

  if (conversations.length === 0) {
    return (
      <div className={styles.scroll}>
        <EmptyState
          style={{ padding: '48px 16px' }}
          title={t('messaging.emptyTitle')}
          body={t('messaging.emptyBody')}
        />
      </div>
    )
  }

  return (
    <div className={styles.scroll}>
      {conversations.length > 0 && (
        <section className={styles.section} aria-label={t('messaging.conversationsTitle')}>
          <h3 className={styles.sectionTitle}>{t('messaging.conversationsTitle')}</h3>
          {conversations.map(conv => {
            const other = conv.other || {}
            const unread = conv.unread_count || 0
            const cls = [
              styles.row,
              conv.closed ? styles.rowClosed : '',
              unread > 0 ? styles.rowUnread : '',
            ].filter(Boolean).join(' ')
            return (
              <button
                key={conv.id}
                type="button"
                className={cls}
                onClick={() => onOpenConversation(conv)}
              >
                <Avatar src={other.avatar_url} name={userHandle(other)} size={40} />
                <span className={styles.rowMain}>
                  <span className={styles.name} style={{ display: 'block' }}>
                    {userHandle(other) || t('messaging.unknownUser')}
                  </span>
                  <span className={styles.rowPreview} style={{ display: 'block' }}>
                    {conv.closed ? t('messaging.closedBadge') : previewText(conv.last_message)}
                  </span>
                </span>
                <span className={styles.rowMeta}>
                  <span className={styles.time}>
                    {formatMessageTime(conv.last_message_at || conv.last_message?.created_at, language)}
                  </span>
                  {unread > 0 && (
                    <span className={styles.badge} aria-label={t('messaging.unreadCount', { n: unread })}>
                      {badgeLabel(unread)}
                    </span>
                  )}
                </span>
              </button>
            )
          })}
        </section>
      )}
    </div>
  )
}
