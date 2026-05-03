import { useState } from 'react'

/**
 * DescriptionAboutFlipCard — §3.5.4 Hero Flip variant (text-on-surface, profile pages)
 *   Front: italic description 3-line clamp + "tap to reveal more" caption
 *   Back: full description overflow-y auto + footer row with Founded year + Location
 *   Internal radial-gradient pink glow. Lift YES, border YES (text-on-surface needs containment).
 */
export default function DescriptionAboutFlipCard({ description, foundedYear, location }) {
  const [isFlipped, setIsFlipped] = useState(false)
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div
      style={{
        perspective: '1200px',
        width: '100%',
        minHeight: 180,
        cursor: 'pointer',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
        marginTop: 18, marginBottom: 18,
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={(e) => {
        if (e.target.closest('button')) return
        setIsFlipped(f => !f)
      }}
    >
      <div style={{
        width: '100%', minHeight: 180,
        position: 'relative',
        transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        transformStyle: 'preserve-3d',
        transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
      }}>
        {/* FRONT — italic description 3-line clamp + "tap to reveal more" */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          borderRadius: 20,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          padding: '20px 22px',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
          minHeight: 180,
        }}>
          {/* Internal radial-gradient pink glow */}
          <div style={{
            position: 'absolute', top: -40, right: -40,
            width: 160, height: 160, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(236,72,153,0.18), transparent 70%)',
            pointerEvents: 'none',
          }} />
          <p style={{
            position: 'relative', zIndex: 1,
            margin: 0,
            color: 'var(--color-text-dim)', fontSize: 15, lineHeight: 1.6,
            fontStyle: 'italic', fontWeight: 500,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {description}
          </p>
          <span style={{
            position: 'relative', zIndex: 1,
            alignSelf: 'flex-end',
            color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
            letterSpacing: '0.04em', textTransform: 'uppercase',
            marginTop: 12,
          }}>
            tap to reveal more
          </span>
        </div>

        {/* BACK — full description + footer (Founded + Location) */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          transform: 'rotateY(180deg)',
          borderRadius: 20,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          padding: '20px 22px',
          display: 'flex', flexDirection: 'column',
          boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
          minHeight: 180,
        }}>
          {/* Internal radial-gradient pink glow */}
          <div style={{
            position: 'absolute', top: -40, right: -40,
            width: 160, height: 160, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(236,72,153,0.18), transparent 70%)',
            pointerEvents: 'none',
          }} />
          <p style={{
            position: 'relative', zIndex: 1,
            margin: '0 0 14px',
            color: 'var(--color-text-2)', fontSize: 13, lineHeight: 1.55,
            fontWeight: 500,
            flex: 1,
            overflowY: 'auto',
          }}>
            {description}
          </p>
          {/* Footer meta — Founded + Location */}
          <div style={{
            position: 'relative', zIndex: 1,
            display: 'flex', flexWrap: 'wrap', gap: 10,
            paddingTop: 12,
            borderTop: '1px solid var(--color-border-soft)',
          }}>
            {foundedYear && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                color: 'var(--color-text-dim)', fontSize: 12, fontWeight: 600,
              }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                  <line x1="16" y1="2" x2="16" y2="6"></line>
                  <line x1="8" y1="2" x2="8" y2="6"></line>
                  <line x1="3" y1="10" x2="21" y2="10"></line>
                </svg>
                Founded {foundedYear}
              </span>
            )}
            {location && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                color: 'var(--color-text-dim)', fontSize: 12, fontWeight: 600,
              }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                  <circle cx="12" cy="10" r="3"></circle>
                </svg>
                {location}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
