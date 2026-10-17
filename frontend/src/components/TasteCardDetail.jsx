import { InfoRow } from './SwipeCard.jsx'
import fb from './TasteFeedback.module.css'

/**
 * Front-face text layers of a taste-start card: bottom gradient (grows to 100%
 * when the detail is open), the caption (title + country · use + tap hint) and
 * the SwipeCard-style detail panel with the gallery button.
 */
export default function TasteCardDetail({ card, expanded, captionHidden, interactive, onOpenGallery, t }) {
  const m = card.metadata || {}
  const country = m.axis_country
  const use = m.axis_typology
  const materialList = Array.isArray(m.axis_material_visual) ? m.axis_material_visual.slice(0, 3) : []
  const material = materialList.length ? materialList.join(', ') : null
  const galleryCount = (card.gallery || []).length
  const hideCaption = expanded || captionHidden

  return (
    <>
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        height: expanded ? '100%' : '52%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.6) 38%, rgba(0,0,0,0.12) 72%, transparent 100%)',
        transition: 'height 0.42s cubic-bezier(0.32, 0, 0.18, 1)',
        pointerEvents: 'none',
      }} />

      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0, padding: '0 14px 14px', color: '#fff',
        opacity: hideCaption ? 0 : 1,
        transform: hideCaption ? 'translateY(-6px)' : 'translateY(0)',
        transition: 'opacity 0.22s ease, transform 0.38s ease',
        pointerEvents: 'none',
      }}>
        <div style={{
          fontSize: 'var(--fs-emphasis)', fontWeight: 600, lineHeight: 1.3,
          overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
        }}>{card.image_title}</div>
        {(country || use) && (
          <div style={{ fontSize: 'var(--fs-caption)', opacity: 0.85, marginTop: 4 }}>
            {[country, use].filter(Boolean).map(String).join(' · ')}
          </div>
        )}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5, marginTop: 10,
          color: 'rgba(255,255,255,0.5)', fontSize: 11, letterSpacing: '0.04em',
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="18 15 12 9 6 15" />
          </svg>
          {t('swipe.detail.tapForDetails')}
        </div>
      </div>

      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0, maxHeight: '100%',
        display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
        padding: '16px 18px 20px', overflow: 'hidden', color: '#fff',
        transform: expanded ? 'translateY(0)' : 'translateY(100%)',
        transition: 'transform 0.42s cubic-bezier(0.32, 0, 0.18, 1)',
      }}>
        <h2 style={{
          color: '#fff', fontSize: 18, fontWeight: 700, lineHeight: 1.3, margin: '0 0 3px', flexShrink: 0,
          overflow: 'hidden', textOverflow: 'ellipsis',
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
        }}>{card.image_title}</h2>
        {m.axis_architects && (
          <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: 12, margin: '0 0 12px', fontStyle: 'italic', flexShrink: 0 }}>
            {m.axis_architects}
          </p>
        )}
        <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12, flexShrink: 0 }} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px', flex: '0 1 auto', minHeight: 0 }}>
          <InfoRow label={t('swipe.detail.labels.type')}       value={use} />
          <InfoRow label={t('swipe.detail.labels.country')}    value={country} />
          <InfoRow label={t('swipe.detail.labels.city')}       value={m.axis_city} />
          <InfoRow label={t('swipe.detail.labels.year')}       value={m.axis_year} />
          <InfoRow label={t('swipe.detail.labels.style')}      value={m.axis_style} />
          <InfoRow label={t('swipe.detail.labels.atmosphere')} value={m.axis_atmosphere} />
          <InfoRow label={t('swipe.detail.labels.material')}   value={material} />
        </div>
        {interactive && expanded && galleryCount > 0 && (
          <button type="button" className={fb.galBtn} data-nodrag="" onClick={onOpenGallery}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
            {t('swipe.detail.viewGallery', { n: galleryCount })}
          </button>
        )}
      </div>
    </>
  )
}
