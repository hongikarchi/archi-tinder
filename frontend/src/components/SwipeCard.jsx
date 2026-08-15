import { useEffect, useRef, useState } from 'react'
import { useImageTelemetry } from '../hooks/useImageTelemetry.js'

/**
 * Shared swipe card — consumed by SwipePage (Taste) and DiscoveryPage (Discovery).
 *
 * Extracted from SwipePage.jsx so Discovery can render the same exact card UI
 * inside its TinderCard deck. No logic changes from the original SwipePage
 * version EXCEPT:
 *   - <img decoding="async"> (was "sync" — sync blocks render)
 *   - explicit width/height on the <img> (prevent layout thrash)
 *   - 4-second image-load timeout that triggers the covers_by_type fallback
 *     chain if the main URL hasn't fired onLoad yet (was 2s; bumped FIX F2)
 *
 * The fallback chain: covers_by_type.exterior → interior → aerial → detail →
 * drawing → gallery[0]. The ?retry=1 cache-bust step was removed (FIX F2 —
 * it doubled bandwidth without salvaging same-origin in-flight requests).
 * Telemetry behavior is unchanged.
 */

const _vw = typeof window !== 'undefined' ? window.innerWidth : 375
const _vh = typeof window !== 'undefined' ? window.innerHeight : 812
export const CARD_WIDTH  = Math.min(420, _vw - 32)
export const CARD_HEIGHT = Math.min(Math.round(CARD_WIDTH * 1.55), _vh - 220)
export const TAP_THRESHOLD = 8

// B2 — adaptive object-fit: cover ONLY when crop loss (fraction of image area
// lost cropping to the card's aspect ratio) stays within this budget. Above
// it (e.g. a square image against the ~0.65 portrait card ratio, ~35% loss)
// we keep 'contain' — letterboxing beats visible cropping.
const COVER_CROP_MAX = 0.25

/**
 * computeFit — pure helper (unit-testable inline): decide 'cover' vs 'contain'
 * for a card image given its natural aspect ratio.
 *   - Unknown ratio (image not yet loaded) -> 'contain' (current behavior,
 *     no letterbox jump).
 *   - Drawings always stay 'contain' regardless of crop loss.
 *   - Otherwise cover only if cropping to the card ratio loses <= COVER_CROP_MAX
 *     of the image area.
 */
export function computeFit(imgRatio, isDrawing) {
  if (!imgRatio || isDrawing) return 'contain'
  const rCard = CARD_WIDTH / CARD_HEIGHT
  const cropLoss = 1 - Math.min(imgRatio, rCard) / Math.max(imgRatio, rCard)
  return cropLoss <= COVER_CROP_MAX ? 'cover' : 'contain'
}

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

