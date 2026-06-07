import { Fragment, useState, useCallback } from 'react'
import BioPersonaFlipCard from '../../components/profile/BioPersonaFlipCard'
import { uploadAvatar } from '../../api/profiles.js'
import styles from './ProfileHero.module.css'

// Canvas-based center-crop + downscale to ≤512px, exported as webp (jpeg fallback).
// UX/bandwidth optimisation only — server re-encodes authoritatively.
function cropAndScale(file) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(url)
      const size = Math.min(img.naturalWidth, img.naturalHeight, 512)
      const canvas = document.createElement('canvas')
      canvas.width = size
      canvas.height = size
      const ctx = canvas.getContext('2d')
      // Center-crop: draw the largest center square of the source image
      const srcX = (img.naturalWidth - Math.min(img.naturalWidth, img.naturalHeight)) / 2
      const srcY = (img.naturalHeight - Math.min(img.naturalWidth, img.naturalHeight)) / 2
      const srcSize = Math.min(img.naturalWidth, img.naturalHeight)
      ctx.drawImage(img, srcX, srcY, srcSize, srcSize, 0, 0, size, size)
      // Prefer webp; fall back to jpeg if webp toBlob is unsupported (returns null)
      canvas.toBlob(
        (blob) => {
          if (blob) { resolve(blob); return }
          // webp unsupported — retry with jpeg
          canvas.toBlob(
            (jpegBlob) => {
              if (jpegBlob) resolve(jpegBlob)
              else reject(new Error('Image encoding failed'))
            },
            'image/jpeg',
            0.9,
          )
        },
        'image/webp',
        0.9,
      )
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Failed to load image'))
    }
    img.src = url
  })
}

