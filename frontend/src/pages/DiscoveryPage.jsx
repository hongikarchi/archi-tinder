import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import TinderCard from 'react-tinder-card'
import { fetchDiscoveryFeed, addLikedBuilding } from '../api/client.js'
import SwipeCard, { CARD_WIDTH, CARD_HEIGHT } from '../components/SwipeCard.jsx'
import SaveToBoardModal from '../components/SaveToBoardModal.jsx'
import SurpriseBoardModal from '../components/SurpriseBoardModal.jsx'

const PAGE_LIMIT = 12
const SURPRISE_THRESHOLD = 5
const PREFETCH_AT_REMAINING = 3 // when deck size <= this, fetch next page
const SWIPE_KEYS = { ArrowLeft: 'left', ArrowRight: 'right' }

/* ── preloadImage helper (mirrors App.jsx preloadImage pattern) ──────────── */
function makeImagePreloader() {
  const cache = new Set()
  return function preload(url) {
    if (!url || cache.has(url)) return
    cache.add(url)
    const img = new Image()
    img.src = url
  }
}

/* ── LoadingCard (matches SwipePage LoadingCard footprint) ───────────────── */
function LoadingCard() {
  return (
    <div style={{
      position: 'absolute', top: 0, left: 0, width: CARD_WIDTH, height: CARD_HEIGHT,
      borderRadius: 20, overflow: 'hidden',
      background: 'var(--color-surface)',
      boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
    }}>
      <div className="skeleton-shimmer" style={{ width: '100%', height: '100%' }} />
    </div>
  )
}

function getCardId(card) {
  return card?.canonical_bld_id || card?.image_id || card?.building_id || null
}

