import { CARD_WIDTH, CARD_HEIGHT } from './SwipeCard.jsx'

// FRONT-UX-14-SIMPLIFY — SwipeDeck is now a pure decoration shell: two static
// dummy cards (never animate, never receive image data) plus a children slot.
// The "next card" is no longer a scaled-up peek image rendered here — callers
// (SwipePage/DiscoveryPage) render the real next card FULL-SIZE in the same
// children slot, in an identical keyed wrapper to the top card, so React
// reuses the DOM node when the card is promoted (no remount = no flicker).
export default function SwipeDeck({ children, active = false }) {
  return (
    <div style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}>
      {active && (
        <>
          {/* Layer 0 — static shadow holder (FRONT-UX-14-R5 FIX1). Permanent,
              never animates, sits below the ladder dummies. Guarantees the
              scene's ground shadow never blinks out during swipe/promotion,
              regardless of what the SwipeCard face shadows above do while
              flying. Gated by `active` same as the ladder dummies — when the
              deck has no card (loading/empty), no holder renders either; a
              lone shadow rectangle with nothing on top of it would read as a
              layout bug, not "ground shadow." */}
          <div aria-hidden="true" style={{
            position: 'absolute', inset: 0,
            borderRadius: 20,
            background: 'var(--color-surface)',
            boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
            zIndex: 0,
            pointerEvents: 'none',
          }} />
          {/* Layer 1 — deepest dummy card (pure decoration, never animates) */}
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
          {/* Layer 2 — mid dummy card (pure decoration, never animates) */}
          <div aria-hidden="true" style={{
            position: 'absolute', inset: 0,
            borderRadius: 20,
            background: 'var(--color-surface-2)',
            border: '1px solid var(--color-border-soft)',
            transform: 'scale(0.95) translateY(10px)',
            transformOrigin: 'bottom center',
            zIndex: 2,
            pointerEvents: 'none',
          }} />
        </>
      )}
      {/* Layer 3 — real cards (top + next), rendered by the caller */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 3 }}>
        {children}
      </div>
    </div>
  )
}
