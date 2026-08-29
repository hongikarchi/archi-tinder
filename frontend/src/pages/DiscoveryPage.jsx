import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchDiscoveryFeed, discoveryFeedback, promoteToTaste, VerifyRequiredError } from '../api/client.js'
import { reportWriteError } from '../utils/reportWriteError.js'
import SwipeCard, { CARD_WIDTH, CARD_HEIGHT } from '../components/SwipeCard.jsx'
import DiscoveryTriggerCard from '../components/DiscoveryTriggerCard.jsx'
import TutorialPopup from '../components/TutorialPopup.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'
import CardSkeleton from '../components/CardSkeleton.jsx'
import SwipeDeck from '../components/SwipeDeck.jsx'
import { SWIPE_PREVENT_ALL } from '../components/swipeGestureConfig.js'
import { discoveryNavigationGuard } from '../utils/discoveryGuard.js'
import { useSwipeOrchestration } from '../hooks/useSwipeOrchestration.js'
import { useKeyboardSwipe } from '../hooks/useKeyboardSwipe.js'
import { useTranslation } from '../i18n/index.js'

// Module-level flag: false on full page reload (module not yet loaded), true after
// the first mount within the same SPA session. Used to detect tab re-entry vs first
// load so we can start a fresh draft on re-entry while still restoring on refresh.
let _discoveryMountedOnce = false

const PREFETCH_AT_REMAINING = 3   // fetch more when deck.length <= this
const TASTE_NUDGE_THRESHOLD = 10  // inject trigger card when draftLikeCount reaches this
const DISCOVERY_LIKE_HARD_CAP = 50  // hard stop — block swiping, force Taste hand-off
const DECK_CACHE_KEY = 'discovery_deck_v4' // v4: added gallery_srcset field (FRONT-UX-14-FIX) — invalidate pre-change cached decks
const DECK_CACHE_TTL_MS = 30 * 60 * 1000  // 30 min
const DRAFT_ID_KEY = 'discovery_draft_id'
const DRAFT_LIKES_KEY = 'discovery_draft_likes'
const SEEN_IDS_KEY = 'discovery_seen_ids'
// Feature B: persists across page refresh within same session
const CONTINUE_AFTER_TRIGGER_KEY = 'discovery_continue_after_trigger'

const TRIGGER_CARD_ID = '__taste_trigger__'

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

/* ── Feature A: inject a high-priority <link rel="preload"> for the first
     card image. This fires before React renders the <img> tag, letting the
     browser start the network request while the deck is being populated.
     Cache: one injected link per URL (idempotent). ────────────────────────── */
