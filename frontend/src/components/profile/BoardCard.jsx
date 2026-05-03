import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useImageTelemetry } from '../../hooks/useImageTelemetry.js'
import InfoCol from './InfoCol'

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
export default function BoardCard({ board }) {
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