/* ── SwipeCard ───────────────────────────────────────────────────────────── */
export default function SwipeCard({ card, onGalleryClose }) {
  const [isExpanded,     setIsExpanded]     = useState(false)
  const [showGallery,    setShowGallery]    = useState(false)
  const [hasBeenOpened,  setHasBeenOpened]  = useState(false)
  const [imgLoaded,      setImgLoaded]      = useState(false)
  const [imgFailed,      setImgFailed]      = useState(false)
  // B2 — natural aspect ratio (naturalWidth/naturalHeight), first known from
  // whichever of {LQIP, main img} fires onLoad first. null = not yet known.
  const [imgRatio,       setImgRatio]       = useState(null)
  // B2 — did the fallback chain (advanceFallback) land the main <img> on the
  // covers_by_type.drawing URL? Drives contain+white background same as
  // isDrawingKind, for cards whose original photo cover failed to load.
  const [landedOnDrawing, setLandedOnDrawing] = useState(false)
  // FRONT-UX-14-FIX: per-gallery-image natural aspect ratio, index -> ratio.
  // Populated by each gallery <img>'s onLoad; drives the same adaptive
  // computeFit(imgRatio, isDrawing) used by the front face. Unknown (not yet
  // loaded) falls back to the pre-adaptive isDrawing?'contain':'cover' so
  // there's no layout flash while the image is still loading.
  const [galleryRatios,  setGalleryRatios]  = useState({})
  // Set of URLs already attempted as src (cache-bust retry + covers_by_type
  // fallback chain). Initialized lazily inside handleImgError on first failure.
  const imgRetried = useRef(null)
  const dragStart = useRef(null)
  const dragStartTime = useRef(null)
  const imgRef = useRef(null)
  const timeoutRef = useRef(null)
  const galleryScrollRef = useRef(null)
  // first-writer-wins guard for imgRatio (LQIP onLoad vs main img onLoad)
  const ratioSetRef = useRef(false)
  // FRONT-UX-14: mirrors showGallery for listeners that must read the CURRENT
  // open state without re-registering (the wheel listener lives for the whole
  // hasBeenOpened lifetime, spanning many open/close cycles).
  const showGalleryRef = useRef(false)

  const { onLoad: telemetryOnLoad, onError: telemetryOnError } = useImageTelemetry({
    buildingId: card.image_id,
    context: 'swipe_card',
  })

  function openGallery() {
    setHasBeenOpened(true)
    setShowGallery(true)
  }
  function closeGallery() { setShowGallery(false); onGalleryClose && onGalleryClose() }

  // Keep showGalleryRef in sync with showGallery for the wheel listener below,
  // which must read the CURRENT open state without re-registering.
  useEffect(() => {
    showGalleryRef.current = showGallery
  }, [showGallery])

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

  // Multi-step fallback chain for cold/warm + external-CDN flakiness (S2).
  // Order: covers_by_type.exterior (canonical default) -> other covers_by_type
  //        variants -> first gallery URL -> give up.
  //
  // FIX F2 (Codex retest 2026-05-26): dropped the ?retry=1 cache-bust step.
  // R2/external CDN images take 1.7-2.6s; the cache-bust was firing on normal-
  // latency loads, adding a duplicate request to the same origin that never
  // salvages the original in-flight GET. The covers_by_type chain handles real
  // failures already; retry=1 only doubled bandwidth.
  function advanceFallback(target) {
    if (!target) return false
    const cbt = card.covers_by_type || {}
    const fallbackChain = [
      cbt.exterior, cbt.interior, cbt.aerial, cbt.detail, cbt.drawing,
      ...(card.gallery || []),
    ].filter(u => u && typeof u === 'string')
    if (!(imgRetried.current instanceof Set)) {
      imgRetried.current = new Set([card.image_url])
    }
    for (const url of fallbackChain) {
      if (!imgRetried.current.has(url)) {
        imgRetried.current.add(url)
        target.srcset = ''   // a 1x-containing srcset wins over src; clear so the fallback URL loads
        // B2 — the fallback is a different photo with its own aspect ratio:
        // re-arm the ratio guard so the fallback's onLoad re-measures fit
        // (contain until it paints — safe no-letterbox-jump default).
        ratioSetRef.current = false
        setImgRatio(null)
        target.src = url
        // B2 — track whether the chain landed on the drawing cover so the
        // main img keeps contain+white background even when isDrawingKind
        // (from image_focus/image_kind) is false for this card.
        if (cbt.drawing && url === cbt.drawing) setLandedOnDrawing(true)
        return true
      }
    }
    return false
  }

  function handleImgError(e) {
    // Emit telemetry FIRST (captures original failed URL before retry mutates e.target.src)
    telemetryOnError(e)
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    if (!advanceFallback(e.target)) {
      setImgFailed(true)
    }
  }

  function handleImgLoad(e) {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    captureImgRatio(e.target)
    setImgLoaded(true)
    telemetryOnLoad(e)
  }

  // B2 — capture natural aspect ratio from whichever <img> (LQIP or main)
  // fires onLoad first. First writer wins — later calls are no-ops.
  function captureImgRatio(node) {
    if (ratioSetRef.current) return
    if (!node || !node.naturalWidth || !node.naturalHeight) return
    ratioSetRef.current = true
    setImgRatio(node.naturalWidth / node.naturalHeight)
  }

  function handleLqipLoad(e) {
    // Once the fallback chain has engaged (imgRetried initialized), the main
    // img no longer shows the LQIP's source image — its ratio is stale.
    if (imgRetried.current) return
    captureImgRatio(e.target)
  }

  // FIX F2 (Codex retest 2026-05-26): bumped timeout 2000ms → 4000ms.
  // R2 cold cache + Singapore latency regularly takes 1.7-2.6s; the old 2s
  // timer was firing prematurely on normal loads. 4s matches the observed
  // worst-case cold-CDN P99 and avoids false-positive fallback triggers.
  useEffect(() => {
    setImgLoaded(false)
    setImgFailed(false)
    setHasBeenOpened(false)
    setShowGallery(false)
    setImgRatio(null)
    setLandedOnDrawing(false)
    setGalleryRatios({})
    ratioSetRef.current = false
    imgRetried.current = null
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      const node = imgRef.current
      if (!node || imgLoaded) return
      if (!advanceFallback(node)) {
        setImgFailed(true)
      }
      timeoutRef.current = null
    }, 4000)
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [card?.image_id, card?.image_url])

  // FRONT-UX-14 FIX 3 — gallery keyboard nav. Bound only while showGallery is
  // true (added/removed per open/close cycle, cleaned up on unmount too).
  // ArrowDown scrolls one card forward, ArrowUp one card back; Escape closes
  // (previously unhandled — SwipeCard had no keydown listener at all, so this
  // also fixes the missing Escape-to-close behavior).
  // FRONT-UX-14-FIX: page-scroll keys removed per user review — ArrowLeft/Right
  // now swipe the deck even while the gallery is open (see useKeyboardSwipe
  // guardCondition in SwipePage/DiscoveryPage), so this listener only owns
  // vertical gallery nav (one card per press) + Escape.
  useEffect(() => {
    if (!showGallery) return
    const reduceMotion = typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const behavior = reduceMotion ? 'auto' : 'smooth'
    function onKeyDown(e) {
      const el = galleryScrollRef.current
      if (e.key === 'Escape') {
        e.preventDefault()
        closeGallery()
        return
      }
      if (!el) return
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        el.scrollBy({ top: CARD_HEIGHT, behavior })
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        el.scrollBy({ top: -CARD_HEIGHT, behavior })
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showGallery])

  // Native direction-lock for gallery vertical scroll.
  // Bubble order: this gallery div listener fires BEFORE the react-tinder-card
  // native touchmove on the ancestor card element. stopPropagation() in a passive
  // listener is valid (passive only forbids preventDefault). We never call
  // preventDefault so the browser still handles pan-y scroll natively.
  // Horizontal intent propagates normally → card swipe still works.
  //
  // FRONT-UX-14 FIX 4 — desktop wheel snap, integrated into this same effect
  // (same [hasBeenOpened] lifetime as the touch direction-lock, per the "don't
  // duplicate listeners" guidance). scrollSnapType+mandatory fights wheel
  // momentum (stutters); intercept wheel, accumulate deltaY, and drive an
  // explicit scrollTo of exactly one card per gesture instead. Guarded by
  // showGalleryRef (not the showGallery closure var) because this effect's
  // listeners live for the whole hasBeenOpened lifetime, spanning multiple
  // open/close cycles — a stale `showGallery` const would still preventDefault
  // wheel events while the gallery face isn't even visible.
  useEffect(() => {
    const el = galleryScrollRef.current
    if (!el) return
    let startX = 0
    let startY = 0
    let axis = null // null (undecided) | 'v' (vertical → block card) | 'h' (horizontal → allow swipe)
    const SLOP = 8  // px before axis is committed
    const onStart = (e) => {
      if (!e.touches.length) return
      const t = e.touches[0]
      startX = t.clientX
      startY = t.clientY
      axis = null
    }
    const onMove = (e) => {
      if (!e.touches.length) return
      const t = e.touches[0]
      const dx = Math.abs(t.clientX - startX)
      const dy = Math.abs(t.clientY - startY)
      if (axis === null && (dx > SLOP || dy > SLOP)) {
        axis = dy > dx ? 'v' : 'h'
      }
      // Vertical intent: stop the event reaching react-tinder-card's native
      // touchmove listener on the parent card (bubble phase). Card does NOT
      // wobble. Horizontal intent propagates → card swipe preserved.
      if (axis === 'v') e.stopPropagation()
    }
    el.addEventListener('touchstart', onStart, { passive: true })
    el.addEventListener('touchmove', onMove, { passive: true })

    // -- FIX 4: wheel snap (desktop trackpad/mouse only; touch is unaffected —
    // wheel events don't fire from touch gestures) --
    let wheelAccum = 0
    let locked = false
    let lockTimer = null
    const WHEEL_THRESHOLD = 40
    const LOCK_MS = 450
    const QUIET_MS = 140
    const onWheel = (e) => {
      if (!showGalleryRef.current) return
      e.preventDefault()
      if (locked) {
        // Momentum-aware unlock: keep the lock alive while momentum deltas
        // still arrive; release only after ~QUIET_MS of wheel silence so one
        // long trackpad flick can't advance a second card.
        clearTimeout(lockTimer)
        lockTimer = setTimeout(() => { locked = false; wheelAccum = 0 }, QUIET_MS)
        return
      }
      wheelAccum += e.deltaY
      if (Math.abs(wheelAccum) > WHEEL_THRESHOLD) {
        const total = gallery.length
        const currentIndex = Math.round(el.scrollTop / CARD_HEIGHT)
        const dir = wheelAccum > 0 ? 1 : -1
        const targetIndex = Math.max(0, Math.min(total - 1, currentIndex + dir))
        const reduceMotion = typeof window.matchMedia === 'function' &&
          window.matchMedia('(prefers-reduced-motion: reduce)').matches
        el.scrollTo({ top: targetIndex * CARD_HEIGHT, behavior: reduceMotion ? 'auto' : 'smooth' })
        locked = true
        wheelAccum = 0
        lockTimer = setTimeout(() => { locked = false }, LOCK_MS)
      }
    }
    el.addEventListener('wheel', onWheel, { passive: false })

    return () => {
      el.removeEventListener('touchstart', onStart)
      el.removeEventListener('touchmove', onMove)
      el.removeEventListener('wheel', onWheel)
      if (lockTimer) clearTimeout(lockTimer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasBeenOpened])

  const typology   = card.metadata?.axis_typology
  const architects = card.metadata?.axis_architects
  const country    = card.metadata?.axis_country
  const city       = card.metadata?.axis_city
  const year       = card.metadata?.axis_year
  const style      = card.metadata?.axis_style
  const atmosphere = card.metadata?.axis_atmosphere
  // canonical_v2 drops single-string `material`; expose first 2-3 of
  // material_visual[] as a comma-joined chip instead.
  const materialList = Array.isArray(card.metadata?.axis_material_visual)
    ? card.metadata.axis_material_visual.slice(0, 3)
    : []
  const material     = materialList.length ? materialList.join(', ') : null
  const gallery         = card.gallery || []
  const drawingStart    = card.gallery_drawing_start ?? gallery.length
  // B1-2 fix: image_focus/image_kind now actually passed through by
  // normalizeCard. B2-4: OR in landedOnDrawing — the fallback chain may have
  // moved the main <img> onto covers_by_type.drawing even when the card's own
  // focus/kind fields say otherwise.
  const isDrawingKind = card.image_focus === 'drawing' || card.image_kind === 'drawing' || landedOnDrawing
  // B2-3: adaptive object-fit — cover only when crop loss is small and it's not a drawing.
  const imgFit = computeFit(imgRatio, isDrawingKind)

  return (
    <div
      style={{
        position: 'absolute', top: 0, left: 0,
        width: CARD_WIDTH, height: CARD_HEIGHT,
        cursor: 'grab',
        userSelect: 'none', WebkitUserSelect: 'none', touchAction: 'pan-y',
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
              <div className="skeleton-shimmer" style={{ position: 'absolute', inset: 0, background: isDrawingKind ? '#fff' : '#111' }} />
              {/* B1 — LQIP blur-up placeholder: paints fast (20px thumb), also
                  supplies the natural aspect ratio (B2) before the main image
                  loads. Hidden once the main image finishes loading. No
                  scale(1.1) edge-bleed hack — cover crops the blur naturally,
                  contain letterboxes as-is. */}
              {card.lqip_url && (
                <img
                  src={card.lqip_url}
                  aria-hidden="true"
                  alt=""
                  draggable={false}
                  onLoad={handleLqipLoad}
                  style={{
                    position: 'absolute', inset: 0,
                    width: '100%', height: '100%',
                    objectFit: imgFit, objectPosition: 'center',
                    filter: 'blur(16px)',
                    opacity: imgLoaded ? 0 : 1,
                    transition: 'opacity 0.2s ease',
                    pointerEvents: 'none',
                  }}
                />
              )}
              <img
                ref={imgRef}
                src={card.image_url}
                srcSet={card.image_srcset || undefined}
                alt={card.image_title}
                width={CARD_WIDTH}
                height={CARD_HEIGHT}
                fetchpriority="high"
                decoding="async"
                draggable={false}
                onLoad={handleImgLoad}
                onError={handleImgError}
                style={{
                  position: 'absolute', inset: 0,
                  width: '100%', height: '100%',
                  objectFit: imgFit, objectPosition: 'center',
                  background: isDrawingKind ? '#fff' : '#111',
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

          {/* Detail content — transparent, slides over expanded gradient.
              Height 72% gives breathing room for 2-line H2 + architects +
              7-row InfoRow grid + gallery button. flexShrink:0 on critical
              elements means only the grid compresses when content overflows;
              H2 / architects / divider / button always keep their natural
              height. */}
          <div style={{
            position: 'absolute', left: 0, right: 0, bottom: 0,
            height: '72%',
            background: 'transparent',
            transform: isExpanded ? 'translateY(0)' : 'translateY(100%)',
            transition: 'transform 0.42s cubic-bezier(0.32, 0, 0.18, 1)',
            display: 'flex', flexDirection: 'column',
            padding: '16px 18px 20px', gap: 0, overflow: 'hidden',
          }}>
            <h2 style={{
              color: '#fff', fontSize: 18, fontWeight: 700, lineHeight: 1.3,
              margin: '0 0 3px', flexShrink: 0,
              overflow: 'hidden', textOverflow: 'ellipsis',
              display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
            }}>
              {card.image_title}
            </h2>
            {architects && (
              <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: 12, margin: '0 0 12px', fontStyle: 'italic', flexShrink: 0 }}>
                {architects}
              </p>
            )}
            <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12, flexShrink: 0 }} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px', flex: '0 1 auto', minHeight: 0 }}>
              <InfoRow label="Type"     value={typology} />
              <InfoRow label="Country"  value={country} />
              <InfoRow label="City"     value={city} />
              <InfoRow label="Year"     value={year} />
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
                  flexShrink: 0,
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

        {/* ── GALLERY FACE ── lazy-mounted on first gallery open, stays mounted after */}
        {hasBeenOpened && <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          transform: 'rotateY(180deg)',
          borderRadius: 20, overflow: 'hidden',
          boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
          background: '#000',
        }}>
          {/* Vertical scroll of full-width images */}
          <div
            ref={galleryScrollRef}
            className="pressable"
            style={{
              position: 'absolute', inset: 0,
              overflowY: 'auto', overflowX: 'hidden',
              scrollSnapType: 'y mandatory',
              overscrollBehaviorY: 'contain',
              scrollbarWidth: 'none',
              touchAction: 'pan-y',
            }}
          >
            {gallery.map((url, i) => {
              const isDrawing = i >= drawingStart
              const knownRatio = galleryRatios[i] ?? null
              // FRONT-UX-14-FIX: adaptive fit via the same computeFit(ratio, isDrawing)
              // used by the front face — 'cover' (fill-bleed, no letterbox) when the
              // image ratio is close to the card ratio, 'contain' (ratio-preserving,
              // letterboxed) when it's far off. Before the ratio is known, fall back
              // to the pre-adaptive isDrawing?'contain':'cover' to avoid a layout flash.
              const galleryFit = knownRatio != null
                ? computeFit(knownRatio, isDrawing)
                : (isDrawing ? 'contain' : 'cover')
              // Background: drawings always keep white (matches the split above).
              // Photos that resolve to 'cover' show no bars at all (background is
              // fully covered, color is moot). Photos that resolve to 'contain' use
              // dark #111 so the letterbox bars match the photo-viewer look.
              const galleryBg = isDrawing ? '#fff' : '#111'
              return (
                <div key={i} className="pressable" style={{
                  width: '100%', height: CARD_HEIGHT,
                  flexShrink: 0,
                  scrollSnapAlign: 'start',
                  scrollSnapStop: 'always',
                  background: galleryBg,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <img
                    src={url}
                    srcSet={card.gallery_srcset?.[i] || undefined}
                    alt=""
                    className="pressable"
                    loading={i === 0 ? 'eager' : 'lazy'}
                    decoding="async"
                    draggable={false}
                    onLoad={e => {
                      const node = e.target
                      if (!node.naturalWidth || !node.naturalHeight) return
                      const ratio = node.naturalWidth / node.naturalHeight
                      setGalleryRatios(prev => (prev[i] != null ? prev : { ...prev, [i]: ratio }))
                    }}
                    onError={e => { e.currentTarget.style.visibility = 'hidden' }}
                    style={{
                      width: '100%',
                      height: '100%',
                      // FRONT-UX-14-FIX (B2-5 successor): adaptive cover/contain —
                      // see computeFit() usage above.
                      objectFit: galleryFit,
                      objectPosition: 'center',
                      display: 'block',
                    }}
                  />
                </div>
              )
            })}
          </div>

          {/* Close button */}
          <button
            onPointerDown={e => e.stopPropagation()}
            onPointerUp={e => e.stopPropagation()}
            onClick={e => { e.stopPropagation(); closeGallery() }}
            style={{
              position: 'absolute', top: 14, right: 14,
              width: 32, height: 32, borderRadius: '50%',
              background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(255,255,255,0.2)',
              color: '#fff', fontSize: 16, lineHeight: 1,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            ✕
          </button>

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
        </div>}

      </div>
    </div>
  )
}
