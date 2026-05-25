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
 *   - 2-second image-load timeout that triggers the covers_by_type fallback
 *     chain if the main URL hasn't fired onLoad yet
 *
 * The fallback chain itself is unchanged: cache-bust → covers_by_type.exterior
 * → interior → aerial → detail → drawing → gallery[0]. Telemetry behavior is
 * unchanged.
 */

const _vw = typeof window !== 'undefined' ? window.innerWidth : 375
const _vh = typeof window !== 'undefined' ? window.innerHeight : 812
export const CARD_WIDTH  = Math.min(420, _vw - 32)
export const CARD_HEIGHT = Math.min(Math.round(CARD_WIDTH * 1.55), _vh - 220)
export const TAP_THRESHOLD = 8

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
export default function SwipeCard({ card, onGalleryOpen, onGalleryClose }) {
  const [isExpanded,     setIsExpanded]     = useState(false)
  const [showGallery,    setShowGallery]    = useState(false)
  const [hasBeenOpened,  setHasBeenOpened]  = useState(false)
  const [imgLoaded,      setImgLoaded]      = useState(false)
  const [imgFailed,      setImgFailed]      = useState(false)
  // Set of URLs already attempted as src (cache-bust retry + covers_by_type
  // fallback chain). Initialized lazily inside handleImgError on first failure.
  const imgRetried = useRef(null)
  const dragStart = useRef(null)
  const dragStartTime = useRef(null)
  const imgRef = useRef(null)
  const timeoutRef = useRef(null)

  const { onLoad: telemetryOnLoad, onError: telemetryOnError } = useImageTelemetry({
    buildingId: card.image_id,
    context: 'swipe_card',
  })

  function openGallery()  { setHasBeenOpened(true); setShowGallery(true);  onGalleryOpen && onGalleryOpen()  }
  function closeGallery() { setShowGallery(false); onGalleryClose && onGalleryClose() }

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
  // Order: cache-bust retry -> covers_by_type.exterior (canonical default) ->
  //        any other covers_by_type variant -> first gallery URL -> give up.
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
    if (!imgRetried.current.has(card.image_url + '?retry=1')) {
      imgRetried.current.add(card.image_url + '?retry=1')
      const sep = (card.image_url || '').includes('?') ? '&' : '?'
      target.src = (card.image_url || '') + sep + 'retry=1'
      return true
    }
    for (const url of fallbackChain) {
      if (!imgRetried.current.has(url)) {
        imgRetried.current.add(url)
        target.src = url
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
    setImgLoaded(true)
    telemetryOnLoad(e)
  }

  // 2-second load timeout — if the main URL hasn't fired onLoad, advance to
  // the covers_by_type fallback chain. Cleared on onLoad / onError / unmount.
  useEffect(() => {
    setImgLoaded(false)
    setImgFailed(false)
    setHasBeenOpened(false)
    setShowGallery(false)
    imgRetried.current = null
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      const node = imgRef.current
      if (!node || imgLoaded) return
      if (!advanceFallback(node)) {
        setImgFailed(true)
      }
      timeoutRef.current = null
    }, 2000)
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [card?.image_id, card?.image_url])

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
  const isDrawingKind = card.image_focus === 'drawing' || card.image_kind === 'drawing'

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
              <div className="skeleton-shimmer" style={{ position: 'absolute', inset: 0, background: isDrawingKind ? '#fff' : '#111' }} />
              <img
                ref={imgRef}
                src={card.image_url}
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
                  objectFit: 'contain', objectPosition: 'center',
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
            {gallery.map((url, i) => {
              const isDrawing = i >= drawingStart
              return (
                <div key={i} style={{
                  width: '100%', height: CARD_HEIGHT,
                  flexShrink: 0,
                  scrollSnapAlign: 'start',
                  scrollSnapStop: 'always',
                  background: isDrawing ? '#fff' : '#111',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <img
                    src={url}
                    alt=""
                    loading={i === 0 ? 'eager' : 'lazy'}
                    decoding="async"
                    draggable={false}
                    onError={e => { e.currentTarget.style.visibility = 'hidden' }}
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'contain',
                      objectPosition: 'center',
                      display: 'block',
                    }}
                  />
                </div>
              )
            })}
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
        </div>}

      </div>
    </div>
  )
}
