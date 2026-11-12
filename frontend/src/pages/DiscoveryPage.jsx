import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchDiscoveryFeed, discoveryFeedback, promoteToTaste, VerifyRequiredError } from '../api/client.js'
import { reportWriteError } from '../utils/reportWriteError.js'
import SwipeCard from '../components/SwipeCard.jsx'
import { useCardSize } from '../hooks/useCardSize.js'
import DiscoveryTriggerCard from '../components/DiscoveryTriggerCard.jsx'
import DiscoveryCapCard from '../components/DiscoveryCapCard.jsx'
import TutorialPopup from '../components/TutorialPopup.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'
import CardSkeleton from '../components/CardSkeleton.jsx'
import SwipeDeck from '../components/SwipeDeck.jsx'
import { SWIPE_PREVENT_ALL } from '../components/swipeGestureConfig.js'
import { discoveryNavigationGuard } from '../utils/discoveryGuard.js'
import { useSwipeOrchestration } from '../hooks/useSwipeOrchestration.js'
import { useCardLeanSource } from '../hooks/useCardLean.js'
import { useKeyboardSwipe } from '../hooks/useKeyboardSwipe.js'
import { useTranslation } from '../i18n/index.js'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import LeaveDiscoveryModal from '../components/LeaveDiscoveryModal.jsx'
import FinishReportButton from '../components/FinishReportButton.jsx'
import DiscoveryPromoteOverlay from '../components/DiscoveryPromoteOverlay.jsx'
import { describePromoteError, promoteErrorText } from '../components/promoteError.js'
import overlayStyles from '../components/DiscoveryPromoteOverlay.module.css'
import { createDraftFeedbackQueue } from '../utils/draftFeedbackQueue.js'

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

// Blocking promote (trigger-card right swipe): POST timeout and max wait for the
// first Taste card image before navigating to /swipe.
const PROMOTE_TIMEOUT_MS = 30000
const FIRST_CARD_IMAGE_MAX_WAIT_MS = 3000

