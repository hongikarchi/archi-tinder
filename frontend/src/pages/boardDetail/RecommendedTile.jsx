import { useState } from 'react'

export default function RecommendedTile({ card, onClick }) {
  const [imgLoading, setImgLoading] = useState(true)
  const title = card.image_title || card.name_en
  return (
    <div onClick={onClick} style={{
      position: 'relative', aspectRatio: '3 / 4', borderRadius: 16, overflow: 'hidden', cursor: 'pointer',
      background: 'rgba(255,255,255,0.03)', border: '1px solid transparent',
      boxShadow: '0 8px 20px rgba(0,0,0,0.25)',
      transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
      userSelect: 'none',
    }}
    onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.borderColor = 'rgba(236,72,153,0.55)' }}
    onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.borderColor = 'transparent' }}>
      {imgLoading && <div className="skeleton-shimmer" style={{ position: 'absolute', inset: 0 }} />}
      <img src={card.image_url} alt={title} loading="lazy" onLoad={() => setImgLoading(false)} onError={() => setImgLoading(false)}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', display: 'block', opacity: imgLoading ? 0 : 1, transition: 'opacity 0.3s' }} />
      <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.2) 50%, transparent 100%)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '12px 14px 16px' }}>
        <p style={{ color: '#fff', fontSize: 13, fontWeight: 600, margin: 0, lineHeight: 1.3, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {title}
        </p>
      </div>
    </div>
  )
}
