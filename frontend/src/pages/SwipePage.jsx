import { useRef, useState, useEffect } from 'react'
import TinderCard from 'react-tinder-card'
import { GalleryOverlay } from '../components/GalleryOverlay.jsx'

const CARD_WIDTH  = Math.min(340, (typeof window !== 'undefined' ? window.innerWidth : 375) - 32)
const CARD_HEIGHT = Math.round(CARD_WIDTH * (480 / 340))
const TAP_THRESHOLD = 8

/* ── FlipCard ────────────────────────────────────────────────────────────── */
function FlipCard({ card, onOpenGallery }) {
  const dragStart = useRef(null)
  const dragStartTime = useRef(null)

  function handlePointerDown(e) {
    dragStart.current = { x: e.clientX, y: e.clientY }
    dragStartTime.current = Date.now()
  }

  function handlePointerUp(e) {
    if (dragStart.current) {
      const dx = Math.abs(e.clientX - dragStart.current.x)
      const dy = Math.abs(e.clientY - dragStart.current.y)
      const dt = Date.now() - dragStartTime.current
      if (dx < TAP_THRESHOLD && dy < TAP_THRESHOLD && dt < 300) {
        onOpenGallery()
      }
    }
    dragStart.current = null
  }

  const typology   = card.metadata?.axis_typology
  const architects = card.metadata?.axis_architects
  const country    = card.metadata?.axis_country
  const area_m2    = card.metadata?.axis_area_m2
  const areaLabel  = area_m2 ? `${Number(area_m2).toLocaleString()} m²` : null
  const gallery    = card.gallery || []

  return (
    <div
      style={{
        position: 'absolute', top: 0, left: 0,
        width: CARD_WIDTH, height: CARD_HEIGHT,
        cursor: 'grab',
        userSelect: 'none', WebkitUserSelect: 'none', touchAction: 'none',
      }}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
    >
      <div
        draggable={false}
        style={{
          width: '100%', height: '100%',
          borderRadius: 20, overflow: 'hidden',
          backgroundImage: `url(${card.image_url})`,
          backgroundSize: 'cover', backgroundPosition: 'center',
          boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
          WebkitUserDrag: 'none', position: 'relative',
        }}
      >
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.15) 55%, transparent 100%)' }} />
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '0 18px 18px' }}>
          <h2 style={{ color: '#fff', fontSize: 17, fontWeight: 700, lineHeight: 1.3, marginBottom: 10, marginTop: 0 }}>
            {card.image_title}
          </h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {typology   && <Tag label="Type"    value={typology} />}
            {architects && <Tag label="By"      value={architects.split(/\s*\+\s*/)[0].trim()} />}
            {areaLabel  && <Tag label="Area"    value={areaLabel} />}
            {country    && <Tag label="Country" value={country} />}
          </div>
          {gallery.length > 0 && (
            <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: 10, marginTop: 10, textAlign: 'center' }}>
              Tap · {gallery.length} more photos
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function Tag({ label, value }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '3px 10px', borderRadius: 999, fontSize: 11, fontWeight: 500,
      background: 'var(--color-tag-bg)', backdropFilter: 'blur(6px)',
      border: '1px solid var(--color-tag-border)', color: '#fff', whiteSpace: 'nowrap',
    }}>
      <span style={{ color: 'var(--color-tag-label)', fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </span>
      {value}
    </span>
  )
}

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
  const [showGallery, setShowGallery] = useState(false)

  useEffect(() => { setShowGallery(false) }, [currentCard?.image_id])

  const current_round  = progress?.current_round  ?? 0
  const total_rounds   = progress?.total_rounds   ?? 1
  const like_count     = progress?.like_count     ?? 0
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
              height: '100%', borderRadius: 999,
              width: `${pct}%`,
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
            preventSwipe={showGallery ? ['left', 'right', 'up', 'down'] : ['up', 'down']}
            swipeRequirementType="position"
            swipeThreshold={120}
          >
            <FlipCard card={currentCard} onOpenGallery={() => setShowGallery(true)} />
          </TinderCard>
        ) : null}
        {showGallery && currentCard && (
          <GalleryOverlay card={currentCard} onClose={() => setShowGallery(false)} />
        )}
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, margin: 0 }}>← skip · tap to flip · save →</p>
        <div style={{ display: 'flex', gap: 32 }}>
          <button
            onClick={() => swipeManual('left')}
            disabled={isLoading || !currentCard}
            style={{
              width: 64, height: 64, borderRadius: '50%',
              background: 'rgba(239,68,68,0.15)', border: '2px solid rgba(239,68,68,0.4)',
              color: isLoading ? 'var(--color-text-dimmer)' : 'var(--color-text)',
              fontSize: 22, cursor: isLoading ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            aria-label="Dislike"
          >✕</button>
          <button
            onClick={() => swipeManual('right')}
            disabled={isLoading || !currentCard}
            style={{
              width: 64, height: 64, borderRadius: '50%',
              background: 'rgba(34,197,94,0.15)', border: '2px solid rgba(34,197,94,0.4)',
              color: isLoading ? 'var(--color-text-dimmer)' : 'var(--color-text)',
              fontSize: 22, cursor: isLoading ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            aria-label="Like"
          >♥</button>
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
