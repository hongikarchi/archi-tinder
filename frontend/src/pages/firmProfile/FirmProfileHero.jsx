import { Fragment } from 'react'
import DescriptionAboutFlipCard from '../../components/profile/DescriptionAboutFlipCard'

export default function FirmProfileHero({ office, followerCount, isFollowing, onToggleFollow, onMessage }) {
  return (
    /* HERO BLOCK — narrower nested column (max-width 480) — mirrors UserProfile */
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
            onClick={onToggleFollow}
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
            onClick={onMessage}
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
  )
}
