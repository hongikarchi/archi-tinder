import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

// TODO: Replace with API call
// TODO(claude): GET /api/v1/landing/${sessionId}/ — backend should return the
// shape below (projects[], offices[], users[] each with match_score 0-1, plus
// the persona_label addition noted in the next TODO).
const MOCK_LANDING = {
  // TODO(claude): backend should include persona_label (string) in the
  // /api/v1/landing/${sessionId}/ response — designer.md "Post-Swipe Landing"
  // contract does not yet list this field, but the celebratory hero needs it
  // to surface the user's persona type as a chip.
  persona_label: "The Parametric Visionary",
  swipes_analyzed: 25,
  likes_count: 12,
  projects: [
    {
      building_id: "B00042",
      name_en: "Seattle Central Library",
      image_url: "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&q=80",
      match_score: 0.94,
      year: 2004,
      city: "Seattle",
      program: "Public",
    },
    {
      building_id: "B00118",
      name_en: "Casa da Musica",
      image_url: "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=800&q=80",
      match_score: 0.92,
      year: 2005,
      city: "Porto",
      program: "Cultural",
    },
    {
      building_id: "B00231",
      name_en: "Fondazione Prada",
      image_url: "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800&q=80",
      match_score: 0.91,
      year: 2015,
      city: "Milan",
      program: "Museum",
    },
    {
      building_id: "B00307",
      name_en: "Qatar National Library",
      image_url: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80",
      match_score: 0.89,
      year: 2018,
      city: "Doha",
      program: "Public",
    },
    {
      building_id: "B00415",
      name_en: "Heydar Aliyev Center",
      image_url: "https://images.unsplash.com/photo-1511818966892-d7d671e672a2?w=800&q=80",
      match_score: 0.88,
      year: 2012,
      city: "Baku",
      program: "Cultural",
    },
    {
      building_id: "B00522",
      name_en: "Therme Vals",
      image_url: "https://images.unsplash.com/photo-1524815340653-53d719ce3660?w=800&q=80",
      match_score: 0.87,
      year: 1996,
      city: "Vals",
      program: "Hospitality",
    },
    {
      building_id: "B00638",
      name_en: "Vitra Design Museum",
      image_url: "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=800&q=80",
      match_score: 0.86,
      year: 1989,
      city: "Weil am Rhein",
      program: "Museum",
    },
    {
      building_id: "B00751",
      name_en: "Taipei Performing Arts Center",
      image_url: "https://images.unsplash.com/photo-1506146332389-18140dc7b2fb?w=800&q=80",
      match_score: 0.85,
      year: 2022,
      city: "Taipei",
      program: "Cultural",
    },
  ],
  offices: [
    {
      office_id: "OFF001",
      name: "OMA",
      logo_url: "https://images.unsplash.com/photo-1616423640778-28d1b53229bd?w=400&q=80",
      project_count: 32,
      match_score: 0.93,
    },
    {
      office_id: "OFF002",
      name: "Herzog & de Meuron",
      logo_url: "https://images.unsplash.com/photo-1497366216548-37526070297c?w=400&q=80",
      project_count: 41,
      match_score: 0.90,
    },
    {
      office_id: "OFF003",
      name: "BIG — Bjarke Ingels Group",
      logo_url: "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=400&q=80",
      project_count: 28,
      match_score: 0.88,
    },
    {
      office_id: "OFF004",
      name: "Snøhetta",
      logo_url: "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=400&q=80",
      project_count: 19,
      match_score: 0.86,
    },
  ],
  users: [
    {
      user_id: 102,
      display_name: "Park Jiwon",
      avatar_url: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&q=80",
      shared_likes: 8,
      match_score: 0.91,
    },
    {
      user_id: 215,
      display_name: "Sarah Chen",
      avatar_url: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&q=80",
      shared_likes: 6,
      match_score: 0.88,
    },
    {
      user_id: 318,
      display_name: "Hiroshi Tanaka",
      avatar_url: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&q=80",
      shared_likes: 5,
      match_score: 0.85,
    },
    {
      user_id: 421,
      display_name: "Lee Minjun",
      avatar_url: "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?w=400&q=80",
      shared_likes: 4,
      match_score: 0.83,
    },
  ],
}

const TABS = [
  { key: 'projects', label: 'Projects' },
  { key: 'offices', label: 'Offices' },
  { key: 'users', label: 'Users' },
]

