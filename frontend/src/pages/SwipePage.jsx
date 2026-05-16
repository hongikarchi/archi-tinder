import { useRef, useState, useEffect } from 'react'
import TinderCard from 'react-tinder-card'
import TutorialPopup from '../components/TutorialPopup.jsx'
import SwipeCard, { CARD_WIDTH, CARD_HEIGHT } from '../components/SwipeCard.jsx'

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
