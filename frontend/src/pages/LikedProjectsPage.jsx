import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLikedBuildings } from '../api/client.js'
import { useTranslation } from '../i18n/index.js'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import s from './LikedProjectsPage.module.css'

/**
 * LikedProjectsPage — grid of buildings the user right-swiped in Discovery.
 * Card style mirrors BuildingTile in BoardDetailPage (§3.5.1 + §3.5.2 RICH PATTERN).
 */
function LikedBuildingCard({ building }) {
  const navigate = useNavigate()
  // Support all canonical id field shapes used across the app
  const buildingId = building.canonical_bld_id || building.image_id || building.id || building.building_id
  const title = building.image_title || building.name_en || building.name || ''
  const imageUrl = building.image_url || ''

  return (
    <div
      onClick={() => { if (buildingId) navigate('/buildings/' + buildingId) }}
      className={s.card}
      style={{
        position: 'relative',
        aspectRatio: '4 / 5',
        borderRadius: 20,
        overflow: 'hidden',
        cursor: buildingId ? 'pointer' : 'default',
        background: 'var(--color-surface)',
        boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
        userSelect: 'none',
      }}
    >
      {imageUrl && (
        <img
          src={imageUrl}
          alt={title}
          loading="lazy"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            display: 'block',
          }}
        />
      )}

      {/* §3.5.1 mandatory bottom gradient overlay */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.4) 50%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />

      {/* Card text overlay */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '16px 18px 20px' }}>
        <h4 style={{
          color: '#fff',
          fontSize: 16,
          fontWeight: 700,
          margin: '0 0 3px',
          lineHeight: 1.3,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {title}
        </h4>
        <p style={{
          color: 'rgba(255,255,255,0.55)',
          fontSize: 12,
          fontStyle: 'italic',
          margin: 0,
        }}>
          Building
        </p>
      </div>
    </div>
  )
}

export default function LikedProjectsPage({ onLogout }) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [buildings, setBuildings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getLikedBuildings()
      .then(data => {
        if (cancelled) return
        setBuildings(data?.buildings || [])
      })
      .catch(err => {
        if (cancelled) return
        setError(err?.message || t('profile.loadError'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(80px + env(safe-area-inset-bottom))',
    }}>
      <PageBackButton onClick={() => navigate(-1)} />
      <PageLogoHeader />
      <PageTopControls onLogout={onLogout} />

      {/* Content area */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '18px 20px 24px' }}>
        <h2 style={{
          fontSize: 20, fontWeight: 700, margin: '0 0 16px',
          color: 'var(--color-text)', letterSpacing: '-0.01em',
        }}>
          Liked Projects
        </h2>
        {loading ? (
          /* Skeleton grid while loading (§8.8 Skeleton pattern) */
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 16,
          }}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                style={{
                  aspectRatio: '4 / 5',
                  borderRadius: 20,
                  background: 'var(--color-surface-2)',
                }}
              />
            ))}
          </div>
        ) : error ? (
          /* Inline error (§8.9 tier 2) */
          <div style={{
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            padding: '60px 20px', gap: 16, textAlign: 'center',
          }}>
            <p style={{ color: 'var(--color-text-dim)', fontSize: 14, fontWeight: 500, margin: 0 }}>
              {error}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                minHeight: 44, padding: '0 20px',
                borderRadius: 12,
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                fontSize: 14, fontWeight: 600,
                cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              {t('profile.retry')}
            </button>
          </div>
        ) : buildings.length === 0 ? (
          /* Empty state (§8.9 tier 1) */
          <div style={{
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            padding: '80px 20px', gap: 16, textAlign: 'center',
          }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-dim)', opacity: 0.5 }}>
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
            </svg>
            <p style={{
              color: 'var(--color-text)', fontSize: 16, fontWeight: 600, margin: 0,
            }}>
              {t('profile.noLikedBuildings')}
            </p>
            <p style={{
              color: 'var(--color-text-dim)', fontSize: 13, fontWeight: 400, margin: 0,
            }}>
              {t('profile.swipeToSave')}
            </p>
            <button
              type="button"
              onClick={() => navigate('/discovery')}
              style={{
                marginTop: 8,
                minHeight: 44, padding: '0 24px',
                borderRadius: 999,
                border: 'none',
                background: 'var(--accent-1)',
                color: '#fff', fontSize: 14, fontWeight: 700,
                cursor: 'pointer', fontFamily: 'inherit',
                boxShadow: '0 8px 22px color-mix(in srgb, var(--accent-1) 32%, transparent)',
              }}
            >
              {t('profile.goToDiscovery')}
            </button>
          </div>
        ) : (
          /* Building grid — 2-column on mobile, auto-fill on desktop */
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 16,
          }}>
            {buildings.map((building, i) => {
              const key = building.canonical_bld_id || building.image_id || building.id || i
              return <LikedBuildingCard key={key} building={building} />
            })}
          </div>
        )}
      </div>
    </div>
  )
}