// Resolves when the card's image is decoded/loaded, or after maxMs. Never rejects.
function waitForCardImage(card, maxMs) {
  const url = card?.image_url
  if (!url) return Promise.resolve()
  const ready = new Promise(resolve => {
    try {
      const img = new Image()
      if (card.image_srcset) img.srcset = card.image_srcset
      img.src = url
      if (typeof img.decode === 'function') {
        img.decode().then(resolve, resolve)
      } else {
        img.onload = img.onerror = () => resolve()
      }
    } catch {
      resolve()
    }
  })
  let timer
  const timeout = new Promise(resolve => { timer = setTimeout(resolve, maxMs) })
  return Promise.race([ready, timeout]).finally(() => clearTimeout(timer))
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

export default function DiscoveryPage({ showToast, onLogout }) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { width: CARD_WIDTH, height: CARD_HEIGHT } = useCardSize()
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
  // Blocking overlay for the trigger-card right-swipe promote: 'idle' | 'loading' | 'error'.
  // The ref mirrors it synchronously for the navigation-guard closure.
  const [promoteBlock, setPromoteBlockState] = useState('idle')
  const promoteBlockRef = useRef('idle')
  const [promoteErrorInfo, setPromoteErrorInfo] = useState(null)
  // False once the page is unmounted (browser back etc. during the blocking
  // promote): the in-flight handler must not navigate to /swipe afterwards.
  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])
  function setPromoteBlock(v) {
    promoteBlockRef.current = v
    setPromoteBlockState(v)
  }
  const promoteBlocking = promoteBlock !== 'idle'
  // Drag lean of the trigger / cap card (external store: no re-render mid-drag).
  const triggerLean = useCardLeanSource()
  const resetTriggerLean = triggerLean.reset
  const [capReached, setCapReached] = useState(false)
  // capReached: the trigger card and the 50-cap card share this store; a left swipe on
  // the trigger card leaves 'left' behind, so clear it when the cap card appears.
  // (Declared AFTER the capReached state: the deps array is read during render.)
  useEffect(() => { resetTriggerLean() }, [promoteBlocking, capReached, resetTriggerLean])
  // Bumped to remount the 50-cap card's gesture frame at rest after it was
  // swiped away but the user stayed (leave modal dismissed / overlay back).
  const [capCardKey, setCapCardKey] = useState(0)
  function restoreCapCard() {
    resetTriggerLean()
    setCapCardKey(k => k + 1)
  }
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
  // Ref-held queue mirrors draftId synchronously and serializes feedback while
  // no draft id is known (prevents duplicate draft boards on rapid swipes).
  const draftQueueRef = useRef(null)
  if (!draftQueueRef.current) {
    draftQueueRef.current = createDraftFeedbackQueue(draftId)
  }
  function applyDraftId(id) {
    draftQueueRef.current.setDraftId(id)
    setDraftId(id)
  }
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
      // Promote call in flight: swallow the attempt (no modal, no proceed) so a
      // tab/logout click does nothing and a second promote can never start.
      if (promoteBlockRef.current === 'loading') return
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
      // -- 50-cap card (no deck behind it; the deck is not advanced) --
      if (capReached) {
        if (action === 'like') {
          // RIGHT swipe → promote to Taste (blocking overlay flow)
          handlePromoteToTaste({ blockUi: true })
        } else {
          // LEFT swipe → Profile tab, through the Discovery leave guard
          handleCapGoProfile()
        }
        return
      }

      const card = topCard
      advance()

      // -- Trigger card handling --
      if (isTriggerCard(card)) {
        if (action === 'like') {
          // RIGHT swipe → promote to Taste (기존 동작 유지)
          handlePromoteToTaste({ blockUi: true })
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
        draftQueueRef.current.send(id => discoveryFeedback(bldId, 'like', id))
          .then(res => {
            if (res.draftId) applyDraftId(res.draftId)
            // Reconcile with authoritative backend count (dedup/cap may adjust).
            setDraftLikeCount(res.draftLikeCount)
            if (res.likeCapReached) setCapReached(true)
          })
          .catch((err) => { if (!(err instanceof VerifyRequiredError)) reportWriteError(showToast, t('discovery.toastLikeFailed')) })
      } else {
        // Pass: server records it for dislike zone; failure is low-stakes but
        // we still surface it consistently per FRONT-UX silent-failure policy.
        draftQueueRef.current.send(id => discoveryFeedback(bldId, 'pass', id))
          .then(res => {
            if (res.draftId) applyDraftId(res.draftId)
          })
          .catch((err) => { if (!(err instanceof VerifyRequiredError)) reportWriteError(showToast, t('discovery.toastPassFailed')) })
      }
    },
  })

  useKeyboardSwipe({
    onSwipe: async (dir) => { await cardRef.current?.swipe(dir) },
    guardCondition: () => !!(
      !cardRef.current || (!capReached && !deck.length) || showTutorial || promoteBlocking ||
      (capReached && leaveModal)
    ),
  })

  // FRONT-FLOW-1: tutorial dismiss — removing 'archithon_show_tutorial' (set only
  // on register success, LoginPage) IS the complete "already seen" record.
  function handleTutorialClose() {
    localStorage.removeItem('archithon_show_tutorial')
    setShowTutorial(false)
  }

  // -- Promote to Taste (triggered by right-swipe on trigger card) --
  // opts.blockUi (trigger-card right swipe only): blocking overlay, error panel
  // instead of a toast, and wait (<=3s) for the first Taste card image before
  // navigating. Other callers (persistent CTA, 50-card button) are unchanged.
  async function handlePromoteToTaste(opts) {
    const blockUi = opts?.blockUi === true
    if (promoteLoading) return
    setPromoteLoading(true)
    if (blockUi) { setPromoteErrorInfo(null); setPromoteBlock('loading') }
    try {
      const result = await (blockUi
        ? promoteToTaste(draftQueueRef.current.getDraftId(), { timeoutMs: PROMOTE_TIMEOUT_MS })
        : promoteToTaste(draftQueueRef.current.getDraftId()))
      // Clear draft session state — a future Discovery visit starts fresh
      applyDraftId(null)
      setDraftLikeCount(0)
      setContinueAfterTrigger(false)
      triggerShownRef.current = false
      sessionStorage.removeItem(DRAFT_ID_KEY)
      sessionStorage.removeItem(DRAFT_LIKES_KEY)
      sessionStorage.removeItem(CONTINUE_AFTER_TRIGGER_KEY)
      if (blockUi) {
        // Persist the session in App without navigating, then hold the overlay
        // until the first Taste card image is ready (max 3s), then go.
        window.dispatchEvent(new CustomEvent('archithon:promote-to-taste', {
          detail: { ...result, skipNav: true },
        }))
        await waitForCardImage(result?.next_image, FIRST_CARD_IMAGE_MAX_WAIT_MS)
        // User left /discovery while we waited: the session is already persisted
        // via the event above, so just skip the redirect.
        if (!mountedRef.current) return
        navigate('/swipe')
        return
      }
      // Hand off the session payload to App.jsx via custom event.
      window.dispatchEvent(new CustomEvent('archithon:promote-to-taste', { detail: result }))
      navigate('/swipe')
    } catch (err) {
      if (err?.status === 400 && err?.data?.detail === 'not_enough_likes') {
        // Phantom trigger from a stale count — clear it so the user isn't stuck.
        setDeck(prev => prev.filter(c => !isTriggerCard(c)))
        triggerShownRef.current = false
        setDraftLikeCount(0)
        setCapReached(false)
        reportWriteError(showToast, t('discovery.toastNotEnoughLikes'))
        if (blockUi) setPromoteBlock('idle')
      } else {
        const info = describePromoteError(err)
        console.warn('[promote-to-taste] failed', {
          status: err?.status, detail: err?.data?.detail, name: err?.name, reason: info.reason,
        })
        if (blockUi) {
          // Overlay shows the failure reason + retry / back buttons (no toast).
          setPromoteErrorInfo(info)
          setPromoteBlock('error')
        } else {
          reportWriteError(showToast, promoteErrorText(t, info))
        }
      }
    } finally {
      setPromoteLoading(false)
    }
  }

  // 50-cap card, LEFT swipe: same as tapping the Profile tab in TabBar
  // (own profile + profileRefresh state), through the Discovery leave guard so
  // the leave-warning modal shows first. The guard is registered by this page.
  function handleCapGoProfile() {
    const path = '/user/me'
    const go = () => navigate(path, { state: { profileRefresh: Date.now() } })
    if (discoveryNavigationGuard.check) discoveryNavigationGuard.check(path, go)
    else go()
  }

  // Leave modal dismissed via "stay": bring the swiped-away cap card back.
  function handleLeaveModalStay() {
    setLeaveModal(null)
    if (capReached && !leaveModalPromoting) restoreCapCard()
  }

  // Error panel: dismiss the overlay and fall back to the persistent
  // "save taste & move" CTA (same state the left swipe on the trigger card sets).
  function handleBackToDiscovery() {
    setPromoteBlock('idle')
    if (capReached) restoreCapCard()
    setContinueAfterTrigger(true)
    try { sessionStorage.setItem(CONTINUE_AFTER_TRIGGER_KEY, '1') } catch { /* ignore */ }
  }

  function handleRetry() {
    sessionStorage.removeItem(DECK_CACHE_KEY)
    setDeck([])
    setError('')
    fetchPage([], true)
  }

  // ── Render ─────────────────────────────────────────────────────────────── //

  // Persistent bottom CTA is hidden on the 50-card screen (the cap card offers Taste itself).
  const showFinishCta = continueAfterTrigger && !capReached

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'space-between',
      height: 'var(--page-height)',
      overflow: 'hidden',
      background: 'var(--color-bg)',
      // + 52px once the fixed bottom CTA shows (44px + 8px gap)
      padding: `20px 16px calc(var(--tabbar-clearance) + ${showFinishCta ? 52 : 0}px)`,
    }}>

      <PageTopControls onLogout={onLogout} />

      <TutorialPopup visible={showTutorial} onClose={handleTutorialClose} />

      {/* Header — Arch|ibe logo (DESIGN.md-mock parity, canvas-design-port.md §6d item 1) */}
      <div style={{ textAlign: 'center', width: '100%' }}>
        <PageLogoHeader padding={0} marginBottom={8} />

      </div>

      {/* Persistent "save taste and go to Taste" CTA — shown after the user
          left-swiped the trigger card. Same fixed pill as the Taste swipe page's
          finish button (sits above the TabBar); the page's bottom padding
          reserves 52px so it never covers the card. */}
      {showFinishCta && (
        <FinishReportButton
          onClick={handlePromoteToTaste}
          disabled={promoteLoading}
          loading={promoteLoading}
          label={t('discovery.saveTasteAndMove')}
          loadingLabel={t('discovery.tasteAnalyzing')}
        />
      )}

      {/* Card stack */}
      <div
        className={promoteBlocking ? overlayStyles.blurStack : undefined}
        style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative', margin: 'auto 0' }}
      >
        {capReached ? (
          <SwipeDeck active>
            <div
              style={{ position: 'absolute', inset: 0, zIndex: 5, pointerEvents: 'auto' }}
            >
              <SwipeGestureFrame
                key={capCardKey}
                ref={cardRef}
                onSwipe={onTinderSwipe}
                onCardLeftScreen={onCardLeftScreen}
                preventSwipe={promoteBlocking ? SWIPE_PREVENT_ALL : undefined}
                onSwipeRequirementFulfilled={triggerLean.onFulfilled}
                onSwipeRequirementUnfulfilled={triggerLean.onUnfulfilled}
              >
                <DiscoveryCapCard leanStore={triggerLean.store} />
              </SwipeGestureFrame>
            </div>
          </SwipeDeck>
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
                      preventSwipe={(isTop && !promoteBlocking) ? undefined : SWIPE_PREVENT_ALL}
                      className={isShaking ? 'discovery-shake' : undefined}
                      onSwipeRequirementFulfilled={isTop && isTrigger ? triggerLean.onFulfilled : undefined}
                      onSwipeRequirementUnfulfilled={isTop && isTrigger ? triggerLean.onUnfulfilled : undefined}
                    >
                      {isTrigger ? (
                        <DiscoveryTriggerCard leanStore={isTop ? triggerLean.store : undefined} />
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

        {/* Blocking promote overlay — above the SwipeDeck (zIndex 5/4), captures all input */}
        {promoteBlocking && (
          <DiscoveryPromoteOverlay
            phase={promoteBlock}
            errorInfo={promoteErrorInfo}
            onRetry={() => handlePromoteToTaste({ blockUi: true })}
            onBack={handleBackToDiscovery}
          />
        )}
      </div>

      {/* Leave-warning modal (DISCOVERY-PERF-3) — shown when user tries to navigate
          away or log out while draftLikeCount >= 1. Presentation lives in
          LeaveDiscoveryModal (shared Modal underneath); the stay / leave logic stays here.
            leave, >=10 likes: auto-promote then navigate to the intended destination.
              Dispatches the custom event with skipNav:true so App.jsx persists
              the session without forcing navigate('/swipe').
            leave, 1-9 likes: no promotion; proceed immediately. The draft board is NOT
              deleted — it was created server-side on the first feedback and stays
              on the profile as a normal board. */}
      {leaveModal && (
        <LeaveDiscoveryModal
          likeCount={draftLikeCount}
          converged={draftLikeCount >= TASTE_NUDGE_THRESHOLD}
          promoting={leaveModalPromoting}
          onStay={handleLeaveModalStay}
          onLeave={async () => {
            if (draftLikeCount >= TASTE_NUDGE_THRESHOLD) {
              // Auto-promote path: persist the Taste session, then go where the
              // user was originally headed (not forced to /swipe).
              const proceed = leaveModal.proceed
              setLeaveModalPromoting(true)
              try {
                const result = await promoteToTaste(draftQueueRef.current.getDraftId())
                // Clear draft sessionStorage — same cleanup as handlePromoteToTaste
                applyDraftId(null)
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
              // 1-9 likes: skip promotion and leave immediately (draft board is kept)
              const proceed = leaveModal.proceed
              setLeaveModal(null)
              proceed()
            }
          }}
        />
      )}

    </div>
  )
}
