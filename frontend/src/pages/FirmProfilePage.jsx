import { useState, useEffect, Fragment } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getOffice } from '../api/client.js'

// TODO: Replace with API call
// TODO(claude): fetch office by officeId — GET /api/v1/offices/${officeId}/
const PROJECT_NAMES = [
  'Seattle Central Library', 'Taipei Performing Arts Center', 'Casa da Musica', 'CCTV Headquarters',
  'Qatar National Library', 'Fondazione Prada', 'De Rotterdam', 'Milstein Hall',
  'Seoul National University Museum of Art', 'IIT McCormick Tribune Campus Center',
]
const PROJECT_IMAGES = [
  'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&q=80',
  'https://images.unsplash.com/photo-1513694203232-719a280e022f?w=800&q=80',
  'https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800&q=80',
  'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80',
  'https://images.unsplash.com/photo-1511818966892-d7d671e672a2?w=800&q=80',
  'https://images.unsplash.com/photo-1524815340653-53d719ce3660?w=800&q=80',
]
const PROJECT_CITIES = [
  'Seattle', 'Taipei', 'Porto', 'Beijing', 'Doha', 'Milan',
  'Rotterdam', 'Ithaca', 'Seoul', 'Chicago',
]
// Stable, hardcoded years (no Math.random() to avoid re-render jitter)
const PROJECT_YEARS = [
  2004, 2022, 2005, 2012, 2018, 2018, 2013, 2011, 2015, 2003,
  2020, 2007, 2009, 2014, 2016, 2019, 2008, 2017, 2021, 2006,
  2023, 2010, 2002, 2024,
]
// Programs use the normalized vocabulary from CLAUDE.md (Housing, Office, Museum, etc.)
const PROJECT_PROGRAMS = [
  'Public', 'Public', 'Museum', 'Office', 'Public', 'Museum',
  'Mixed Use', 'Education', 'Museum', 'Education',
]

const MOCK_OFFICE = {
  office_id: 'OFF001',
  name: 'OMA',
  verified: true,
  website_url: 'https://oma.com',
  contact_email: 'info@oma.com',
  description: 'Office for Metropolitan Architecture is a leading international partnership practicing architecture, urbanism, and cultural analysis. Founded in 1975, OMA combines visionary design with rigorous research to shape the contemporary built environment.',
  logo_url: 'https://images.unsplash.com/photo-1616423640778-28d1b53229bd?w=400&q=80',
  location: 'Rotterdam, Netherlands',
  founded_year: 1975,
  follower_count: 1247,        // TODO(claude): backend should add follower_count to /api/v1/offices/${officeId}/ Firm/Office Profile contract
  following_count: 38,         // TODO(claude): backend should add following_count to /api/v1/offices/${officeId}/ Firm/Office Profile contract
  projects: Array.from({ length: 24 }).map((_, i) => ({
    building_id: `B${String(i + 1).padStart(5, '0')}`,
    name_en: PROJECT_NAMES[i % 10] + (i >= 10 ? ` Phase ${Math.floor(i / 10) + 1}` : ''),
    image_url: PROJECT_IMAGES[i % 6],
    year: PROJECT_YEARS[i],
    program: PROJECT_PROGRAMS[i % 10],
    city: PROJECT_CITIES[i % 10],
  })),
  articles: [
    {
      title: 'OMA Unveils New Campus Design for Singapore Riverside',
      source: 'ArchDaily',
      url: 'https://archdaily.com/',
      date: '2025-01-15',
    },
    {
      title: 'Rem Koolhaas on the future of urbanism and the post-pandemic city',
      source: 'Dezeen',
      url: 'https://dezeen.com/',
      date: '2024-11-20',
    },
    {
      title: 'Inside OMA’s latest cultural intervention in Doha',
      source: 'Wallpaper*',
      url: 'https://wallpaper.com/',
      date: '2024-09-08',
    },
  ],
}


