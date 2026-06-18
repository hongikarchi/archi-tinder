import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getUserSavedStudios } from '../api/client.js'

/* ── Placeholder SVG icons ──────────────────────────────────────────────── */

function BuildingPlaceholderSmall() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-muted)', opacity: 0.5 }}>
      <rect x="3" y="9" width="13" height="13" rx="1" />
      <path d="M16 9V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v5" />
      <line x1="9" y1="21" x2="9" y2="15" />
      <line x1="13" y1="21" x2="13" y2="15" />
    </svg>
  )
}

function BuildingPlaceholderLarge() {
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

function BuildingIconEmpty() {
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

/* ── OfficeCard ─────────────────────────────────────────────────────────── */

function OfficeCard({ office, onClick }) {
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

      {/* Cover image */}
      <div style={{
        width: '100%',
        aspectRatio: '16 / 10',
        borderRadius: 12,
        overflow: 'hidden',
        background: 'var(--color-surface-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
        className="office-card-img-wrap"
      >
        {office.cover_image_url ? (
          <img
            src={office.cover_image_url}
            alt={office.name}
            loading="lazy"
            style={{
              width: '100%', height: '100%', objectFit: 'cover', display: 'block',
              transition: 'transform 220ms cubic-bezier(0.4,0,0.2,1)',
            }}
            className="office-card-img"
          />
        ) : (
          <BuildingPlaceholderLarge />
        )}
      </div>
    </div>
  )
}

/* ── Skeleton card ──────────────────────────────────────────────────────── */

function SkeletonCard() {
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
  const [studios, setStudios] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  function fetchStudios() {
    const rawUser = sessionStorage.getItem('archithon_user')
    const userId = rawUser ? rawUser.trim() : null
    if (!userId) {
      setError('로그인이 필요해요.')
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
        setError(err?.message || '데이터를 불러오지 못했어요.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }

  useEffect(() => {
    const cleanup = fetchStudios()
    return cleanup
  }, [])

  return (
    <>
      {/* CSS for card hover — CSS :hover pseudo-class per DESIGN.md §4 */}
      <style>{`
        .office-card-img-wrap:hover .office-card-img {
          transform: scale(1.02);
        }
      `}</style>

      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        overflowY: 'auto',
        background: '#0a0a0a',
        paddingBottom: 'calc(80px + env(safe-area-inset-bottom, 0px))',
      }}>
        {/* Sticky header */}
        <div style={{
          position: 'sticky', top: 0, zIndex: 10,
          background: 'rgba(10,10,10,0.85)',
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
            /* Skeleton (§8.8) */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>
              {[0, 1, 2].map(i => <SkeletonCard key={i} />)}
            </div>
          ) : error ? (
            /* Inline error (§8.9 tier 2) */
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
                다시 시도
              </button>
            </div>
          ) : studios.length === 0 ? (
            /* Empty state (§8.9 tier 1) */
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              padding: '80px 20px', gap: 16, textAlign: 'center',
            }}>
              <BuildingIconEmpty />
              <p style={{ color: 'var(--color-text)', fontSize: 16, fontWeight: 600, margin: 0 }}>
                저장한 오피스가 없어요
              </p>
              <p style={{ color: 'var(--color-text-muted)', fontSize: 13, fontWeight: 400, margin: 0 }}>
                건축가 프로필에서 팔로우하면 여기에 표시돼요
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
                건축가 탐색하기
              </button>
            </div>
          ) : (
            /* Feed list — gap 40px between cards per spec */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>
              {studios.map((office, i) => (
                <OfficeCard
                  key={office.architect_id || i}
                  office={office}
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
