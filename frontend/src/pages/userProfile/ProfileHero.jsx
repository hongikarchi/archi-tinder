import { Fragment } from 'react'
import { useNavigate } from 'react-router-dom'
import BioPersonaFlipCard from '../../components/profile/BioPersonaFlipCard'

export default function ProfileHero({
  user,
  boardsTotalCount,
  followerCount,
  isMe,
  isFollowing,
  isFollowingPending,
  onToggleFollow,
}) {
  const navigate = useNavigate()

  // External-link helpers (pure derivations — no hooks)
  const igHandle = user?.external_links?.instagram?.replace(/^@/, '') || ''
  const igUrl = igHandle ? `https://instagram.com/${igHandle}` : null
  const emailUrl = user?.external_links?.email ? `mailto:${user.external_links.email}` : null

  return (
    /* HERO BLOCK — narrower nested column (max-width 480) */
    <div style={{ maxWidth: 480, margin: '0 auto 36px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>

        {/* Avatar w/ on-brand pink-rose ambient halo */}
        {user.avatar_url ? (
          <div style={{ position: 'relative', marginBottom: 18 }}>
            <div
              style={{
                position: 'absolute', inset: -6, borderRadius: '50%',
                background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                opacity: 0.55, filter: 'blur(12px)',
              }}
              aria-hidden="true"
            />
            <img
              src={user.avatar_url}
              alt="avatar"
              style={{
                position: 'relative', zIndex: 2,
                width: 108, height: 108, borderRadius: '50%',
                border: '2px solid var(--color-border-soft)',
                objectFit: 'cover',
                background: 'var(--color-surface)',
                display: 'block',
              }}
            />
          </div>
        ) : (
          <div
            style={{
              width: 108, height: 108, borderRadius: '50%',
              background: 'var(--color-surface)',
              border: '2px solid var(--color-border-soft)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginBottom: 18,
            }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="8" r="4"></circle>
              <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"></path>
            </svg>
          </div>
        )}

        {/* Name */}
        <h1 style={{
          color: 'var(--color-text)', fontSize: 24, fontWeight: 700,
          margin: '0 0 4px', lineHeight: 1.2, letterSpacing: '-0.01em',
        }}>
          {user.display_name}
        </h1>

        {/* §3.7 Compact stats row */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: 0, marginTop: 14, marginBottom: 4,
        }}>
          {[
            { count: boardsTotalCount, label: 'Boards' },
            { count: followerCount, label: 'Followers' },
            { count: user.following_count, label: 'Following' },
          ].map((stat, i, arr) => (
            <Fragment key={stat.label}>
              <button
                onClick={() => {
                  if (stat.label === 'Followers' && user?.user_id) {
                    navigate(`/user/${user.user_id}/followers`)
                  } else if (stat.label === 'Following' && user?.user_id) {
                    navigate(`/user/${user.user_id}/following`)
                  }
                  // Boards: no dedicated list route yet — no-op
                }}
                style={{
                  flex: '0 0 auto',
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  padding: '6px 18px', minHeight: 44,
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                  fontFamily: 'inherit', color: 'inherit',
                }}
              >
                <span style={{ color: 'var(--color-text)', fontSize: 18, fontWeight: 700, lineHeight: 1 }}>
                  {stat.count}
                </span>
                <span style={{ color: 'var(--color-text-dim)', fontSize: 12, fontWeight: 500 }}>
                  {stat.label}
                </span>
              </button>
              {i < arr.length - 1 && (
                <div style={{ width: 1, height: 28, background: 'var(--color-border)' }} />
              )}
            </Fragment>
          ))}
        </div>

        {/* §3.5.4 Hero Flip — BioPersonaFlipCard */}
        {user.persona_summary && (
          <BioPersonaFlipCard
            bio={user.bio}
            persona={user.persona_summary}
            mbti={user.mbti}
          />
        )}

        {/* External links — Instagram + email pills */}
        {(igUrl || emailUrl) && (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
            {igUrl && (
              <a
                href={igUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  padding: '10px 14px', borderRadius: 999,
                  background: 'var(--color-surface-2, rgba(255,255,255,0.04))',
                  border: '1px solid var(--color-border-soft)',
                  color: 'var(--color-text-2)',
                  textDecoration: 'none', fontSize: 13, fontWeight: 600,
                  transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.18s, color 0.18s',
                  minHeight: 44,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-1px)'
                  e.currentTarget.style.borderColor = 'rgba(236,72,153,0.45)'
                  e.currentTarget.style.color = '#ec4899'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)'
                  e.currentTarget.style.borderColor = 'var(--color-border-soft)'
                  e.currentTarget.style.color = 'var(--color-text-2)'
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect>
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
                </svg>
                {user.external_links.instagram}
              </a>
            )}
            {emailUrl && (
              <a
                href={emailUrl}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  padding: '10px 14px', borderRadius: 999,
                  background: 'var(--color-surface-2, rgba(255,255,255,0.04))',
                  border: '1px solid var(--color-border-soft)',
                  color: 'var(--color-text-2)',
                  textDecoration: 'none', fontSize: 13, fontWeight: 600,
                  transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.18s, color 0.18s',
                  minHeight: 44,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-1px)'
                  e.currentTarget.style.borderColor = 'rgba(236,72,153,0.45)'
                  e.currentTarget.style.color = '#ec4899'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)'
                  e.currentTarget.style.borderColor = 'var(--color-border-soft)'
                  e.currentTarget.style.color = 'var(--color-text-2)'
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                  <polyline points="22,6 12,13 2,6"></polyline>
                </svg>
                {user.external_links.email}
              </a>
            )}
          </div>
        )}

        {/* §3.6 Profile Action Row — only for !isMe */}
        {!isMe && (
          <div style={{ display: 'flex', gap: 10, marginTop: 14, width: '100%' }}>
            <button
              onClick={onToggleFollow}
              disabled={isFollowingPending}
              onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)' }}
              onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)' }}
              onMouseDown={(e) => { e.currentTarget.style.transform = 'scale(0.98)' }}
              onMouseUp={(e) => { e.currentTarget.style.transform = 'translateY(-1px)' }}
              style={{
                flex: 1,
                minHeight: 44, padding: '12px 18px',
                borderRadius: 12,
                background: isFollowing ? 'var(--color-surface-2)' : 'linear-gradient(135deg, #ec4899, #f43f5e)',
                color: isFollowing ? 'var(--color-text-2)' : '#fff',
                border: isFollowing ? '1px solid var(--color-border)' : 'none',
                fontSize: 14, fontWeight: 700,
                cursor: isFollowingPending ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
                boxShadow: isFollowing ? 'none' : '0 8px 22px rgba(236,72,153,0.32)',
                transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), background 0.2s, color 0.2s, box-shadow 0.2s',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}
            >
              {/* TODO(designer): wire spinner UI when main pipeline wires the call */}
              {isFollowing ? (
                <>Following<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg></>
              ) : 'Follow'}
            </button>
            <button
              onClick={() => {
                // TODO(claude): wire DM endpoint — POST /api/v1/messages/ or similar
              }}
              aria-label="Message"
              style={{
                width: 44, height: 44, minWidth: 44, flexShrink: 0,
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 12, cursor: 'pointer',
                color: 'var(--color-text-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'border-color 0.18s, color 0.18s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(236,72,153,0.45)'; e.currentTarget.style.color = '#ec4899' }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text-2)' }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
