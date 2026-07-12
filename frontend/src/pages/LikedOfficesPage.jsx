import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getUserSavedStudios, getArchitectProfile } from '../api/client.js'
import { useTranslation } from '../i18n/index.js'

/* ── Placeholder SVG icons ──────────────────────────────────────────────── */

export function BuildingPlaceholderSmall() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-muted)', opacity: 0.5 }}>
      <rect x="3" y="9" width="13" height="13" rx="1" />
      <path d="M16 9V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v5" />
      <line x1="9" y1="21" x2="9" y2="15" />
      <line x1="13" y1="21" x2="13" y2="15" />
    </svg>
  )
}

export function BuildingPlaceholderLarge() {
  return (
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-muted)', opacity: 0.4 }}>
      <rect x="3" y="9" width="13" height="13" rx="1" />
      <path d="M16 9V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v5" />
      <line x1="9" y1="21" x2="9" y2="15" />
      <line x1="13" y1="21" x2="13" y2="15" />
      <rect x="16" y="13" width="5" height="9" rx="1" />
      <line x1="18.5" y1="11" x2="18.5" y2="13" />
    </svg>
  )
}

export function BuildingIconEmpty() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-muted)', opacity: 0.45 }}>
      <rect x="2" y="7" width="14" height="15" rx="1" />
      <path d="M16 7V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1v4" />
      <line x1="6" y1="22" x2="6" y2="17" />
      <line x1="10" y1="22" x2="10" y2="17" />
      <rect x="16" y="11" width="6" height="11" rx="1" />
      <line x1="19" y1="9" x2="19" y2="11" />
      <line x1="17" y1="14" x2="22" y2="14" />
      <line x1="17" y1="17" x2="22" y2="17" />
    </svg>
  )
}

/* ── BuildingCarousel ───────────────────────────────────────────────────── */

