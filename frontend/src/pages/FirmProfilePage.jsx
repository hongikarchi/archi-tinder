import { useParams, useNavigate } from 'react-router-dom'

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

export default function FirmProfilePage() {
  // eslint-disable-next-line no-unused-vars
  const { officeId } = useParams()
  const navigate = useNavigate()

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
          background: 'radial-gradient(circle at 50% 0%, rgba(236,72,153,0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      {/* Sticky Header with back button */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          background: 'rgba(15, 15, 15, 0.72)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderBottom: '1px solid var(--color-border-soft)',
          padding: '8px 12px',
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
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'transparent',
            border: 'none',
            color: 'var(--color-text-dim)',
            cursor: 'pointer',
            borderRadius: 10,
            transition: 'color 0.18s cubic-bezier(0.4, 0, 0.2, 1), background 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
            padding: 0,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = '#ec4899'
            e.currentTarget.style.background = 'rgba(236,72,153,0.08)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--color-text-dim)'
            e.currentTarget.style.background = 'transparent'
          }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
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
            letterSpacing: '0.01em',
            flex: 1,
            textAlign: 'center',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          Firm Profile
        </h2>

        {/* Symmetric placeholder so title stays optically centered */}
        <div style={{ width: 44, height: 44, flexShrink: 0 }} aria-hidden="true" />
      </div>

      {/* Page content — single responsive container */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          maxWidth: 1100,
          margin: '0 auto',
          padding: '32px 20px 48px',
        }}
      >
        {/* Hero — constrained inside the wider container */}
        <section
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            maxWidth: 560,
            margin: '0 auto 56px',
          }}
        >
          {/* Logo + brand-pink glow */}
          {MOCK_OFFICE.logo_url ? (
            <div style={{ position: 'relative', marginBottom: 24 }}>
              <div
                style={{
                  position: 'absolute',
                  inset: -16,
                  borderRadius: '50%',
                  background: '#ec4899',
                  opacity: 0.4,
                  filter: 'blur(20px)',
                  zIndex: 0,
                }}
                aria-hidden="true"
              />
              <img
                src={MOCK_OFFICE.logo_url}
                alt={`${MOCK_OFFICE.name} logo`}
                style={{
                  position: 'relative',
                  zIndex: 1,
                  width: 104,
                  height: 104,
                  borderRadius: 24,
                  objectFit: 'cover',
                  background: '#fff',
                  border: '1px solid rgba(255,255,255,0.18)',
                  display: 'block',
                }}
              />
            </div>
          ) : (
            <div
              style={{
                width: 104,
                height: 104,
                borderRadius: 24,
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border-soft)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 24,
              }}
            >
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>
                <line x1="9" y1="22" x2="15" y2="22"></line>
                <line x1="12" y1="6" x2="12" y2="6.01"></line>
                <line x1="12" y1="10" x2="12" y2="10.01"></line>
                <line x1="12" y1="14" x2="12" y2="14.01"></line>
              </svg>
            </div>
          )}

          {/* Name + verified */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              marginBottom: 16,
              flexWrap: 'wrap',
            }}
          >
            <h1
              style={{
                color: 'var(--color-text)',
                fontSize: 34,
                fontWeight: 900,
                margin: 0,
                lineHeight: 1.15,
                letterSpacing: '-0.02em',
              }}
            >
              {MOCK_OFFICE.name}
            </h1>
            {MOCK_OFFICE.verified && (
              <span
                title="Verified office"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 26,
                  height: 26,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                  flexShrink: 0,
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </span>
            )}
          </div>

          {/* Meta chips — wraps gracefully on narrow viewports */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'center',
              gap: 8,
              marginBottom: 24,
            }}
          >
            <Chip>
              <ChipIcon>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                  <circle cx="12" cy="10" r="3"></circle>
                </svg>
              </ChipIcon>
              {MOCK_OFFICE.location}
            </Chip>
            <Chip>
              <ChipIcon>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                  <line x1="16" y1="2" x2="16" y2="6"></line>
                  <line x1="8" y1="2" x2="8" y2="6"></line>
                  <line x1="3" y1="10" x2="21" y2="10"></line>
                </svg>
              </ChipIcon>
              Est. {MOCK_OFFICE.founded_year}
            </Chip>
            <Chip>
              <ChipIcon>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 21h18"></path>
                  <path d="M5 21V7l7-4 7 4v14"></path>
                  <path d="M9 9h0M9 13h0M9 17h0M15 9h0M15 13h0M15 17h0"></path>
                </svg>
              </ChipIcon>
              {MOCK_OFFICE.projects.length} projects
            </Chip>
          </div>

          {/* Description */}
          <p
            style={{
              color: 'var(--color-text-dim)',
              fontSize: 15,
              lineHeight: 1.65,
              margin: '0 0 28px',
              fontWeight: 400,
              maxWidth: 520,
            }}
          >
            {MOCK_OFFICE.description}
          </p>

          {/* Action buttons */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'center',
              gap: 12,
              width: '100%',
            }}
          >
            {MOCK_OFFICE.website_url && (
              <ActionButton
                href={MOCK_OFFICE.website_url}
                primary
                icon={
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="2" y1="12" x2="22" y2="12"></line>
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                  </svg>
                }
              >
                Website
              </ActionButton>
            )}
            {MOCK_OFFICE.contact_email && (
              <ActionButton
                href={`mailto:${MOCK_OFFICE.contact_email}`}
                icon={
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                    <polyline points="22,6 12,13 2,6"></polyline>
                  </svg>
                }
              >
                Email
              </ActionButton>
            )}
          </div>
        </section>

        {/* Projects */}
        <section style={{ marginBottom: 56 }}>
          <SectionHeader title="Projects" count={MOCK_OFFICE.projects.length} />
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
              gap: 18,
            }}
          >
            {MOCK_OFFICE.projects.map((project) => (
              <ProjectCard key={project.building_id} project={project} />
            ))}
          </div>
        </section>

        {/* Articles */}
        {MOCK_OFFICE.articles?.length > 0 && (
          <section>
            <SectionHeader title="Featured Articles" count={MOCK_OFFICE.articles.length} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {MOCK_OFFICE.articles.map((article, idx) => (
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

function Chip({ children }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.08)',
        padding: '6px 12px',
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        color: 'var(--color-text-dim)',
        whiteSpace: 'nowrap',
        lineHeight: 1.2,
      }}
    >
      {children}
    </span>
  )
}

function ChipIcon({ children }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--color-text-dimmer)',
      }}
    >
      {children}
    </span>
  )
}