/**
 * DescriptionAboutFlipCard — §3.5.4 Hero Flip variant (text-on-surface, profile pages)
 *   Front: italic description 3-line clamp + "tap to reveal more" caption
 *   Back: full description overflow-y auto + footer row with Founded year + Location
 *   Internal radial-gradient pink glow. Lift YES, border YES (text-on-surface needs containment).
 */
function DescriptionAboutFlipCard({ description, foundedYear, location }) {
  const [isFlipped, setIsFlipped] = useState(false)
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div
      style={{
        perspective: '1200px',
        width: '100%',
        minHeight: 180,
        cursor: 'pointer',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
        marginTop: 18, marginBottom: 18,
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={(e) => {
        if (e.target.closest('button')) return
        setIsFlipped(f => !f)
      }}
    >
      <div style={{
        width: '100%', minHeight: 180,
        position: 'relative',
        transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        transformStyle: 'preserve-3d',
        transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
      }}>
        {/* FRONT — italic description 3-line clamp + "tap to reveal more" */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          borderRadius: 20,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          padding: '20px 22px',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
          minHeight: 180,
        }}>
          {/* Internal radial-gradient pink glow */}
          <div style={{
            position: 'absolute', top: -40, right: -40,
            width: 160, height: 160, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(236,72,153,0.18), transparent 70%)',
            pointerEvents: 'none',
          }} />
          <p style={{
            position: 'relative', zIndex: 1,
            margin: 0,
            color: 'var(--color-text-dim)', fontSize: 15, lineHeight: 1.6,
            fontStyle: 'italic', fontWeight: 500,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {description}
          </p>
          <span style={{
            position: 'relative', zIndex: 1,
            alignSelf: 'flex-end',
            color: 'var(--color-text-dimmer)', fontSize: 10, fontWeight: 600,
            letterSpacing: '0.04em', textTransform: 'uppercase',
            marginTop: 12,
          }}>
            tap to reveal more
          </span>
        </div>

        {/* BACK — full description + footer (Founded + Location) */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          transform: 'rotateY(180deg)',
          borderRadius: 20,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          padding: '20px 22px',
          display: 'flex', flexDirection: 'column',
          boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
          minHeight: 180,
        }}>
          {/* Internal radial-gradient pink glow */}
          <div style={{
            position: 'absolute', top: -40, right: -40,
            width: 160, height: 160, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(236,72,153,0.18), transparent 70%)',
            pointerEvents: 'none',
          }} />
          <p style={{
            position: 'relative', zIndex: 1,
            margin: '0 0 14px',
            color: 'var(--color-text-2)', fontSize: 13, lineHeight: 1.55,
            fontWeight: 500,
            flex: 1,
            overflowY: 'auto',
          }}>
            {description}
          </p>
          {/* Footer meta — Founded + Location */}
          <div style={{
            position: 'relative', zIndex: 1,
            display: 'flex', flexWrap: 'wrap', gap: 10,
            paddingTop: 12,
            borderTop: '1px solid var(--color-border-soft)',
          }}>
            {foundedYear && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                color: 'var(--color-text-dim)', fontSize: 12, fontWeight: 600,
              }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                  <line x1="16" y1="2" x2="16" y2="6"></line>
                  <line x1="8" y1="2" x2="8" y2="6"></line>
                  <line x1="3" y1="10" x2="21" y2="10"></line>
                </svg>
                Founded {foundedYear}
              </span>
            )}
            {location && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                color: 'var(--color-text-dim)', fontSize: 12, fontWeight: 600,
              }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                  <circle cx="12" cy="10" r="3"></circle>
                </svg>
                {location}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


