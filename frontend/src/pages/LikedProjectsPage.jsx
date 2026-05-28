import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLikedBuildings } from '../api/client.js'

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
      style={{
        position: 'relative',
        aspectRatio: '4 / 5',
        borderRadius: 20,
        overflow: 'hidden',
        cursor: buildingId ? 'pointer' : 'default',
        background: 'var(--color-surface)',
        border: '1px solid transparent',
        boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
        transition: 'transform var(--motion-normal, 220ms) var(--motion-ease, cubic-bezier(0.4,0,0.2,1)), border-color var(--motion-normal, 220ms) var(--motion-ease, cubic-bezier(0.4,0,0.2,1))',
        userSelect: 'none',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)'
        e.currentTarget.style.borderColor = 'rgba(236,72,153,0.55)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.borderColor = 'transparent'
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

export default function LikedProjectsPage() {
  const navigate = useNavigate()
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
        setError(err?.message || '데이터를 불러오지 못했어요.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(80px + env(safe-area-inset-bottom))',
    }}>
      {/* Sticky header */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 10,
        background: 'var(--color-header-bg, rgba(246,248,250,0.85))',
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
            transition: 'background var(--motion-fast, 180ms) var(--motion-ease, cubic-bezier(0.4,0,0.2,1))',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-surface-2)' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
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
          Liked Projects
        </h2>
      </div>

      {/* Content area */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 20px' }}>
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
              다시 시도
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
              아직 좋아요한 건물이 없어요
            </p>
            <p style={{
              color: 'var(--color-text-dim)', fontSize: 13, fontWeight: 400, margin: 0,
            }}>
              Discovery에서 오른쪽으로 스와이프하면 여기에 저장돼요
            </p>
            <button
              type="button"
              onClick={() => navigate('/discovery')}
              style={{
                marginTop: 8,
                minHeight: 44, padding: '0 24px',
                borderRadius: 999,
                border: 'none',
                background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                color: '#fff', fontSize: 14, fontWeight: 700,
                cursor: 'pointer', fontFamily: 'inherit',
                boxShadow: '0 8px 22px rgba(236,72,153,0.32)',
              }}
            >
              Discovery 가기
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