function ActionButton({ href, children, icon, primary = false }) {
  const baseStyle = {
    flex: '1 1 140px',
    minWidth: 140,
    minHeight: 44,
    padding: '12px 18px',
    borderRadius: 12,
    fontSize: 14,
    fontWeight: 700,
    textDecoration: 'none',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    cursor: 'pointer',
    transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.18s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
  }
  const primaryStyle = {
    ...baseStyle,
    background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
    color: '#fff',
    border: 'none',
    boxShadow: '0 8px 24px rgba(236,72,153,0.25)',
  }
  const secondaryStyle = {
    ...baseStyle,
    background: 'var(--color-surface)',
    color: 'var(--color-text)',
    border: '1px solid var(--color-border)',
  }

  const target = href?.startsWith('mailto:') ? undefined : '_blank'
  const rel = target === '_blank' ? 'noreferrer' : undefined

  return (
    <a
      href={href}
      target={target}
      rel={rel}
      style={primary ? primaryStyle : secondaryStyle}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)'
        if (primary) {
          e.currentTarget.style.boxShadow = '0 12px 32px rgba(236,72,153,0.35)'
        } else {
          e.currentTarget.style.borderColor = 'rgba(236,72,153,0.4)'
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        if (primary) {
          e.currentTarget.style.boxShadow = '0 8px 24px rgba(236,72,153,0.25)'
        } else {
          e.currentTarget.style.borderColor = 'var(--color-border)'
        }
      }}
    >
      {icon}
      {children}
    </a>
  )
}

function SectionHeader({ title, count }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 12,
        marginBottom: 20,
      }}
    >
      <h3
        style={{
          color: 'var(--color-text)',
          fontSize: 20,
          fontWeight: 800,
          margin: 0,
          letterSpacing: '-0.01em',
        }}
      >
        {title}
      </h3>
      <span
        style={{
          color: 'var(--color-text-dimmer)',
          fontSize: 13,
          fontWeight: 700,
        }}
      >
        {count}
      </span>
    </div>
  )
}

function ProjectCard({ project }) {
  return (
    <div
      // TODO(claude): navigate to project detail on click — e.g. navigate(`/buildings/${project.building_id}`)
      style={{
        position: 'relative',
        borderRadius: 20,
        overflow: 'hidden',
        cursor: 'pointer',
        background: 'var(--color-surface)',
        border: '1px solid rgba(255,255,255,0.06)',
        aspectRatio: '4 / 5',
        boxShadow: '0 6px 16px rgba(0,0,0,0.25)',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)'
        e.currentTarget.style.borderColor = 'rgba(236,72,153,0.35)'
        e.currentTarget.style.boxShadow = '0 14px 32px rgba(0,0,0,0.4)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'
        e.currentTarget.style.boxShadow = '0 6px 16px rgba(0,0,0,0.25)'
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
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.4) 45%, rgba(0,0,0,0.0) 100%)',
        }}
        aria-hidden="true"
      />

      {/* Program tag — top-right */}
      <span
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          background: 'rgba(0,0,0,0.55)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          color: '#fff',
          fontSize: 11,
          fontWeight: 700,
          padding: '4px 10px',
          borderRadius: 999,
          border: '1px solid rgba(255,255,255,0.12)',
          letterSpacing: '0.02em',
        }}
      >
        {project.program}
      </span>

      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '20px',
        }}
      >
        <h4
          style={{
            color: '#fff',
            fontSize: 17,
            fontWeight: 800,
            margin: '0 0 6px',
            lineHeight: 1.3,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            letterSpacing: '-0.005em',
          }}
        >
          {project.name_en}
        </h4>
        <p
          style={{
            color: 'rgba(255,255,255,0.65)',
            fontSize: 13,
            margin: 0,
            fontWeight: 600,
          }}
        >
          {project.city} · {project.year}
        </p>
      </div>
    </div>
  )
}

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
        border: '1px solid var(--color-border)',
        borderLeft: '3px solid #ec4899',
        borderRadius: 14,
        textDecoration: 'none',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)'
        e.currentTarget.style.borderColor = 'rgba(236,72,153,0.25)'
        e.currentTarget.style.borderLeftColor = '#f43f5e'
        e.currentTarget.style.boxShadow = '0 10px 24px rgba(0,0,0,0.25)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.borderColor = 'var(--color-border)'
        e.currentTarget.style.borderLeftColor = '#ec4899'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      <p
        style={{
          color: 'var(--color-text)',
          fontSize: 15,
          fontWeight: 700,
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
            fontWeight: 700,
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
