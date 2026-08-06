import { CARD_WIDTH, CARD_HEIGHT } from './SwipeCard.jsx'

export default function SwipeDeck({ children, nextCard = null }) {
  return (
    <div style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}>
      {nextCard?.image_url && (
        <div aria-hidden="true" style={{
          position: 'absolute', inset: 0,
          borderRadius: 20, overflow: 'hidden',
          boxShadow: '0 16px 40px rgba(0,0,0,0.35)',
          background: '#111',
          transform: 'scale(0.95) translateY(10px)',
          transformOrigin: 'bottom center',
          zIndex: 1,
          pointerEvents: 'none',
        }}>
          <img
            src={nextCard.image_url}
            alt=""
            draggable={false}
            style={{ width: '100%', height: '100%', objectFit: 'contain', objectPosition: 'center', display: 'block' }}
          />
        </div>
      )}
      <div style={{ position: 'absolute', inset: 0, zIndex: 2 }}>
        {children}
      </div>
    </div>
  )
}
