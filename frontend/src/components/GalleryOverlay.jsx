import { useRef } from 'react'

const TAP_THRESHOLD = 8
const CARD_WIDTH = 340

export function GalleryOverlay({ card, onClose, fullscreen = false }) {
  const gallery = card.gallery || []
  const dragStart = useRef(null)
  const dragStartTime = useRef(null)

  function handlePointerDown(e) {
    dragStart.current = { x: e.clientX, y: e.clientY }
    dragStartTime.current = Date.now()
  }

  function handlePointerUp(e) {
    if (dragStart.current) {
      const dx = Math.abs(e.clientX - dragStart.current.x)
      const dy = Math.abs(e.clientY - dragStart.current.y)
      const dt = Date.now() - dragStartTime.current
      if (dx < TAP_THRESHOLD && dy < TAP_THRESHOLD && dt < 300) onClose()
    }
    dragStart.current = null
  }

  if (fullscreen) {
    return (
      <div
        style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'var(--color-bg)',
          display: 'flex', flexDirection: 'column',
        }}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
      >
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 16px', flexShrink: 0,
          borderBottom: '1px solid var(--color-border)',
        }}>
          <p style={{
            color: 'var(--color-text)', fontSize: 14, fontWeight: 700, margin: 0,
            flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {card.image_title}
          </p>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', color: 'var(--color-text-muted)',
              fontSize: 20, cursor: 'pointer', padding: '0 0 0 12px', lineHeight: 1,
            }}
          >✕</button>
        </div>

        <div style={{
          flex: 1,
          overflowY: 'auto', overflowX: 'hidden',
          display: 'flex', flexDirection: 'column',
          gap: 4, padding: '4px 0',
          WebkitOverflowScrolling: 'touch',
        }}>
          {gallery.length > 0 ? gallery.map((url, i) => (
            <img
              key={i}
              src={url}
              alt={`${card.image_title} ${i + 1}`}
              loading="lazy"
              style={{ width: '100%', height: 'auto', display: 'block', objectFit: 'cover', flexShrink: 0 }}
            />
          )) : (
            <div style={{
              flex: 1, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              color: 'var(--color-text-dimmer)', fontSize: 13,
            }}>
              No additional images
            </div>
          )}
        </div>

        {gallery.length > 0 && (
          <p style={{ color: 'var(--color-text-dimmer)', fontSize: 11, textAlign: 'center', padding: '8px 0 12px', margin: 0, flexShrink: 0 }}>
            {gallery.length} photo{gallery.length !== 1 ? 's' : ''} · scroll up/down
          </p>
        )}
      </div>
    )
  }

  return (
    <div
      style={{
        position: 'absolute', inset: 0, zIndex: 10,
        borderRadius: 20, overflow: 'hidden',
        background: 'var(--color-bg)',
        display: 'flex', flexDirection: 'column',
      }}
      onPointerDown={e => { e.stopPropagation(); handlePointerDown(e) }}
      onPointerUp={handlePointerUp}
      onTouchStart={e => e.stopPropagation()}
    >
      <div style={{
        display: 'flex', alignItems: 'center',
        padding: '12px 14px', flexShrink: 0,
        borderBottom: '1px solid var(--color-border)',
      }}>
        <p style={{
          color: 'var(--color-text)', fontSize: 13, fontWeight: 700, margin: 0,
          flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {card.image_title}
        </p>
      </div>

      <div style={{
        flex: 1,
        display: 'flex', flexDirection: 'row',
        overflowX: 'auto', overflowY: 'hidden',
        gap: 8, padding: '10px',
        WebkitOverflowScrolling: 'touch',
        scrollSnapType: 'x mandatory',
      }}>
        {gallery.length > 0 ? gallery.map((url, i) => (
          <img
            key={i}
            src={url}
            alt={`${card.image_title} ${i + 1}`}
            loading="lazy"
            style={{
              height: '100%', width: 'auto',
              maxWidth: `${CARD_WIDTH - 20}px`,
              borderRadius: 10, objectFit: 'cover',
              flexShrink: 0, scrollSnapAlign: 'start',
            }}
          />
        )) : (
          <div style={{
            width: '100%', display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            color: 'var(--color-text-dimmer)', fontSize: 13,
          }}>
            No additional images
          </div>
        )}
      </div>

      {gallery.length > 0 && (
        <p style={{ color: 'var(--color-text-dimmer)', fontSize: 11, textAlign: 'center', padding: '6px 0 10px', margin: 0 }}>
          {gallery.length} photo{gallery.length !== 1 ? 's' : ''} · scroll left/right
        </p>
      )}
    </div>
  )
}
