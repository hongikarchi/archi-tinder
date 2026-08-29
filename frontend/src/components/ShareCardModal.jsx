/**
 * ShareCardModal.jsx — Profile share modal.
 *
 * Shows the BusinessCard (white printed card, theme-independent by design)
 * inside a themed modal chrome (backdrop + surface box + instructional text).
 *
 * The modal chrome uses --color-* tokens so it themes correctly across all 4
 * app themes. The card inside is always white PAPER (#FFFFFF) + dark INK —
 * that is intentional (printed-card metaphor, NOT a bug).
 *
 * The QR on the BusinessCard is real and scannable — it encodes
 * `${window.location.origin}/user/${user.user_id}`. See ProfileQr.jsx.
 *
 * Usage:
 *   <ShareCardModal user={user} onClose={() => setOpen(false)} />
 */

import { useState } from 'react'
import BusinessCard from './profile/BusinessCard.jsx'
import { useTranslation } from '../i18n/index.js'

export default function ShareCardModal({ user, onClose }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  const profileUrl = user?.user_id
    ? `${window.location.origin}/user/${user.user_id}`
    : window.location.href

  const canNativeShare = typeof navigator !== 'undefined' && !!navigator.share

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(profileUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* silent — clipboard blocked */ }
  }

  async function handleNativeShare() {
    const shareData = {
      title: user?.display_name ? t('share.nativeTitle', { name: user.display_name }) : t('share.nativeTitleFallback'),
      url: profileUrl,
    }
    try { await navigator.share(shareData) } catch { /* user cancelled */ }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('share.cardAria')}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10200,
        // Themed backdrop (slightly stronger than SaveToBoardModal for card contrast)
        background: 'var(--color-scrim)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      {/* Modal chrome — themed surface box */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(94vw, 400px)',
          // Themed surface (shifts per theme via --color-* tokens)
          background: 'var(--color-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-soft)',
          color: 'var(--color-text)',
          boxShadow: '0 20px 48px rgba(0,0,0,0.30)',
          overflow: 'hidden',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header row — themed */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 16px 0',
          gap: 8,
        }}>
          <h3 style={{
            margin: 0,
            fontSize: 16,
            fontWeight: 700,
            color: 'var(--color-text)',
            letterSpacing: '-0.01em',
          }}>
            {t('share.title')}
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('share.close')}
            style={{
              width: 36,
              height: 36,
              borderRadius: '50%',
              border: '1px solid var(--color-border-soft)',
              background: 'transparent',
              color: 'var(--color-text-dim)',
              fontSize: 16,
              lineHeight: 1,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: 'inherit',
              flexShrink: 0,
            }}
          >
            ✕
          </button>
        </div>

        {/* Scrollable card area */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 16px 4px',
        }}>
          {/* BusinessCard — always white PAPER regardless of app theme (by design) */}
          <BusinessCard user={user} />
        </div>

        {/* Instructional footer — themed text + share actions */}
        <div style={{
          padding: '4px 20px 20px',
          textAlign: 'center',
          borderTop: '1px solid var(--color-border)',
        }}>
          <p style={{
            margin: '12px 0 4px',
            fontSize: 13,
            color: 'var(--color-text-muted)',
            lineHeight: 1.5,
          }}>
            {t('share.tapToFlip')}
          </p>
          <p style={{
            margin: '0 0 14px',
            fontSize: 11,
            color: 'var(--color-text-dim)',
            lineHeight: 1.4,
          }}>
            {t('share.scanQr')}
          </p>

          {/* Share action buttons */}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
            {/* Copy link — always present */}
            <button
              type="button"
              onClick={handleCopy}
              style={{
                flex: 1,
                maxWidth: 160,
                height: 40,
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-soft)',
                background: copied ? 'var(--accent-1)' : 'transparent',
                color: copied ? '#fff' : 'var(--color-text)',
                fontSize: 13,
                fontWeight: 600,
                fontFamily: 'inherit',
                cursor: 'pointer',
                transition: 'background var(--motion-normal) var(--motion-ease), color var(--motion-normal) var(--motion-ease)',
              }}
            >
              {copied ? t('share.copied') : t('share.copyLink')}
            </button>

            {/* Native share — progressive enhancement (mobile only) */}
            {canNativeShare && (
              <button
                type="button"
                onClick={handleNativeShare}
                style={{
                  flex: 1,
                  maxWidth: 160,
                  height: 40,
                  borderRadius: 'var(--radius-md)',
                  border: 'none',
                  background: 'var(--accent-1)',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 600,
                  fontFamily: 'inherit',
                  cursor: 'pointer',
                }}
              >
                {t('share.share')}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