export default function DiscoveryPage() {
  const navigate = useNavigate()
  const isActiveRef = useRef(true)
  const requestIdRef = useRef(0)
  const fetchingRef = useRef(false)
  const preloadRef = useRef(makeImagePreloader())
  const pendingActionRef = useRef(null)
  const cardRef = useRef(null)
  const keySwipingRef = useRef(false)
  const longPressTimer = useRef(null)
  const longPressFired = useRef(false)
  const touchStartPos = useRef(null)

  const [deck, setDeck] = useState([])          // queue of cards (front = top)
  const [cursor, setCursor] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [tasteState, setTasteState] = useState('cold')
  const [loading, setLoading] = useState(false)  // page fetch in flight
  const [error, setError] = useState('')
  const [saveModalCard, setSaveModalCard] = useState(null)  // long-press save target
  const [savesThisVisit, setSavesThisVisit] = useState(0)
  const [surpriseShown, setSurpriseShown] = useState(false)
  const [surpriseOpen, setSurpriseOpen] = useState(false)

  useEffect(() => {
    isActiveRef.current = true
    return () => { isActiveRef.current = false }
  }, [])

  // Keyboard swipe: ← pass, → save. Blocked while either modal is open so
  // the user can type in the modal's text field without triggering deck swipes.
  useEffect(() => {
    async function onKey(e) {
      const dir = SWIPE_KEYS[e.key]
      if (!dir || !cardRef.current || keySwipingRef.current) return
      if (saveModalCard || surpriseOpen) return
      if (!deck.length) return
      keySwipingRef.current = true
      try {
        await cardRef.current.swipe(dir)
      } finally {
        keySwipingRef.current = false
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [deck.length, saveModalCard, surpriseOpen])

  // Surprise trigger: fires once per visit after SURPRISE_THRESHOLD saves
  useEffect(() => {
    if (savesThisVisit >= SURPRISE_THRESHOLD && !surpriseShown) {
      setSurpriseShown(true)
      setSurpriseOpen(true)
    }
  }, [savesThisVisit, surpriseShown])

  // -- Fetch next page --
  const fetchPage = useCallback(async (nextCursor, reset = false) => {
    if (fetchingRef.current) return
    if (!reset && !hasMore) return
    fetchingRef.current = true

    const requestId = ++requestIdRef.current
    const normalizedCursor = typeof nextCursor === 'number' ? nextCursor : 0
    setLoading(true)
    setError('')

    try {
      const result = await fetchDiscoveryFeed(normalizedCursor, PAGE_LIMIT)
      if (!isActiveRef.current || requestId !== requestIdRef.current) return

      // Preload images so subsequent cards render with image already cached.
      const preload = preloadRef.current
      for (const c of result.cards.slice(0, 3)) {
        if (c?.image_url) preload(c.image_url)
      }

      setDeck(prev => (reset ? result.cards : [...prev, ...result.cards]))
      setCursor(result.nextCursor ?? 0)
      setHasMore(Boolean(result.hasMore))
      setTasteState(result.tasteState || 'cold')
    } catch (err) {
      if (!isActiveRef.current || requestId !== requestIdRef.current) return
      setError(err?.message || "Couldn't load Discovery. Tap to retry.")
    } finally {
      if (isActiveRef.current && requestId === requestIdRef.current) {
        setLoading(false)
      }
      fetchingRef.current = false
    }
  }, [hasMore])

  // Initial load
  useEffect(() => {
    fetchPage(0, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-prefetch next page when deck running low
  useEffect(() => {
    if (!hasMore || fetchingRef.current) return
    if (deck.length === 0) return // initial-load case handled above
    if (deck.length <= PREFETCH_AT_REMAINING) {
      fetchPage(cursor)
    }
  }, [deck.length, hasMore, cursor, fetchPage])

  const topCard = deck[0] || null

  function advance() {
    setDeck(prev => prev.slice(1))
  }

  // -- Swipe handlers --
  // Right (like): card slides off; call addLikedBuilding directly — no modal.
  //   savesThisVisit increments to trigger the Surprise threshold.
  // Left (pass): card slides off; advance immediately.
  function onTinderSwipe(dir) {
    if (longPressFired.current) return  // modal is open; suppress swipe
    pendingActionRef.current = dir === 'right' ? 'like' : 'pass'
  }

  function onCardLeftScreen() {
    const action = pendingActionRef.current
    pendingActionRef.current = null
    if (!action) return
    if (action === 'like') {
      const card = topCard
      advance()
      if (card?.canonical_bld_id) {
        addLikedBuilding(card.canonical_bld_id).catch(() => {
          // Fire-and-forget; errors are silent (card is already advanced)
        })
        setSavesThisVisit(s => s + 1)
      }
    } else {
      advance()
    }
  }

  // Long-press modal callbacks (SaveToBoardModal opened by 400ms long-press)
  function handleSaved() {
    longPressFired.current = false
    setSaveModalCard(null)
    setSavesThisVisit(s => s + 1)
  }

  function handleSaveCancel() {
    longPressFired.current = false
    setSaveModalCard(null)
  }

  // -- Long-press handlers (400ms) --
  function handleTouchStart(e) {
    touchStartPos.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }
    longPressFired.current = false
    clearTimeout(longPressTimer.current)
    longPressTimer.current = setTimeout(() => {
      longPressFired.current = true
      if (topCard) {
        setSaveModalCard(topCard)
      }
    }, 400)
  }

  function handleTouchEnd() {
    clearTimeout(longPressTimer.current)
  }

  function handleTouchMove(e) {
    if (!touchStartPos.current) return
    const dx = Math.abs(e.touches[0].clientX - touchStartPos.current.x)
    const dy = Math.abs(e.touches[0].clientY - touchStartPos.current.y)
    if (dx > 10 || dy > 10) clearTimeout(longPressTimer.current)
  }

  function handleRetry() {
    setDeck([])
    setCursor(0)
    setHasMore(true)
    fetchPage(0, true)
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'space-between',
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflow: 'hidden',
      background: 'var(--color-bg)',
      padding: '20px 16px',
    }}>

      {/* Header */}
      <div style={{ textAlign: 'center', width: '100%' }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 14px', letterSpacing: '-0.01em' }}>
          <span style={{ color: 'var(--color-text)' }}>Disc</span>
          <span style={{ color: '#ec4899' }}>overy</span>
        </h1>
        <div style={{
          color: 'var(--color-text-dim)',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
        }}>
          {tasteState}
        </div>
      </div>

      {/* Card stack */}
      <div
        style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onTouchMove={handleTouchMove}
      >
        {error && deck.length === 0 ? (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: 12, textAlign: 'center',
            color: 'var(--color-text)', padding: '0 20px',
          }}>
            <p style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>
              Couldn&apos;t load Discovery. Tap to retry.
            </p>
            <button
              type="button"
              onClick={handleRetry}
              style={{
                minHeight: 44,
                padding: '0 16px',
                borderRadius: 12,
                border: '1px solid var(--color-border-soft)',
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                fontSize: 14,
                fontWeight: 700,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              Retry
            </button>
          </div>
        ) : deck.length === 0 && loading ? (
          <LoadingCard />
        ) : deck.length === 0 && !loading ? (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            textAlign: 'center', color: 'var(--color-text)', padding: '0 20px',
          }}>
            <p style={{ margin: 0, color: 'var(--color-text)', fontSize: 16, fontWeight: 700 }}>
              Nothing to show yet
            </p>
            <button
              type="button"
              onClick={() => navigate('/new')}
              style={{
                marginTop: 12,
                minHeight: 44,
                padding: '0 18px',
                borderRadius: 12,
                border: 'none',
                background: 'linear-gradient(135deg,#ec4899,#f43f5e)',
                color: '#fff',
                fontSize: 14,
                fontWeight: 700,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              Start Taste Analysis
            </button>
          </div>
        ) : (
          // Render up to 3 stacked cards. The top-of-deck is the active
          // TinderCard; lower cards are static previews for depth.
          <>
            {deck.slice(0, 3).reverse().map((card, idxFromBottom) => {
              const stackIndex = 2 - idxFromBottom // 0 = top
              const isTop = stackIndex === 0
              const id = getCardId(card)
              if (isTop) {
                return (
                  <TinderCard
                    key={`top-${id}`}
                    ref={cardRef}
                    onSwipe={onTinderSwipe}
                    onCardLeftScreen={onCardLeftScreen}
                    preventSwipe={['up', 'down']}
                    swipeRequirementType='position'
                    swipeThreshold={120}
                  >
                    <SwipeCard
                      card={card}
                      onGalleryOpen={() => {}}
                      onGalleryClose={() => {}}
                    />
                  </TinderCard>
                )
              }
              return (
                <div
                  key={`bg-${id}-${stackIndex}`}
                  style={{
                    position: 'absolute', top: 0, left: 0,
                    width: CARD_WIDTH, height: CARD_HEIGHT,
                    transform: `scale(${1 - stackIndex * 0.04}) translateY(${stackIndex * 8}px)`,
                    opacity: 1 - stackIndex * 0.18,
                    pointerEvents: 'none',
                    zIndex: -stackIndex,
                  }}
                >
                  <SwipeCard
                    card={card}
                    onGalleryOpen={() => {}}
                    onGalleryClose={() => {}}
                  />
                </div>
              )
            })}
            {loading && deck.length > 0 && (
              <div style={{
                position: 'absolute', bottom: -28, left: 0, right: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <div style={{
                  width: 18, height: 18, borderRadius: '50%',
                  border: '2px solid rgba(255,255,255,0.2)',
                  borderTopColor: '#ec4899',
                  animation: 'spin 0.8s linear infinite',
                }} />
              </div>
            )}
          </>
        )}
      </div>

      {/* Hint */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, margin: 0 }}>
          ← skip · tap card · save →&nbsp;&nbsp;·&nbsp;&nbsp;arrow keys supported
        </p>
      </div>

      {saveModalCard && (
        <SaveToBoardModal
          card={saveModalCard}
          onClose={handleSaveCancel}
          onSaved={handleSaved}
        />
      )}

      {surpriseOpen && (
        <SurpriseBoardModal
          onClose={() => setSurpriseOpen(false)}
          onSaved={() => setSurpriseOpen(false)}
        />
      )}
    </div>
  )
}
