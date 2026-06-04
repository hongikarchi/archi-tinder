import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchDiscoveryFeed, discoveryFeedback, promoteToTaste } from '../api/client.js'
import { reportWriteError } from '../utils/reportWriteError.js'
import SwipeCard, { CARD_WIDTH, CARD_HEIGHT } from '../components/SwipeCard.jsx'
import SaveToBoardModal from '../components/SaveToBoardModal.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'

const PREFETCH_AT_REMAINING = 3   // fetch more when deck.length <= this
const TASTE_NUDGE_THRESHOLD = 10  // show Taste nudge when draftLikeCount reaches this
const SWIPE_KEYS = { ArrowLeft: 'left', ArrowRight: 'right' }

const DECK_CACHE_KEY = 'discovery_deck_v2'
const DECK_CACHE_TTL_MS = 30 * 60 * 1000  // 30 min

// tasteState → short Korean label
const TASTE_STATE_LABEL = {
  cold:   '탐색 중',
  single: '취향 파악 중',
  multi:  '취향 다양',
}

function loadDeckCache() {
  try {
    const raw = sessionStorage.getItem(DECK_CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed.ts || Date.now() - parsed.ts > DECK_CACHE_TTL_MS) return null
    if (!Array.isArray(parsed.deck) || parsed.deck.length === 0) return null
    return parsed
  } catch {
    return null
  }
}

/* ── preloadImage helper ─────────────────────────────────────────────────── */
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