const _preloadLinkCache = new Set()
function injectFirstCardPreload(url) {
  if (!url || _preloadLinkCache.has(url)) return
  _preloadLinkCache.add(url)
  try {
    const link = document.createElement('link')
    link.rel = 'preload'
    link.as = 'image'
    link.href = url
    link.fetchPriority = 'high'
    document.head.appendChild(link)
  } catch { /* ignore — best-effort */ }
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

function getCardId(card) {
  return card?.canonical_bld_id || card?.image_id || card?.building_id || null
}

function isTriggerCard(card) {
  return card?.canonical_bld_id === TRIGGER_CARD_ID || card?.__trigger === true
}

// Helper: wipe all Discovery draft sessionStorage keys and return cleared defaults.
// Called on tab re-entry (SPA remount) to force a fresh draft start.
function _clearDraftSessionStorage() {
  sessionStorage.removeItem(DRAFT_ID_KEY)
  sessionStorage.removeItem(DRAFT_LIKES_KEY)
  sessionStorage.removeItem(DECK_CACHE_KEY)
  sessionStorage.removeItem(SEEN_IDS_KEY)
  sessionStorage.removeItem(CONTINUE_AFTER_TRIGGER_KEY)
}

export default function DiscoveryPage({ showToast }) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const isActiveRef = useRef(true)
  const requestIdRef = useRef(0)
  const fetchingRef = useRef(false)
  const preloadRef = useRef(makeImagePreloader())
  const cardRef = useRef(null)
  // triggerShownRef: true once the trigger card has been injected this session
  const triggerShownRef = useRef(false)
  // seenIdsRef: tracks cards seen this session for shake animation on re-appearance
  const seenIdsRef = useRef(loadSeenIds())
  // shakeCardId: the card id currently being shaken
  const [shakeCardId, setShakeCardId] = useState(null)
  const [promoteLoading, setPromoteLoading] = useState(false)
  const [capReached, setCapReached] = useState(false)
  // FRONT-FLOW-1: shown once on first Discovery entry for newly registered
  // accounts — flag set by LoginPage's register-success path. DiscoveryPage
  // owns both localStorage keys end-to-end (component itself stays dumb).
  const [showTutorial, setShowTutorial] = useState(
    () => localStorage.getItem('archithon_show_tutorial') === '1'
  )
  // Leave-warning modal state (DISCOVERY-PERF-3)
  const [leaveModal, setLeaveModal] = useState(null)  // null | { proceed: fn }
  // True while the modal's auto-promote call is in-flight (>=10 path)
  const [leaveModalPromoting, setLeaveModalPromoting] = useState(false)
  // Stable ref to draftLikeCount for the guard closure (avoids stale closure issues).
  // Seeded with 0; the effect at lines 249-251 keeps it in sync after every render.
  const draftLikeCountRef = useRef(0)

  // Detect tab re-entry: _discoveryMountedOnce is false only on full page load
  // (module not yet executed). On SPA tab navigation it stays true, so a second
  // mount (user went to another tab and came back) is a re-entry → fresh draft.
  // Capture the flag value once at mount into a ref so subsequent re-renders do
  // not re-read the (now-always-true) module variable.
  const isReentryMountRef = useRef(null)
  if (isReentryMountRef.current === null) {
    // First render of this mount: capture the module flag, then set it.
    isReentryMountRef.current = _discoveryMountedOnce  // true = re-entry
    if (!_discoveryMountedOnce) {
      _discoveryMountedOnce = true
    }
    // If re-entry: wipe sessionStorage immediately (before useState initialisers
    // further down read from it) so they all start with clean slate.
    if (isReentryMountRef.current) {
      _clearDraftSessionStorage()
    }
  }
  const isReentryMount = isReentryMountRef.current

  // Feature B: set when user left-swipes the trigger card ("Discovery 계속")
  const [continueAfterTrigger, setContinueAfterTrigger] = useState(
    () => isReentryMount ? false : sessionStorage.getItem(CONTINUE_AFTER_TRIGGER_KEY) === '1'
  )

  const _cached = isReentryMount ? null : loadDeckCache()
  const [deck, setDeck] = useState(_cached ? _cached.deck : [])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Draft-id session state — persisted to sessionStorage
  const [draftId, setDraftId] = useState(() => {
    if (isReentryMount) return null
    return sessionStorage.getItem(DRAFT_ID_KEY) || null
  })
  const [draftLikeCount, setDraftLikeCount] = useState(() => {
    if (isReentryMount) return 0
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
    // On tab re-entry: reset refs that carry over between renders but won't be
    // re-initialized by useState (since they start with useRef()).
    if (isReentryMount) {
      triggerShownRef.current = false
      seenIdsRef.current = new Set()
    }
    return () => { isActiveRef.current = false }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

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

  // Hard cap: set capReached when like count hits the limit (covers sessionStorage restore case)
  useEffect(() => {
    if (draftLikeCount >= DISCOVERY_LIKE_HARD_CAP) setCapReached(true)
  }, [draftLikeCount])

  // Keep draftLikeCountRef in sync for guard closure reads
  useEffect(() => {
    draftLikeCountRef.current = draftLikeCount
  }, [draftLikeCount])

  // Register / update the module-level navigation guard (DISCOVERY-PERF-3).
  // The guard is set whenever DiscoveryPage is mounted; it checks draftLikeCountRef
  // at call time (not at registration time) so it always reflects the current count.
  // Cleared on unmount so callers outside /discovery fall through immediately.
  useEffect(() => {
    discoveryNavigationGuard.check = (action, proceed) => {
      if (draftLikeCountRef.current < 1) {
        proceed()
        return
      }
      setLeaveModal({ proceed })
    }
    return () => {
      discoveryNavigationGuard.check = null
    }
  }, [])

  // Keyboard swipe: ← pass, → like.

  // Inject trigger card when draftLikeCount first reaches threshold.
  // triggerShownRef is set INSIDE the updater so it is only marked true when the
  // injection actually happens. The outer deck.length guard is intentionally
  // absent: if the deck is temporarily empty (fetch in flight) the updater
  // returns prev unchanged and triggerShownRef stays false, so the effect
  // re-fires correctly once the deck is refilled (draftLikeCount still ≥10).
  //
  // Fix #4: splice at index 0 (not 1) so the trigger card becomes the NEXT card
  // immediately — splice(1,0) would put it after the card-currently-leaving,
  // which means it only appears two swipes later.
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
        // Splice at index 0: trigger card becomes the new top card immediately
        const next = [...prev]
        next.splice(0, 0, triggerCard)
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

      // Feature A: immediately inject a high-priority <link rel="preload"> for
      // the first card's image_url so the browser starts fetching before React
      // renders the <img> tag. This fires concurrently with the deck state update.
      if (reset && result.cards[0]?.image_url) {
        injectFirstCardPreload(result.cards[0].image_url)
      }

      // Preload the first few images so subsequent cards render with image cached
      const preload = preloadRef.current
      for (const c of result.cards.slice(0, 3)) {
        if (c?.image_url) preload(c.image_url)
      }

      setDeck(prev => (reset ? result.cards : [...prev, ...result.cards]))
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

  // Persist deck to sessionStorage for back-navigation restoration
  useEffect(() => {
    if (deck.length === 0) return
    // Don't persist the trigger card into the deck cache
    const cacheable = deck.filter(c => !isTriggerCard(c))
    if (cacheable.length === 0) return
    try {
      sessionStorage.setItem(DECK_CACHE_KEY, JSON.stringify({
        deck: cacheable, ts: Date.now(),
      }))
    } catch {
      // sessionStorage quota exceeded or unavailable — ignore
    }
  }, [deck])

  const topCard = deck[0] || null
  const topCardId = getCardId(topCard)

  function advance() {
    setDeck(prev => prev.slice(1))
  }

  // -- Swipe handlers --
  // Right (like): optimistic advance + POST feedback.
  // Left (pass): optimistic advance + POST feedback (fire-and-forget, low-stakes).
  //
  // onCommit reads topCard via render closure: react-tinder-card captures the
  // onCardLeftScreen handler at drag-release, so `topCard` here is frozen to the
  // card that was on top when the swipe began (same mechanism as pre-refactor).
  const { onTinderSwipe, onCardLeftScreen } = useSwipeOrchestration({
    likeAction: 'like',
    dismissAction: 'pass',
    onCommit: (action) => {
      const card = topCard
      advance()

      // -- Trigger card handling --
      if (isTriggerCard(card)) {
        if (action === 'like') {
          // RIGHT swipe → promote to Taste (기존 동작 유지)
          handlePromoteToTaste()
        } else {
          // LEFT swipe → Discovery 계속; set Feature B flag so the persistent
          // "Taste로 저장·이동" button appears on all subsequent cards.
          setContinueAfterTrigger(true)
          try { sessionStorage.setItem(CONTINUE_AFTER_TRIGGER_KEY, '1') } catch { /* ignore */ }
        }
        return
      }

      const bldId = card?.canonical_bld_id || card?.image_id
      if (!bldId) return

      // Track seen id for shake dedup
      seenIdsRef.current.add(bldId)
      saveSeenIds(seenIdsRef.current)

      if (action === 'like') {
        // Fix #4: optimistically increment draftLikeCount before the API call so
        // the threshold check (draftLikeCount >= TASTE_NUDGE_THRESHOLD) fires
        // synchronously this render cycle. The backend response reconciles with
        // the authoritative count (handles dedup / edge cases).
        setDraftLikeCount(prev => prev + 1)
        discoveryFeedback(bldId, 'like', draftId)
          .then(res => {
            if (res.draftId) setDraftId(res.draftId)
            // Reconcile with authoritative backend count (dedup/cap may adjust).
            setDraftLikeCount(res.draftLikeCount)
            if (res.likeCapReached) setCapReached(true)
          })
          .catch((err) => { if (!(err instanceof VerifyRequiredError)) reportWriteError(showToast, t('discovery.toastLikeFailed')) })
      } else {
        // Pass: server records it for dislike zone; failure is low-stakes but
        // we still surface it consistently per FRONT-UX silent-failure policy.
        discoveryFeedback(bldId, 'pass', draftId)
          .then(res => {
            if (res.draftId) setDraftId(res.draftId)
          })
          .catch((err) => { if (!(err instanceof VerifyRequiredError)) reportWriteError(showToast, t('discovery.toastPassFailed')) })
      }
    },
  })

  useKeyboardSwipe({
    onSwipe: async (dir) => { await cardRef.current?.swipe(dir) },
    guardCondition: () => !!(capReached || !cardRef.current || !deck.length || showTutorial),
  })

  // FRONT-FLOW-1: tutorial dismiss — removing 'archithon_show_tutorial' (set only
  // on register success, LoginPage) IS the complete "already seen" record.
  function handleTutorialClose() {
    localStorage.removeItem('archithon_show_tutorial')
    setShowTutorial(false)
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
      setContinueAfterTrigger(false)
      triggerShownRef.current = false
      sessionStorage.removeItem(DRAFT_ID_KEY)
      sessionStorage.removeItem(DRAFT_LIKES_KEY)
      sessionStorage.removeItem(CONTINUE_AFTER_TRIGGER_KEY)
      // Hand off the session payload to App.jsx via custom event.
      window.dispatchEvent(new CustomEvent('archithon:promote-to-taste', { detail: result }))
      navigate('/swipe')
    } catch (err) {
      if (err?.status === 400 && err?.data?.detail === 'not_enough_likes') {
        // Phantom trigger from a stale count — clear it so the user isn't stuck.
        setDeck(prev => prev.filter(c => !isTriggerCard(c)))
        triggerShownRef.current = false
        setDraftLikeCount(0)
        reportWriteError(showToast, t('discovery.toastNotEnoughLikes'))
      } else {
        reportWriteError(showToast, t('discovery.toastAnalysisFailed'))
      }
    } finally {
      setPromoteLoading(false)
    }
  }

  function handleRetry() {
    sessionStorage.removeItem(DECK_CACHE_KEY)
    setDeck([])
    setError('')
    fetchPage([], true)
  }

  // ── Render ─────────────────────────────────────────────────────────────── //

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'space-between',
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflow: 'hidden',
      background: 'var(--color-bg)',
      padding: '20px 16px',
    }}>

      <TutorialPopup visible={showTutorial} onClose={handleTutorialClose} />

      {/* Header */}
      <div style={{ textAlign: 'center', width: '100%' }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 8px', letterSpacing: '-0.01em' }}>
          <span style={{ color: 'var(--color-text)' }}>Disc</span>
          <span style={{ color: 'var(--accent-1)' }}>overy</span>
        </h1>

        {/* Feature B: persistent "Taste로 저장·이동" CTA — shown after user left-swiped
            the trigger card (Discovery 계속 선택). Rendered in the header (normal document
            flow, before the absolute card stack) so it is always above the cards and
            fully clickable. Primary CTA gradient per DESIGN.md §8.1, min-height 44px §3.2,
            radius var(--radius-md) §3.1. position:relative + zIndex:10 + pointerEvents:auto
            ensure it stays on top of the absolute-positioned card stack beneath it. */}
        {continueAfterTrigger && (
          <div style={{
            width: '100%',
            maxWidth: CARD_WIDTH,
            margin: '10px auto 0',
            position: 'relative',
            zIndex: 10,
            pointerEvents: 'auto',
          }}>
            <button
              type="button"
              onClick={handlePromoteToTaste}
              disabled={promoteLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                width: '100%',
                minHeight: 44,
                padding: '0 20px',
                borderRadius: 'var(--radius-md, 12px)',
                border: 'none',
                background: promoteLoading
                  ? 'color-mix(in srgb, var(--accent-1) 40%, transparent)'
                  : 'var(--accent-1)',
                color: '#fff',
                fontSize: 14,
                fontWeight: 600,
                cursor: promoteLoading ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
                letterSpacing: '-0.01em',
                transition: `transform var(--motion-normal, 220ms) var(--motion-ease, cubic-bezier(0.4,0,0.2,1))`,
              }}
            >
              {promoteLoading ? (
                <>
                  <div style={{
                    width: 14, height: 14, borderRadius: '50%',
                    border: '2px solid rgba(255,255,255,0.4)',
                    borderTopColor: '#fff',
                    animation: 'spin 0.8s linear infinite',
                    flexShrink: 0,
                  }} />
                  {t('discovery.tasteAnalyzing')}
                </>
              ) : (
                t('discovery.saveTasteAndMove')
              )}
            </button>
          </div>
        )}
      </div>

      {/* Card stack */}
      <div
        style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}
      >
        {capReached ? (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: 20, textAlign: 'center',
            padding: '0 24px',
            background: 'var(--color-bg)',
            borderRadius: 20,
          }}>
            <p style={{
              margin: 0,
              fontSize: 16,
              fontWeight: 700,
              color: 'var(--color-text)',
              lineHeight: 1.6,
            }}>
              <span style={{ color: 'var(--accent-1)' }}>{t('discovery.capReachedCount', { n: 50 })}</span>
              {' '}{t('discovery.capReachedBody')}
            </p>
            <button
              type="button"
              onClick={handlePromoteToTaste}
              disabled={promoteLoading}
              style={{
                minHeight: 44,
                padding: '0 24px',
                borderRadius: 12,
                border: 'none',
                background: promoteLoading
                  ? 'color-mix(in srgb, var(--accent-1) 40%, transparent)'
                  : 'var(--accent-1)',
                color: '#fff',
                fontSize: 15,
                fontWeight: 700,
                cursor: promoteLoading ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              {promoteLoading ? (
                <>
                  <div style={{
                    width: 14, height: 14, borderRadius: '50%',
                    border: '2px solid rgba(255,255,255,0.4)',
                    borderTopColor: '#fff',
                    animation: 'spin 0.8s linear infinite',
                    flexShrink: 0,
                  }} />
                  {t('discovery.tasteAnalyzing')}
                </>
              ) : (
                t('discovery.startTasteDeep')
              )}
            </button>
          </div>
        ) : error && deck.length === 0 ? (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: 12, textAlign: 'center',
            color: 'var(--color-text)', padding: '0 20px',
          }}>
            <p style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>
              {t('discovery.loadError')}
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
              {t('discovery.retry')}
            </button>
          </div>
        ) : deck.length === 0 && loading ? (
          <CardSkeleton />
        ) : deck.length === 0 && !loading ? (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            textAlign: 'center', color: 'var(--color-text)', padding: '0 20px',
          }}>
            <p style={{ margin: 0, color: 'var(--color-text)', fontSize: 16, fontWeight: 700 }}>
              {t('discovery.emptyTitle')}
            </p>
            <button
              type="button"
              onClick={() => navigate('/search')}
              style={{
                marginTop: 12,
                minHeight: 44,
                padding: '0 18px',
                borderRadius: 12,
                border: 'none',
                background: 'var(--accent-1)',
                color: '#fff',
                fontSize: 14,
                fontWeight: 700,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {t('discovery.startAnalysis')}
            </button>
          </div>
        ) : (
          <>
            {/* FRONT-UX-14-SIMPLIFY — full-size under-card stack via the shared
                SwipeDeck static ladder. Top + next real cards render in
                IDENTICAL keyed wrappers (key = card id only) so React reuses
                the DOM node when a card is promoted from under to top — no
                remount, no flicker. The under card is a real SwipeCard
                rendered inert (pointerEvents:none, aria-hidden); its image
                telemetry fires while hidden (acceptable — see report). The
                trigger card, when it is the under-card, renders inert too. */}
            <SwipeDeck active>
              {[deck[1], deck[0]].filter(Boolean).map(card => {
                const isTop = card === deck[0]
                const id = getCardId(card)
                const isTrigger = isTriggerCard(card)
                const isShaking = isTop && !isTrigger && shakeCardId === topCardId
                return (
                  <div
                    key={id}
                    style={{
                      position: 'absolute', inset: 0,
                      zIndex: isTop ? 5 : 4,
                      pointerEvents: isTop ? 'auto' : 'none',
                    }}
                    aria-hidden={!isTop}
                  >
                    <SwipeGestureFrame
                      ref={isTop ? cardRef : null}
                      onSwipe={isTop ? onTinderSwipe : undefined}
                      onCardLeftScreen={isTop ? onCardLeftScreen : undefined}
                      preventSwipe={isTop ? undefined : SWIPE_PREVENT_ALL}
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
                  </div>
                )
              })}
            </SwipeDeck>
            {loading && deck.length > 0 && (
              <div style={{
                position: 'absolute', bottom: -28, left: 0, right: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                zIndex: 6,
              }}>
                <div style={{
                  width: 18, height: 18, borderRadius: '50%',
                  border: '2px solid rgba(255,255,255,0.2)',
                  borderTopColor: 'var(--accent-1)',
                  animation: 'spin 0.8s linear infinite',
                }} />
              </div>
            )}
          </>
        )}
      </div>

      {/* Bottom area: swipe hint */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
        <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, margin: 0 }}>
          {t('discovery.swipeHintBar')}
        </p>
      </div>

      {/* Leave-warning modal (DISCOVERY-PERF-3) — shown when user tries to navigate
          away or log out while draftLikeCount >= 1. DESIGN.md §8.10: mobile = bottom
          sheet style (radius-xl top corners), desktop = centered modal (max-width 480px).
          Backdrop: rgba(0,0,0,0.4) per §8.10 sheet-backdrop. Buttons min-height 44px per §3.2. */}
      {leaveModal && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setLeaveModal(null)}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', maxWidth: 480,
              background: 'var(--color-surface, #F6F8FA)',
              borderRadius: '24px 24px 0 0',
              padding: 24,
              paddingBottom: 'calc(24px + env(safe-area-inset-bottom, 0px))',
              boxShadow: '0 -4px 32px rgba(0,0,0,0.18)',
            }}
          >
            {/* Handle bar */}
            <div style={{
              width: 36, height: 4, borderRadius: 999,
              background: 'var(--color-surface-3, #E1E4E8)',
              margin: '0 auto 20px',
            }} />

            <p style={{
              margin: '0 0 20px',
              fontSize: 14,
              fontWeight: 400,
              color: 'var(--color-text, #1F2328)',
              lineHeight: 1.6,
            }}>
              {draftLikeCount >= TASTE_NUDGE_THRESHOLD
                ? t('discovery.leaveModalBodyConverged')
                : t('discovery.leaveModalBodyDraft')}
            </p>

            {/* Primary action: stay */}
            <button
              type="button"
              onClick={() => setLeaveModal(null)}
              disabled={leaveModalPromoting}
              style={{
                display: 'block', width: '100%',
                minHeight: 44,
                padding: '0 16px',
                borderRadius: 12,
                border: 'none',
                background: 'var(--accent-1)',
                color: '#fff',
                fontSize: 15,
                fontWeight: 600,
                cursor: leaveModalPromoting ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
                marginBottom: 10,
                opacity: leaveModalPromoting ? 0.6 : 1,
              }}
            >
              {t('discovery.leaveModalStay')}
            </button>

            {/* Secondary action: leave
                >=10 likes: auto-promote then navigate to the intended destination.
                  Dispatches the custom event with skipNav:true so App.jsx persists
                  the session without forcing navigate('/swipe').
                1-9 likes: discard draft and proceed immediately. */}
            <button
              type="button"
              disabled={leaveModalPromoting}
              onClick={async () => {
                if (draftLikeCount >= TASTE_NUDGE_THRESHOLD) {
                  // Auto-promote path: persist the Taste session, then go where the
                  // user was originally headed (not forced to /swipe).
                  const proceed = leaveModal.proceed
                  setLeaveModalPromoting(true)
                  try {
                    const result = await promoteToTaste(draftId)
                    // Clear draft sessionStorage — same cleanup as handlePromoteToTaste
                    setDraftId(null)
                    setDraftLikeCount(0)
                    setContinueAfterTrigger(false)
                    triggerShownRef.current = false
                    sessionStorage.removeItem(DRAFT_ID_KEY)
                    sessionStorage.removeItem(DRAFT_LIKES_KEY)
                    sessionStorage.removeItem(CONTINUE_AFTER_TRIGGER_KEY)
                    // Persist the session via App.jsx listener with skipNav:true so
                    // App stores the project / calls applySessionResponse but does NOT
                    // force-navigate to /swipe — proceed() will do the real navigation.
                    window.dispatchEvent(new CustomEvent('archithon:promote-to-taste', {
                      detail: { ...result, skipNav: true },
                    }))
                  } catch (err) {
                    console.error('[LeaveModal] auto-promote failed:', err)
                    // Surface a brief error toast but do NOT trap the user — still let
                    // them proceed to their intended destination.
                    if (showToast) showToast(t('discovery.toastSaveFailedLeave'), 'warning')
                  } finally {
                    setLeaveModalPromoting(false)
                  }
                  setLeaveModal(null)
                  proceed()
                } else {
                  // 1-9 likes: discard draft, leave immediately
                  const proceed = leaveModal.proceed
                  setLeaveModal(null)
                  proceed()
                }
              }}
              style={{
                display: 'block', width: '100%',
                minHeight: 44,
                padding: '0 16px',
                borderRadius: 12,
                border: '1px solid var(--color-border-soft, rgba(0,0,0,0.12))',
                background: 'var(--color-surface, #F6F8FA)',
                color: 'var(--color-text-muted, #656D76)',
                fontSize: 14,
                fontWeight: 500,
                cursor: leaveModalPromoting ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
                opacity: leaveModalPromoting ? 0.6 : 1,
              }}
            >
              {leaveModalPromoting ? (
                <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                  <span style={{
                    display: 'inline-block', width: 13, height: 13, borderRadius: '50%',
                    border: '2px solid var(--color-text-dim, #8C959F)',
                    borderTopColor: 'var(--accent-1, #0969DA)',
                    animation: 'spin 0.8s linear infinite',
                  }} />
                  {t('discovery.tasteSaving')}
                </span>
              ) : (
                <>
                  {t('discovery.leaveModalLeave')}
                  <span style={{
                    display: 'block',
                    fontSize: 11,
                    fontWeight: 400,
                    color: 'var(--color-text-dim, #8C959F)',
                    marginTop: 2,
                  }}>
                    {draftLikeCount >= TASTE_NUDGE_THRESHOLD
                      ? t('discovery.leaveModalSubConverged')
                      : t('discovery.leaveModalSubDraft')}
                  </span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

    </div>
  )
}
