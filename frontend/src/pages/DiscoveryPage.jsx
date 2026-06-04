import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchDiscoveryFeed, discoveryFeedback, promoteToTaste } from '../api/client.js'
import { reportWriteError } from '../utils/reportWriteError.js'
import SwipeCard, { CARD_WIDTH, CARD_HEIGHT } from '../components/SwipeCard.jsx'
import DiscoveryTriggerCard from '../components/DiscoveryTriggerCard.jsx'
import SaveToBoardModal from '../components/SaveToBoardModal.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'

const PREFETCH_AT_REMAINING = 3   // fetch more when deck.length <= this
const TASTE_NUDGE_THRESHOLD = 10  // inject trigger card when draftLikeCount reaches this
const SWIPE_KEYS = { ArrowLeft: 'left', ArrowRight: 'right' }

const DECK_CACHE_KEY = 'discovery_deck_v2'
const DECK_CACHE_TTL_MS = 30 * 60 * 1000  // 30 min
const DRAFT_ID_KEY = 'discovery_draft_id'
const DRAFT_LIKES_KEY = 'discovery_draft_likes'
const SEEN_IDS_KEY = 'discovery_seen_ids'

const TRIGGER_CARD_ID = '__taste_trigger__'

// tasteState → short Korean label
const TASTE_STATE_LABEL = {
  cold:   '탐색 중',
  single: '취향 파악 중',
  multi:  '취향 다양',
}

