import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getArchitectProfile } from '../api/architects.js'
import styles from './ArchitectProfilePage.module.css'

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
      {/* Bottom gradient + name overlay */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 55%)',
        pointerEvents: 'none',
      }} />
      <p style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        margin: 0,
        padding: '10px 10px 12px',
        color: '#fff',
        fontSize: 12,
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

function SkeletonGrid() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(3, 1fr)',
      gap: 8,
      padding: '0 12px',
    }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className={styles.skeletonCard} />
      ))}
    </div>
  )
}

export default function ArchitectProfilePage() {
  const { architectId } = useParams()
  const navigate = useNavigate()
  // undefined = loading, null = not found, object = loaded
  const [profile, setProfile] = useState(undefined)
  const [error, setError] = useState(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    if (!architectId) {
      setProfile(null)
      return
    }
    setProfile(undefined)
    setError(null)
    getArchitectProfile(architectId)
      .then(data => setProfile(data))
      .catch(() => setError(true))
  }, [architectId, retryKey])

  const isLoading = profile === undefined && !error

  return (
    <div style={{
      height: 'calc(100vh - 64px)',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(80px + env(safe-area-inset-bottom, 0px))',
    }}>
      {/* Top nav */}
      <div style={{
        padding: '16px 16px 0',
      }}>
        <button
          className={styles.backBtn}
          onClick={() => navigate(-1)}
          type="button"
          aria-label="뒤로 가기"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          뒤로
        </button>
      </div>

      {isLoading && (
        <>
          {/* Skeleton header */}
          <div style={{ padding: '24px 16px 20px' }}>
            <div style={{
              width: '55%',
              height: 28,
              borderRadius: 8,
              background: 'var(--color-surface-2)',
              marginBottom: 12,
            }} />
            <div style={{
              width: 80,
              height: 20,
              borderRadius: 999,
              background: 'var(--color-surface-2)',
            }} />
          </div>
          <SkeletonGrid />
        </>
      )}

      {error && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '80px 20px',
          gap: 16,
          textAlign: 'center',
        }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4, color: 'var(--color-text-muted)' }}>
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p style={{
            color: 'var(--color-text-muted)',
            fontSize: 14,
            fontWeight: 600,
            margin: 0,
          }}>
            불러오는 데 실패했어요. 다시 시도해주세요.
          </p>
          <button
            onClick={() => { setError(null); setProfile(undefined); setRetryKey(k => k + 1) }}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border-soft)',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
            type="button"
          >
            다시 시도
          </button>
        </div>
      )}

      {!isLoading && !error && profile === null && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '80px 20px',
          gap: 12,
          textAlign: 'center',
        }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4, color: 'var(--color-text-muted)' }}>
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <p style={{
            color: 'var(--color-text-muted)',
            fontSize: 14,
            fontWeight: 600,
            margin: 0,
          }}>
            사무소 정보를 찾을 수 없어요.
          </p>
        </div>
      )}

      {!isLoading && !error && profile && (
        <>
          {/* Header */}
          <div style={{ padding: '24px 16px 20px' }}>
            <h1 style={{
              fontSize: 'clamp(22px, 5vw, 28px)',
              fontWeight: 700,
              color: 'var(--color-text)',
              margin: '0 0 10px',
              lineHeight: 1.2,
            }}>
              {profile.name}
            </h1>
            {profile.building_count != null && (
              <span style={{
                display: 'inline-block',
                padding: '4px 12px',
                borderRadius: 999,
                background: 'var(--color-surface-2)',
                color: 'var(--color-text-muted)',
                fontSize: 13,
                fontWeight: 600,
              }}>
                건물 {profile.building_count.toLocaleString()}개
              </span>
            )}
          </div>

          {/* Building grid */}
          {Array.isArray(profile.buildings) && profile.buildings.length > 0 ? (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 8,
              padding: '0 12px',
            }}>
              {profile.buildings.map(building => (
                <BuildingCard
                  key={building.canonical_bld_id}
                  building={building}
                  onClick={id => navigate('/buildings/' + id)}
                />
              ))}
            </div>
          ) : (
            <p style={{
              padding: '40px 20px',
              color: 'var(--color-text-muted)',
              fontSize: 14,
              textAlign: 'center',
              margin: 0,
            }}>
              등록된 건물이 없어요.
            </p>
          )}
        </>
      )}
    </div>
  )
}
