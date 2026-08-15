import { useNavigate } from 'react-router-dom'
import { IconBack, IconShare, IconSettings, IconBell } from '../../components/icons'
import { useUnreadNotifications } from '../../hooks/useUnreadNotifications.js'
import { useTranslation } from '../../i18n/index.js'
import styles from './ProfileHeader.module.css'

export default function ProfileHeader({
  isMe,
  handle,
  onLogout,
  onShare,
}) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  // Own-profile only — bell + unread badge (NOTIF-INAPP-1). Count fetch is
  // mount + visibilitychange only (no polling) per the hook's own contract.
  // enabled=isMe so viewing someone else's profile never fires the request.
  const { count: unreadCount } = useUnreadNotifications(isMe)
  const badgeLabel = unreadCount > 9 ? '9+' : String(unreadCount)

  return (
    /* Sticky Header — isMe: title+handle left, controls right | others: back left, title center, controls right */
    <div style={{
      position: 'sticky', top: 0, zIndex: 10,
      background: 'color-mix(in srgb, var(--color-bg) 72%, transparent)',
      backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
      padding: '12px 16px',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      borderBottom: '1px solid var(--color-border-soft)',
      gap: 8,
    }}>
      {isMe ? (
        /* Own profile: title block on the left (no back button) */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1 }}>
          <h2 style={{
            color: 'var(--color-text)', fontSize: 17, fontWeight: 700,
            margin: 0, letterSpacing: '-0.01em', lineHeight: 1.2,
          }}>
            Profile
          </h2>
          {handle && (
            <span style={{
              color: 'var(--color-text-muted)', fontSize: 12, fontWeight: 500,
              letterSpacing: '0.01em', lineHeight: 1,
            }}>
              @{handle}
            </span>
          )}
        </div>
      ) : (
        /* Other user: back button on left */
        <button
          onClick={() => navigate(-1)}
          aria-label="Back"
          className={styles.iconBtnBack}
        >
          <IconBack width={20} height={20} />
        </button>
      )}

      {!isMe && (
        <h2 style={{
          color: 'var(--color-text)', fontSize: 17, fontWeight: 700,
          margin: 0, letterSpacing: '-0.01em',
        }}>
          Profile
        </h2>
      )}

      {/* Right-side controls */}
      {isMe ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* Notifications bell + unread badge (NOTIF-INAPP-1) */}
          <button
            onClick={() => navigate('/notifications')}
            aria-label={t('profile.notifications')}
            title={t('profile.notifications')}
            className={styles.iconBtn}
          >
            <IconBell width={18} height={18} />
            {unreadCount > 0 && (
              <span
                aria-hidden="true"
                style={{
                  position: 'absolute',
                  top: 4,
                  right: 4,
                  minWidth: 16,
                  height: 16,
                  padding: '0 4px',
                  borderRadius: 999,
                  background: 'var(--accent-1)',
                  color: '#fff',
                  fontSize: 10,
                  fontWeight: 700,
                  lineHeight: '16px',
                  textAlign: 'center',
                  boxSizing: 'border-box',
                }}
              >
                {badgeLabel}
              </span>
            )}
          </button>

          {/* Share */}
          <button
            onClick={onShare}
            aria-label={t('profile.shareCard')}
            title={t('profile.shareCard')}
            className={styles.iconBtn}
          >
            <IconShare width={18} height={18} />
          </button>

          {/* Settings */}
          <button
            onClick={() => navigate('/settings')}
            aria-label={t('profile.settings')}
            title={t('profile.settings')}
            className={styles.iconBtn}
          >
            <IconSettings width={18} height={18} />
          </button>

          {/* Logout — unchanged */}
          <button
            onClick={onLogout}
            aria-label="Log out"
            title="Log out"
            className={styles.iconBtnDestructive}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
              <polyline points="16 17 21 12 16 7"></polyline>
              <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Share */}
          <button
            onClick={onShare}
            aria-label={t('profile.shareCard')}
            title={t('profile.shareCard')}
            className={styles.iconBtn}
          >
            <IconShare width={18} height={18} />
          </button>
        </div>
      )}
    </div>
  )
}
