import { useEffect, useRef, useState } from 'react'

async function downloadImage(url, fallbackName = 'image') {
  try {
    const res = await fetch(url, { mode: 'cors' })
    if (!res.ok) throw new Error('fetch failed')
    const blob = await res.blob()
    const ext = blob.type.split('/')[1]?.replace('jpeg', 'jpg') || 'jpg'
    const name = url.split('/').pop().split('?')[0] || `${fallbackName}.${ext}`
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = name
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(objectUrl)
  } catch {
    // CORS blocked or fetch failed — open in new tab as fallback
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

export default function PhotoLightbox({ images, activeIndex, onClose, onNavigate }) {
  // images: [{ url, alt }]
  const total = images.length
  const current = images[activeIndex] || images[0]
  const [downloading, setDownloading] = useState(false)
  const touchStartX = useRef(null)

  // Lock body scroll
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  // Keyboard nav
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft')  onNavigate(Math.max(0, activeIndex - 1))
      if (e.key === 'ArrowRight') onNavigate(Math.min(total - 1, activeIndex + 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [activeIndex, total, onClose, onNavigate])

  function onTouchStart(e) {
    touchStartX.current = e.touches[0].clientX
  }
  function onTouchEnd(e) {
    if (touchStartX.current === null) return
    const dx = e.changedTouches[0].clientX - touchStartX.current
    touchStartX.current = null
    if (dx > 50 && activeIndex > 0)          onNavigate(activeIndex - 1)
    else if (dx < -50 && activeIndex < total - 1) onNavigate(activeIndex + 1)
  }

  async function handleDownload() {
    if (downloading || !current?.url) return
    setDownloading(true)
    await downloadImage(current.url, 'building-photo')
    setDownloading(false)
  }

  const btnStyle = {
    width: 44, height: 44, borderRadius: 12,
    border: '1px solid rgba(255,255,255,0.15)',
    background: 'rgba(0,0,0,0.55)',
    backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
    color: '#fff', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 99999,
        background: 'rgba(0,0,0,0.96)',
        display: 'flex', flexDirection: 'column',
      }}
      onClick={onClose}
    >
      {/* Top bar */}
      <div
        onClick={e => e.stopPropagation()}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 14px',
          flexShrink: 0,
        }}
      >
        <span style={{ color: 'rgba(255,255,255,0.55)', fontSize: 13, fontWeight: 600 }}>
          {activeIndex + 1} / {total}
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          {/* Download */}
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            aria-label="Download image"
            style={{ ...btnStyle, opacity: downloading ? 0.55 : 1 }}
          >
            {downloading ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 0.8s linear infinite' }}>
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            )}
          </button>
          {/* Close */}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={btnStyle}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>

      {/* Image + side nav */}
      <div
        style={{ flex: 1, display: 'flex', alignItems: 'center', position: 'relative', overflow: 'hidden' }}
        onClick={e => e.stopPropagation()}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {/* Prev */}
        {activeIndex > 0 && (
          <button
            type="button"
            onClick={() => onNavigate(activeIndex - 1)}
            aria-label="Previous"
            style={{ ...btnStyle, position: 'absolute', left: 12, zIndex: 2 }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        )}

        <img
          key={current.url}
          src={current.url}
          alt={current.alt || ''}
          style={{
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
            display: 'block',
            margin: '0 auto',
            userSelect: 'none',
            WebkitUserDrag: 'none',
          }}
          draggable={false}
        />

        {/* Next */}
        {activeIndex < total - 1 && (
          <button
            type="button"
            onClick={() => onNavigate(activeIndex + 1)}
            aria-label="Next"
            style={{ ...btnStyle, position: 'absolute', right: 12, zIndex: 2 }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        )}
      </div>

      {/* Bottom alt text */}
      {current.alt && (
        <div
          onClick={e => e.stopPropagation()}
          style={{
            padding: '10px 16px 14px',
            color: 'rgba(255,255,255,0.45)',
            fontSize: 12, textAlign: 'center', flexShrink: 0,
          }}
        >
          {current.alt}
        </div>
      )}

      {/* spin keyframe (shared with app) */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
