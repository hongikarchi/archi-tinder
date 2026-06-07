import { useNavigate } from 'react-router-dom'
import { IconBack, IconShare, IconEdit, IconSettings } from '../../components/icons'

export default function ProfileHeader({
  isMe,
  handle,
  onLogout,
  onShare,
  onFollow,
  isFollowing,
  isFollowingPending,
}) {
  const navigate = useNavigate()

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
          style={{
            width: 44, height: 44, minWidth: 44,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'transparent', border: 'none',
            color: 'var(--color-text)', cursor: 'pointer',
            borderRadius: 12,
            transition: 'background 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-surface-2, rgba(255,255,255,0.05))' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
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
          {/* Share */}
          <button
            onClick={onShare}
            aria-label="프로필 카드 공유"
            title="프로필 카드 공유"
            style={{
              width: 44, height: 44, minWidth: 44,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'transparent', border: 'none',
              color: 'var(--color-text-dim)', cursor: 'pointer',
              borderRadius: 12,
              transition: 'color 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-text)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-dim)' }}
          >
            <IconShare width={18} height={18} />
          </button>

          {/* Edit — deep-links to /settings/edit-profile */}
          <button
            onClick={() => navigate('/settings/edit-profile')}
            aria-label="프로필 편집"
            title="프로필 편집"
            style={{
              width: 44, height: 44, minWidth: 44,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'transparent', border: 'none',
              color: 'var(--color-text-dim)', cursor: 'pointer',
              borderRadius: 12,
              transition: 'color 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-text)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-dim)' }}
          >
            <IconEdit width={18} height={18} />
          </button>

          {/* Settings */}
          <button
            onClick={() => navigate('/settings')}
            aria-label="설정"
            title="설정"
            style={{
              width: 44, height: 44, minWidth: 44,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'transparent', border: 'none',
              color: 'var(--color-text-dim)', cursor: 'pointer',
              borderRadius: 12,
              transition: 'color 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-text)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-dim)' }}
          >
            <IconSettings width={18} height={18} />
          </button>

          {/* Logout — unchanged */}
          <button
            onClick={onLogout}
            aria-label="Log out"
            title="Log out"
            style={{
              width: 44, height: 44, minWidth: 44,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'transparent', border: 'none',
              color: 'var(--color-text-dim)', cursor: 'pointer',
              borderRadius: 12,
              transition: 'color 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#ef4444' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-dim)' }}
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
            aria-label="프로필 카드 공유"
            title="프로필 카드 공유"
            style={{
              width: 44, height: 44, minWidth: 44,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'transparent', border: 'none',
              color: 'var(--color-text-dim)', cursor: 'pointer',
              borderRadius: 12,
              transition: 'color 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-text)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-dim)' }}
          >
            <IconShare width={18} height={18} />
          </button>

          {/* Follow button */}
          <button
            onClick={onFollow}
            disabled={isFollowingPending}
            style={{
              minHeight: 38, padding: '0 16px',
              borderRadius: 'var(--radius-md)',
              background: isFollowing ? 'var(--color-surface-2)' : 'linear-gradient(135deg,#ec4899,#f43f5e)',
              color: isFollowing ? 'var(--color-text-2)' : '#fff',
              border: isFollowing ? '1px solid var(--color-border)' : 'none',
              fontSize: 14, fontWeight: 700,
              cursor: isFollowingPending ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              display: 'flex', alignItems: 'center', gap: 5,
              transition: 'background 0.2s, color 0.2s',
              whiteSpace: 'nowrap',
              opacity: isFollowingPending ? 0.7 : 1,
            }}
          >
            {isFollowing ? (
              <>
                Following
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </>
            ) : 'Follow'}
          </button>
        </div>
      )}
    </div>
  )
}
