import { useEffect, useRef, useState } from 'react'
import { computeFit, preloadImg } from './SwipeCard.jsx'
import { isTypingTarget } from '../utils/tasteStart.js'
import { useImageTelemetry } from '../hooks/useImageTelemetry.js'
import fb from './TasteFeedback.module.css'

/**
 * Gallery face of a taste-start card — mirrors SwipeCard's gallery face (one
 * photo per card-height slot, y-mandatory snap owned imperatively, adaptive
 * cover/contain via computeFit, rAF glide on ArrowUp/Down, Escape closes).
 * Rendered inside the flip wrapper of TasteCardStack; the stack handles the
 * "tap closes gallery" gesture.
 */

const CARD_RATIO = 280 / 380
const GLIDE_DURATION_MS = 450
function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

function GalleryImage({ card, index, ratio, onRatio, isDrawing }) {
  const { onLoad, onError } = useImageTelemetry({
    buildingId: card.image_id,
    context: 'taste_start_gallery',
  })
  const fit = ratio != null
    ? computeFit(ratio, isDrawing, CARD_RATIO)
    : (isDrawing ? 'contain' : 'cover')
  return (
    <div style={{
      width: '100%', height: '100%', flexShrink: 0, scrollSnapAlign: 'start',
      background: isDrawing ? '#fff' : '#111',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <img
        src={card.gallery[index]}
        srcSet={card.gallery_srcset?.[index] || undefined}
        alt=""
        loading={index <= 1 ? 'eager' : 'lazy'}
        decoding="async"
        draggable={false}
        onLoad={e => {
          const node = e.target
          if (node.naturalWidth && node.naturalHeight) onRatio(index, node.naturalWidth / node.naturalHeight)
          onLoad(e)
        }}
        onError={e => { e.currentTarget.style.visibility = 'hidden'; onError(e) }}
        style={{ width: '100%', height: '100%', objectFit: fit, objectPosition: 'center', display: 'block' }}
      />
    </div>
  )
}

export default function TasteCardGallery({ card, active, onClose, closeLabel }) {
  const scrollRef = useRef(null)
  const [ratios, setRatios] = useState({})
  const snapRestoreRef = useRef(null)
  const targetRef = useRef(null)
  const rafRef = useRef(null)
  const gallery = card.gallery || []
  const drawingStart = card.gallery_drawing_start ?? gallery.length

  // Snap is owned imperatively so React re-renders never resurrect it mid-glide.
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.style.scrollSnapType = 'y mandatory'
  }, [])

  // Keyboard: ArrowUp/Down glide one slot, Escape closes. Bound only while open.
  useEffect(() => {
    if (!active) return undefined
    function cancelGlide(restoreSnap) {
      if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
      if (restoreSnap && snapRestoreRef.current != null) {
        const el = scrollRef.current
        if (el) el.style.scrollSnapType = snapRestoreRef.current
        snapRestoreRef.current = null
      }
      if (restoreSnap) targetRef.current = null
    }
    function animateScroll(el, targetTop) {
      if (targetRef.current == null && el.scrollTop === targetTop) return
      cancelGlide(false)
      if (snapRestoreRef.current == null) {
        snapRestoreRef.current = el.style.scrollSnapType || 'y mandatory'
        el.style.scrollSnapType = 'none'
      }
      targetRef.current = targetTop
      const startTop = el.scrollTop
      const delta = targetTop - startTop
      let startTime = null
      function step(now) {
        if (startTime == null) startTime = now
        const t = Math.min(1, (now - startTime) / GLIDE_DURATION_MS)
        el.scrollTop = startTop + delta * easeInOutCubic(t)
        if (t < 1) rafRef.current = requestAnimationFrame(step)
        else { el.scrollTop = targetTop; cancelGlide(true) }
      }
      rafRef.current = requestAnimationFrame(step)
    }
    function onKeyDown(e) {
      if (isTypingTarget(document.activeElement)) return
      if (e.key === 'Escape') { e.preventDefault(); onClose(); return }
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
      const el = scrollRef.current
      if (!el) return
      e.preventDefault()
      const h = el.clientHeight || 1
      const maxScroll = Math.max(0, el.scrollHeight - el.clientHeight)
      const base = targetRef.current ?? el.scrollTop
      const idx = Math.round(base / h) + (e.key === 'ArrowDown' ? 1 : -1)
      animateScroll(el, Math.min(Math.max(idx * h, 0), maxScroll))
      const srcset = card.gallery_srcset || []
      preloadImg(gallery[idx + 1], srcset[idx + 1])
      preloadImg(gallery[idx - 1], srcset[idx - 1])
    }
    window.addEventListener('keydown', onKeyDown)
    return () => { window.removeEventListener('keydown', onKeyDown); cancelGlide(true) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active])

  function onRatio(i, r) {
    setRatios(prev => (prev[i] != null ? prev : { ...prev, [i]: r }))
  }

  return (
    <>
      <div
        ref={scrollRef}
        className={fb.galScroll}
        style={{
          position: 'absolute', inset: 0, overflowY: 'auto', overflowX: 'hidden',
          overscrollBehaviorY: 'contain', touchAction: 'pan-y',
        }}
      >
        {gallery.map((_, i) => (
          <GalleryImage
            key={i} card={card} index={i} ratio={ratios[i] ?? null}
            onRatio={onRatio} isDrawing={i >= drawingStart}
          />
        ))}
      </div>
      <button type="button" className={fb.galClose} data-nodrag="" aria-label={closeLabel} onClick={onClose}>✕</button>
      <div style={{ position: 'absolute', top: 14, left: 0, right: 0, display: 'flex', justifyContent: 'center', pointerEvents: 'none' }}>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="18 15 12 9 6 15" />
        </svg>
      </div>
      <div style={{ position: 'absolute', bottom: 14, left: 0, right: 0, display: 'flex', justifyContent: 'center', pointerEvents: 'none' }}>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
    </>
  )
}