export default function FirmProfilePage() {
  const { officeId } = useParams()
  const navigate = useNavigate()

  const [office, setOffice] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [isFollowing, setIsFollowing] = useState(false)
  const [followerCount, setFollowerCount] = useState(0)

  useEffect(() => {
    if (!officeId) {
      setLoading(false)
      setError('No office ID found.')
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getOffice(officeId)
      .then(data => {
        if (cancelled) return
        // articles[] absent (Phase 18 External territory) — default to []
        setOffice({ ...data, articles: data.articles || [] })
        setIsFollowing(false)  // is_following: Phase 15 SOC1 territory
        setFollowerCount(data.follower_count || 0)
      })
      .catch(err => {
        if (cancelled) return
        setError(err.message || 'Failed to load office profile.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [officeId])

  function handleToggleFollow() {
    // TODO(claude): POST /api/v1/offices/{id}/follow/ or DELETE
    setIsFollowing(f => !f)
    setFollowerCount(prev => isFollowing ? prev - 1 : prev + 1)
  }

  function handleMessage() {
    // TODO(claude): wire DM endpoint — POST /api/v1/messages/ or similar
  }

  if (loading) {
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 14,
      }}>
        Loading office profile...
      </div>
    )
  }

  if (error || !office) {
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 14,
      }}>
        {error || 'Office not found.'}
      </div>
    )
  }

  return (
    <div
      style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        overflowY: 'auto',
        background: 'var(--color-bg)',
        paddingBottom: 'calc(80px + env(safe-area-inset-bottom, 0px))',
        position: 'relative',
      }}
    >
      {/* Ambient glow — single brand-pink, no purple */}
      <div
        style={{
          position: 'absolute',
          top: '-10%',
          left: '-10%',
          width: '120%',
          height: '50%',
          background: 'radial-gradient(circle at 50% 0%, rgba(236,72,153,0.10) 0%, transparent 70%)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      {/* Sticky Header — back left, title center, symmetric placeholder right (mirrors UserProfile) */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          background: 'var(--color-header-bg, rgba(15, 15, 15, 0.72))',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderBottom: '1px solid var(--color-border-soft)',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <button
          type="button"
          onClick={() => navigate(-1)}
          aria-label="Go back"
          style={{
            width: 44,
            height: 44,
            minWidth: 44,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'transparent',
            border: 'none',
            color: 'var(--color-text)',
            cursor: 'pointer',
            borderRadius: 12,
            transition: 'background 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
            padding: 0,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--color-surface-2, rgba(255,255,255,0.05))'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent'
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
        </button>

        <h2
          style={{
            color: 'var(--color-text)',
            fontSize: 17,
            fontWeight: 700,
            margin: 0,
            letterSpacing: '-0.01em',
            flex: 1,
            textAlign: 'center',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          Profile
        </h2>

        {/* Symmetric placeholder — keeps title optically centered */}
        <div style={{ width: 44, height: 44, flexShrink: 0 }} aria-hidden="true" />
      </div>

      {/* Unified responsive container (max-width 1100) — mirrors UserProfile */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          maxWidth: 1100,
          margin: '0 auto',
          padding: '32px 20px 40px',
        }}
      >
        {/* HERO BLOCK — narrower nested column (max-width 480) — mirrors UserProfile */}
        <div style={{ maxWidth: 480, margin: '0 auto 36px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>

            {/* Logo + brand-pink halo glow (matches UserProfile avatar pattern) */}
            {office.logo_url ? (
              <div style={{ position: 'relative', marginBottom: 18 }}>
                <div
                  style={{
                    position: 'absolute',
                    inset: -6,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                    opacity: 0.55,
                    filter: 'blur(12px)',
                  }}
                  aria-hidden="true"
                />
                <img
                  src={office.logo_url}
                  alt={`${office.name} logo`}
                  style={{
                    position: 'relative',
                    zIndex: 2,
                    width: 108,
                    height: 108,
                    borderRadius: '50%',
                    objectFit: 'cover',
                    background: '#fff',
                    border: '2px solid var(--color-border-soft)',
                    display: 'block',
                  }}
                />
              </div>
            ) : (
              <div
                style={{
                  width: 108,
                  height: 108,
                  borderRadius: '50%',
                  background: 'var(--color-surface)',
                  border: '2px solid var(--color-border-soft)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: 18,
                }}
              >
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>
                  <line x1="9" y1="22" x2="15" y2="22"></line>
                </svg>
              </div>
            )}

            {/* Name + verified mark inline (the Instagram blue-mark equivalent) */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                marginBottom: 8,
                flexWrap: 'wrap',
              }}
            >
              <h1
                style={{
                  color: 'var(--color-text)',
                  fontSize: 28,
                  fontWeight: 700,
                  margin: 0,
                  lineHeight: 1.2,
                  letterSpacing: '-0.01em',
                }}
              >
                {office.name}
              </h1>
              {office.verified && (
                <span
                  title="Verified office"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 22,
                    height: 22,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                    flexShrink: 0,
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                </span>
              )}
            </div>

            {/* §3.7 Compact stats row */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              gap: 0, marginTop: 14, marginBottom: 4,
            }}>
              {[
                { count: (office.projects || []).length, label: 'Projects' },
                { count: followerCount, label: 'Followers' },
                { count: office.following_count || 0, label: 'Following' },
              ].map((stat, i, arr) => (
                <Fragment key={stat.label}>
                  <button
                    onClick={() => {
                      if (stat.label === 'Projects') {
                        // TODO(claude): scroll to projects section or navigate to filtered project list
                      } else if (stat.label === 'Followers') {
                        // TODO(claude): navigate to office followers/following list — GET /api/v1/offices/{id}/{followers|following}/
                      } else {
                        // TODO(claude): navigate to office followers/following list — GET /api/v1/offices/{id}/{followers|following}/
                      }
                    }}
                    style={{
                      flex: '0 0 auto',
                      background: 'transparent', border: 'none', cursor: 'pointer',
                      padding: '6px 18px', minHeight: 44,
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                      fontFamily: 'inherit', color: 'inherit',
                    }}
                  >
                    <span style={{ color: 'var(--color-text)', fontSize: 18, fontWeight: 700, lineHeight: 1 }}>
                      {stat.count}
                    </span>
                    <span style={{ color: 'var(--color-text-dim)', fontSize: 12, fontWeight: 500 }}>
                      {stat.label}
                    </span>
                  </button>
                  {i < arr.length - 1 && (
                    <div style={{ width: 1, height: 28, background: 'var(--color-border)' }} />
                  )}
                </Fragment>
              ))}
            </div>

            {/* §3.5.4 Hero Flip — DescriptionAboutFlipCard */}
            <DescriptionAboutFlipCard
              description={office.description}
              foundedYear={office.founded_year}
              location={office.location}
            />

            {/* §3.6 Profile Action Row — always shown for office profiles */}
            <div style={{ display: 'flex', gap: 10, marginTop: 14, width: '100%' }}>
              <button
                onClick={handleToggleFollow}
                onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)' }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)' }}
                onMouseDown={(e) => { e.currentTarget.style.transform = 'scale(0.98)' }}
                onMouseUp={(e) => { e.currentTarget.style.transform = 'translateY(-1px)' }}
                style={{
                  flex: 1,
                  minHeight: 44, padding: '12px 18px',
                  borderRadius: 12,
                  background: isFollowing ? 'var(--color-surface-2)' : 'linear-gradient(135deg, #ec4899, #f43f5e)',
                  color: isFollowing ? 'var(--color-text-2)' : '#fff',
                  border: isFollowing ? '1px solid var(--color-border)' : 'none',
                  fontSize: 14, fontWeight: 700,
                  cursor: 'pointer', fontFamily: 'inherit',
                  boxShadow: isFollowing ? 'none' : '0 8px 22px rgba(236,72,153,0.32)',
                  transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), background 0.2s, color 0.2s, box-shadow 0.2s',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                }}
              >
                {isFollowing ? (
                  <>Following<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg></>
                ) : 'Follow'}
              </button>
              <button
                onClick={handleMessage}
                aria-label="Message"
                style={{
                  width: 44, height: 44, minWidth: 44, flexShrink: 0,
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 12, cursor: 'pointer',
                  color: 'var(--color-text-2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'border-color 0.18s, color 0.18s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(236,72,153,0.45)'; e.currentTarget.style.color = '#ec4899' }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text-2)' }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </button>
            </div>

            {/* Action pills — Website + Email (User-style icon-pills, NOT chunky buttons) */}
            {(office.website_url || office.contact_email) && (
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
                {office.website_url && (
                  <a
                    href={office.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 7,
                      padding: '10px 14px', borderRadius: 999,
                      background: 'var(--color-surface-2, rgba(255,255,255,0.04))',
                      border: '1px solid var(--color-border-soft)',
                      color: 'var(--color-text-2)',
                      textDecoration: 'none', fontSize: 13, fontWeight: 600,
                      transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.18s, color 0.18s',
                      minHeight: 44,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'translateY(-1px)'
                      e.currentTarget.style.borderColor = 'rgba(236,72,153,0.45)'
                      e.currentTarget.style.color = '#ec4899'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)'
                      e.currentTarget.style.borderColor = 'var(--color-border-soft)'
                      e.currentTarget.style.color = 'var(--color-text-2)'
                    }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="2" y1="12" x2="22" y2="12"></line>
                      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                    </svg>
                    Website
                  </a>
                )}
                {office.contact_email && (
                  <a
                    href={`mailto:${office.contact_email}`}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 7,
                      padding: '10px 14px', borderRadius: 999,
                      background: 'var(--color-surface-2, rgba(255,255,255,0.04))',
                      border: '1px solid var(--color-border-soft)',
                      color: 'var(--color-text-2)',
                      textDecoration: 'none', fontSize: 13, fontWeight: 600,
                      transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.18s, color 0.18s',
                      minHeight: 44,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'translateY(-1px)'
                      e.currentTarget.style.borderColor = 'rgba(236,72,153,0.45)'
                      e.currentTarget.style.color = '#ec4899'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)'
                      e.currentTarget.style.borderColor = 'var(--color-border-soft)'
                      e.currentTarget.style.color = 'var(--color-text-2)'
                    }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                      <polyline points="22,6 12,13 2,6"></polyline>
                    </svg>
                    Email
                  </a>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Projects section header — same style as UserProfile "Curated Boards · N" */}
        <div style={{
          display: 'flex', alignItems: 'baseline', gap: 12,
          marginBottom: 20, padding: '0 4px',
        }}>
          <h3 style={{
            color: 'var(--color-text)', fontSize: 20, fontWeight: 700,
            margin: 0, letterSpacing: '-0.01em',
          }}>
            Projects
          </h3>
          <span style={{
            color: 'var(--color-text-dimmer)', fontSize: 13, fontWeight: 600,
          }}>
            {(office.projects || []).length}
          </span>
        </div>

        {/* Projects grid — same unified container, responsive auto-fill, same column breakpoint as UserProfile boards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 20,
            marginBottom: 36,
          }}
        >
          {(office.projects || []).map((project) => (
            <ProjectCard key={project.building_id} project={project} />
          ))}
        </div>

        {/* Articles */}
        {office.articles?.length > 0 && (
          <section>
            <div style={{
              display: 'flex', alignItems: 'baseline', gap: 12,
              marginBottom: 20, padding: '0 4px',
            }}>
              <h3 style={{
                color: 'var(--color-text)', fontSize: 20, fontWeight: 700,
                margin: 0, letterSpacing: '-0.01em',
              }}>
                Featured Articles
              </h3>
              <span style={{
                color: 'var(--color-text-dimmer)', fontSize: 13, fontWeight: 600,
              }}>
                {office.articles.length}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {office.articles.map((article, idx) => (
                <ArticleCard key={`${article.url}-${idx}`} article={article} />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

/* ----------------------------- Sub-components ----------------------------- */

/**
 * InfoCol — local primitive for §3.5.2 RICH PATTERN 2-col info grid.
 *   Caps label (10/600 uppercase 0.06em) + single-line ellipsis value (13/600 white).
 */
function InfoCol({ label, value }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      <span style={{
        color: 'rgba(255,255,255,0.5)',
        fontSize: 10, fontWeight: 600,
        letterSpacing: '0.06em', textTransform: 'uppercase',
        marginBottom: 2,
      }}>
        {label}
      </span>
      <span style={{
        color: '#fff', fontSize: 13, fontWeight: 600,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {value}
      </span>
    </div>
  )
}


/**
 * ProjectCard — image-overlay card per DESIGN.md §3.5.1 + §3.5.2 RICH PATTERN.
 *   - No default border (transparent), hover lifts -4px and adds pink border (§3.5.1).
 *   - Title 18/700 + "Project" sub-italic + divider + 2-col CITY/YEAR grid (§3.5.2 RICH).
 *   - NO corner chip per §3.5.3 — program is metadata, not status; chips are reserved for
 *     binary status state. CITY+YEAR in the info grid carry the relevant metadata.
 */
function ProjectCard({ project }) {
  return (
    <div
      // TODO(claude): navigate to project detail on click — e.g. navigate(`/buildings/${project.building_id}`)
      style={{
        position: 'relative',
        borderRadius: 20,
        overflow: 'hidden',
        cursor: 'pointer',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid transparent',          // §3.5.1: NO default light border
        aspectRatio: '4 / 5',
        boxShadow: '0 10px 25px rgba(0,0,0,0.3)', // §3.5.1 mandatory depth
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
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
      <img
        src={project.image_url}
        alt={project.name_en}
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
      {/* §3.5.1 mandatory bottom gradient overlay */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.4) 50%, transparent 100%)',
        }}
        aria-hidden="true"
      />

      {/* §3.5.2 RICH PATTERN: title + "Project" sub-italic + divider + 2-col CITY/YEAR grid */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '16px 18px 20px',
        }}
      >
        <h4
          style={{
            color: '#fff',
            fontSize: 18,
            fontWeight: 700,
            margin: '0 0 3px',
            lineHeight: 1.3,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {project.name_en}
        </h4>
        <p
          style={{
            color: 'rgba(255,255,255,0.55)',
            fontSize: 12,
            fontStyle: 'italic',
            margin: '0 0 12px',
          }}
        >
          Project
        </p>
        <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12 }} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
          <InfoCol label="CITY" value={project.city} />
          <InfoCol label="YEAR" value={project.year} />
        </div>
      </div>
    </div>
  )
}


/**
 * ArticleCard — list-style card with §3.5.1 hover behavior (no default border, hover lift)
 *   Content-specific differentiator: left accent border + source pill (preserved from prior redesign).
 */
function ArticleCard({ article }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noreferrer"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '18px 20px 18px 22px',
        background: 'var(--color-surface)',
        border: '1px solid transparent',   // §3.5.1: NO default border
        borderLeft: '3px solid #ec4899',    // content-specific accent (articles only)
        borderRadius: 14,
        textDecoration: 'none',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)'
        e.currentTarget.style.borderColor = 'rgba(236,72,153,0.55)'
        e.currentTarget.style.borderLeftColor = '#f43f5e'
        e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.3)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.borderColor = 'transparent'
        e.currentTarget.style.borderLeftColor = '#ec4899'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      <p
        style={{
          color: 'var(--color-text)',
          fontSize: 15,
          fontWeight: 600,
          margin: 0,
          lineHeight: 1.4,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {article.title}
      </p>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            background: 'rgba(236,72,153,0.12)',
            color: '#ec4899',
            fontSize: 11,
            fontWeight: 600,
            padding: '4px 10px',
            borderRadius: 999,
            letterSpacing: '0.02em',
            textTransform: 'uppercase',
          }}
        >
          {article.source}
        </span>
        <span
          style={{
            color: 'var(--color-text-dimmer)',
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {article.date}
        </span>
      </div>
    </a>
  )
}
