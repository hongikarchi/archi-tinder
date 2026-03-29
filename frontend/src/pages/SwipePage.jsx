import { useRef, useState } from 'react'
import TinderCard from 'react-tinder-card'

const CARD_WIDTH  = Math.min(340, (typeof window !== 'undefined' ? window.innerWidth : 375) - 32)
const CARD_HEIGHT = Math.round(CARD_WIDTH * (480 / 340))
const TAP_THRESHOLD = 8

/* ── InfoRow ─────────────────────────────────────────────────────────────── */
function InfoRow({ label, value }) {
  if (!value) return null
  return (
    <div>
      <div style={{ color: 'rgba(255,255,255,0.45)', fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ color: '#e2e8f0', fontSize: 12, fontWeight: 500, lineHeight: 1.3 }}>{value}</div>
    </div>
  )
}

/* ── Card ────────────────────────────────────────────────────────────────── */
function SwipeCard({ card, onGalleryOpen, onGalleryClose }) {
  const [isExpanded,  setIsExpanded]  = useState(false)
  const [showGallery, setShowGallery] = useState(false)
  const dragStart = useRef(null)
  const dragStartTime = useRef(null)

  function openGallery()  { setShowGallery(true);  onGalleryOpen()  }
  function closeGallery() { setShowGallery(false); onGalleryClose() }

  function handlePointerDown(e) {
    dragStart.current = { x: e.clientX, y: e.clientY }
    dragStartTime.current = Date.now()
  }
  function handlePointerUp(e) {
    if (!dragStart.current) return
    const dx = Math.abs(e.clientX - dragStart.current.x)
    const dy = Math.abs(e.clientY - dragStart.current.y)
    const dt = Date.now() - dragStartTime.current
    dragStart.current = null
    if (dx < TAP_THRESHOLD && dy < TAP_THRESHOLD && dt < 300) {
      if (showGallery) closeGallery()
      else setIsExpanded(v => !v)
    }
  }

  const typology   = card.metadata?.axis_typology
  const architects = card.metadata?.axis_architects
  const country    = card.metadata?.axis_country
  const area_m2    = card.metadata?.axis_area_m2
  const year       = card.metadata?.axis_year
  const mood       = card.metadata?.axis_mood
  const material   = card.metadata?.axis_material
  const areaLabel  = area_m2 ? `${Number(area_m2).toLocaleString()} m²` : null
  const gallery         = card.gallery || []
  const drawingStart    = card.gallery_drawing_start ?? gallery.length

  return (
    <div
      style={{
        position: 'absolute', top: 0, left: 0,
        width: CARD_WIDTH, height: CARD_HEIGHT,
        cursor: 'grab',
        userSelect: 'none', WebkitUserSelect: 'none', touchAction: 'none',
        perspective: 1200,
      }}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
    >
      <div style={{
        width: '100%', height: '100%', position: 'relative',
        transformStyle: 'preserve-3d',
        transform: showGallery ? 'rotateY(180deg)' : 'rotateY(0deg)',
        transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
      }}>

        {/* ── FRONT FACE ── */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          borderRadius: 20, overflow: 'hidden',
          boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
        }}>
          {/* Photo */}
          <div style={{
            position: 'absolute', inset: 0,
            backgroundImage: `url(${card.image_url})`,
            backgroundSize: 'cover', backgroundPosition: 'center',
          }} />

          {/* Gradient — expands upward on detail open */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            height: isExpanded ? '100%' : '52%',
            background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.6) 38%, rgba(0,0,0,0.12) 72%, transparent 100%)',
            transition: 'height 0.42s cubic-bezier(0.32, 0, 0.18, 1)',
            pointerEvents: 'none',
          }} />

          {/* Front: hint only (no title) */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, padding: '0 18px 20px',
            opacity: isExpanded ? 0 : 1,
            transform: isExpanded ? 'translateY(-6px)' : 'translateY(0)',
            transition: 'opacity 0.22s ease, transform 0.38s ease',
            pointerEvents: isExpanded ? 'none' : 'auto',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5, color: 'rgba(255,255,255,0.5)', fontSize: 11, letterSpacing: '0.04em' }}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="18 15 12 9 6 15" />
              </svg>
              tap for details
            </div>
          </div>

          {/* Detail content — transparent, slides over expanded gradient */}
          <div style={{
            position: 'absolute', left: 0, right: 0, bottom: 0,
            height: '66%',
            background: 'transparent',
            transform: isExpanded ? 'translateY(0)' : 'translateY(100%)',
            transition: 'transform 0.42s cubic-bezier(0.32, 0, 0.18, 1)',
            display: 'flex', flexDirection: 'column',
            padding: '16px 18px 20px', gap: 0, overflow: 'hidden',
          }}>
            <h2 style={{ color: '#fff', fontSize: 18, fontWeight: 700, lineHeight: 1.3, margin: '0 0 3px' }}>
              {card.image_title}
            </h2>
            {architects && (
              <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: 12, margin: '0 0 12px', fontStyle: 'italic' }}>
                {architects}
              </p>
            )}
            <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12 }} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px', flex: 1 }}>
              <InfoRow label="Type"     value={typology} />
              <InfoRow label="Country"  value={country} />
              <InfoRow label="Year"     value={year} />
              <InfoRow label="Area"     value={areaLabel} />
              <InfoRow label="Mood"     value={mood} />
              <InfoRow label="Material" value={material} />
            </div>
            {gallery.length > 0 && (
              <button
                onPointerDown={e => e.stopPropagation()}
                onPointerUp={e => e.stopPropagation()}
                onClick={e => { e.stopPropagation(); openGallery() }}
                style={{
                  marginTop: 12, width: '100%', padding: '10px 14px', borderRadius: 10,
                  background: 'rgba(255,255,255,0.09)', border: '1px solid rgba(255,255,255,0.18)',
                  color: '#fff', fontSize: 12, fontWeight: 600,
                  cursor: 'pointer', fontFamily: 'inherit',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                }}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="28" height="28" rx="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <polyline points="21 15 16 10 5 21"/>
                </svg>
                View Gallery · {gallery.length} photos
              </button>
            )}
          </div>
        </div>

        {/* ── GALLERY FACE ── */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          transform: 'rotateY(180deg)',
          borderRadius: 20, overflow: 'hidden',
          boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
          background: '#000',
        }}>
          {/* Vertical scroll of full-width images */}
          <div
            onTouchStart={e => e.stopPropagation()}
            onTouchMove={e => e.stopPropagation()}
            style={{
              position: 'absolute', inset: 0,
              overflowY: 'auto', overflowX: 'hidden',
              scrollSnapType: 'y mandatory',
              overscrollBehaviorY: 'contain',
              scrollbarWidth: 'none',
            }}
          >
            {gallery.map((url, i) => (
              <div key={i} style={{
                width: '100%', height: CARD_HEIGHT,
                flexShrink: 0,
                scrollSnapAlign: 'start',
                scrollSnapStop: 'always',
                backgroundImage: `url(${url})`,
                backgroundSize: i >= drawingStart ? 'contain' : 'cover',
                backgroundPosition: 'center',
                backgroundRepeat: 'no-repeat',
                backgroundColor: i >= drawingStart ? '#fff' : 'transparent',
              }} />
            ))}
          </div>

          {/* Top arrow */}
          <div style={{ position: 'absolute', top: 14, left: 0, right: 0, display: 'flex', justifyContent: 'center', pointerEvents: 'none' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="18 15 12 9 6 15"/>
            </svg>
          </div>
          {/* Bottom arrow */}
          <div style={{ position: 'absolute', bottom: 14, left: 0, right: 0, display: 'flex', justifyContent: 'center', pointerEvents: 'none' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </div>
        </div>

      </div>
    </div>
  )
}

/* ── LoadingCard ─────────────────────────────────────────────────────────── */
function LoadingCard() {
  return (
    <div style={{
      position: 'absolute', top: 0, left: 0, width: CARD_WIDTH, height: CARD_HEIGHT,
      borderRadius: 20, overflow: 'hidden',
      background: 'var(--color-surface)',
      boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
    }}>
      <div className="skeleton-shimmer" style={{ width: '100%', height: '100%' }} />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '0 18px 22px' }}>
        <div className="skeleton-shimmer" style={{ height: 17, width: '65%', borderRadius: 6, marginBottom: 12 }} />
        <div style={{ display: 'flex', gap: 6 }}>
          {[72, 88, 60].map((w, i) => (
            <div key={i} className="skeleton-shimmer" style={{ height: 24, width: w, borderRadius: 999 }} />
          ))}
        </div>
      </div>
    </div>
  )
}

