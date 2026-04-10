import { useState, useEffect } from 'react'

export default function TutorialPopup({ visible, onClose }) {
  const [isTouch, setIsTouch] = useState(false)

  useEffect(() => {
    const mql = window.matchMedia('(pointer: coarse)')
    setIsTouch(mql.matches)
    
    const handler = e => setIsTouch(e.matches)
    if (mql.addEventListener) mql.addEventListener('change', handler)
    else mql.addListener(handler)
    
    return () => {
      if (mql.removeEventListener) mql.removeEventListener('change', handler)
      else mql.removeListener(handler)
    }
  }, [])

  if (!visible) return null

  function handleClose() {
    localStorage.setItem('archithon_tutorial_dismissed', 'true')
    onClose()
  }

  const iconStyle = { marginBottom: 12, opacity: 0.9 }
  const textStyle = { color: 'rgba(255,255,255,0.9)', fontSize: 16, fontWeight: 700, letterSpacing: '0.02em', textAlign: 'center' }
  const subTextStyle = { color: 'rgba(255,255,255,0.6)', fontSize: 13, marginTop: 4, fontWeight: 500 }

  return (
    <div
      onClick={handleClose}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.65)',
        backdropFilter: 'blur(3px)',
        zIndex: 10000,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer',
      }}
    >
      <div style={{
         position: 'relative', width: '100%', maxWidth: 400, height: '100%',
         display: 'flex', flexDirection: 'column',
         alignItems: 'center', justifyContent: 'center',
      }}>

        {isTouch ? (
          <div style={{ display: 'flex', width: '100%', justifyContent: 'space-between', padding: '0 32px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              <svg style={iconStyle} width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round">
                <path d="M15 18l-6-6 6-6" />
                <path d="M21 18l-6-6 6-6" opacity="0.3" />
              </svg>
              <div style={textStyle}>Swipe Left</div>
              <div style={{...subTextStyle, color: '#ef4444'}}>Skip</div>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
               <svg style={iconStyle} width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ec4899" strokeWidth="2.5" strokeLinecap="round">
                <path d="M9 18l6-6-6-6" />
                <path d="M3 18l6-6-6-6" opacity="0.3" />
              </svg>
              <div style={textStyle}>Swipe Right</div>
              <div style={{...subTextStyle, color: '#ec4899'}}>Save</div>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', width: '100%', justifyContent: 'space-between', padding: '0 40px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              <div style={{...iconStyle, display: 'flex', alignItems: 'center', justifyContent: 'center', width: 44, height: 44, border: '2.5px solid #ef4444', borderRadius: 8, color: '#ef4444'}}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                  <path d="M15 18l-6-6 6-6" />
                </svg>
              </div>
              <div style={textStyle}>Left Arrow</div>
              <div style={{...subTextStyle, color: '#ef4444'}}>Skip</div>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              <div style={{...iconStyle, display: 'flex', alignItems: 'center', justifyContent: 'center', width: 44, height: 44, border: '2.5px solid #ec4899', borderRadius: 8, color: '#ec4899'}}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                  <path d="M9 18l6-6-6-6" />
                </svg>
              </div>
              <div style={textStyle}>Right Arrow</div>
              <div style={{...subTextStyle, color: '#ec4899'}}>Save</div>
            </div>
          </div>
        )}

        <div style={{ height: 180 }} /> {/* Spacer to avoid middle card area */}

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
           <svg style={iconStyle} width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#e2e8f0" strokeWidth="2" strokeLinecap="round">
             <circle cx="12" cy="12" r="10" strokeOpacity="0.3"/>
             <circle cx="12" cy="12" r="4" fill="#e2e8f0" fillOpacity="0.4"/>
           </svg>
           <div style={textStyle}>Tap Card</div>
           <div style={subTextStyle}>View details</div>
        </div>

        <div style={{ position: 'absolute', bottom: 40, color: 'rgba(255,255,255,0.4)', fontSize: 13, letterSpacing: '0.05em', fontWeight: 500, border: '1px solid rgba(255,255,255,0.1)', padding: '8px 20px', borderRadius: 999 }}>
          Tap anywhere to continue
        </div>

      </div>
    </div>
  )
}
