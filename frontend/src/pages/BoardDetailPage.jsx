import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useImageTelemetry } from '../hooks/useImageTelemetry.js'

// TODO(claude): Replace MOCK_BOARD with API call to GET /api/v1/boards/${boardId}/
// Returns: { board_id, name, visibility, owner{user_id, display_name, avatar_url},
// buildings[], reaction_count, is_reacted }
// TODO(claude): Backend should add `cover_image_url` to Board Detail response (or
// derive on the frontend from buildings[0].image_url as fallback). Currently this
// mockup shows it as a top-level field.
const MOCK_BOARD = {
  board_id: "proj_123",
  name: "Museum References",
  visibility: "public",
  cover_image_url: "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1600&q=80",
  owner: {
    user_id: 1,
    display_name: "Kim Minseo",
    avatar_url: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&q=80",
  },
  buildings: [
    {
      building_id: "B00042",
      name_en: "Seattle Central Library",
      image_url: "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&q=80",
      architect: "OMA / Rem Koolhaas",
      year: 2004,
      program: "Public",
      city: "Seattle",
    },
    {
      building_id: "B00109",
      name_en: "Casa da Musica",
      image_url: "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800&q=80",
      architect: "OMA / Rem Koolhaas",
      year: 2005,
      program: "Cultural",
      city: "Porto",
    },
    {
      building_id: "B00231",
      name_en: "Heydar Aliyev Center",
      image_url: "https://images.unsplash.com/photo-1511818966892-d7d671e672a2?w=800&q=80",
      architect: "Zaha Hadid",
      year: 2012,
      program: "Cultural",
      city: "Baku",
    },
    {
      building_id: "B00358",
      name_en: "Therme Vals",
      image_url: "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=800&q=80",
      architect: "Peter Zumthor",
      year: 1996,
      program: "Sports",
      city: "Vals",
    },
    {
      building_id: "B00413",
      name_en: "Centre Pompidou",
      image_url: "https://images.unsplash.com/photo-1524815340653-53d719ce3660?w=800&q=80",
      architect: "Renzo Piano",
      year: 1977,
      program: "Museum",
      city: "Paris",
    },
    {
      building_id: "B00504",
      name_en: "Vitra Fire Station",
      image_url: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80",
      architect: "Zaha Hadid",
      year: 1993,
      program: "Public",
      city: "Weil am Rhein",
    },
    {
      building_id: "B00612",
      name_en: "Fondazione Prada",
      image_url: "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=800&q=80",
      architect: "OMA / Rem Koolhaas",
      year: 2015,
      program: "Museum",
      city: "Milan",
    },
    {
      building_id: "B00718",
      name_en: "Bruder Klaus Field Chapel",
      image_url: "https://images.unsplash.com/photo-1506146332389-18140dc7b2fb?w=800&q=80",
      architect: "Peter Zumthor",
      year: 2007,
      program: "Religion",
      city: "Mechernich",
    },
    {
      building_id: "B00802",
      name_en: "Milstein Hall",
      image_url: "https://images.unsplash.com/photo-1486718448742-163732cd1544?w=800&q=80",
      architect: "OMA / Rem Koolhaas",
      year: 2011,
      program: "Public",
      city: "Ithaca",
    },
    {
      building_id: "B00917",
      name_en: "Maxxi Museum",
      image_url: "https://images.unsplash.com/photo-1496564203457-11bb12075d90?w=800&q=80",
      architect: "Zaha Hadid",
      year: 2010,
      program: "Museum",
      city: "Rome",
    },
    {
      building_id: "B01024",
      name_en: "Kolumba Museum",
      image_url: "https://images.unsplash.com/photo-1481026469463-66327c86e544?w=800&q=80",
      architect: "Peter Zumthor",
      year: 2007,
      program: "Museum",
      city: "Cologne",
    },
    {
      building_id: "B01138",
      name_en: "Whitney Museum",
      image_url: "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=800&q=80",
      architect: "Renzo Piano",
      year: 2015,
      program: "Museum",
      city: "New York",
    },
  ],
  reaction_count: 7,
  is_reacted: false,
}

/**
 * InfoCol — local primitive for §3.5.2 RICH PATTERN 2-col info grid.
 *   Caps label (10/600 uppercase 0.06em) + single-line ellipsis value (13/600 white).
 *   Mirrors the InfoCol used in FirmProfile + UserProfile + PostSwipeLanding.
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
 * BuildingTile — image-overlay card per §3.5.1 + §3.5.2 RICH PATTERN.
 *   - No default border (transparent), hover lifts -4px and adds pink border (§3.5.1).
 *   - Title 18/700 + "Building" sub-italic + divider + 2-col ARCHITECT/YEAR grid.
 *   - NO program corner chip per §3.5.3 — program is metadata, not status; chips are
 *     reserved for binary status state. Matches the rationale used in FirmProfile
 *     ProjectCard (also drops program chip).
 */