/* ── SwipePage ───────────────────────────────────────────────────────────── */
export default function SwipePage({ currentCard, progress, isCompleted, isLoading, projectName, onSwipe, onViewResults }) {
  const cardRef = useRef(null)
  const pendingAction = useRef(null)
  const [galleryOpen, setGalleryOpen] = useState(false)

  const current_round = progress?.current_round ?? 0
  const total_rounds  = progress?.total_rounds  ?? 1
  const like_count    = progress?.like_count    ?? 0
  const pct      = Math.round((current_round / Math.max(total_rounds, 1)) * 100)
  const showExit = total_rounds > 0 && (current_round / total_rounds) >= 0.3

  function onTinderSwipe(dir) {
    pendingAction.current = dir === 'right' ? 'like' : 'dislike'
  }

  function onCardLeftScreen() {
    if (pendingAction.current) {
      onSwipe(pendingAction.current)
      pendingAction.current = null
    }
  }

  async function swipeManual(dir) {
    if (!cardRef.current || isLoading) return
    await cardRef.current.swipe(dir)
  }

  if (isCompleted) {
    return (
      <div style={{
        height: 'calc(100vh - 64px)', overflow: 'hidden', background: 'var(--color-bg)', display: 'flex',
        flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: 24, gap: 12,
      }}>
        <div style={{ fontSize: 64 }}>🎉</div>
        <h2 style={{ color: 'var(--color-text)', fontSize: 22, fontWeight: 800, margin: 0 }}>All done!</h2>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 14, textAlign: 'center', margin: 0 }}>
          {`"${projectName || 'Project'}" swiping complete`}
        </p>
        <p style={{ color: 'var(--color-text-dimmer)', fontSize: 13, textAlign: 'center' }}>
          ♥ {like_count} saved
        </p>
        <button
          onClick={onViewResults}
          style={{
            marginTop: 8, padding: '14px 36px', borderRadius: 14,
            background: 'linear-gradient(135deg, #f43f5e, #fb923c)',
            color: '#fff', fontSize: 15, fontWeight: 700,
            border: 'none', cursor: 'pointer', fontFamily: 'inherit',
            boxShadow: '0 4px 20px rgba(244,63,94,0.35)',
          }}
        >
          View Image Board →
        </button>
      </div>
    )
  }

  if (!isLoading && !currentCard) {
    return (
      <div style={{
        height: 'calc(100vh - 64px)', overflow: 'hidden', background: 'var(--color-bg)', display: 'flex',
        flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: 24, gap: 12,
      }}>
        <div style={{ fontSize: 48 }}>🏛️</div>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 14, textAlign: 'center' }}>
          No buildings match your criteria.<br />Try adjusting your filters.
        </p>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'space-between', height: 'calc(100vh - 64px)', overflow: 'hidden',
      background: 'var(--color-bg)', padding: '32px 16px',
    }}>

      {/* Header */}
      <div style={{ textAlign: 'center', width: '100%' }}>
        <h1 style={{ fontSize: 20, fontWeight: 900, margin: '0 0 14px', letterSpacing: '-0.01em' }}>
          {projectName
            ? <span style={{ color: 'var(--color-text)' }}>{projectName}</span>
            : <><span style={{ color: 'var(--color-text)' }}>Archi</span><span style={{ color: '#ec4899' }}>Tinder</span></>}
        </h1>
        <div style={{ maxWidth: CARD_WIDTH, margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ color: 'var(--color-text-dim)', fontSize: 11 }}>Progress</span>
            <span style={{ color: 'var(--color-text-2)', fontSize: 11, fontWeight: 600 }}>
              {current_round} / {total_rounds}
            </span>
          </div>
          <div style={{ height: 4, borderRadius: 999, background: 'var(--color-progress-track)', overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 999, width: `${pct}%`,
              background: 'linear-gradient(to right, #f43f5e, #fb923c)',
              transition: 'width 0.4s ease',
            }} />
          </div>
        </div>
      </div>

      {/* Card */}
      <div style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}>
        {isLoading ? (
          <LoadingCard />
        ) : currentCard ? (
          <TinderCard
            ref={cardRef}
            key={currentCard.image_id}
            onSwipe={onTinderSwipe}
            onCardLeftScreen={onCardLeftScreen}
            preventSwipe={galleryOpen ? ['left', 'right', 'up', 'down'] : ['up', 'down']}
            swipeRequirementType="position"
            swipeThreshold={120}
          >
            <SwipeCard
              card={currentCard}
              onGalleryOpen={() => setGalleryOpen(true)}
              onGalleryClose={() => setGalleryOpen(false)}
            />
          </TinderCard>
        ) : null}
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, margin: 0 }}>← skip · tap card · save →</p>
        <div style={{ display: 'flex', gap: 32 }}>
          <button
            onClick={() => swipeManual('left')}
            disabled={isLoading || !currentCard}
            style={{
              width: 64, height: 64, borderRadius: '50%',
              background: 'rgba(239,68,68,0.15)', border: '2px solid rgba(239,68,68,0.4)',
              color: isLoading ? 'var(--color-text-dimmer)' : '#ef4444',
              cursor: isLoading ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            aria-label="Dislike"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <button
            onClick={() => swipeManual('right')}
            disabled={isLoading || !currentCard}
            style={{
              width: 64, height: 64, borderRadius: '50%',
              background: 'rgba(236,72,153,0.15)', border: '2px solid rgba(236,72,153,0.4)',
              color: isLoading ? 'var(--color-text-dimmer)' : '#ec4899',
              cursor: isLoading ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            aria-label="Like"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
            </svg>
          </button>
        </div>
        {showExit && (
          <button
            onClick={onViewResults}
            style={{
              padding: '11px 32px', borderRadius: 14,
              background: 'linear-gradient(135deg, #f43f5e, #fb923c)',
              color: '#fff', fontSize: 14, fontWeight: 700,
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              boxShadow: '0 4px 20px rgba(244,63,94,0.35)',
            }}
          >
            View Results →
          </button>
        )}
      </div>

    </div>
  )
}
