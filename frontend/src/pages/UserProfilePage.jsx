import { useState, useEffect, Fragment } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getUserProfile } from '../api/client.js'
import { useImageTelemetry } from '../hooks/useImageTelemetry.js'

/**
 * formatBoardDate — converts ISO 8601 timestamp to "Month YYYY" display string.
 * Handles null / undefined / invalid strings safely.
 */
function formatBoardDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    return d.toLocaleString('en-US', { month: 'long', year: 'numeric' })
  } catch {
    return ''
  }
}

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
    // Stable count (no Math.random() — value is shown twice on flip-card front + View Gallery btn,
    // and re-renders would otherwise produce mismatched values on each render)
    building_count: 8 + ((i * 7) % 47),
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
      "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&q=80",
      "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=800&q=80",
      "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800&q=80",
      "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80",
      "https://images.unsplash.com/photo-1511818966892-d7d671e672a2?w=800&q=80",
      "https://images.unsplash.com/photo-1524815340653-53d719ce3660?w=800&q=80",
      "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=800&q=80",
      "https://images.unsplash.com/photo-1506146332389-18140dc7b2fb?w=800&q=80"
    ][(i * 3 + j) % 8])
  })),
  persona_summary: {
    persona_type: "The Parametric Visionary",
    one_liner: "They seek purity where form and light converge",
    styles: ["Modern", "Parametric"],
    programs: ["Museum", "Public"]
  }
}


/**
 * InfoCol — local primitive for §3.5.2 RICH PATTERN 2-col info grid.
 *   Caps label (10/600 uppercase 0.06em) + single-line ellipsis value (13/600 white).
 */