function BuildingTile({ building }) {
  const { onLoad, onError } = useImageTelemetry({
    buildingId: building.building_id,
    context: 'board_detail_gallery',
  })

  return (
    <div
      onClick={() => {
        // TODO(claude): navigate to building detail (modal overlay or
        // route `/building/${building.building_id}`) — wire when building
        // detail endpoint / route is decided.
      }}
      style={{
        position: 'relative',
        aspectRatio: '4 / 5',
        borderRadius: 20,
        overflow: 'hidden',
        cursor: 'pointer',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid transparent',          // §3.5.1: NO default light border
        boxShadow: '0 10px 25px rgba(0,0,0,0.3)', // §3.5.1 mandatory depth (static)
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        userSelect: 'none',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)'
        e.currentTarget.style.borderColor = 'rgba(236,72,153,0.55)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.borderColor = 'transparent'
      }}
    >
      <img
        src={building.image_url}
        alt={building.name_en}
        loading="lazy"
        onLoad={onLoad}
        onError={onError}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
        }}
      />

      {/* §3.5.1 mandatory bottom gradient overlay */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.4) 50%, transparent 100%)',
        pointerEvents: 'none',
      }} aria-hidden="true" />

      {/* §3.5.2 RICH PATTERN: title + "Building" sub-italic + divider + 2-col ARCHITECT/YEAR grid */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        padding: '16px 18px 20px',
      }}>
        <h4 style={{
          color: '#fff',
          fontSize: 18,
          fontWeight: 700,
          margin: '0 0 3px',
          lineHeight: 1.3,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {building.name_en}
        </h4>
        <p style={{
          color: 'rgba(255,255,255,0.55)',
          fontSize: 12,
          fontStyle: 'italic',
          margin: '0 0 12px',
        }}>
          Building
        </p>
        <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12 }} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
          <InfoCol label="ARCHITECT" value={building.architect} />
          <InfoCol label="YEAR" value={building.year} />
        </div>
      </div>
    </div>
  )
}

