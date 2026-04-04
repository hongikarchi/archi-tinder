import { useState } from 'react'

export default function TutorialPopup({ visible, onClose }) {
  const [dontShowAgain, setDontShowAgain] = useState(false)

  if (!visible) return null

  function handleClose() {
    if (dontShowAgain) {
      localStorage.setItem('archithon_tutorial_dismissed', 'true')
    }
    onClose()
  }

  const steps = [
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="#ec4899">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
      ),
      title: 'Swipe Right',
      desc: 'Save buildings you love to your collection',
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      ),
      title: 'Swipe Left',
      desc: 'Skip buildings that don\'t interest you',
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fb923c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <circle cx="8.5" cy="8.5" r="1.5" fill="#fb923c"/>
          <polyline points="21 15 16 10 5 21"/>
        </svg>
      ),
      title: 'Tap Card',
      desc: 'See building details, then tap again for the gallery',
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="#a78bfa">
          <path d="M12 0l3.09 6.26L22 9l-6.91 2.74L12 18l-3.09-6.26L2 9l6.91-2.74L12 0z"/>
        </svg>
      ),
      title: 'AI Learns Your Taste',
      desc: 'The more you swipe, the smarter recommendations get',
    },
  ]

  return (
    <div
      style={{
        position: 'fixed',
        top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.7)',
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
      onClick={handleClose}
    >
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: 340,
          borderRadius: 20,
          background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
          boxShadow: '0 25px 60px rgba(0,0,0,0.6)',
          padding: '28px 24px 24px',
          overflow: 'hidden',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={handleClose}
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.1)',
            border: 'none',
            color: 'rgba(255,255,255,0.6)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 18,
            fontFamily: 'inherit',
          }}
          aria-label="Close tutorial"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>

        {/* Title */}
        <h2 style={{
          color: '#fff',
          fontSize: 20,
          fontWeight: 800,
          margin: '0 0 20px 0',
          textAlign: 'center',
          lineHeight: 1.3,
        }}>
          How to Use ArchiTinder
        </h2>

        {/* Steps */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {steps.map((step, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                background: 'rgba(255,255,255,0.06)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                {step.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{
                  color: '#fff',
                  fontSize: 14,
                  fontWeight: 700,
                  marginBottom: 2,
                }}>
                  {step.title}
                </div>
                <div style={{
                  color: 'rgba(255,255,255,0.55)',
                  fontSize: 12,
                  lineHeight: 1.4,
                }}>
                  {step.desc}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Divider */}
        <div style={{
          height: 1,
          background: 'rgba(255,255,255,0.1)',
          margin: '20px 0 16px',
        }} />

        {/* Don't show again checkbox */}
        <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          cursor: 'pointer',
          marginBottom: 16,
        }}>
          <input
            type="checkbox"
            checked={dontShowAgain}
            onChange={e => setDontShowAgain(e.target.checked)}
            style={{
              width: 16,
              height: 16,
              accentColor: '#f43f5e',
              cursor: 'pointer',
            }}
          />
          <span style={{
            color: 'rgba(255,255,255,0.5)',
            fontSize: 12,
          }}>
            Don't show this again
          </span>
        </label>

        {/* Got it button */}
        <button
          onClick={handleClose}
          style={{
            width: '100%',
            padding: '12px 24px',
            borderRadius: 14,
            background: 'linear-gradient(135deg, #f43f5e, #fb923c)',
            color: '#fff',
            fontSize: 15,
            fontWeight: 700,
            border: 'none',
            cursor: 'pointer',
            fontFamily: 'inherit',
            boxShadow: '0 4px 20px rgba(244,63,94,0.35)',
          }}
        >
          Got it!
        </button>
      </div>
    </div>
  )
}