function ProjectCard({ project }) {
  const [isHovered, setIsHovered] = useState(false)
  return (
    <div
      onClick={() => {
        // TODO(claude): open building detail modal or navigate to /building/${project.building_id}
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        position: 'relative',
        aspectRatio: '4/5',
        borderRadius: 20,
        overflow: 'hidden',
        cursor: 'pointer',
        border: isHovered ? '1px solid rgba(236,72,153,0.5)' : '1px solid rgba(255,255,255,0.08)',
        boxShadow: isHovered ? '0 20px 40px rgba(236,72,153,0.18)' : '0 10px 25px rgba(0,0,0,0.35)',
        transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        minHeight: 0,
      }}
    >
      <img
        src={project.image_url}
        alt={project.name_en}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
      />
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.45) 40%, rgba(0,0,0,0.05) 75%, transparent 100%)',
      }} />

      {/* Match score chip */}
      <div style={{
        position: 'absolute', top: 12, right: 12,
        padding: '6px 12px', borderRadius: 999,
        background: 'rgba(236,72,153,0.85)',
        backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
        color: '#fff', fontSize: 12, fontWeight: 800, letterSpacing: '0.02em',
        boxShadow: '0 4px 12px rgba(236,72,153,0.35)',
      }}>
        {Math.round(project.match_score * 100)}% match
      </div>

      {/* Bottom info */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '20px' }}>
        <h4 style={{
          color: '#fff', fontSize: 18, fontWeight: 800, margin: '0 0 6px', lineHeight: 1.3,
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {project.name_en}
        </h4>
        <p style={{ color: 'rgba(255,255,255,0.65)', fontSize: 13, margin: 0, fontWeight: 600 }}>
          {project.year} · {project.city}
        </p>
      </div>
    </div>
  )
}

function OfficeCard({ office }) {
  const navigate = useNavigate()
  const [isHovered, setIsHovered] = useState(false)
  return (
    <div
      onClick={() => navigate(`/office/${office.office_id}`)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        position: 'relative',
        aspectRatio: '1/1',
        borderRadius: 20,
        overflow: 'hidden',
        cursor: 'pointer',
        background: 'var(--color-surface)',
        border: isHovered ? '1px solid rgba(236,72,153,0.5)' : '1px solid rgba(255,255,255,0.08)',
        boxShadow: isHovered ? '0 20px 40px rgba(236,72,153,0.18)' : '0 10px 25px rgba(0,0,0,0.35)',
        transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        display: 'flex', flexDirection: 'column',
        minHeight: 0,
      }}
    >
      {/* Match score chip */}
      <div style={{
        position: 'absolute', top: 12, right: 12, zIndex: 2,
        padding: '6px 12px', borderRadius: 999,
        background: 'rgba(236,72,153,0.85)',
        backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
        color: '#fff', fontSize: 12, fontWeight: 800, letterSpacing: '0.02em',
        boxShadow: '0 4px 12px rgba(236,72,153,0.35)',
      }}>
        {Math.round(office.match_score * 100)}% match
      </div>

      {/* Logo half */}
      <div style={{
        flex: '0 0 55%',
        background: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        overflow: 'hidden',
      }}>
        <img
          src={office.logo_url}
          alt={office.name}
          style={{ width: '100%', height: '100%', objectFit: 'contain', padding: 16 }}
        />
      </div>

      {/* Info half */}
      <div style={{
        flex: 1,
        padding: '16px 18px',
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
        background: 'var(--color-surface)',
        borderTop: '1px solid rgba(255,255,255,0.08)',
      }}>
        <h4 style={{
          color: 'var(--color-text)', fontSize: 17, fontWeight: 800, margin: '0 0 4px',
          lineHeight: 1.3,
          display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical',
          overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {office.name}
        </h4>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 13, margin: 0, fontWeight: 600 }}>
          {office.project_count} projects
        </p>
      </div>
    </div>
  )
}

