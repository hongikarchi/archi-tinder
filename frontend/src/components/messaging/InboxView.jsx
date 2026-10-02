import { useTranslation } from '../../i18n/index.js'
import Avatar from '../Avatar.jsx'
import Skeleton from '../Skeleton.jsx'
import EmptyState from '../EmptyState.jsx'
import { badgeLabel, formatMessageTime, previewText } from './messagingUtils.js'
import styles from './Messaging.module.css'

/**
 * InboxView — View A of the messages sheet: received contact requests at the
 * top (Accept / Ignore), then the conversation list. Handles loading, error
 * and empty states. Purely presentational; MessagesSheet owns the data.
 */
export default function InboxView({
  loadState, requests, conversations, busy, actionError,
  onRetry, onAccept, onIgnore, onOpenConversation,
}) {
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

  const empty = requests.length === 0 && conversations.length === 0
  if (empty) {
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
      {actionError && <p className={styles.inlineError} role="alert">{t(actionError)}</p>}

      {requests.length > 0 && (
        <section className={styles.section} aria-label={t('messaging.requestsTitle')}>
          <h3 className={styles.sectionTitle}>{t('messaging.requestsTitle')}</h3>
          {requests.map(req => {
            const mine = busy?.id === req.id
            const sender = req.sender || {}
            return (
              <div key={req.id} className={styles.requestCard}>
                <div className={styles.requestTop}>
                  <Avatar src={sender.avatar_url} name={sender.display_name} size={40} />
                  <div className={styles.requestText}>
                    <p className={styles.name}>{sender.display_name || t('messaging.unknownUser')}</p>
                    <p className={styles.greeting}>{req.greeting || t('messaging.noGreeting')}</p>
                  </div>
                  <span className={styles.time}>{formatMessageTime(req.created_at, language)}</span>
                </div>
                <div className={styles.requestActions}>
                  <button
                    type="button"
                    className={`${styles.btn} ${styles.btnSecondary}`}
                    onClick={() => onIgnore(req)}
                    disabled={!!busy}
                  >
                    {t('messaging.ignore')}
                  </button>
                  <button
                    type="button"
                    className={`${styles.btn} ${styles.btnPrimary}`}
                    onClick={() => onAccept(req)}
                    disabled={!!busy}
                  >
                    {mine && busy.action === 'accept' ? t('messaging.sending') : t('messaging.accept')}
                  </button>
                </div>
              </div>
            )
          })}
        </section>
      )}

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
                <Avatar src={other.avatar_url} name={other.display_name} size={40} />
                <span className={styles.rowMain}>
                  <span className={styles.name} style={{ display: 'block' }}>
                    {other.display_name || t('messaging.unknownUser')}
                  </span>
                  <span className={styles.rowPreview} style={{ display: 'block' }}>
                    {conv.closed ? t('messaging.closedBadge') : previewText(conv.last_message, t)}
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