export default function BoardDetailPage() {
  const navigate = useNavigate()
  // TODO(claude): use `boardId` from URL params to fetch board data
  // GET /api/v1/boards/${boardId}/
  const { boardId: _boardId } = useParams()

  const [isReacted, setIsReacted] = useState(MOCK_BOARD.is_reacted)
  const [reactionCount, setReactionCount] = useState(MOCK_BOARD.reaction_count)
  const [isReactHovered, setIsReactHovered] = useState(false)
  const [isReactPressed, setIsReactPressed] = useState(false)
  const [isOwnerRowHovered, setIsOwnerRowHovered] = useState(false)
  const [isBackHovered, setIsBackHovered] = useState(false)
  const [isShareHovered, setIsShareHovered] = useState(false)

  function handleToggleReaction() {
    // TODO(claude): if !isReacted -> POST /api/v1/boards/${MOCK_BOARD.board_id}/react/
    //               else         -> DELETE /api/v1/boards/${MOCK_BOARD.board_id}/react/
    // Response shape: { reaction_count, is_reacted } — sync with server response.
    if (isReacted) {
      setIsReacted(false)
      setReactionCount(prev => Math.max(0, prev - 1))
    } else {
      setIsReacted(true)
      setReactionCount(prev => prev + 1)
    }
  }

  function handleNavigateToOwner() {
    navigate(`/user/${MOCK_BOARD.owner.user_id}`)
  }

  const isPublic = MOCK_BOARD.visibility === 'public'
  const buildings = MOCK_BOARD.buildings || []
  const coverImage = MOCK_BOARD.cover_image_url || (buildings[0] && buildings[0].image_url)

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(80px + env(safe-area-inset-bottom))',
    }}>
      {/* Hero cover */}
      <div style={{
        position: 'relative',
        width: '100%',
        height: 'clamp(280px, 42vw, 360px)',
        overflow: 'hidden',
        background: 'var(--color-surface)',
      }}>
        {coverImage && (
          <img
            src={coverImage}
            alt={MOCK_BOARD.name}
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
        )}

        {/* Bottom gradient overlay (specified in brief) */}
        <div style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(to top, var(--color-bg) 0%, rgba(15,15,15,0.85) 30%, rgba(15,15,15,0.4) 60%, transparent 100%)',
          pointerEvents: 'none',
        }} />

        {/* Sticky header bar overlaid on top of cover */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          padding: '12px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          zIndex: 5,
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, transparent 100%)',
        }}>
          <button
            onClick={() => navigate(-1)}
            onMouseEnter={() => setIsBackHovered(true)}
            onMouseLeave={() => setIsBackHovered(false)}
            aria-label="Back"
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              background: 'rgba(0,0,0,0.4)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: isBackHovered ? '#ec4899' : '#fff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 0,
              transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: isBackHovered ? 'scale(1.05)' : 'scale(1)',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"></line>
              <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
          </button>

          <button
            onClick={() => {
              // TODO(claude): wire share endpoint or use Web Share API.
              // Likely client-side `navigator.share({ url })` with fallback;
              // backend may expose a shareable short-link endpoint.
            }}
            onMouseEnter={() => setIsShareHovered(true)}
            onMouseLeave={() => setIsShareHovered(false)}
            aria-label="Share"
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              background: 'rgba(0,0,0,0.4)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: isShareHovered ? '#ec4899' : '#fff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 0,
              transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: isShareHovered ? 'scale(1.05)' : 'scale(1)',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="18" cy="5" r="3"></circle>
              <circle cx="6" cy="12" r="3"></circle>
              <circle cx="18" cy="19" r="3"></circle>
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
              <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
            </svg>
          </button>
        </div>

        {/* §3.5.3 PRIVATE-only icon-lock chip — small dark blur circle, white-ish lock SVG.
            PUBLIC renders nothing (public is the default; only flag the exception).
            Anchored to hero top-right, sits alongside the back/share row at z-index 5. */}
        {!isPublic && (
          <div style={{
            position: 'absolute',
            top: 68,
            right: 20,
            zIndex: 5,
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

        {/* Hero content overlapping cover bottom */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '24px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          {/* Board name — reduced to 28/700 to align with §3.5 card-system tone (was 32/900 — too display-y). */}
          <h1 style={{
            color: '#fff',
            fontSize: 'clamp(24px, 5vw, 28px)',
            fontWeight: 700,
            margin: 0,
            lineHeight: 1.2,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            textShadow: '0 2px 12px rgba(0,0,0,0.4)',
          }}>
            {MOCK_BOARD.name}
          </h1>

          {/* Owner row */}
          <div
            onClick={handleNavigateToOwner}
            onMouseEnter={() => setIsOwnerRowHovered(true)}
            onMouseLeave={() => setIsOwnerRowHovered(false)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                handleNavigateToOwner()
              }
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 10,
              cursor: 'pointer',
              padding: '6px 4px',
              minHeight: 44,
              userSelect: 'none',
              alignSelf: 'flex-start',
            }}
          >
            <img
              src={MOCK_BOARD.owner.avatar_url}
              alt={MOCK_BOARD.owner.display_name}
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                objectFit: 'cover',
                border: '1px solid rgba(255,255,255,0.25)',
                background: 'var(--color-surface)',
              }}
            />
            <span style={{
              color: '#fff',
              fontSize: 14,
              fontWeight: 600,
              textDecoration: isOwnerRowHovered ? 'underline' : 'none',
              textUnderlineOffset: 3,
            }}>
              {MOCK_BOARD.owner.display_name}
            </span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.65)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </div>

          {/* Meta strip */}
          <p style={{
            color: 'rgba(255,255,255,0.7)',
            fontSize: 12,
            fontWeight: 600,
            margin: 0,
            letterSpacing: '0.02em',
          }}>
            {buildings.length} {buildings.length === 1 ? 'building' : 'buildings'} · {reactionCount} {String.fromCharCode(0x2764)}
          </p>
        </div>
      </div>

      {/* Action row - reaction button */}
      <div style={{
        padding: '24px 20px 8px',
        display: 'flex',
        justifyContent: 'center',
      }}>
        <button
          onClick={handleToggleReaction}
          onMouseEnter={() => setIsReactHovered(true)}
          onMouseLeave={() => { setIsReactHovered(false); setIsReactPressed(false) }}
          onMouseDown={() => setIsReactPressed(true)}
          onMouseUp={() => setIsReactPressed(false)}
          style={{
            width: '100%',
            maxWidth: 320,
            minHeight: 44,
            padding: '14px 24px',
            borderRadius: 999,
            background: isReacted
              ? 'var(--color-surface)'
              : 'linear-gradient(135deg, #ec4899, #f43f5e)',
            color: isReacted ? '#ec4899' : '#fff',
            border: isReacted ? '1px solid #ec4899' : 'none',
            fontSize: 15,
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
            transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), filter 0.2s cubic-bezier(0.4, 0, 0.2, 1), background 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
            transform: isReactPressed ? 'scale(0.98)' : (isReactHovered ? 'scale(1.02)' : 'scale(1)'),
            filter: isReactHovered && !isReacted ? 'brightness(1.08)' : 'none',
            boxShadow: isReacted ? 'none' : '0 8px 22px rgba(236,72,153,0.32)',
            fontFamily: 'inherit',
          }}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill={isReacted ? '#ec4899' : 'none'}
            stroke={isReacted ? '#ec4899' : 'currentColor'}
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
          </svg>
          <span>{isReacted ? `Loved · ${reactionCount}` : 'Love this'}</span>
        </button>
      </div>

      {/* Buildings section */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0' }}>
        <h3 style={{
          color: 'var(--color-text)',
          fontSize: 20,
          fontWeight: 700,
          margin: '32px 0 16px',
          padding: '0 20px',
          letterSpacing: '-0.01em',
        }}>
          Buildings
        </h3>

        {buildings.length === 0 ? (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '60px 20px',
            color: 'var(--color-text-muted, #9ca3af)',
            textAlign: 'center',
            gap: 16,
          }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5 }}>
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <circle cx="8.5" cy="8.5" r="1.5"></circle>
              <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
            <p style={{
              color: 'var(--color-text-muted, #9ca3af)',
              fontSize: 14,
              fontWeight: 600,
              margin: 0,
            }}>
              This board is empty
            </p>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 20,
            padding: '0 20px',
          }}>
            {buildings.map(building => (
              <BuildingTile key={building.building_id} building={building} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