function UserCard({ user }) {
  const navigate = useNavigate()
  const [isHovered, setIsHovered] = useState(false)
  return (
    <div
      onClick={() => navigate(`/user/${user.user_id}`)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        position: 'relative',
        padding: '32px 20px 24px',
        borderRadius: 20,
        background: 'var(--color-surface)',
        border: isHovered ? '1px solid rgba(236,72,153,0.5)' : '1px solid rgba(255,255,255,0.08)',
        boxShadow: isHovered ? '0 20px 40px rgba(236,72,153,0.18)' : '0 10px 25px rgba(0,0,0,0.35)',
        transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        cursor: 'pointer',
        display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
        minHeight: 220,
      }}
    >
      {/* Match score chip */}
      <div style={{
        position: 'absolute', top: 12, right: 12,
        padding: '6px 12px', borderRadius: 999,
        background: 'rgba(236,72,153,0.85)',
        backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
        color: '#fff', fontSize: 12, fontWeight: 800, letterSpacing: '0.02em',
        boxShadow: '0 4px 12px rgba(236,72,153,0.35)',
      }}>
        {Math.round(user.match_score * 100)}% match
      </div>

      {/* Avatar with brand-glow halo */}
      <div style={{ position: 'relative', marginBottom: 16 }}>
        <div style={{
          position: 'absolute', inset: -3, borderRadius: '50%',
          background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
          opacity: 0.4, filter: 'blur(8px)',
        }} />
        <img
          src={user.avatar_url}
          alt={user.display_name}
          style={{
            width: 100, height: 100, borderRadius: '50%',
            objectFit: 'cover', position: 'relative', zIndex: 2,
            border: '2px solid rgba(255,255,255,0.12)',
            background: 'var(--color-surface-2)',
          }}
        />
      </div>

      <h4 style={{
        color: 'var(--color-text)', fontSize: 16, fontWeight: 700,
        margin: '0 0 4px', lineHeight: 1.3,
      }}>
        {user.display_name}
      </h4>
      <p style={{
        color: 'var(--color-text-dim)', fontSize: 13, margin: 0,
        fontStyle: 'italic', fontWeight: 500,
      }}>
        {user.shared_likes} shared likes
      </p>
    </div>
  )
}

function EmptyState({ message }) {
  return (
    <div style={{
      gridColumn: '1 / -1',
      padding: '60px 20px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      textAlign: 'center',
      color: 'var(--color-text-dim)',
    }}>
      <div style={{ fontSize: 42, marginBottom: 16, opacity: 0.6 }}>📁</div>
      <p style={{ fontSize: 14, fontWeight: 500, margin: 0, maxWidth: 320, lineHeight: 1.5 }}>
        {message}
      </p>
    </div>
  )
}

