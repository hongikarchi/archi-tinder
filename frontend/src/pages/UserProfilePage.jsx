import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

// TODO: Replace with API call
const MOCK_USER = {
  user_id: 1,
  display_name: "Kim Minseo",
  avatar_url: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&q=80",
  bio: "Architecture student at SNU, obsessed with brutalism and minimal design.",
  mbti: "INTJ",
  external_links: {
    instagram: "@kimarch",
    email: "kim@example.com"
  },
  follower_count: 42,
  following_count: 18,
  is_following: false,
  boards: Array.from({ length: 24 }).map((_, i) => ({
    board_id: `proj_${123 + i}`,
    name: [
      "Museum References", "Concrete Dreams", "Minimalist Living", "Urban Brutalism",
      "Wood & Light", "Glass Facades", "Parametric Forms", "Public Spaces",
      "Residential Concepts", "Adaptive Reuse"
    ][i % 10] + (i >= 10 ? ` Vol.${Math.floor(i/10) + 1}` : ""),
    date: `April 2026`,
    visibility: i % 5 === 0 ? "private" : "public",
    building_count: Math.floor(Math.random() * 50) + 5,
    cover_image_url: [
      "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&q=80",
      "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=800&q=80",
      "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800&q=80",
      "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80",
      "https://images.unsplash.com/photo-1511818966892-d7d671e672a2?w=800&q=80",
      "https://images.unsplash.com/photo-1524815340653-53d719ce3660?w=800&q=80"
    ][i % 6],
    // TODO(claude): backend should add thumbnails[6] to /api/v1/boards/{id}/ minimal response or replace with derived top-N images
    thumbnails: Array.from({ length: 6 }).map((_, j) => [
      "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=200&q=80",
      "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=200&q=80",
      "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=200&q=80",
      "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=200&q=80",
      "https://images.unsplash.com/photo-1511818966892-d7d671e672a2?w=200&q=80",
      "https://images.unsplash.com/photo-1524815340653-53d719ce3660?w=200&q=80",
      "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=200&q=80",
      "https://images.unsplash.com/photo-1506146332389-18140dc7b2fb?w=200&q=80"
    ][(i * 3 + j) % 8])
  })),
  persona_summary: {
    persona_type: "The Parametric Visionary",
    one_liner: "They seek purity where form and light converge",
    styles: ["Modern", "Parametric"],
    programs: ["Museum", "Public"]
  }
}


