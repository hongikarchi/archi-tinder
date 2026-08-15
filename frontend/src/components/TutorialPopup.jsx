/**
 * TutorialPopup — full-screen swipe-gesture teaching overlay.
 * FRONT-FLOW-1: relocated from SwipePage (Taste) to DiscoveryPage — shown once,
 * on first Discovery entry for newly registered accounts (flag set in
 * LoginPage's register-success path, owned end-to-end by DiscoveryPage).
 * Copy now Discovery-semantic (left = pass, right = like) and fully via i18n.
 * Colors: left/pass = neutral (var(--color-text-muted), non-destructive in
 * Discovery), right/like = var(--accent-1). The dark scrim + white-on-scrim
 * text stays rgba(255,255,255,...) — a theme-independent overlay idiom.
 * The component itself is "dumb": it only calls onClose(); the caller
 * (DiscoveryPage) owns the localStorage flags.
 */
import { useState, useEffect } from 'react'
import { useTranslation } from '../i18n/index.js'

export default function TutorialPopup({ visible, onClose }) {
  const { t } = useTranslation()
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
    onClose()
  }

  const iconStyle = { marginBottom: 12, opacity: 0.9 }
  const textStyle = { color: 'rgba(255,255,255,0.9)', fontSize: 16, fontWeight: 700, letterSpacing: '0.02em', textAlign: 'center' }
  const subTextStyle = { color: 'rgba(255,255,255,0.6)', fontSize: 13, marginTop: 4, fontWeight: 500 }
  const leftColor = 'var(--color-text-muted)'
  const rightColor = 'var(--accent-1)'

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
              <svg style={{ ...iconStyle, color: leftColor }} width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M15 18l-6-6 6-6" />
                <path d="M21 18l-6-6 6-6" opacity="0.3" />
              </svg>
              <div style={textStyle}>{t('discovery.tutorial.swipeLeftTitle')}</div>
              <div style={{...subTextStyle, color: leftColor}}>{t('discovery.tutorial.swipeLeftSub')}</div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
               <svg style={{ ...iconStyle, color: rightColor }} width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M9 18l6-6-6-6" />
                <path d="M3 18l6-6-6-6" opacity="0.3" />
              </svg>
              <div style={textStyle}>{t('discovery.tutorial.swipeRightTitle')}</div>
              <div style={{...subTextStyle, color: rightColor}}>{t('discovery.tutorial.swipeRightSub')}</div>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', width: '100%', justifyContent: 'space-between', padding: '0 40px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              <div style={{...iconStyle, display: 'flex', alignItems: 'center', justifyContent: 'center', width: 44, height: 44, border: `2.5px solid ${leftColor}`, borderRadius: 8, color: leftColor}}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                  <path d="M15 18l-6-6 6-6" />
                </svg>
              </div>
              <div style={textStyle}>{t('discovery.tutorial.leftArrowTitle')}</div>
              <div style={{...subTextStyle, color: leftColor}}>{t('discovery.tutorial.leftArrowSub')}</div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              <div style={{...iconStyle, display: 'flex', alignItems: 'center', justifyContent: 'center', width: 44, height: 44, border: `2.5px solid ${rightColor}`, borderRadius: 8, color: rightColor}}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                  <path d="M9 18l6-6-6-6" />
                </svg>
              </div>
              <div style={textStyle}>{t('discovery.tutorial.rightArrowTitle')}</div>
              <div style={{...subTextStyle, color: rightColor}}>{t('discovery.tutorial.rightArrowSub')}</div>
            </div>
          </div>
        )}

        <div style={{ height: 180 }} /> {/* Spacer to avoid middle card area */}

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
           <svg style={{ ...iconStyle, color: 'rgba(255,255,255,0.85)' }} width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
             <circle cx="12" cy="12" r="10" strokeOpacity="0.3"/>
             <circle cx="12" cy="12" r="4" fill="currentColor" fillOpacity="0.4"/>
           </svg>
           <div style={textStyle}>{t('discovery.tutorial.tapCardTitle')}</div>
           <div style={subTextStyle}>{t('discovery.tutorial.tapCardSub')}</div>
        </div>

        <div style={{ position: 'absolute', bottom: 40, color: 'rgba(255,255,255,0.4)', fontSize: 13, letterSpacing: '0.05em', fontWeight: 500, border: '1px solid rgba(255,255,255,0.1)', padding: '8px 20px', borderRadius: 999 }}>
          {t('discovery.tutorial.continueHint')}
        </div>

      </div>
    </div>
  )
}
