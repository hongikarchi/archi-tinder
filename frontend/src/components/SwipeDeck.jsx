import { useEffect, useState } from 'react'
import { CARD_WIDTH, CARD_HEIGHT, computeFit } from './SwipeCard.jsx'

// FRONT-UX-14-TUNE3 — module-scope reduced-motion check (mirrors
// SwipeCard.jsx's animateGallerySnap guard). Read once; `prefers-reduced-motion`
// changing mid-session without a reload is an edge case we don't chase here.
const PREFERS_REDUCED_MOTION = typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

export default function SwipeDeck({ children, nextCard = null, active = false, promoting = false }) {
  // B2 peek-layer parity — track the peek image's natural ratio so its
  // objectFit matches SwipeCard's adaptive cover/contain (computeFit) instead
  // of a hardcoded 'contain'. Prevents a contain->cover pop when the peek
  // card promotes to active. Reset whenever the peek image changes.
  const [peekRatio, setPeekRatio] = useState(null)

  useEffect(() => {
    setPeekRatio(null)
  }, [nextCard?.image_url])

  function handlePeekLoad(e) {
    const node = e.target
    if (node.naturalWidth && node.naturalHeight) {
      setPeekRatio(node.naturalWidth / node.naturalHeight)
    }
  }

  const isDrawing = nextCard?.image_focus === 'drawing' || nextCard?.image_kind === 'drawing'
  const peekFit = computeFit(peekRatio, isDrawing)

  // FRONT-UX-14-TUNE3 — progressive stack promotion. While `promoting` is
  // true (the top card has committed to exit and is flying out), the peek
  // layers step forward toward the active-card resting transform so the
  // depth change reads as one continuous motion instead of a post-exit pop.
  // The transition is gated to ONLY apply while promoting — when the top
  // card finally leaves the screen and the deck advances, `promoting` flips
  // back to false and a FRESH peek card is now behind the (new) active card;
  // that reset to the resting 0.95/0.90 transform must snap instantly (no
  // reverse-animate), so transition is 'none' outside the promoting window.
  const promoteTransition = (!PREFERS_REDUCED_MOTION && promoting)
    ? 'transform 520ms var(--motion-ease)'
    : 'none'
  const layer2Transform = promoting ? 'scale(1) translateY(0px)' : 'scale(0.95) translateY(10px)'
  const layer1Transform = promoting ? 'scale(0.95) translateY(10px)' : 'scale(0.90) translateY(20px)'

  return (
    <div style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}>
      {active && (
        <>
          {/* Layer 1 — deepest dummy card */}
          <div aria-hidden="true" style={{
            position: 'absolute', inset: 0,
            borderRadius: 20,
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border-soft)',
            transform: layer1Transform,
            transition: promoteTransition,
            transformOrigin: 'bottom center',
            zIndex: 1,
            pointerEvents: 'none',
          }} />
          {/* Layer 2 — next card */}
          <div aria-hidden="true" style={{
            position: 'absolute', inset: 0,
            borderRadius: 20, overflow: 'hidden',
            background: 'var(--color-surface-2)',
            border: '1px solid var(--color-border-soft)',
            transform: layer2Transform,
            transition: promoteTransition,
            transformOrigin: 'bottom center',
            zIndex: 2,
            pointerEvents: 'none',
          }}>
            {nextCard?.image_url && (
              <img
                src={nextCard.image_url}
                alt=""
                draggable={false}
                onLoad={handlePeekLoad}
                style={{
                  width: '100%', height: '100%',
                  objectFit: peekFit, objectPosition: 'center',
                  background: isDrawing ? '#fff' : '#111',
                  display: 'block',
                }}
              />
            )}
          </div>
        </>
      )}
      {/* Layer 3 — active card */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 3 }}>
        {children}
      </div>
    </div>
  )
}
