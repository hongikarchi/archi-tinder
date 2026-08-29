import { Fragment } from 'react'
import DescriptionAboutFlipCard from '../../components/profile/DescriptionAboutFlipCard'
import s from './FirmProfileHero.module.css'

export default function FirmProfileHero({ office, followerCount, onMessage }) {
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
                background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
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
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-dim)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
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
                background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
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

        {/* §3.6 Profile Action Row — message only (follow removed: office-follow endpoint deleted) */}
        <div style={{ display: 'flex', gap: 10, marginTop: 14, width: '100%' }}>
          <button
            onClick={onMessage}
            aria-label="Message"
            className={s.messageBtn}
            style={{
              width: 44, height: 44, minWidth: 44, flexShrink: 0,
              background: 'var(--color-surface)',
              borderRadius: 12, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
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
                className={s.actionPill}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  padding: '10px 14px', borderRadius: 999,
                  background: 'var(--color-surface-2, rgba(255,255,255,0.04))',
                  textDecoration: 'none', fontSize: 13, fontWeight: 600,
                  minHeight: 44,
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
                className={s.actionPill}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  padding: '10px 14px', borderRadius: 999,
                  background: 'var(--color-surface-2, rgba(255,255,255,0.04))',
                  textDecoration: 'none', fontSize: 13, fontWeight: 600,
                  minHeight: 44,
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