function InfoCol({ label, value }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      <span style={{
        color: 'rgba(255,255,255,0.5)',
        fontSize: 10, fontWeight: 600,
        letterSpacing: '0.06em', textTransform: 'uppercase',
        marginBottom: 2,
      }}>
        {label}
      </span>
      <span style={{
        color: '#fff', fontSize: 13, fontWeight: 600,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {value}
      </span>
    </div>
  )
}


/**
 * BoardCard — flip card per DESIGN.md §3.5.4
 *   Front face: image-overlay card per §3.5.1 + §3.5.2 RICH PATTERN
 *               (title + "Curated Board" sub-italic + divider + 2-col CREATED/SAVED grid)
 *               + §3.5.3 PRIVATE-only icon-lock chip (PUBLIC = no chip).
 *   Back face: swipe-style horizontal full-bleed gallery per §3.5.5 + persistent "View Gallery" action bar.
 *
 * Hover lift YES, hover border NO per §3.5.4. The subtle translateY(-4px) lift matches
 * every other interactive card in the app; only the pink border is omitted because a
 * static border lingers awkwardly behind the rotating card.
 */
function BoardCard({ board }) {
  const [isFlipped, setIsFlipped] = useState(false)
  const [isHovered, setIsHovered] = useState(false)
  const navigate = useNavigate()

  const isPrivate = board.visibility === 'private'

  const { onLoad: coverOnLoad, onError: coverOnError } = useImageTelemetry({
    buildingId: board.board_id,
    context: 'user_profile_board_cover',
  })
  const { onError: thumbOnError } = useImageTelemetry({
    buildingId: board.board_id,
    context: 'user_profile_board_thumb',
  })

  return (
    <div
      style={{
        perspective: '1200px',
        width: '100%',
        aspectRatio: '3/4',
        cursor: 'pointer',
        userSelect: 'none', WebkitUserSelect: 'none', touchAction: 'manipulation',
        // §3.5.4: lift YES, border NO. Lift on outer perspective wrapper so it doesn't
        // double-compose with the inner rotateY transform.
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
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
        {/* FRONT FACE — image-overlay per §3.5.1 + §3.5.2 RICH PATTERN + §3.5.3 (PRIVATE-only icon chip) */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          borderRadius: 20, overflow: 'hidden',
          boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
          background: 'rgba(255,255,255,0.03)',
        }}>
          <img
            src={board.cover_image_url}
            alt={board.name}
            loading="lazy"
            onLoad={coverOnLoad}
            onError={coverOnError}
            style={{
              position: 'absolute', inset: 0,
              width: '100%', height: '100%',
              objectFit: 'cover', objectPosition: 'center',
              display: 'block',
            }}
          />

          {/* §3.5.1 mandatory bottom gradient overlay for legibility */}
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.4) 50%, transparent 100%)',
            pointerEvents: 'none',
          }} />

          {/* §3.5.3 PRIVATE-only icon chip — small dark blur circle, white-ish lock SVG.
              PUBLIC renders nothing (public is the default; only flag the exception). */}
          {isPrivate && (
            <div style={{
              position: 'absolute', top: 16, right: 16,
              background: 'rgba(0,0,0,0.4)',
              backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
              padding: 6, borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            aria-label="Private board"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                   stroke="rgba(255,255,255,0.85)" strokeWidth="2"
                   strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
              </svg>
            </div>
          )}

          {/* §3.5.2 RICH PATTERN: title + "Curated Board" sub-italic + divider + 2-col CREATED/SAVED grid */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            padding: '16px 18px 20px',
          }}>
            <h2 style={{
              color: '#fff', fontSize: 18, fontWeight: 700, lineHeight: 1.3,
              margin: '0 0 3px',
              display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
              overflow: 'hidden', textOverflow: 'ellipsis',
            }}>
              {board.name}
            </h2>
            <p style={{
              color: 'rgba(255,255,255,0.55)', fontSize: 12,
              margin: '0 0 12px', fontStyle: 'italic',
            }}>
              Curated Board
            </p>
            <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12 }} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
              <InfoCol label="CREATED" value={board.date} />
              <InfoCol label="SAVED" value={`${board.building_count} photos`} />
            </div>
          </div>
        </div>

        {/* BACK FACE — §3.5.5 swipe-style horizontal full-bleed gallery */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          transform: 'rotateY(180deg)',
          borderRadius: 20, overflow: 'hidden',
          boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
          background: '#000',
          display: 'flex', flexDirection: 'column',
        }}>
          {/* §3.5.5 Left scroll indicator — sibling of scroll container, pointerEvents none */}
          <div style={{
            position: 'absolute', left: 10, top: '50%',
            transform: 'translateY(-50%)',
            pointerEvents: 'none',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 32, height: 32, borderRadius: '50%',
            background: 'rgba(0,0,0,0.32)', backdropFilter: 'blur(6px)',
            zIndex: 2,
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                 stroke="rgba(255,255,255,0.85)" strokeWidth="2.5"
                 strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </div>
          {/* §3.5.5 Right scroll indicator */}
          <div style={{
            position: 'absolute', right: 10, top: '50%',
            transform: 'translateY(-50%)',
            pointerEvents: 'none',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 32, height: 32, borderRadius: '50%',
            background: 'rgba(0,0,0,0.32)', backdropFilter: 'blur(6px)',
            zIndex: 2,
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                 stroke="rgba(255,255,255,0.85)" strokeWidth="2.5"
                 strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </div>

          {/* Scroll container with scroll-snap — one image per snap point */}
          <div
            className="hide-scrollbar"
            style={{
              flex: 1,
              overflowX: 'auto',
              overflowY: 'hidden',
              display: 'flex',
              scrollSnapType: 'x mandatory',
              WebkitOverflowScrolling: 'touch',
              scrollbarWidth: 'none',
              msOverflowStyle: 'none',
            }}
          >
            {board.thumbnails?.map((img, i) => (
              <div key={i} style={{
                flex: '0 0 100%',
                height: '100%',
                scrollSnapAlign: 'start',
                position: 'relative',
              }}>
                <img
                  src={img}
                  alt=""
                  loading="lazy"
                  onError={thumbOnError}
                  style={{
                    width: '100%', height: '100%',
                    objectFit: 'cover',
                    display: 'block',
                  }}
                />
              </div>
            ))}
          </div>

          {/* Persistent action bar — §3.5.5 4-stop soft gradient */}
          <div style={{
            padding: '20px 16px 16px',
            background: 'linear-gradient(to top, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.65) 45%, rgba(0,0,0,0.18) 80%, transparent 100%)',
          }}>
            <button
              onClick={() => navigate('/library/' + board.board_id)}
              style={{
                width: '100%', minHeight: 44,
                padding: '10px 14px', borderRadius: 12,
                background: 'rgba(255,255,255,0.10)',
                border: '1px solid rgba(255,255,255,0.18)',
                color: '#fff', fontSize: 13, fontWeight: 600,
                cursor: 'pointer', fontFamily: 'inherit',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                transition: 'background 0.18s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(236,72,153,0.18)'
                e.currentTarget.style.borderColor = 'rgba(236,72,153,0.45)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.10)'
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.18)'
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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


/**
 * BioPersonaFlipCard — §3.5.4 Hero Flip variant (text-on-surface, profile pages)
 *   Front: italic bio + "tap to reveal persona" caption
 *   Back: persona_type gradient text + one_liner + Styles/Programs chip rows + MBTI bottom-right
 *   Internal radial-gradient pink glow. Lift YES, border YES (text-on-surface needs containment).
 */
function BioPersonaFlipCard({ bio, persona, mbti }) {
  const [isFlipped, setIsFlipped] = useState(false)
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div
      style={{
        perspective: '1200px',
        width: '100%',
        minHeight: 180,
        cursor: 'pointer',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
        marginTop: 18, marginBottom: 18,
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={(e) => {
        if (e.target.closest('button')) return
        setIsFlipped(f => !f)
      }}
    >
      <div style={{
        width: '100%', minHeight: 180,
        position: 'relative',
        transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        transformStyle: 'preserve-3d',
        transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
      }}>
        {/* FRONT — italic bio + "tap to reveal persona" */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          borderRadius: 20,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          padding: '20px 22px',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
          minHeight: 180,
        }}>
          {/* Internal radial-gradient pink glow */}
          <div style={{
            position: 'absolute', top: -40, right: -40,
            width: 160, height: 160, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(236,72,153,0.18), transparent 70%)',
            pointerEvents: 'none',
          }} />
          <p style={{
            position: 'relative', zIndex: 1,
            margin: 0,
            color: 'var(--color-text-dim)', fontSize: 15, lineHeight: 1.6,
            fontStyle: 'italic', fontWeight: 500,
          }}>
            {bio}
          </p>
          <span style={{
            position: 'relative', zIndex: 1,
            alignSelf: 'flex-end',
            color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
            letterSpacing: '0.04em', textTransform: 'uppercase',
            marginTop: 12,
          }}>
            tap to reveal persona
          </span>
        </div>

        {/* BACK — persona_type gradient + one_liner + chips + MBTI */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          transform: 'rotateY(180deg)',
          borderRadius: 20,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          padding: '20px 22px',
          display: 'flex', flexDirection: 'column',
          boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
          minHeight: 180,
        }}>
          {/* Internal radial-gradient pink glow */}
          <div style={{
            position: 'absolute', top: -40, right: -40,
            width: 160, height: 160, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(236,72,153,0.18), transparent 70%)',
            pointerEvents: 'none',
          }} />
          <h3 style={{
            position: 'relative', zIndex: 1,
            margin: '0 0 6px',
            fontSize: 20, fontWeight: 700, lineHeight: 1.2,
            letterSpacing: '-0.01em',
            background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            color: '#ec4899',
          }}>
            {persona.persona_type}
          </h3>
          {persona.one_liner && (
            <p style={{
              position: 'relative', zIndex: 1,
              margin: '0 0 14px',
              color: 'var(--color-text-dim)', fontSize: 13, lineHeight: 1.5,
              fontStyle: 'italic', fontWeight: 500,
            }}>
              &ldquo;{persona.one_liner}&rdquo;
            </p>
          )}
          {persona.styles?.length > 0 && (
            <div style={{ position: 'relative', zIndex: 1, marginBottom: 10 }}>
              <span style={{
                display: 'block',
                color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
                letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6,
              }}>
                Styles
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {persona.styles.map(s => (
                  <span key={s} style={{
                    display: 'inline-block',
                    padding: '4px 10px', borderRadius: 999,
                    background: 'rgba(236,72,153,0.15)',
                    color: '#ec4899',
                    fontSize: 11, fontWeight: 600,
                  }}>
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
          {persona.programs?.length > 0 && (
            <div style={{ position: 'relative', zIndex: 1 }}>
              <span style={{
                display: 'block',
                color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
                letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6,
              }}>
                Programs
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {persona.programs.map(p => (
                  <span key={p} style={{
                    display: 'inline-block',
                    padding: '4px 10px', borderRadius: 999,
                    background: 'rgba(236,72,153,0.15)',
                    color: '#ec4899',
                    fontSize: 11, fontWeight: 600,
                  }}>
                    {p}
                  </span>
                ))}
              </div>
            </div>
          )}
          {/* MBTI subtle bottom-right */}
          {mbti && (
            <span style={{
              position: 'absolute', bottom: 12, right: 14, zIndex: 1,
              color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
              letterSpacing: '0.08em',
            }}>
              {mbti}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}


export default function UserProfilePage({ theme, onToggleTheme, onLogout }) {
  const { userId: routeUserId } = useParams()
  const navigate = useNavigate()

  const sessionUserId = sessionStorage.getItem('archithon_user')
  const effectiveUserId = routeUserId || sessionUserId
  const isMe = !routeUserId || String(routeUserId) === String(sessionUserId)

  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [isFollowing, setIsFollowing] = useState(false)
  const [followerCount, setFollowerCount] = useState(0)

  useEffect(() => {
    if (!effectiveUserId) {
      setLoading(false)
      setError('No user ID found.')
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getUserProfile(effectiveUserId)
      .then(data => {
        if (cancelled) return
        // Boards adapter: map project_id -> board_id + format ISO date -> "Month YYYY"
        const boards = (data.boards || []).map(b => ({
          ...b,
          board_id: b.project_id,
          date: formatBoardDate(b.date),
        }))
        setUser({ ...data, boards })
        setIsFollowing(false)  // is_following: Phase 15 SOC1 territory
        setFollowerCount(data.follower_count || 0)
      })
      .catch(err => {
        if (cancelled) return
        setError(err.message || 'Failed to load profile.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [effectiveUserId])

  function handleToggleFollow() {
     // TODO(claude): POST /api/v1/users/{id}/follow/ or DELETE
     setIsFollowing(!isFollowing)
     setFollowerCount(prev => isFollowing ? prev - 1 : prev + 1)
  }

  // External-link helpers (pure derivations — no hooks)
  const igHandle = user?.external_links?.instagram?.replace(/^@/, '') || ''
  const igUrl = igHandle ? `https://instagram.com/${igHandle}` : null
  const emailUrl = user?.external_links?.email ? `mailto:${user.external_links.email}` : null

  if (loading) {
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 14,
      }}>
        Loading profile...
      </div>
    )
  }

  if (error || !user) {
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 14,
      }}>
        {error || 'Profile not found.'}
      </div>
    )
  }

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
          color: 'var(--color-text)', fontSize: 17, fontWeight: 700,
          margin: 0, letterSpacing: '-0.01em',
        }}>
          Profile
        </h2>

        {/* Right-side controls — only shown for own profile */}
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

      {/* Unified responsive container (max-width 1100) */}
      <div style={{ position: 'relative', zIndex: 1, maxWidth: 1100, margin: '0 auto', padding: '32px 20px 40px' }}>

        {/* HERO BLOCK — narrower nested column (max-width 480) */}
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
                { count: user.boards.length, label: 'Boards' },
                { count: followerCount, label: 'Followers' },
                { count: user.following_count, label: 'Following' },
              ].map((stat, i, arr) => (
                <Fragment key={stat.label}>
                  <button
                    onClick={() => {
                      if (stat.label === 'Boards') {
                        // TODO(claude): navigate to user's boards list when route exists
                      } else if (stat.label === 'Followers') {
                        // TODO(claude): navigate to followers list — GET /api/v1/users/{id}/followers/
                      } else {
                        // TODO(claude): navigate to following list — GET /api/v1/users/{id}/following/
                      }
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
                  onClick={handleToggleFollow}
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
                    cursor: 'pointer', fontFamily: 'inherit',
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

        {/* Boards section header */}
        <div style={{
          display: 'flex', alignItems: 'baseline', gap: 12,
          marginBottom: 20, padding: '0 4px',
        }}>
          <h3 style={{
            color: 'var(--color-text)', fontSize: 20, fontWeight: 700,
            margin: 0, letterSpacing: '-0.01em',
          }}>
            Curated Boards
          </h3>
          <span style={{
            color: 'var(--color-text-dimmer)', fontSize: 13, fontWeight: 600,
          }}>
            {user.boards.length}
          </span>
        </div>

        {/* Boards grid — same unified container, responsive auto-fill */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 20,
        }}>
          {user.boards.map(board => (
            <BoardCard key={board.board_id} board={board} />
          ))}
        </div>

      </div>
    </div>
  )
}