export default function ProfileHero({
  user,
  boardsTotalCount,
  followerCount,
  savedStudiosCount,
  onSelectTab,
  onOpenFollowModal,
  // Avatar upload props (owner-only)
  isMe,
  onAvatarUpdated,
}) {
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)

  // External-link helpers (pure derivations — no hooks)
  const igHandle = user?.external_links?.instagram?.replace(/^@/, '') || ''
  const igUrl = igHandle ? `https://instagram.com/${igHandle}` : null
  const emailUrl = user?.external_links?.email ? `mailto:${user.external_links.email}` : null
  const websiteUrl = user?.external_links?.website || null

  // Profile identity lines
  const handleStr = user?.handle || ''
  const roleAffiliation = [user?.role, user?.affiliation].filter(Boolean).join(' · ')

  const stats = [
    { count: boardsTotalCount, label: 'Boards', onClick: () => onSelectTab('boards') },
    { count: savedStudiosCount ?? 0, label: 'Studios', onClick: () => onSelectTab('studios') },
    { count: followerCount, label: 'Followers', onClick: () => onOpenFollowModal('followers') },
    { count: user.following_count, label: 'Following', onClick: () => onOpenFollowModal('following') },
  ]

  const handleFileChange = useCallback(async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    // Reset input so re-selecting the same file re-fires onChange
    e.target.value = ''

    setUploadError(null)
    setUploading(true)
    try {
      const blob = await cropAndScale(file)
      const updatedUser = await uploadAvatar(blob)
      onAvatarUpdated?.(updatedUser)
    } catch (err) {
      setUploadError(err.message || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }, [onAvatarUpdated])

  // Avatar circle — renders the image+halo or the placeholder.
  // When isMe: wrapped in an upload <label> trigger with hover overlay.
  function AvatarCircle() {
    if (user.avatar_url) {
      return (
        <div style={{ position: 'relative' }}>
          <div
            style={{
              position: 'absolute', inset: -6, borderRadius: '50%',
              background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
              opacity: 0.55, filter: 'blur(12px)',
            }}
            aria-hidden="true"
          />
          <img
            src={user.avatar_url}
            alt="avatar"
            style={{
              position: 'relative', zIndex: 2,
              width: 108, height: 108, borderRadius: '50%',
              border: '2px solid var(--color-border-soft)',
              objectFit: 'cover',
              background: 'var(--color-surface)',
              display: 'block',
            }}
          />
        </div>
      )
    }
    return (
      <div
        style={{
          width: 108, height: 108, borderRadius: '50%',
          background: 'var(--color-surface)',
          border: '2px solid var(--color-border-soft)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="8" r="4"></circle>
          <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"></path>
        </svg>
      </div>
    )
  }

  // Overlay content: camera icon + label
  const overlayContent = (
    <div className={styles.avatarOverlay} aria-hidden="true">
      {/* Camera icon */}
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
        <circle cx="12" cy="13" r="4"></circle>
      </svg>
      <span>Change photo</span>
    </div>
  )

  // Uploading spinner overlay
  const spinnerOverlay = uploading && (
    <div className={styles.spinnerOverlay} aria-label="Uploading..." aria-live="polite">
      {/* animation inline to safely reference global @keyframes spin — same pattern as UserProfilePage spinner */}
      <div className={styles.spinner} style={{ animation: 'spin 0.8s linear infinite' }} />
    </div>
  )

  return (
    /* HERO BLOCK — narrower nested column (max-width 480) */
    <div style={{ maxWidth: 480, margin: '0 auto 36px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>

        {/* Avatar — upload trigger when isMe, static when not */}
        {isMe ? (
          <label
            className={styles.avatarTrigger}
            aria-label="Change profile photo"
            title="Change profile photo"
          >
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className={styles.fileInput}
              onChange={handleFileChange}
              disabled={uploading}
              aria-label="Upload profile photo"
            />
            <AvatarCircle />
            {overlayContent}
            {spinnerOverlay}
          </label>
        ) : (
          <div style={{ marginBottom: 18 }}>
            <AvatarCircle />
          </div>
        )}

        {/* Inline upload error */}
        {isMe && uploadError && (
          <p className={styles.uploadError} role="alert">
            {uploadError}
          </p>
        )}

        {/* Name */}
        <h1 style={{
          color: 'var(--color-text)', fontSize: 24, fontWeight: 700,
          margin: '0 0 4px', lineHeight: 1.2, letterSpacing: '-0.01em',
        }}>
          {user.display_name}
        </h1>

        {/* @handle — monospace muted, only if present */}
        {handleStr && (
          <p style={{
            margin: '0 0 4px',
            color: 'var(--color-text-muted)',
            fontSize: 13,
            fontFamily: '"IBM Plex Mono", "Courier New", monospace',
            fontWeight: 500,
            letterSpacing: '0.01em',
            lineHeight: 1.3,
          }}>
            @{handleStr}
          </p>
        )}

        {/* Role · Affiliation — only if at least one present */}
        {roleAffiliation && (
          <p style={{
            margin: '0 0 4px',
            color: 'var(--color-text-muted)',
            fontSize: 13,
            fontWeight: 400,
            lineHeight: 1.3,
          }}>
            {roleAffiliation}
          </p>
        )}

        {/* Compact stats row — 4 items: Boards · Studios · Followers · Following */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: 0, marginTop: 14, marginBottom: 4,
        }}>
          {stats.map((stat, i, arr) => (
            <Fragment key={stat.label}>
              <button
                onClick={stat.onClick}
                style={{
                  flex: '0 0 auto',
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  padding: '6px 14px', minHeight: 44,
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

        {/* Hero Flip — BioPersonaFlipCard */}
        {user.persona_summary && (
          <BioPersonaFlipCard
            bio={user.bio}
            persona={user.persona_summary}
          />
        )}

        {/* External links — Instagram + email + website pills */}
        {(igUrl || emailUrl || websiteUrl) && (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
            {igUrl && (
              <a
                href={igUrl}
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
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect>
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
                </svg>
                {user.external_links.instagram}
              </a>
            )}
            {emailUrl && (
              <a
                href={emailUrl}
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
                {user.external_links.email}
              </a>
            )}
            {websiteUrl && (
              <a
                href={websiteUrl}
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
                {websiteUrl.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