export default function DiscoveryPage({ showToast }) {
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
  // Tracks whether the Taste nudge was dismissed this visit so it doesn't re-arm
  const nudgeDismissedRef = useRef(false)
  const [promoteLoading, setPromoteLoading] = useState(false)

  const _cached = loadDeckCache()
  const [deck, setDeck] = useState(_cached ? _cached.deck : [])
  const [tasteState, setTasteState] = useState(_cached ? (_cached.tasteState || 'cold') : 'cold')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [saveModalCard, setSaveModalCard] = useState(null)
  // Server-authoritative count updated after each feedback POST
  const [draftLikeCount, setDraftLikeCount] = useState(0)
  // Taste nudge visible: true when threshold hit and not dismissed
  const [nudgeVisible, setNudgeVisible] = useState(false)

  const initialDeckLengthRef = useRef(deck.length)

  useEffect(() => {
    isActiveRef.current = true
    return () => { isActiveRef.current = false }
  }, [])

  // Keyboard swipe: ← pass, → like. Blocked while save modal or nudge is open.
  useEffect(() => {
    async function onKey(e) {
      const dir = SWIPE_KEYS[e.key]
      if (!dir || !cardRef.current || keySwipingRef.current) return
      if (saveModalCard || nudgeVisible) return
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
  }, [deck.length, saveModalCard, nudgeVisible])

  // Taste nudge: show when threshold reached and not already dismissed this visit
  useEffect(() => {
    if (
      draftLikeCount >= TASTE_NUDGE_THRESHOLD &&
      !nudgeDismissedRef.current &&
      !nudgeVisible
    ) {
      setNudgeVisible(true)
    }
  }, [draftLikeCount, nudgeVisible])

  // -- Fetch next chunk --
  // Passes current deck ids as buffer so the server won't re-serve them.
  const fetchPage = useCallback(async (currentDeck, reset = false) => {
    if (fetchingRef.current) return
    fetchingRef.current = true

    const requestId = ++requestIdRef.current
    const bufferIds = (currentDeck || [])
      .map(c => c?.canonical_bld_id || c?.image_id)
      .filter(Boolean)

    setLoading(true)
    setError('')

    try {
      const result = await fetchDiscoveryFeed(bufferIds)
      if (!isActiveRef.current || requestId !== requestIdRef.current) return

      // Preload the first few images so subsequent cards render with image cached
      const preload = preloadRef.current
      for (const c of result.cards.slice(0, 3)) {
        if (c?.image_url) preload(c.image_url)
      }

      setDeck(prev => (reset ? result.cards : [...prev, ...result.cards]))
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
  }, [])

  // Initial load — skip if deck was restored from sessionStorage cache
  useEffect(() => {
    if (initialDeckLengthRef.current > 0) return
    fetchPage([], true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-prefetch next chunk when deck is running low
  useEffect(() => {
    if (fetchingRef.current) return
    if (deck.length === 0) return  // initial-load case handled above
    if (deck.length <= PREFETCH_AT_REMAINING) {
      fetchPage(deck)
    }
  }, [deck, fetchPage])

  // Persist deck + tasteState to sessionStorage for back-navigation restoration
  useEffect(() => {
    if (deck.length === 0) return
    try {
      sessionStorage.setItem(DECK_CACHE_KEY, JSON.stringify({
        deck, tasteState, ts: Date.now(),
      }))
    } catch {
      // sessionStorage quota exceeded or unavailable — ignore
    }
  }, [deck, tasteState])

  const topCard = deck[0] || null

  function advance() {
    setDeck(prev => prev.slice(1))
  }

  // -- Swipe handlers --
  // Right (like): optimistic advance + POST feedback.
  // Left (pass): optimistic advance + POST feedback (fire-and-forget, low-stakes).
  function onTinderSwipe(dir) {
    if (longPressFired.current) return
    pendingActionRef.current = dir === 'right' ? 'like' : 'pass'
  }

  function onCardLeftScreen() {
    const action = pendingActionRef.current
    pendingActionRef.current = null
    if (!action) return

    const card = topCard
    advance()

    const bldId = card?.canonical_bld_id || card?.image_id
    if (!bldId || bldId === '__action_card__') return

    if (action === 'like') {
      discoveryFeedback(bldId, 'like')
        .then(res => setDraftLikeCount(res.draftLikeCount))
        .catch(() => reportWriteError(showToast, '좋아요 저장 실패'))
    } else {
      // Pass: server records it for dislike zone; failure is low-stakes but
      // we still surface it consistently per FRONT-UX silent-failure policy.
      discoveryFeedback(bldId, 'pass')
        .catch(() => reportWriteError(showToast, '패스 기록 실패'))
    }
  }

  // Long-press modal callbacks (SaveToBoardModal opened by 400ms long-press)
  function handleSaved() {
    longPressFired.current = false
    setSaveModalCard(null)
    advance()
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
      if (topCard) setSaveModalCard(topCard)
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

  function handleMouseDown(e) {
    touchStartPos.current = { x: e.clientX, y: e.clientY }
    longPressFired.current = false
    clearTimeout(longPressTimer.current)
    longPressTimer.current = setTimeout(() => {
      longPressFired.current = true
      if (topCard) setSaveModalCard(topCard)
    }, 400)
  }

  function handleMouseUp() {
    clearTimeout(longPressTimer.current)
  }

  function handleMouseLeave() {
    clearTimeout(longPressTimer.current)
  }

  function handleMouseMove(e) {
    if (!touchStartPos.current) return
    const dx = Math.abs(e.clientX - touchStartPos.current.x)
    const dy = Math.abs(e.clientY - touchStartPos.current.y)
    if (dx > 10 || dy > 10) clearTimeout(longPressTimer.current)
  }

  function handleRetry() {
    sessionStorage.removeItem(DECK_CACHE_KEY)
    setDeck([])
    setError('')
    fetchPage([], true)
  }

  // -- Taste nudge handlers --
  async function handlePromoteToTaste() {
    if (promoteLoading) return
    setPromoteLoading(true)
    try {
      const result = await promoteToTaste()
      // Hand off the session payload to App.jsx via custom event.
      // App.jsx's archithon:promote-to-taste handler creates a local project,
      // calls applySessionResponse, and navigates to /swipe.
      window.dispatchEvent(new CustomEvent('archithon:promote-to-taste', { detail: result }))
    } catch (err) {
      if (err?.status === 400 && err?.data?.detail === 'not_enough_likes') {
        reportWriteError(showToast, '좋아요가 부족합니다 (최소 10개)')
      } else {
        reportWriteError(showToast, 'Taste 분석 시작 실패 — 다시 시도해주세요')
      }
    } finally {
      setPromoteLoading(false)
    }
  }

  function handleContinueDiscovery() {
    nudgeDismissedRef.current = true
    setNudgeVisible(false)
  }

  // ── Render ─────────────────────────────────────────────────────────────── //
  const tasteLabel = TASTE_STATE_LABEL[tasteState] || tasteState

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
          {tasteLabel}
        </div>
      </div>

      {/* Card stack */}
      <div
        style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onTouchMove={handleTouchMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onMouseMove={handleMouseMove}
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
          <>
            {deck.slice(0, 3).reverse().map((card, idxFromBottom) => {
              const stackIndex = 2 - idxFromBottom // 0 = top
              const isTop = stackIndex === 0
              const id = getCardId(card)
              if (isTop) {
                return (
                  <SwipeGestureFrame
                    key={`top-${id}`}
                    ref={cardRef}
                    onSwipe={onTinderSwipe}
                    onCardLeftScreen={onCardLeftScreen}
                  >
                    <SwipeCard
                      card={card}
                      onGalleryOpen={() => {}}
                      onGalleryClose={() => {}}
                    />
                  </SwipeGestureFrame>
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

      {/* Bottom area: Taste Nudge banner OR hint text */}
      {nudgeVisible ? (
        <div style={{
          width: '100%',
          maxWidth: CARD_WIDTH,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 8,
          padding: '16px 0 4px',
        }}>
          {/* Main CTA — Primary button per DESIGN.md §8.1 */}
          <button
            type="button"
            disabled={promoteLoading}
            onClick={handlePromoteToTaste}
            style={{
              width: '100%',
              minHeight: 44,
              padding: '12px 16px',
              borderRadius: 12,
              border: 'none',
              background: promoteLoading
                ? 'var(--color-surface-2)'
                : 'linear-gradient(135deg, var(--accent-1, #0969DA), var(--accent-2, #8250DF))',
              color: promoteLoading ? 'var(--color-text-dim)' : '#fff',
              fontSize: 14,
              fontWeight: 600,
              cursor: promoteLoading ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              letterSpacing: '-0.01em',
              transition: `transform var(--motion-normal, 220ms) var(--motion-ease, cubic-bezier(0.4,0,0.2,1)),
                           box-shadow var(--motion-slow, 400ms) var(--motion-ease-out, cubic-bezier(0,0,0.2,1))`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            {promoteLoading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  width: 16, height: 16, borderRadius: '50%',
                  border: '2px solid var(--color-text-dim)',
                  borderTopColor: 'transparent',
                  animation: 'spin 0.8s linear infinite',
                  display: 'inline-block',
                }} />
                분석 중…
              </span>
            ) : (
              <span>✨ 취향이 10장 모였어요 — Taste에서 깊게 탐색하기</span>
            )}
          </button>

          {/* Secondary text button — Ghost style per DESIGN.md §8.3 */}
          <button
            type="button"
            onClick={handleContinueDiscovery}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--color-text-muted)',
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: 'inherit',
              padding: '6px 8px',
              borderRadius: 8,
              minHeight: 32,
              letterSpacing: '-0.005em',
            }}
          >
            계속 Discovery에서 탐색하기
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, margin: 0 }}>
            ← skip · tap card · save →&nbsp;&nbsp;·&nbsp;&nbsp;arrow keys supported
          </p>
        </div>
      )}

      {saveModalCard && (
        <SaveToBoardModal
          card={saveModalCard}
          onClose={handleSaveCancel}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
