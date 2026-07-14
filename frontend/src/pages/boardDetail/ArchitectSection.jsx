import { useState } from 'react'
import styles from './ArchitectSection.module.css'
import { useTranslation } from '../../i18n/index.js'

function BuildingCard({ building, onClick }) {
  const [imgLoaded, setImgLoaded] = useState(false)
  const title = building.name_en || building.name || ''

  return (
    <div
      className={styles.buildingCard}
      onClick={() => onClick(building.canonical_bld_id)}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(building.canonical_bld_id) } }}
      aria-label={title}
    >
      {!imgLoaded && (
        <div style={{
          position: 'absolute',
          inset: 0,
          background: 'var(--color-surface-2)',
        }} />
      )}
      {building.image_url && (
        <img
          src={building.image_url}
          alt={title}
          loading="lazy"
          onLoad={() => setImgLoaded(true)}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            display: 'block',
            opacity: imgLoaded ? 1 : 0,
            transition: 'opacity 0.3s',
          }}
        />
      )}
      {/* Bottom gradient + title overlay */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.75) 0%, transparent 55%)',
        pointerEvents: 'none',
      }} />
      <p style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        margin: 0,
        padding: '8px 8px 10px',
        color: '#fff',
        fontSize: 11,
        fontWeight: 600,
        lineHeight: 1.3,
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}>
        {title}
      </p>
    </div>
  )
}

export default function ArchitectSection({ architect, onBuildingClick, onProfileClick }) {
  const { t } = useTranslation()
  const buildings = architect?.buildings || []

  return (
    <div className={styles.section}>
      {/* Header row */}
      <div style={{ marginBottom: 10 }}>
        <span style={{
          display: 'block',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--color-text-muted)',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          marginBottom: 6,
        }}>
          {t('board.recommendedOffice')}
        </span>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <span style={{
            fontSize: 15,
            fontWeight: 700,
            color: 'var(--color-text)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {architect?.name || ''}
          </span>
          <button
            className={styles.profileBtn}
            onClick={() => onProfileClick(architect?.architect_id)}
            type="button"
          >
            {t('board.profile')}
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>
      </div>

      {/* Divider */}
      <div style={{
        height: 1,
        background: 'var(--color-border-soft)',
        marginBottom: 12,
      }} />

      {/* Horizontal building strip */}
      {buildings.length > 0 ? (
        <div
          className="hide-scrollbar"
          style={{
            display: 'flex',
            gap: 10,
            overflowX: 'auto',
          }}
        >
          {buildings.map(building => (
            <BuildingCard
              key={building.canonical_bld_id}
              building={building}
              onClick={onBuildingClick}
            />
          ))}
        </div>
      ) : (
        <p style={{
          fontSize: 13,
          color: 'var(--color-text-muted)',
          margin: 0,
          padding: '8px 0',
        }}>
          {t('board.noBuildingInfo')}
        </p>
      )}
    </div>
  )
}
