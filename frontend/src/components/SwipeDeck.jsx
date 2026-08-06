import { CARD_WIDTH, CARD_HEIGHT } from './SwipeCard.jsx'

export default function SwipeDeck({ children, nextCard = null }) {
  return (
    <div style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}>
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
            style={{ width: '100%', height: '100%', objectFit: 'contain', objectPosition: 'center', display: 'block' }}
          />
        )}
      </div>
      {/* Layer 3 — active card */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 3 }}>
        {children}
      </div>
    </div>
  )
}
