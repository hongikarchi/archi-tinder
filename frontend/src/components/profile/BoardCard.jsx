import { useState, useMemo, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useImageTelemetry } from '../../hooks/useImageTelemetry.js'
import InfoCol from './InfoCol'
import { useTranslation } from '../../i18n/index.js'

/**
 * BoardCard — flip card per DESIGN.md §3.5.4
 *   Front face: image-overlay card per §3.5.1 + §3.5.2 RICH PATTERN
 *               (title + "Curated Board" sub-italic + divider + 2-col CREATED/SAVED grid)
 *               + §3.5.3 PRIVATE-only icon-lock chip (PUBLIC = no chip).
 *   Back face: swipe-style horizontal full-bleed gallery per §3.5.5 + persistent "View Gallery" action bar.
 *
 * Hover lift YES, hover border NO per §3.5.4. The subtle translateY(-4px) lift matches
 * every other interactive card in the app; only the pink border is omitted because a
 * static border lingers awkwardly behind the rotating card. When selected, a 3px pink
 * ring is applied via box-shadow on the outer wrapper instead.
 *
 * When `board.cover_image_url` is empty/falsy (pre-cutover legacy boards whose
 * cover refers to an old building id no longer present in canonical_v2),
 * render a brand-gradient placeholder div in place of a broken <img>.
 *
 * Owner props:
 *   isOwner (bool, default false) — shows lock-toggle chip + X delete button.
 *   onVisibilityChange (fn) — called with 'public' | 'private' when owner clicks lock chip.
 *   onDelete (fn) — called after 2-step confirm when owner deletes.
 *
 * Select-mode props (P6 bulk edit):
 *   selectMode (bool, default false) — when true, card click toggles selection; no flip.
 *   isSelected (bool, default false) — whether this card is in the current selection.
 *   onSelectToggle (fn) — called with board_id when card is clicked in select mode.
 */
