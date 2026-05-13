import { useRef, useState, useEffect } from 'react'
import TinderCard from 'react-tinder-card'
import TutorialPopup from '../components/TutorialPopup.jsx'
import { useImageTelemetry } from '../hooks/useImageTelemetry.js'

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
  const [imgLoaded,   setImgLoaded]   = useState(false)
  const [imgFailed,   setImgFailed]   = useState(false)
  const imgRetried = useRef(false)
  const dragStart = useRef(null)
  const dragStartTime = useRef(null)

  const { onLoad: telemetryOnLoad, onError: telemetryOnError } = useImageTelemetry({
    buildingId: card.image_id,
    context: 'swipe_card',
  })

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

  function handleImgError(e) {
    // Emit telemetry FIRST (captures original failed URL before retry mutates e.target.src)
    telemetryOnError(e)
    if (!imgRetried.current) {
      // Retry once with cache-busting query param
      imgRetried.current = true
      const sep = card.image_url.includes('?') ? '&' : '?'
      e.target.src = card.image_url + sep + 'retry=1'
    } else {
      // Retry also failed -- show fallback
      setImgFailed(true)
    }
  }

  function handleImgLoad(e) {
    setImgLoaded(true)
    telemetryOnLoad(e)
  }

  const typology   = card.metadata?.axis_typology
  const architects = card.metadata?.axis_architects
  const country    = card.metadata?.axis_country
  const area_m2    = card.metadata?.axis_area_m2
  const year       = card.metadata?.axis_year
  const style      = card.metadata?.axis_style
  const atmosphere = card.metadata?.axis_atmosphere
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
          {/* Photo / Skeleton / Fallback */}
          {imgFailed ? (
            <div style={{
              position: 'absolute', inset: 0,
              background: 'linear-gradient(135deg, #1e293b 0%, #334155 100%)',
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              gap: 12,
            }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <polyline points="21 15 16 10 5 21"/>
              </svg>
              <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: 12, fontWeight: 500 }}>
                Image unavailable
              </span>
            </div>
          ) : (
            <>
              <div className="skeleton-shimmer" style={{ position: 'absolute', inset: 0 }} />
              <img
                src={card.image_url}
                alt={card.image_title}
                fetchpriority="high"
                decoding="sync"
                draggable={false}
                onLoad={handleImgLoad}
                onError={handleImgError}
                style={{
                  position: 'absolute', inset: 0,
                  width: '100%', height: '100%',
                  objectFit: 'cover', objectPosition: 'center',
                  opacity: imgLoaded ? 1 : 0,
                  transition: 'opacity 0.2s ease',
                }}
              />
            </>
          )}

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
            <h2 style={{ color: '#fff', fontSize: 18, fontWeight: 700, lineHeight: 1.3, margin: '0 0 3px', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
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
              <InfoRow label="Style"      value={style} />
              <InfoRow label="Atmosphere" value={atmosphere} />
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

/* ── ConfidenceBar (unified progress for all phases) ─────────────────────── */
function ConfidenceBar({ value, phase, likeCount }) {
  // value: confidence in [0, 1] (analyzing+ phases) or null (exploring / pre-reset)
  // When confidence is null and we're in exploring phase, fall back to like-count
  // progress (0-3 likes to unlock analysis). Always renders one bar + one label
  // so the header never branches between two visualizations.
  let pct = 0
  let label = ''
  if (value !== null && value !== undefined) {
    pct = Math.round(value * 100)
    label = phase === 'converged' || phase === 'completed'
      ? '분석 완료'
      : `취향 안정도 ${pct}%`
  } else if (phase === 'exploring') {
    const likes = Math.min(likeCount ?? 0, 3)
    pct = Math.round((likes / 3) * 100)
    label = `탐색 중 · ♥ ${likes}/3`
  } else {
    pct = 0
    label = '준비 중'
  }
  return (
    <div style={{ width: '100%' }}>
      <div style={{
        height: 4, borderRadius: 999,
        background: 'var(--color-progress-track)',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: '#ec4899',
          borderRadius: 999,
          transition: 'width 300ms ease',
        }} />
      </div>
      <div style={{
        fontSize: 11,
        color: 'var(--color-text-dim)',
        textAlign: 'right',
        marginTop: 4,
      }}>
        {label}
      </div>
    </div>
  )
}

/* ── SwipePage ───────────────────────────────────────────────────────────── */
export default function SwipePage({
  currentCard, cardResetToken = 0, progress, isCompleted, isLoading, isResultLoading = false,
  projectName, onSwipe, onViewResults, onExtendSession,
}) {
  const cardRef = useRef(null)
  const pendingAction = useRef(null)
  const swipedCardId = useRef(null)
  const [galleryOpen, setGalleryOpen] = useState(false)
  const [showTutorial, setShowTutorial] = useState(() => !localStorage.getItem('archithon_tutorial_dismissed'))

  const like_count       = progress?.like_count    ?? 0
  const phase            = progress?.phase
  const filter_relaxed   = progress?.filter_relaxed || false
  const confidence       = progress?.confidence ?? null

  function onTinderSwipe(dir) {
    swipedCardId.current = currentCard?.image_id
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
    pendingAction.current = dir === 'right' ? 'like' : 'dislike'
    await cardRef.current.swipe(dir)
  }

  // When cardResetToken changes the TinderCard was force-remounted after a
  // locked swipe. Clear the guard refs so the same card can be swiped again.
  useEffect(() => {
    swipedCardId.current = null
    pendingAction.current = null
  }, [cardResetToken])

  useEffect(() => {
    function handleKeyDown(e) {
      if (isLoading || !currentCard) return
      if (showTutorial || pendingAction.current) return
      if (swipedCardId.current === currentCard.image_id) return

      if (e.key === 'ArrowLeft') {
        swipedCardId.current = currentCard.image_id
        if (galleryOpen) setGalleryOpen(false)
        swipeManual('left')
      } else if (e.key === 'ArrowRight') {
        swipedCardId.current = currentCard.image_id
        if (galleryOpen) setGalleryOpen(false)
        swipeManual('right')
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isLoading, currentCard, showTutorial, galleryOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  if (isCompleted) {
    const canContinue = !!progress?.can_continue
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        overflow: 'hidden',
        background: 'var(--color-bg)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        gap: 16,
      }}>
        <div style={{
          width: CARD_WIDTH,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 20,
          padding: '32px 24px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
        }}>
          <div style={{ fontSize: 56 }}>✨</div>
          <h2 style={{
            color: 'var(--color-text)',
            fontSize: 22,
            fontWeight: 700,
            margin: 0,
            textAlign: 'center',
          }}>
            Your taste is found
          </h2>
          <p style={{
            color: 'var(--color-text-2)',
            fontSize: 14,
            textAlign: 'center',
            margin: 0,
            lineHeight: 1.5,
          }}>
            {projectName ? `"${projectName}"` : 'Project'} swiping complete · ♥ {like_count} saved
          </p>
          <p style={{
            color: 'var(--color-text-muted)',
            fontSize: 12,
            textAlign: 'center',
            margin: '4px 0 0',
            lineHeight: 1.5,
          }}>
            {canContinue
              ? 'View your persona report, or keep exploring more buildings.'
              : 'Your persona report is ready.'}
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: CARD_WIDTH }}>
          <button
            onClick={onViewResults}
            disabled={isResultLoading}
            style={{
              padding: '14px 24px',
              borderRadius: 14,
              background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
              color: '#fff',
              fontSize: 15,
              fontWeight: 700,
              border: 'none',
              cursor: isResultLoading ? 'default' : 'pointer',
              fontFamily: 'inherit',
              boxShadow: '0 4px 20px rgba(236,72,153,0.35)',
              opacity: isResultLoading ? 0.6 : 1,
              transition: 'opacity 0.2s',
              minHeight: 44,
            }}
          >
            {isResultLoading ? 'Preparing report...' : 'View persona report →'}
          </button>
          {canContinue && (
            <button
              onClick={onExtendSession}
              disabled={isLoading || isResultLoading}
              style={{
                padding: '12px 24px',
                borderRadius: 14,
                background: 'var(--color-surface-2)',
                color: 'var(--color-text)',
                fontSize: 14,
                fontWeight: 600,
                border: '1px solid var(--color-border)',
                cursor: (isLoading || isResultLoading) ? 'default' : 'pointer',
                fontFamily: 'inherit',
                opacity: (isLoading || isResultLoading) ? 0.6 : 1,
                transition: 'opacity 0.2s, background 0.15s',
                minHeight: 44,
              }}
            >
              Keep exploring
            </button>
          )}
        </div>
      </div>
    )
  }

  if (!isLoading && !currentCard) {
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflow: 'hidden', background: 'var(--color-bg)', display: 'flex',
        flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: 24, gap: 12,
      }}>
        <div style={{ fontSize: 48 }}>🏛️</div>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 14, textAlign: 'center' }}>
          No more buildings available.<br />Try starting a new session with different filters.
        </p>
      </div>
    )
  }

  return (
    <>
      <TutorialPopup visible={showTutorial} onClose={() => setShowTutorial(false)} />
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'space-between', height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflow: 'hidden',
        background: 'var(--color-bg)', padding: '20px 16px',
      }}>

        {/* Header */}
        <div style={{ textAlign: 'center', width: '100%' }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 14px', letterSpacing: '-0.01em' }}>
            {projectName
              ? <span style={{ color: 'var(--color-text)' }}>{projectName}</span>
              : <><span style={{ color: 'var(--color-text)' }}>Archi</span><span style={{ color: '#ec4899' }}>Tinder</span></>}
          </h1>
          <div style={{ maxWidth: CARD_WIDTH, margin: '0 auto' }}>
            <ConfidenceBar value={confidence} phase={phase} likeCount={like_count} />
            {filter_relaxed && (
              <p style={{ color: 'var(--color-text-dimmer)', fontSize: 11, marginTop: 6, textAlign: 'center' }}>
                Filters were relaxed to find more buildings
              </p>
            )}
          </div>
        </div>

        {/* Card */}
        <div style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}>
          {currentCard ? (
            <>
              <TinderCard
                ref={cardRef}
                key={`${currentCard.image_id}_${cardResetToken}`}
                onSwipe={onTinderSwipe}
                onCardLeftScreen={onCardLeftScreen}
                preventSwipe={galleryOpen ? ['left', 'right', 'up', 'down'] : ['up', 'down']}
                swipeRequirementType='position'
                swipeThreshold={120}
              >
                <SwipeCard
                  card={currentCard}
                  onGalleryOpen={() => setGalleryOpen(true)}
                  onGalleryClose={() => setGalleryOpen(false)}
                />
              </TinderCard>
              {isLoading && (
                <div style={{
                  position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  borderRadius: 20, background: 'rgba(0,0,0,0.15)', pointerEvents: 'none',
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: '50%',
                    border: '3px solid rgba(255,255,255,0.2)',
                    borderTopColor: '#fff',
                    animation: 'spin 0.8s linear infinite',
                  }} />
                </div>
              )}
            </>
          ) : isLoading ? (
            <LoadingCard />
          ) : null}
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, margin: 0 }}>← skip · tap card · save →</p>
        </div>

      </div>
    </>
  )
}
