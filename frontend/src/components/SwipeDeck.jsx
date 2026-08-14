import { useEffect, useState } from 'react'
import { CARD_WIDTH, CARD_HEIGHT, computeFit } from './SwipeCard.jsx'

export default function SwipeDeck({ children, nextCard = null, active = false }) {
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
            transform: 'scale(0.90) translateY(20px)',
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
            transform: 'scale(0.95) translateY(10px)',
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