export default function BoardCard({
  board,
  isOwner = false,
  onVisibilityChange = () => {},
  onDelete = () => {},
  selectMode = false,
  isSelected = false,
  onSelectToggle = () => {},
  directNavigate = false,
  onResume,
  onStartNew,
}) {
  const { t } = useTranslation()
  const [isFlipped, setIsFlipped] = useState(false)
  const [isHovered, setIsHovered] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const confirmTimerRef = useRef(null)
  const deleteBtnRef = useRef(null)
  const navigate = useNavigate()

  // Detect mobile once at mount — touch devices always show owner chips
  const isMobile = useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(hover: none)').matches,
    []
  )

  // Clear timeout on unmount
  useEffect(() => () => clearTimeout(confirmTimerRef.current), [])

  // P6: when select mode activates, un-flip so the selection circle on the front face is visible
  useEffect(() => {
    if (selectMode) setIsFlipped(false)
  }, [selectMode])

  // Click-outside cancels pending delete confirm
  useEffect(() => {
    if (!confirmingDelete) return
    function handleOutsideClick(e) {
      if (deleteBtnRef.current && !deleteBtnRef.current.contains(e.target)) {
        clearTimeout(confirmTimerRef.current)
        setConfirmingDelete(false)
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [confirmingDelete])

  const isPrivate = board.visibility === 'private'
  const hasCover = !!board.cover_image_url

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
        // In select mode, replace the lift with a pink ring when selected (box-shadow
        // lives outside the element so it doesn't affect layout or fight the border).
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
        boxShadow: isSelected ? '0 0 0 3px #ec4899' : 'none',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={(e) => {
        // Select mode: whole card body toggles selection — before button guard.
        if (selectMode) {
          onSelectToggle(board.board_id)
          return
        }
        if (e.target.closest('button')) return
        if (directNavigate) {
          navigate('/board/' + board.board_id)
          return
        }
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
          {hasCover ? (
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
          ) : (
            // Gradient placeholder for boards with no cover (e.g. pre-cutover
            // legacy boards whose cover FK points to a removed building).
            // Uses DESIGN.md brand gradient as a soft tint over surface,
            // not the pure CTA gradient — this is a placeholder, not a button.
            <div
              aria-hidden
              style={{
                position: 'absolute', inset: 0,
                background: 'linear-gradient(135deg, rgba(236,72,153,0.22) 0%, rgba(244,63,94,0.18) 50%, rgba(15,15,15,0.85) 100%)',
              }}
            />
          )}

          {/* §3.5.1 mandatory bottom gradient overlay for legibility */}
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.4) 50%, transparent 100%)',
            pointerEvents: 'none',
          }} />

          {/* P6 select-mode: selection circle indicator replaces lock chip for owners.
              28px circle, top-right. Unchecked = outlined on dark bg; Checked = pink fill + checkmark. */}
          {selectMode && isOwner ? (
            <div
              aria-label={isSelected ? 'Selected' : 'Not selected'}
              style={{
                position: 'absolute', top: 16, right: 16,
                width: 28, height: 28, borderRadius: '50%',
                border: isSelected ? 'none' : '2px solid rgba(255,255,255,0.9)',
                background: isSelected ? '#ec4899' : 'rgba(0,0,0,0.4)',
                backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.15s cubic-bezier(0.4,0,0.2,1), border 0.15s cubic-bezier(0.4,0,0.2,1)',
                pointerEvents: 'none', // card body handles the click
              }}
            >
              {isSelected && (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                     stroke="#fff" strokeWidth="2.5"
                     strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              )}
            </div>
          ) : (
            /* §3.5.3 Lock chip — owner: toggle visibility; non-owner: indicator only when private.
               Owner chip visible when isHovered || isMobile || isPrivate.
               Non-owner chip visible only when isPrivate (current behavior, no change).
               Hidden entirely for owner when selectMode is true (selection circle takes this slot). */
            isOwner ? (
              (isHovered || isMobile || isPrivate) && (
                <button
                  type="button"
                  aria-label={isPrivate ? 'Make public' : 'Make private'}
                  onClick={(e) => {
                    e.stopPropagation()
                    onVisibilityChange(isPrivate ? 'public' : 'private')
                  }}
                  style={{
                    position: 'absolute', top: 16, right: 16,
                    background: 'rgba(0,0,0,0.4)',
                    backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
                    padding: 6, borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: 'none', cursor: 'pointer',
                    transition: 'background 0.18s cubic-bezier(0.4,0,0.2,1)',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.6)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.4)' }}
                >
                  {isPrivate ? (
                    // Lock-closed SVG (private)
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                         stroke="rgba(255,255,255,0.85)" strokeWidth="2"
                         strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                  ) : (
                    // Lock-open SVG (public) — shackle stops short on right side
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                         stroke="rgba(255,255,255,0.85)" strokeWidth="2"
                         strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                      <path d="M7 11V7a5 5 0 0 1 9.9-1"></path>
                    </svg>
                  )}
                </button>
              )
            ) : (
              // Non-owner: show indicator-only chip when private
              isPrivate && (
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
              )
            )
          )}

          {/* X delete button — owner-only, top-left, mirrors lock chip styling.
              Grows from circle (idle) to pill (confirming) with "Confirm?" inside.
              Hidden in select mode — bulk delete is handled by the bulk action bar. */}
          {isOwner && !selectMode && (isHovered || isMobile || confirmingDelete) && (
            <button
              ref={deleteBtnRef}
              type="button"
              aria-label={confirmingDelete ? 'Click again to confirm delete' : 'Delete board'}
              onClick={(e) => {
                e.stopPropagation()
                if (!confirmingDelete) {
                  clearTimeout(confirmTimerRef.current)
                  setConfirmingDelete(true)
                  confirmTimerRef.current = setTimeout(() => setConfirmingDelete(false), 3000)
                } else {
                  clearTimeout(confirmTimerRef.current)
                  setConfirmingDelete(false)
                  onDelete()
                }
              }}
              style={{
                position: 'absolute', top: 16, left: 16,
                display: confirmingDelete ? 'flex' : 'inline-flex',
                alignItems: 'center',
                gap: 6,
                background: 'rgba(0,0,0,0.4)',
                backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
                padding: confirmingDelete ? '6px 10px 6px 6px' : 6,
                borderRadius: confirmingDelete ? 16 : '50%',
                border: 'none', cursor: 'pointer',
                transition: 'all 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.6)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.4)' }}
            >
              {/* X icon — red when confirming, white-ish when idle */}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                   stroke={confirmingDelete ? '#ef4444' : 'rgba(255,255,255,0.85)'}
                   strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
              {confirmingDelete && (
                <span style={{ fontSize: 11, color: '#ef4444', fontWeight: 600 }}>
                  Confirm?
                </span>
              )}
            </button>
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
            display: 'flex', flexDirection: 'column', gap: 8,
          }}>
            {/* Resume vs New — only when a prior interrupted session exists */}
            {isOwner && board.latest_session_meta && onResume && onStartNew && (
              <div style={{ display: 'flex', gap: 8 }}>
                {/* Primary CTA — resume per DESIGN.md §8.1 */}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onResume() }}
                  style={{
                    flex: 1, minHeight: 44,
                    padding: '10px 8px', borderRadius: 12,
                    background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
                    border: 0,
                    color: '#fff', fontSize: 12, fontWeight: 600,
                    cursor: 'pointer', fontFamily: 'inherit',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'transform var(--motion-normal) var(--motion-ease)',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)' }}
                >
                  {t('board.resume', { count: board.latest_session_meta.like_count })}
                </button>
                {/* Secondary — new session per DESIGN.md §8.2 */}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onStartNew() }}
                  style={{
                    flex: 1, minHeight: 44,
                    padding: '10px 8px', borderRadius: 12,
                    background: 'rgba(255,255,255,0.10)',
                    border: '1px solid rgba(255,255,255,0.18)',
                    color: '#fff', fontSize: 12, fontWeight: 600,
                    cursor: 'pointer', fontFamily: 'inherit',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'background var(--motion-fast) var(--motion-ease)',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.18)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.10)' }}
                >
                  {t('board.startNew')}
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={() => navigate('/board/' + board.board_id)}
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
