import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLikedBuildings } from '../api/client.js'
import { useTranslation } from '../i18n/index.js'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import PageTitle from '../components/PageTitle.jsx'
import Skeleton from '../components/Skeleton.jsx'
import PhotoTile from '../components/PhotoTile.jsx'

/**
 * LikedProjectsPage — grid of buildings the user right-swiped in Discovery.
 * Card style mirrors BuildingTile in BoardDetailPage (§3.5.1 + §3.5.2 RICH PATTERN).
 * UI-CONSISTENCY-B Phase 2b: the local `LikedBuildingCard` is now the shared
 * `PhotoTile` component (identical 4:5/radius-lg overlay tile, extracted
 * so LikedProjectsPage and UserProfilePage's Liked tab share one card).
 */
function LikedBuildingCard({ building }) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  // Support all canonical id field shapes used across the app
  const buildingId = building.canonical_bld_id || building.image_id || building.id || building.building_id
  const title = building.image_title || building.name_en || building.name || ''
  const imageUrl = building.image_url || ''

  return (
    <PhotoTile
      imageUrl={imageUrl}
      title={title}
      subtitle={t('detailB3.buildingSubtitle')}
      onClick={buildingId ? () => navigate('/buildings/' + buildingId) : undefined}
    />
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
      height: 'var(--page-height)',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'var(--tabbar-clearance)',
    }}>
      <PageLogoHeader />
      <PageTopControls onLogout={onLogout} leading={<PageBackButton inline onClick={() => navigate(-1)} />} />

      {/* Content area */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '18px 20px 24px' }}>
        <PageTitle style={{ margin: '0 0 16px' }}>
          {t('detailB3.likedProjectsTitle')}
        </PageTitle>
        {loading ? (
          /* Skeleton grid while loading (§8.8 Skeleton pattern) */
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 16,
          }}>
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton
                key={i}
                width="100%"
                height="auto"
                radius="var(--radius-lg)"
                style={{ aspectRatio: '4 / 5' }}
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
            <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-medium)', margin: 0 }}>
              {error}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                minHeight: 44, padding: '0 20px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-semibold)',
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
              color: 'var(--color-text)', fontSize: 'var(--fs-emphasis)', fontWeight: 'var(--fw-semibold)', margin: 0,
            }}>
              {t('profile.noLikedBuildings')}
            </p>
            <p style={{
              color: 'var(--color-text-dim)', fontSize: 'var(--fs-caption)', fontWeight: 'var(--fw-regular)', margin: 0,
            }}>
              {t('profile.swipeToSave')}
            </p>
            <button
              type="button"
              onClick={() => navigate('/discovery')}
              style={{
                marginTop: 8,
                minHeight: 44, padding: '0 24px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                background: 'var(--accent-1)',
                color: '#fff', fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-bold)',
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