function BoardCard({ board }) {
  const [isFlipped, setIsFlipped] = useState(false)
  const navigate = useNavigate()

  const isPublic = board.visibility === 'public'
  const visibilityChipBg = isPublic ? 'rgba(236,72,153,0.18)' : 'rgba(239,68,68,0.18)'
  const visibilityChipColor = isPublic ? '#ec4899' : '#ef4444'
  const visibilityChipBorder = isPublic ? 'rgba(236,72,153,0.35)' : 'rgba(239,68,68,0.35)'

  return (
    <div
      style={{
        perspective: '1200px',
        width: '100%',
        aspectRatio: '3/4',
        cursor: 'pointer',
        userSelect: 'none', WebkitUserSelect: 'none', touchAction: 'none',
      }}
      onClick={(e) => {
        if (e.target.closest('button')) return
        setIsFlipped(!isFlipped)
      }}
    >
      <div style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        transformStyle: 'preserve-3d',
        transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)'
      }}>
        {/* FRONT FACE */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          borderRadius: 20, overflow: 'hidden',
          boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
        }}>
          <img
            src={board.cover_image_url}
            alt={board.name}
            style={{
              position: 'absolute', inset: 0,
              width: '100%', height: '100%',
              objectFit: 'cover', objectPosition: 'center'
            }}
          />

          {/* Cinematic gradient overlay */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            height: '60%',
            background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.6) 38%, rgba(0,0,0,0.12) 72%, transparent 100%)',
            pointerEvents: 'none',
          }} />

          {/* Visibility chip (corner pill) — replaces previous lock icon */}
          <div style={{
            position: 'absolute', top: 14, right: 14,
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '4px 10px', borderRadius: 999,
            background: visibilityChipBg,
            color: visibilityChipColor,
            border: `1px solid ${visibilityChipBorder}`,
            backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
            fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
          }}>
            {!isPublic && (
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
              </svg>
            )}
            {isPublic ? 'Public' : 'Private'}
          </div>

          <div style={{
            position: 'absolute', left: 0, right: 0, bottom: 0,
            display: 'flex', flexDirection: 'column',
            padding: '16px 18px 20px',
          }}>
            <h2 style={{
              color: '#fff', fontSize: 18, fontWeight: 700, lineHeight: 1.3,
              margin: '0 0 3px',
              overflow: 'hidden', textOverflow: 'ellipsis',
              display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical'
            }}>
              {board.name}
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: 12, margin: '0 0 12px', fontStyle: 'italic' }}>
              Curated Board
            </p>

            <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12 }} />

            {/* Tightened 2-col meta strip (Created / Saved); Visibility moved to corner chip */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px', alignItems: 'baseline' }}>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{
                  color: 'rgba(255,255,255,0.5)', fontSize: 10,
                  letterSpacing: '0.06em', textTransform: 'uppercase',
                  marginBottom: 2, fontWeight: 600,
                }}>
                  Created
                </span>
                <span style={{
                  color: '#fff', fontSize: 12, fontWeight: 600,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {board.date}
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{
                  color: 'rgba(255,255,255,0.5)', fontSize: 10,
                  letterSpacing: '0.06em', textTransform: 'uppercase',
                  marginBottom: 2, fontWeight: 600,
                }}>
                  Saved
                </span>
                <span style={{
                  color: '#fff', fontSize: 12, fontWeight: 600,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {board.building_count} photos
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* BACK FACE */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          transform: 'rotateY(180deg)',
          borderRadius: 20, overflow: 'hidden',
          boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
          background: '#000',
          display: 'flex',
          flexDirection: 'column'
        }}>
          {/* scrollbarWidth hides Firefox scrollbar; WebKit::-webkit-scrollbar requires CSS file
              (can't be set via inline style). Acceptable visual trade-off given inline-style constraint. */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px 16px 0', scrollbarWidth: 'none' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
              {board.thumbnails?.map((thumb, idx) => (
                <div key={idx} style={{ aspectRatio: '1', borderRadius: 8, overflow: 'hidden', background: '#222' }}>
                  <img src={thumb} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
              ))}
            </div>
          </div>

          <div style={{ padding: '16px', background: 'linear-gradient(to top, rgba(0,0,0,0.95) 20%, transparent 100%)' }}>
            <button
              onClick={() => navigate('/library/' + board.board_id)}
              style={{
                width: '100%', padding: '10px 14px', borderRadius: 10,
                background: 'rgba(255,255,255,0.09)',
                border: '1px solid rgba(255,255,255,0.18)',
                color: '#fff', fontSize: 12, fontWeight: 600,
                cursor: 'pointer', fontFamily: 'inherit',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                minHeight: 44,
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
              </svg>
              View Gallery · {board.building_count} photos
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}


export default function UserProfilePage({ theme, onToggleTheme, onLogout }) {
  const [isFollowing, setIsFollowing] = useState(MOCK_USER.is_following)
  const [followerCount, setFollowerCount] = useState(MOCK_USER.follower_count)
  const navigate = useNavigate()

  const isMe = true // TODO(claude): check if profile user_id === active session user_id

  function handleToggleFollow() {
     // TODO(claude): POST /api/v1/users/{id}/follow/ or DELETE
     setIsFollowing(!isFollowing)
     setFollowerCount(prev => isFollowing ? prev - 1 : prev + 1)
  }

  // External-link helpers (pure derivations — no hooks)
  const igHandle = MOCK_USER.external_links?.instagram?.replace(/^@/, '') || ''
  const igUrl = igHandle ? `https://instagram.com/${igHandle}` : null
  const emailUrl = MOCK_USER.external_links?.email ? `mailto:${MOCK_USER.external_links.email}` : null

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(100px + env(safe-area-inset-bottom))'
    }}>
      {/* Ambient brand-pink glow — on-brand */}
      <div style={{
        position: 'fixed', top: '-10%', left: '-10%', width: '120%', height: '50%',
        background: 'radial-gradient(circle at 50% 0%, rgba(236,72,153,0.10) 0%, transparent 70%)',
        pointerEvents: 'none', zIndex: 0,
      }} />

      {/* Sticky Header — Back left, title center, controls right (when isMe) */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 10,
        background: 'var(--color-header-bg, rgba(10, 10, 12, 0.65))',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        padding: '12px 16px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        borderBottom: '1px solid var(--color-border-soft)',
        gap: 8,
      }}>
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
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
        </button>

        <h2 style={{
          color: 'var(--color-text)', fontSize: 17, fontWeight: 800,
          margin: 0, letterSpacing: '-0.01em',
        }}>
          Profile
        </h2>

        {/* Right-side controls — only shown for own profile (MainLayout hides its own chrome on /user/*) */}
        {isMe ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              onClick={onToggleTheme}
              aria-label="Toggle theme"
              title={theme === 'light' ? 'Switch to dark' : 'Switch to light'}
              style={{
                width: 44, height: 44, minWidth: 44,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'transparent', border: 'none',
                color: 'var(--color-text-dim)', cursor: 'pointer',
                borderRadius: 12,
                transition: 'color 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = '#ec4899' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-dim)' }}
            >
              {theme === 'light' ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="4"></circle>
                  <line x1="12" y1="2" x2="12" y2="5"></line>
                  <line x1="12" y1="19" x2="12" y2="22"></line>
                  <line x1="4.93" y1="4.93" x2="7.05" y2="7.05"></line>
                  <line x1="16.95" y1="16.95" x2="19.07" y2="19.07"></line>
                  <line x1="2" y1="12" x2="5" y2="12"></line>
                  <line x1="19" y1="12" x2="22" y2="12"></line>
                  <line x1="4.93" y1="19.07" x2="7.05" y2="16.95"></line>
                  <line x1="16.95" y1="7.05" x2="19.07" y2="4.93"></line>
                </svg>
              )}
            </button>
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
          <div style={{ width: 44, height: 44 }} aria-hidden="true" />
        )}
      </div>

      {/* Unified responsive container (max-width 1100) — hero column nests narrower constraint */}
      <div style={{ position: 'relative', zIndex: 1, maxWidth: 1100, margin: '0 auto', padding: '32px 20px 40px' }}>

        {/* HERO BLOCK — narrower nested column */}
        <div style={{ maxWidth: 480, margin: '0 auto', marginBottom: 28 }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>

            {/* Avatar w/ on-brand pink-rose ambient halo */}
            <div style={{ position: 'relative', marginBottom: 18 }}>
              <div style={{
                position: 'absolute', inset: -6, borderRadius: '50%',
                background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                opacity: 0.55, filter: 'blur(12px)',
              }} />
              <img
                src={MOCK_USER.avatar_url}
                alt="avatar"
                style={{
                  width: 108, height: 108, borderRadius: '50%',
                  border: '2px solid var(--color-border-soft)',
                  objectFit: 'cover', position: 'relative', zIndex: 2,
                  background: 'var(--color-surface)',
                }}
              />
            </div>

            {/* Name + MBTI chip */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
              <h1 style={{
                color: 'var(--color-text)', fontSize: 26, fontWeight: 800,
                margin: 0, lineHeight: 1.2, letterSpacing: '-0.01em',
              }}>
                {MOCK_USER.display_name}
              </h1>
              {MOCK_USER.mbti && (
                <span style={{
                  display: 'inline-flex', alignItems: 'center',
                  padding: '4px 10px', borderRadius: 999,
                  background: 'rgba(236,72,153,0.15)',
                  color: '#ec4899',
                  fontWeight: 700, fontSize: 11, letterSpacing: '0.04em',
                  border: '1px solid rgba(236,72,153,0.25)',
                }}>
                  {MOCK_USER.mbti}
                </span>
              )}
            </div>

            <p style={{
              color: 'var(--color-text-dim)', fontSize: 15, lineHeight: 1.6,
              margin: '0 0 18px', maxWidth: 320, fontWeight: 500,
            }}>
              {MOCK_USER.bio}
            </p>

            {/* External links — Instagram + email pills */}
            {(igUrl || emailUrl) && (
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center', marginBottom: 22 }}>
                {igUrl && (
                  <a
                    href={igUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 7,
                      padding: '8px 14px', borderRadius: 999,
                      background: 'var(--color-surface-2, rgba(255,255,255,0.04))',
                      border: '1px solid var(--color-border-soft)',
                      color: 'var(--color-text-2)',
                      textDecoration: 'none', fontSize: 13, fontWeight: 600,
                      transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.18s, color 0.18s',
                      minHeight: 36,
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
                    {MOCK_USER.external_links.instagram}
                  </a>
                )}
                {emailUrl && (
                  <a
                    href={emailUrl}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 7,
                      padding: '8px 14px', borderRadius: 999,
                      background: 'var(--color-surface-2, rgba(255,255,255,0.04))',
                      border: '1px solid var(--color-border-soft)',
                      color: 'var(--color-text-2)',
                      textDecoration: 'none', fontSize: 13, fontWeight: 600,
                      transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.18s, color 0.18s',
                      minHeight: 36,
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
                    {MOCK_USER.external_links.email}
                  </a>
                )}
              </div>
            )}

            {/* Following / Followers card */}
            <div style={{
              display: 'flex', gap: 32, padding: '16px 36px',
              background: 'var(--color-surface)', borderRadius: 24,
              border: '1px solid var(--color-border-soft)',
              boxShadow: '0 10px 30px rgba(0,0,0,0.1)',
            }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <span style={{ color: 'var(--color-text)', fontSize: 22, fontWeight: 800 }}>
                  {MOCK_USER.following_count}
                </span>
                <span style={{
                  color: 'var(--color-text-dimmer)', fontSize: 12, fontWeight: 600,
                  letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 4,
                }}>
                  Following
                </span>
              </div>
              <div style={{ width: 1, background: 'var(--color-border-soft)' }} />
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <span style={{ color: 'var(--color-text)', fontSize: 22, fontWeight: 800 }}>
                  {followerCount}
                </span>
                <span style={{
                  color: 'var(--color-text-dimmer)', fontSize: 12, fontWeight: 600,
                  letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 4,
                }}>
                  Followers
                </span>
              </div>
            </div>
          </div>

          {/* PERSONA card — restored, polished. Renders for every user (not just self). */}
          {MOCK_USER.persona_summary && (
            <div style={{
              marginTop: 22,
              padding: '20px 22px 22px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border-soft)',
              borderRadius: 20,
              boxShadow: '0 10px 30px rgba(0,0,0,0.1)',
              position: 'relative', overflow: 'hidden',
            }}>
              {/* Subtle internal glow */}
              <div style={{
                position: 'absolute', top: -40, right: -40,
                width: 160, height: 160, borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(236,72,153,0.18), transparent 70%)',
                pointerEvents: 'none',
              }} />

              <span style={{
                display: 'inline-block',
                color: '#ec4899', fontSize: 11, fontWeight: 700,
                letterSpacing: '0.12em', textTransform: 'uppercase',
                marginBottom: 6,
              }}>
                Persona
              </span>
              <h3 style={{
                margin: '0 0 8px',
                fontSize: 22, fontWeight: 800, lineHeight: 1.2,
                letterSpacing: '-0.01em',
                background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                color: '#ec4899',
              }}>
                {MOCK_USER.persona_summary.persona_type}
              </h3>
              <p style={{
                margin: '0 0 16px',
                color: 'var(--color-text-dim)', fontSize: 14, lineHeight: 1.5,
                fontStyle: 'italic',
              }}>
                &ldquo;{MOCK_USER.persona_summary.one_liner}&rdquo;
              </p>

              {/* Style chips */}
              {MOCK_USER.persona_summary.styles?.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <span style={{
                    display: 'block',
                    color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 700,
                    letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6,
                  }}>
                    Styles
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {MOCK_USER.persona_summary.styles.map(s => (
                      <span key={s} style={{
                        display: 'inline-block',
                        padding: '6px 12px', borderRadius: 999,
                        background: 'rgba(236,72,153,0.18)',
                        color: '#ffffff',
                        fontSize: 12, fontWeight: 600,
                        border: '1px solid rgba(236,72,153,0.30)',
                      }}>
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Program chips */}
              {MOCK_USER.persona_summary.programs?.length > 0 && (
                <div>
                  <span style={{
                    display: 'block',
                    color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 700,
                    letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6,
                  }}>
                    Programs
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {MOCK_USER.persona_summary.programs.map(p => (
                      <span key={p} style={{
                        display: 'inline-block',
                        padding: '6px 12px', borderRadius: 999,
                        background: 'rgba(236,72,153,0.18)',
                        color: '#ffffff',
                        fontSize: 12, fontWeight: 600,
                        border: '1px solid rgba(236,72,153,0.30)',
                      }}>
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Follow button — only for non-self profiles */}
          {!isMe && (
            <button
              onClick={handleToggleFollow}
              style={{
                width: '100%', minHeight: 48, padding: '14px',
                borderRadius: 14,
                background: isFollowing
                  ? 'var(--color-surface-2)'
                  : 'linear-gradient(135deg, #ec4899, #f43f5e)',
                color: isFollowing ? 'var(--color-text-2)' : '#fff',
                fontSize: 15, fontWeight: 700,
                border: isFollowing ? '1px solid var(--color-border)' : 'none',
                cursor: 'pointer',
                marginTop: 22,
                boxShadow: isFollowing ? 'none' : '0 8px 20px rgba(236,72,153,0.3)',
                transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
                fontFamily: 'inherit',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)' }}
              onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)' }}
            >
              {/* TODO(designer): wire spinner UI when main pipeline wires the call */}
              {isFollowing ? 'Following' : 'Follow'}
            </button>
          )}
        </div>

        {/* Boards section header */}
        <div style={{
          display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
          marginTop: 24, marginBottom: 16, padding: '0 4px',
        }}>
          <div>
            <h3 style={{
              color: 'var(--color-text)', fontSize: 20, fontWeight: 800,
              margin: 0, letterSpacing: '-0.01em',
            }}>
              Curated Boards
            </h3>
            <p style={{
              margin: '4px 0 0', color: 'var(--color-text-dimmer)', fontSize: 12,
            }}>
              {MOCK_USER.boards.length} board{MOCK_USER.boards.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        {/* Boards grid — same unified container, responsive auto-fill */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 20,
        }}>
          {MOCK_USER.boards.map(board => (
            <BoardCard key={board.board_id} board={board} />
          ))}
        </div>

      </div>
    </div>
  )
}
