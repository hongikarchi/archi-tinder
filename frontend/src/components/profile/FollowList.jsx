/**
 * FollowList.jsx — renders a paginated list of follow relationships.
 *
 * API item shape (UserMiniSerializer):
 *   { user_id, display_name, avatar_url }
 *
 * Props:
 *   users         — array of UserMiniSerializer items
 *   onOpenUser    — callback(user) when a row is clicked
 *   emptyMessage  — string shown when list is empty
 */
import { IconChevron } from '../icons.jsx'
import styles from './FollowList.module.css'

function initials(name) {
  return (name || '').split(/\s+/).map((w) => w[0] || '').join('').slice(0, 2).toUpperCase()
}

export default function FollowList({ users, onOpenUser, emptyMessage }) {
  if (!users || users.length === 0) {
    return (
      <div style={{ padding: '24px 14px', textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
        {emptyMessage}
      </div>
    )
  }

  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
    }}>
      {users.map((u) => (
        <button
          key={u.user_id}
          type="button"
          onClick={() => onOpenUser?.(u)}
          className={styles.row}
        >
          {/* Avatar — uses real avatar_url when available, falls back to initials gradient */}
          {u.avatar_url ? (
            <img
              src={u.avatar_url}
              alt={u.display_name || ''}
              style={{
                width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
                objectFit: 'cover',
                background: 'var(--color-surface-2)',
              }}
            />
          ) : (
            <span style={{
              width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg, var(--accent-2), var(--accent-3))',
              color: '#fff',
              fontSize: 14, fontWeight: 600,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {initials(u.display_name)}
            </span>
          )}

          {/* Name */}
          <span style={{ flex: 1, minWidth: 0 }}>
            <span style={{
              display: 'block',
              fontSize: 14, fontWeight: 600,
              color: 'var(--color-text)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {u.display_name}
            </span>
          </span>

          {/* Chevron indicator */}
          <span style={{ color: 'var(--color-text-dim)', flexShrink: 0, display: 'flex', alignItems: 'center' }}>
            <IconChevron width={16} height={16} />
          </span>
        </button>
      ))}
    </div>
  )
}
