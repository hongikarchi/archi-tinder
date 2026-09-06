import { Fragment, useState, useCallback, useEffect } from 'react'
import { uploadAvatar } from '../../api/profiles.js'
import { getRoles } from '../../api/meta.js'
import { useLanguage } from '../../hooks/useLanguage.js'
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
  savedStudiosCount,
  likedCount,
  onSelectTab,
  // Avatar upload props (owner-only)
  isMe,
  onAvatarUpdated,
}) {
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [roleOptions, setRoleOptions] = useState([])
  const [imgFailed, setImgFailed] = useState(false)
  const { language } = useLanguage()

  // Reset the broken-image fallback whenever the avatar URL changes (e.g. a
  // fresh upload after a prior failure) so the user isn't stuck on the
  // placeholder forever.
  useEffect(() => {
    setImgFailed(false)
  }, [user.avatar_url])

  // Role list only needed to localize onboarding_role (legacy free-text
  // user.role never needs it) — fetch once, memoized at module scope.
  useEffect(() => {
    let cancelled = false
    getRoles().then(list => { if (!cancelled) setRoleOptions(list) })
    return () => { cancelled = true }
  }, [])

  // External-link helpers (pure derivations — no hooks)
  const igHandle = user?.external_links?.instagram?.replace(/^@/, '') || ''
  const igUrl = igHandle ? `https://instagram.com/${igHandle}` : null
  const emailUrl = user?.external_links?.email ? `mailto:${user.external_links.email}` : null
  const websiteUrl = user?.external_links?.website || null

  // Profile identity lines
  const handleStr = user?.handle || ''

  // Role display rule (SETTINGS-POLISH-1 §A.5): legacy free-text user.role if
  // present; else localized onboarding_role label EXCEPT 'other' (suppressed
  // — meaningless publicly); else nothing. Joined with affiliation via ' · '.
  function resolveRoleText() {
    if (user?.role) return user.role
    const code = user?.onboarding_role
    if (!code || code === 'other') return ''
    const opt = roleOptions.find(r => r.value === code)
    if (!opt) return ''
    return language === 'ko' ? (opt.label_ko || opt.label_en) : (opt.label_en || opt.label_ko)
  }
  const roleAffiliation = [resolveRoleText(), user?.affiliation].filter(Boolean).join(' · ')

  const stats = [
    { count: boardsTotalCount, label: 'Boards', onClick: () => onSelectTab('boards') },
    { count: savedStudiosCount ?? 0, label: 'Studios', onClick: () => onSelectTab('studios') },
    { count: likedCount ?? 0, label: 'Liked', onClick: () => onSelectTab('liked') },
  ]

  // 2B: single data source for the external-link pills — map renders one
  // shared .linkPill class instead of 3 near-duplicate <a> blocks.
  const linkPills = [
    igUrl && {
      key: 'instagram',
      href: igUrl,
      external: true,
      label: user.external_links.instagram,
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect>
          <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
          <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
        </svg>
      ),
    },
    emailUrl && {
      key: 'email',
      href: emailUrl,
      external: false,
      label: user.external_links.email,
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
          <polyline points="22,6 12,13 2,6"></polyline>
        </svg>
      ),
    },
    websiteUrl && {
      key: 'website',
      href: websiteUrl,
      external: true,
      label: websiteUrl.replace(/^https?:\/\//, '').replace(/\/$/, ''),
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="2" y1="12" x2="22" y2="12"></line>
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
        </svg>
      ),
    },
  ].filter(Boolean)

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
    if (user.avatar_url && !imgFailed) {
      return (
        <div style={{ position: 'relative' }}>
          <div
            style={{
              position: 'absolute', inset: -6, borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
              opacity: 0.55, filter: 'blur(12px)',
            }}
            aria-hidden="true"
          />
          <img
            src={user.avatar_url}
            alt="avatar"
            onError={() => setImgFailed(true)}
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
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-dim)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
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

        {/* Compact stats row — 2 items: Boards · Studios */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: 0, marginTop: 14, marginBottom: 4,
        }}>
          {stats.map((stat, i, arr) => (
            <Fragment key={stat.label}>
              <button onClick={stat.onClick} className={styles.statBtn}>
                <span style={{ color: 'var(--color-text)', fontSize: 18, fontWeight: 700, lineHeight: 1 }}>
                    {stat.count}
                  </span>
                <span className={styles.statLabel}>
                  {stat.label}
                </span>
              </button>
              {i < arr.length - 1 && (
                <div style={{ width: 1, height: 28, background: 'var(--color-border)' }} />
              )}
            </Fragment>
          ))}
        </div>


        {/* External links — Instagram + email + website pills */}
        {linkPills.length > 0 && (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
            {linkPills.map(pill => (
              <a
                key={pill.key}
                href={pill.href}
                {...(pill.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                className={styles.linkPill}
              >
                {pill.icon}
                {pill.label}
              </a>
            ))}
          </div>
        )}

      </div>
    </div>
  )
}
