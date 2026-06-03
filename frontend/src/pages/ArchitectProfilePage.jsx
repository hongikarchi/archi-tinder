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

function SkeletonHeader() {
  return (
    <div style={{ background: 'linear-gradient(180deg, rgba(236,72,153,0.08) 0%, transparent 100%)', padding: '24px 16px 20px', textAlign: 'center' }}>
      <div style={{
        width: 108,
        height: 108,
        borderRadius: '50%',
        background: 'var(--color-surface-2)',
        margin: '0 auto 18px',
      }} />
      <div style={{ width: '50%', height: 22, borderRadius: 8, background: 'var(--color-surface-2)', margin: '0 auto 10px' }} />
      <div style={{ width: '25%', height: 14, borderRadius: 999, background: 'var(--color-surface-2)', margin: '0 auto' }} />
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

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({ title: profile?.name || 'ArchiTinder', url: window.location.href }).catch(() => {})
    }
  }

  const handleWebsite = () => {
    const url = profile?.website
    if (url && /^https?:\/\//i.test(url)) {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }

  const handleContact = () => {
    const email = profile?.email
    if (email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      window.open('mailto:' + email)
    }
  }

  const btnBase = {
    flex: 1,
    minHeight: 44,
    padding: '10px 12px',
    borderRadius: 10,
    border: '1px solid var(--color-border-soft)',
    background: 'var(--color-surface)',
    color: 'var(--color-text)',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    fontFamily: 'inherit',
  }

  return (
    <div style={{
      height: 'calc(100vh - 64px)',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(80px + env(safe-area-inset-bottom, 0px))',
    }}>
      {/* Sticky top header */}
      <div style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        background: 'var(--color-bg)',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
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
        </button>

        <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-text)' }}>
          Office
        </span>

        <button
          className={styles.iconBtn}
          onClick={handleShare}
          type="button"
          aria-label="공유"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="18" cy="5" r="3" />
            <circle cx="6" cy="12" r="3" />
            <circle cx="18" cy="19" r="3" />
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
          </svg>
        </button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <>
          <SkeletonHeader />
          {/* Stats bar skeleton */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 40, padding: '12px 16px 16px' }}>
            <div style={{ width: 70, height: 40, borderRadius: 8, background: 'var(--color-surface-2)' }} />
            <div style={{ width: 70, height: 40, borderRadius: 8, background: 'var(--color-surface-2)' }} />
          </div>
          {/* Action buttons skeleton */}
          <div style={{ display: 'flex', gap: 8, padding: '0 16px 16px' }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{ flex: 1, height: 44, borderRadius: 10, background: 'var(--color-surface-2)' }} />
            ))}
          </div>
          <SkeletonGrid />
        </>
      )}

      {/* Error state */}
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
            불러오는 데 실패했어요.
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

      {/* Not found state */}
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
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M9 9h6M9 12h6M9 15h6" />
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

      {/* Loaded state */}
      {!isLoading && !error && profile && (
        <>
          {/* Profile hero area — pink gradient background */}
          <div style={{
            background: 'linear-gradient(180deg, rgba(236,72,153,0.12) 0%, transparent 100%)',
            padding: '24px 16px 20px',
            textAlign: 'center',
          }}>
            {/* Logo with pink halo */}
            <div style={{ position: 'relative', display: 'inline-block', marginBottom: 18 }}>
              {/* halo */}
              <div style={{
                position: 'absolute',
                inset: -6,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                opacity: 0.55,
                filter: 'blur(12px)',
              }} aria-hidden="true" />
              {profile.logo_url ? (
                <img
                  src={profile.logo_url}
                  alt={profile.name}
                  style={{
                    position: 'relative',
                    zIndex: 2,
                    width: 108,
                    height: 108,
                    borderRadius: '50%',
                    border: '2px solid var(--color-border-soft)',
                    objectFit: 'cover',
                    background: 'var(--color-surface)',
                    display: 'block',
                  }}
                />
              ) : (
                <div style={{
                  position: 'relative',
                  zIndex: 2,
                  width: 108,
                  height: 108,
                  borderRadius: '50%',
                  background: 'var(--color-surface)',
                  border: '2px solid var(--color-border-soft)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <path d="M9 9h6M9 12h6M9 15h6" />
                  </svg>
                </div>
              )}
            </div>

            {/* Office name */}
            <h1 style={{
              fontSize: 'clamp(20px, 5vw, 24px)',
              fontWeight: 700,
              color: 'var(--color-text)',
              margin: '0 0 6px',
              lineHeight: 1.2,
            }}>
              {profile.name}
            </h1>

            {/* Country */}
            {profile.primary_country && (
              <p style={{
                margin: 0,
                fontSize: 14,
                color: 'var(--color-text-muted)',
              }}>
                {profile.primary_country}
              </p>
            )}
          </div>

          {/* Stats bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '12px 16px 16px',
          }}>
            <div style={{ textAlign: 'center', padding: '0 24px' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text)' }}>
                {profile.building_count != null ? profile.building_count.toLocaleString() : '—'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
                Buildings
              </div>
            </div>
            <div style={{
              width: 1,
              height: 28,
              background: 'var(--color-border)',
            }} />
            <div style={{ textAlign: 'center', padding: '0 24px' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text)' }}>
                {profile.saved_count != null ? profile.saved_count.toLocaleString() : '—'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
                Saved
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 8, padding: '0 16px 16px' }}>
            {/* Follow — UI ready, backend TBD */}
            <button
              type="button"
              className={styles.actionBtn}
              style={{
                ...btnBase,
                background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                color: '#fff',
                border: 'none',
                boxShadow: '0 4px 14px rgba(236,72,153,0.28)',
              }}
              aria-label="팔로우"
            >
              Follow
            </button>

            {/* Website — show only when available */}
            {profile.website && (
              <button
                type="button"
                className={styles.actionBtn}
                style={btnBase}
                onClick={handleWebsite}
                aria-label="웹사이트 열기"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="2" y1="12" x2="22" y2="12" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                </svg>
                Website
              </button>
            )}

            {/* Contact — show only when email available */}
            {profile.email && (
              <button
                type="button"
                className={styles.actionBtn}
                style={btnBase}
                onClick={handleContact}
                aria-label="이메일 보내기"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                  <polyline points="22,6 12,13 2,6" />
                </svg>
                Contact
              </button>
            )}
          </div>

          {/* Description card */}
          {profile.description && (
            <div style={{
              margin: '0 16px 16px',
              padding: 16,
              borderRadius: 12,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border-soft)',
            }}>
              <p style={{
                margin: 0,
                fontSize: 14,
                color: 'var(--color-text)',
                lineHeight: 1.6,
              }}>
                {profile.description}
              </p>
            </div>
          )}

          {/* Buildings section */}
          {Array.isArray(profile.buildings) && profile.buildings.length > 0 && (
            <>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '0 16px 12px',
              }}>
                <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text)' }}>
                  Buildings
                </span>
                <span style={{
                  padding: '2px 10px',
                  borderRadius: 999,
                  background: 'var(--color-surface-2)',
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--color-text-muted)',
                }}>
                  {profile.building_count != null ? profile.building_count.toLocaleString() : profile.buildings.length}
                </span>
              </div>
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
            </>
          )}

          {(!Array.isArray(profile.buildings) || profile.buildings.length === 0) && (
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