export default function PostSwipeLandingPage() {
  const navigate = useNavigate()
  // TODO(claude): sessionId will drive GET /api/v1/landing/${sessionId}/ once
  // backend integration replaces MOCK_LANDING.
  const { sessionId } = useParams()
  const [activeTab, setActiveTab] = useState('projects')

  const counts = {
    projects: MOCK_LANDING.projects.length,
    offices: MOCK_LANDING.offices.length,
    users: MOCK_LANDING.users.length,
  }
  const activeIndex = TABS.findIndex(t => t.key === activeTab)

  const renderTabContent = () => {
    if (activeTab === 'projects') {
      if (MOCK_LANDING.projects.length === 0) {
        return <EmptyState message="No matches yet — keep swiping to refine your taste" />
      }
      return MOCK_LANDING.projects.map(p => (
        <ProjectCard key={p.building_id} project={p} />
      ))
    }
    if (activeTab === 'offices') {
      if (MOCK_LANDING.offices.length === 0) {
        return <EmptyState message="No matches yet — keep swiping to refine your taste" />
      }
      return MOCK_LANDING.offices.map(o => (
        <OfficeCard key={o.office_id} office={o} />
      ))
    }
    if (MOCK_LANDING.users.length === 0) {
      return <EmptyState message="No matches yet — keep swiping to refine your taste" />
    }
    return MOCK_LANDING.users.map(u => (
      <UserCard key={u.user_id} user={u} />
    ))
  }

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(80px + env(safe-area-inset-bottom))',
      position: 'relative',
    }}>
      {/* Ambient background glow */}
      <div style={{
        position: 'fixed', top: '-10%', left: '-10%', width: '120%', height: '50%',
        background: 'radial-gradient(circle at 50% 0%, rgba(236,72,153,0.10) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* Sticky Header */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 11,
        background: 'var(--color-header-bg, rgba(10, 10, 12, 0.65))',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderBottom: '1px solid var(--color-border-soft)',
      }}>
        {/* Back button */}
        <button
          onClick={() => navigate(-1)}
          aria-label="Back"
          style={{
            width: 44, height: 44, minWidth: 44, minHeight: 44,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: 'var(--color-text)', borderRadius: 12,
            transition: 'color 0.2s ease',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#ec4899' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text)' }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
        </button>

        {/* Title with brand gradient */}
        <h1 style={{
          margin: 0, fontSize: 20, fontWeight: 900, letterSpacing: '0.04em',
          background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
          WebkitBackgroundClip: 'text', backgroundClip: 'text',
          WebkitTextFillColor: 'transparent', color: 'transparent',
        }}>
          MATCHED!
        </h1>

        {/* Right placeholder (share-like slot, 44px touch) */}
        <button
          onClick={() => {
            // TODO(claude): wire share endpoint — POST /api/v1/landing/${sessionId}/share/ or use Web Share API
          }}
          aria-label="Share"
          style={{
            width: 44, height: 44, minWidth: 44, minHeight: 44,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: 'var(--color-text-dim)', borderRadius: 12,
            transition: 'color 0.2s ease',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#ec4899' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-dim)' }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="18" cy="5" r="3"></circle>
            <circle cx="6" cy="12" r="3"></circle>
            <circle cx="18" cy="19" r="3"></circle>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
          </svg>
        </button>
      </div>

      {/* Celebratory Hero */}
      <div style={{
        maxWidth: 720, margin: '0 auto', padding: '40px 20px 32px',
        textAlign: 'center', position: 'relative', zIndex: 1,
      }}>
        <p style={{
          color: 'var(--color-text-muted)',
          fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
          textTransform: 'uppercase', margin: '0 0 16px',
        }}>
          Based on your taste
        </p>
        <h2 style={{
          color: 'var(--color-text)',
          fontSize: 'clamp(28px, 5vw, 32px)', fontWeight: 900,
          lineHeight: 1.2, margin: '0 0 14px',
        }}>
          Your taste is unique.
        </h2>
        <p style={{
          color: 'var(--color-text-dim)',
          fontSize: 15, lineHeight: 1.55, margin: '0 auto 24px',
          maxWidth: 480, fontWeight: 500,
        }}>
          Curated picks across projects, offices, and similar architects.
        </p>

        {/* Stat chips */}
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: 8,
          justifyContent: 'center', alignItems: 'center',
        }}>
          <span style={{
            padding: '8px 14px', borderRadius: 999,
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.08)',
            color: 'var(--color-text-2)', fontSize: 12, fontWeight: 600,
          }}>
            {MOCK_LANDING.swipes_analyzed} swipes analyzed
          </span>
          <span style={{
            padding: '8px 14px', borderRadius: 999,
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.08)',
            color: 'var(--color-text-2)', fontSize: 12, fontWeight: 600,
          }}>
            {MOCK_LANDING.likes_count} likes
          </span>
          <span style={{
            padding: '8px 14px', borderRadius: 999,
            background: 'linear-gradient(135deg, rgba(236,72,153,0.18), rgba(244,63,94,0.18))',
            border: '1px solid rgba(236,72,153,0.35)',
            color: '#fff', fontSize: 12, fontWeight: 700,
          }}>
            Persona: {MOCK_LANDING.persona_label}
          </span>
        </div>

        {/* Hidden session reference for downstream debugging — keeps the
            useParams binding live until backend integration consumes it. */}
        <span style={{ display: 'none' }} data-session-id={sessionId ?? ''} />
      </div>

      {/* Sticky Tab Bar */}
      <div style={{
        position: 'sticky', top: 68, zIndex: 9,
        background: 'var(--color-header-bg, rgba(10, 10, 12, 0.65))',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '1px solid var(--color-border-soft)',
      }}>
        <div style={{
          maxWidth: 660, margin: '0 auto',
          display: 'flex', alignItems: 'stretch',
          position: 'relative',
        }}>
          {TABS.map(tab => {
            const isActive = activeTab === tab.key
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  flex: 1,
                  minHeight: 52,
                  padding: '14px 12px',
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  color: isActive ? '#ec4899' : 'var(--color-text-dim)',
                  fontSize: 14, fontWeight: isActive ? 700 : 600,
                  letterSpacing: '0.02em',
                  transition: 'color 0.2s ease',
                  fontFamily: 'inherit',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.color = 'var(--color-text-2)'
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.color = 'var(--color-text-dim)'
                }}
              >
                {tab.label} ({counts[tab.key]})
              </button>
            )
          })}

          {/* Animated underline — positioned by activeIndex, equal-flex tabs
              make percentage math reliable. */}
          <div style={{
            position: 'absolute', bottom: 0, height: 2,
            left: 0,
            width: `${100 / TABS.length}%`,
            transform: `translateX(${activeIndex * 100}%)`,
            background: '#ec4899',
            borderRadius: 2,
            transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          }} />
        </div>
      </div>

      {/* Tab Content Grid */}
      <div style={{
        maxWidth: 1100, margin: '0 auto', padding: '24px 20px 40px',
        position: 'relative', zIndex: 1,
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 20,
        }}>
          {renderTabContent()}
        </div>
      </div>
    </div>
  )
}