// Shake keyframes injected once per page mount
const SHAKE_STYLE_ID = 'discovery-shake-style'
function ensureShakeStyle() {
  if (document.getElementById(SHAKE_STYLE_ID)) return
  const el = document.createElement('style')
  el.id = SHAKE_STYLE_ID
  el.textContent = `
    @keyframes discovery-shake {
      0%,100% { transform: translateX(0); }
      20%,60%  { transform: translateX(-8px); }
      40%,80%  { transform: translateX(8px); }
    }
    .discovery-shake {
      animation: discovery-shake 0.5s var(--motion-ease, cubic-bezier(0.4,0,0.2,1));
    }
  `
  document.head.appendChild(el)
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

function loadSeenIds() {
  try {
    const raw = sessionStorage.getItem(SEEN_IDS_KEY)
    if (!raw) return new Set()
    return new Set(JSON.parse(raw))
  } catch {
    return new Set()
  }
}

function saveSeenIds(set) {
  try {
    sessionStorage.setItem(SEEN_IDS_KEY, JSON.stringify([...set]))
  } catch { /* quota exceeded — ignore */ }
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

function isTriggerCard(card) {
  return card?.canonical_bld_id === TRIGGER_CARD_ID || card?.__trigger === true
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
  // triggerShownRef: true once the trigger card has been injected this session
  const triggerShownRef = useRef(false)
  // seenIdsRef: tracks cards seen this session for shake animation on re-appearance
  const seenIdsRef = useRef(loadSeenIds())
  // shakeCardId: the card id currently being shaken
  const [shakeCardId, setShakeCardId] = useState(null)
  const [promoteLoading, setPromoteLoading] = useState(false)

  const _cached = loadDeckCache()
  const [deck, setDeck] = useState(_cached ? _cached.deck : [])
  const [tasteState, setTasteState] = useState(_cached ? (_cached.tasteState || 'cold') : 'cold')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [saveModalCard, setSaveModalCard] = useState(null)

  // Draft-id session state — persisted to sessionStorage
  const [draftId, setDraftId] = useState(() => sessionStorage.getItem(DRAFT_ID_KEY) || null)
  const [draftLikeCount, setDraftLikeCount] = useState(() => {
    const hasDraft = sessionStorage.getItem(DRAFT_ID_KEY)
    if (!hasDraft) {
      sessionStorage.removeItem(DRAFT_LIKES_KEY)   // stale count with no board — discard
      return 0
    }
    const stored = sessionStorage.getItem(DRAFT_LIKES_KEY)
    return stored ? parseInt(stored, 10) : 0
  })

  const initialDeckLengthRef = useRef(deck.length)

  useEffect(() => {
    isActiveRef.current = true
    ensureShakeStyle()
    return () => { isActiveRef.current = false }
  }, [])

  // Persist draftId to sessionStorage whenever it changes
  useEffect(() => {
    if (draftId) {
      sessionStorage.setItem(DRAFT_ID_KEY, draftId)
    } else {
      sessionStorage.removeItem(DRAFT_ID_KEY)
    }
  }, [draftId])

  // Persist draftLikeCount to sessionStorage
  useEffect(() => {
    sessionStorage.setItem(DRAFT_LIKES_KEY, String(draftLikeCount))
  }, [draftLikeCount])

  // Keyboard swipe: ← pass, → like. Blocked while save modal is open.
  useEffect(() => {
    async function onKey(e) {
      const dir = SWIPE_KEYS[e.key]
      if (!dir || !cardRef.current || keySwipingRef.current) return
      if (saveModalCard) return
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
  }, [deck.length, saveModalCard])

  // Inject trigger card when draftLikeCount first reaches threshold.
  // triggerShownRef is set INSIDE the updater so it is only marked true when the
  // injection actually happens. The outer deck.length guard is intentionally
  // absent: if the deck is temporarily empty (fetch in flight) the updater
  // returns prev unchanged and triggerShownRef stays false, so the effect
  // re-fires correctly once the deck is refilled (draftLikeCount still ≥10).
  useEffect(() => {
    if (draftId && draftLikeCount >= TASTE_NUDGE_THRESHOLD && !triggerShownRef.current) {
      const triggerCard = { canonical_bld_id: TRIGGER_CARD_ID, __trigger: true }
      setDeck(prev => {
        // Deck cleared mid-fetch — don't inject; effect re-fires when refilled
        if (prev.length === 0) return prev
        // Already present (strict guard against double-inject)
        if (prev.some(c => isTriggerCard(c))) return prev
        // Mark only when actually injecting
        triggerShownRef.current = true
        // Splice at index 1 (after the current top card) so it appears next
        const next = [...prev]
        next.splice(1, 0, triggerCard)
        return next
      })
    }
  }, [draftId, draftLikeCount])

  // Shake animation: when top card has already been seen (re-appearance), shake it
  useEffect(() => {
    const topCard = deck[0] || null
    if (!topCard || isTriggerCard(topCard)) return
    const id = getCardId(topCard)
    if (id && seenIdsRef.current.has(id)) {
      setShakeCardId(id)
      // Remove the class after animation completes so it can re-trigger next time
      const timer = setTimeout(() => setShakeCardId(null), 550)
      return () => clearTimeout(timer)
    }
  }, [deck]) // We only want to re-check when deck[0] changes

  // -- Fetch next chunk --
  // Passes current deck ids as buffer so the server won't re-serve them.
  const fetchPage = useCallback(async (currentDeck, reset = false) => {
    if (fetchingRef.current) return
    fetchingRef.current = true

    const requestId = ++requestIdRef.current
    const bufferIds = (currentDeck || [])
      .map(c => c?.canonical_bld_id || c?.image_id)
      .filter(id => id && id !== TRIGGER_CARD_ID)

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

  // Auto-prefetch next chunk when deck is running low (ignore trigger card in count)
  useEffect(() => {
    if (fetchingRef.current) return
    if (deck.length === 0) return  // initial-load case handled above
    const realCardCount = deck.filter(c => !isTriggerCard(c)).length
    if (realCardCount <= PREFETCH_AT_REMAINING) {
      fetchPage(deck)
    }
  }, [deck, fetchPage])

  // Persist deck + tasteState to sessionStorage for back-navigation restoration
  useEffect(() => {
    if (deck.length === 0) return
    // Don't persist the trigger card into the deck cache
    const cacheable = deck.filter(c => !isTriggerCard(c))
    if (cacheable.length === 0) return
    try {
      sessionStorage.setItem(DECK_CACHE_KEY, JSON.stringify({
        deck: cacheable, tasteState, ts: Date.now(),
      }))
    } catch {
      // sessionStorage quota exceeded or unavailable — ignore
    }
  }, [deck, tasteState])

  const topCard = deck[0] || null
  const topCardId = getCardId(topCard)

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

    // -- Trigger card handling --
    if (isTriggerCard(card)) {
      if (action === 'like') {
        // RIGHT swipe → promote to Taste
        handlePromoteToTaste()
      }
      // LEFT swipe → just advance (already done). Do NOT re-inject this session.
      return
    }

    const bldId = card?.canonical_bld_id || card?.image_id
    if (!bldId) return

    // Track seen id for shake dedup
    seenIdsRef.current.add(bldId)
    saveSeenIds(seenIdsRef.current)

    if (action === 'like') {
      discoveryFeedback(bldId, 'like', draftId)
        .then(res => {
          if (res.draftId) setDraftId(res.draftId)
          setDraftLikeCount(res.draftLikeCount)
        })
        .catch(() => reportWriteError(showToast, '좋아요 저장 실패'))
    } else {
      // Pass: server records it for dislike zone; failure is low-stakes but
      // we still surface it consistently per FRONT-UX silent-failure policy.
      discoveryFeedback(bldId, 'pass', draftId)
        .then(res => {
          if (res.draftId) setDraftId(res.draftId)
        })
        .catch(() => reportWriteError(showToast, '패스 기록 실패'))
    }
  }

  // -- Promote to Taste (triggered by right-swipe on trigger card) --
  async function handlePromoteToTaste() {
    if (promoteLoading) return
    setPromoteLoading(true)
    try {
      const result = await promoteToTaste(draftId)
      // Clear draft session state — a future Discovery visit starts fresh
      setDraftId(null)
      setDraftLikeCount(0)
      triggerShownRef.current = false
      sessionStorage.removeItem(DRAFT_ID_KEY)
      sessionStorage.removeItem(DRAFT_LIKES_KEY)
      // Hand off the session payload to App.jsx via custom event.
      window.dispatchEvent(new CustomEvent('archithon:promote-to-taste', { detail: result }))
      navigate('/swipe')
    } catch (err) {
      if (err?.status === 400 && err?.data?.detail === 'not_enough_likes') {
        // Phantom trigger from a stale count — clear it so the user isn't stuck.
        setDeck(prev => prev.filter(c => !isTriggerCard(c)))
        triggerShownRef.current = false
        setDraftLikeCount(0)
        reportWriteError(showToast, '좋아요가 부족합니다 (최소 10개)')
      } else {
        reportWriteError(showToast, 'Taste 분석 시작 실패 — 다시 시도해주세요')
      }
    } finally {
      setPromoteLoading(false)
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
      if (topCard && !isTriggerCard(topCard)) setSaveModalCard(topCard)
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
      if (topCard && !isTriggerCard(topCard)) setSaveModalCard(topCard)
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

  // ── Render ─────────────────────────────────────────────────────────────── //
  const tasteLabel = TASTE_STATE_LABEL[tasteState] || tasteState
  // Progress bar: 0–10 likes fills the bar
  const progressPct = Math.min(draftLikeCount / TASTE_NUDGE_THRESHOLD, 1)
  const progressComplete = draftLikeCount >= TASTE_NUDGE_THRESHOLD

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
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 8px', letterSpacing: '-0.01em' }}>
          <span style={{ color: 'var(--color-text)' }}>Disc</span>
          <span style={{ color: '#ec4899' }}>overy</span>
        </h1>
        <div style={{
          color: 'var(--color-text-dim)',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          marginBottom: 10,
        }}>
          {tasteLabel}
        </div>

        {/* Progress bar — fills draftLikeCount/10; shows '취향 탐색 중' at >=10 */}
        <div style={{ width: '100%', maxWidth: CARD_WIDTH, margin: '0 auto' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 4,
          }}>
            <span style={{
              fontSize: 11,
              fontWeight: 600,
              color: progressComplete ? '#ec4899' : 'var(--color-text-muted)',
              letterSpacing: '0.02em',
            }}>
              {progressComplete ? '취향 탐색 중' : `${draftLikeCount}/10`}
            </span>
          </div>
          <div style={{
            width: '100%',
            height: 3,
            borderRadius: 999,
            background: 'var(--color-surface-3, #E1E4E8)',
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${progressPct * 100}%`,
              borderRadius: 999,
              background: progressComplete
                ? 'linear-gradient(90deg, #ec4899, var(--accent-1, #0969DA))'
                : '#ec4899',
              transition: `width var(--motion-normal, 220ms) var(--motion-ease, cubic-bezier(0.4,0,0.2,1))`,
            }} />
          </div>
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
              const isTrigger = isTriggerCard(card)

              if (isTop) {
                const isShaking = !isTrigger && shakeCardId === topCardId
                return (
                  <SwipeGestureFrame
                    key={`top-${id}`}
                    ref={cardRef}
                    onSwipe={onTinderSwipe}
                    onCardLeftScreen={onCardLeftScreen}
                    className={isShaking ? 'discovery-shake' : undefined}
                  >
                    {isTrigger ? (
                      <DiscoveryTriggerCard />
                    ) : (
                      <SwipeCard
                        card={card}
                        onGalleryOpen={() => {}}
                        onGalleryClose={() => {}}
                      />
                    )}
                  </SwipeGestureFrame>
                )
              }
              // Background stack cards: never render trigger card in the stack
              if (isTrigger) return null
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

      {/* Bottom area: swipe hint */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        {promoteLoading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 14, height: 14, borderRadius: '50%',
              border: '2px solid var(--color-text-dim)',
              borderTopColor: '#ec4899',
              animation: 'spin 0.8s linear infinite',
            }} />
            <span style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>
              Taste 분석 중…
            </span>
          </div>
        ) : (
          <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, margin: 0 }}>
            ← skip · tap card · save →&nbsp;&nbsp;·&nbsp;&nbsp;arrow keys supported
          </p>
        )}
      </div>

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