export function BuildingCarousel({ buildings, fallbackUrl, altText, onNavigate }) {
  // null → still loading (show existing cover image as fallback)
  // []   → loaded but no buildings (show placeholder)
  // [..] → show carousel

  if (buildings === null || buildings === undefined) {
    return (
      <div
        onClick={e => { e.stopPropagation(); onNavigate?.() }}
        style={{
          width: '100%', aspectRatio: '16 / 10', borderRadius: 12,
          overflow: 'hidden', background: 'var(--color-surface-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        {fallbackUrl ? (
          <img
            src={fallbackUrl}
            alt={altText}
            loading="lazy"
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
          />
        ) : (
          <BuildingPlaceholderLarge />
        )}
      </div>
    )
  }

  if (buildings.length === 0) {
    return (
      <div style={{
        width: '100%', aspectRatio: '16 / 10', borderRadius: 12,
        background: 'var(--color-surface-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <BuildingPlaceholderLarge />
      </div>
    )
  }

  return (
    <div
      className="building-carousel"
      onClick={e => e.stopPropagation()}
      style={{
        display: 'flex',
        overflowX: 'auto',
        scrollSnapType: 'x mandatory',
        gap: 8,
        borderRadius: 12,
      }}
    >
      {buildings.map((bld, i) => (
        <div
          key={bld.canonical_bld_id || i}
          onClick={e => { e.stopPropagation(); onNavigate?.() }}
          style={{
            flex: '0 0 80%',
            flexShrink: 0,
            scrollSnapAlign: 'start',
            borderRadius: 12,
            overflow: 'hidden',
            aspectRatio: '16 / 10',
            background: 'var(--color-surface-2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          {bld.image_url ? (
            <img
              src={bld.image_url}
              alt={bld.name_en || altText}
              loading="lazy"
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            />
          ) : (
            <BuildingPlaceholderLarge />
          )}
        </div>
      ))}
    </div>
  )
}

/* ── OfficeCard ─────────────────────────────────────────────────────────── */

export function OfficeCard({ office, buildings, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 0 }}
    >
      {/* Header row: logo + name + subtitle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        {/* Logo circle */}
        <div style={{
          width: 44, height: 44, minWidth: 44,
          borderRadius: '50%',
          background: 'var(--color-surface-2)',
          border: '1px solid var(--color-border-soft)',
          overflow: 'hidden',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          {office.logo_url ? (
            <img
              src={office.logo_url}
              alt={office.name}
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            />
          ) : (
            <BuildingPlaceholderSmall />
          )}
        </div>

        {/* Text block */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, minWidth: 0 }}>
          <p style={{
            fontSize: 15, fontWeight: 700, color: 'var(--color-text)',
            margin: 0, lineHeight: 1.3,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {office.name}
          </p>
          <p style={{
            fontSize: 12, color: 'var(--color-text-muted)', fontWeight: 500,
            margin: '2px 0 0', lineHeight: 1.4,
          }}>
            Saved to liked offices
          </p>
        </div>
      </div>

      {/* Building carousel */}
      <BuildingCarousel
        buildings={buildings}
        fallbackUrl={office.cover_image_url}
        altText={office.name}
        onNavigate={onClick}
      />
    </div>
  )
}

/* ── Skeleton card ──────────────────────────────────────────────────────── */

export function SkeletonCard() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <div style={{
          width: 44, height: 44, minWidth: 44,
          borderRadius: '50%',
          background: 'var(--color-surface-2)',
          flexShrink: 0,
        }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
          <div style={{ height: 14, borderRadius: 6, background: 'var(--color-surface-2)', width: '55%' }} />
          <div style={{ height: 11, borderRadius: 6, background: 'var(--color-surface-2)', width: '38%' }} />
        </div>
      </div>
      <div style={{ height: 200, borderRadius: 12, background: 'var(--color-surface-2)' }} />
    </div>
  )
}

/* ── Main page ──────────────────────────────────────────────────────────── */

export default function LikedOfficesPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [studios, setStudios] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // architect_id → buildings[] (null = not yet fetched)
  const [buildingsMap, setBuildingsMap] = useState({})

  function fetchStudios() {
    const rawUser = sessionStorage.getItem('archithon_user')
    const userId = rawUser ? rawUser.trim() : null
    if (!userId) {
      setError(t('profile.loginRequired'))
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    let cancelled = false
    getUserSavedStudios(userId)
      .then(data => {
        if (cancelled) return
        setStudios(Array.isArray(data) ? data : [])
      })
      .catch(err => {
        if (cancelled) return
        setError(err?.message || t('profile.loadError'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }

  useEffect(() => {
    const cleanup = fetchStudios()
    return cleanup
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- mount-only fetch; t identity churn must not refetch

  // Fetch architect profiles in parallel to get building lists for carousels
  useEffect(() => {
    if (!studios.length) return
    studios.forEach(office => {
      getArchitectProfile(office.architect_id)
        .then(profile => {
          setBuildingsMap(prev => ({
            ...prev,
            [office.architect_id]: profile?.buildings || [],
          }))
        })
        .catch(() => {
          setBuildingsMap(prev => ({ ...prev, [office.architect_id]: [] }))
        })
    })
  }, [studios])

  return (
    <>
      {/* CSS for carousel scrollbar hiding */}
      <style>{`
        .building-carousel::-webkit-scrollbar { display: none; }
        .building-carousel { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>

      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        overflowY: 'auto',
        background: 'var(--color-bg)',
        paddingBottom: 'calc(80px + env(safe-area-inset-bottom, 0px))',
      }}>
        {/* Sticky header */}
        <div style={{
          position: 'sticky', top: 0, zIndex: 10,
          background: 'color-mix(in srgb, var(--color-bg) 72%, transparent)',
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          padding: '12px 16px',
          display: 'flex', alignItems: 'center', gap: 8,
          borderBottom: '1px solid var(--color-border-soft)',
        }}>
          <button
            onClick={() => navigate(-1)}
            aria-label="Back"
            style={{
              width: 44, height: 44, minWidth: 44,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'transparent', border: 'none',
              color: 'var(--color-text)', cursor: 'pointer',
              borderRadius: 12,
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
          </button>

          <h2 style={{
            color: 'var(--color-text)', fontSize: 17, fontWeight: 700,
            margin: 0, letterSpacing: '-0.01em',
          }}>
            Liked Offices
          </h2>
        </div>

        {/* Content area */}
        <div style={{ maxWidth: 480, margin: '0 auto', padding: '24px 20px' }}>
          {loading ? (
            /* Skeleton */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>
              {[0, 1, 2].map(i => <SkeletonCard key={i} />)}
            </div>
          ) : error ? (
            /* Inline error */
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              padding: '60px 20px', gap: 16, textAlign: 'center',
            }}>
              <p style={{ color: 'var(--color-text-muted)', fontSize: 14, fontWeight: 500, margin: 0 }}>
                {error}
              </p>
              <button
                type="button"
                onClick={() => fetchStudios()}
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
          ) : studios.length === 0 ? (
            /* Empty state */
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              padding: '80px 20px', gap: 16, textAlign: 'center',
            }}>
              <BuildingIconEmpty />
              <p style={{ color: 'var(--color-text)', fontSize: 16, fontWeight: 600, margin: 0 }}>
                {t('profile.noSavedOffices')}
              </p>
              <p style={{ color: 'var(--color-text-muted)', fontSize: 13, fontWeight: 400, margin: 0 }}>
                {t('profile.followToShowOffices')}
              </p>
              <button
                type="button"
                onClick={() => navigate('/discovery')}
                style={{
                  marginTop: 8,
                  minHeight: 44, padding: '0 24px',
                  borderRadius: 999,
                  border: 'none',
                  background: 'linear-gradient(135deg, var(--accent-1, #0969DA), var(--accent-2, #8250DF))',
                  color: '#fff', fontSize: 14, fontWeight: 700,
                  cursor: 'pointer', fontFamily: 'inherit',
                }}
              >
                {t('profile.exploreArchitects')}
              </button>
            </div>
          ) : (
            /* Feed list */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>
              {studios.map((office, i) => (
                <OfficeCard
                  key={office.architect_id || i}
                  office={office}
                  buildings={buildingsMap[office.architect_id] ?? null}
                  onClick={() => navigate('/architects/' + office.architect_id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
