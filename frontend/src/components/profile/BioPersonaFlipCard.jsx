import { useState } from 'react'

/**
 * BioPersonaFlipCard — §3.5.4 Hero Flip variant (text-on-surface, profile pages)
 *   Front: italic bio + "tap to reveal persona" caption
 *   Back: persona_type gradient text + one_liner + Styles/Programs chip rows + MBTI bottom-right
 *   Internal radial-gradient pink glow. Lift YES, border YES (text-on-surface needs containment).
 */
export default function BioPersonaFlipCard({ bio, persona, mbti }) {
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
        {/* FRONT — italic bio + "tap to reveal persona" */}
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
          }}>
            {bio}
          </p>
          <span style={{
            position: 'relative', zIndex: 1,
            alignSelf: 'flex-end',
            color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
            letterSpacing: '0.04em', textTransform: 'uppercase',
            marginTop: 12,
          }}>
            tap to reveal persona
          </span>
        </div>

        {/* BACK — persona_type gradient + one_liner + chips + MBTI */}
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
          <h3 style={{
            position: 'relative', zIndex: 1,
            margin: '0 0 6px',
            fontSize: 20, fontWeight: 700, lineHeight: 1.2,
            letterSpacing: '-0.01em',
            background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            color: '#ec4899',
          }}>
            {persona.persona_type}
          </h3>
          {persona.one_liner && (
            <p style={{
              position: 'relative', zIndex: 1,
              margin: '0 0 14px',
              color: 'var(--color-text-dim)', fontSize: 13, lineHeight: 1.5,
              fontStyle: 'italic', fontWeight: 500,
            }}>
              &ldquo;{persona.one_liner}&rdquo;
            </p>
          )}
          {persona.styles?.length > 0 && (
            <div style={{ position: 'relative', zIndex: 1, marginBottom: 10 }}>
              <span style={{
                display: 'block',
                color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
                letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6,
              }}>
                Styles
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {persona.styles.map(s => (
                  <span key={s} style={{
                    display: 'inline-block',
                    padding: '4px 10px', borderRadius: 999,
                    background: 'rgba(236,72,153,0.15)',
                    color: '#ec4899',
                    fontSize: 11, fontWeight: 600,
                  }}>
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
          {persona.programs?.length > 0 && (
            <div style={{ position: 'relative', zIndex: 1 }}>
              <span style={{
                display: 'block',
                color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
                letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6,
              }}>
                Programs
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {persona.programs.map(p => (
                  <span key={p} style={{
                    display: 'inline-block',
                    padding: '4px 10px', borderRadius: 999,
                    background: 'rgba(236,72,153,0.15)',
                    color: '#ec4899',
                    fontSize: 11, fontWeight: 600,
                  }}>
                    {p}
                  </span>
                ))}
              </div>
            </div>
          )}
          {/* MBTI subtle bottom-right */}
          {mbti && (
            <span style={{
              position: 'absolute', bottom: 12, right: 14, zIndex: 1,
              color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
              letterSpacing: '0.08em',
            }}>
              {mbti}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
