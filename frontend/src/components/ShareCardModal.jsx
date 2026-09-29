/**
 * ShareCardModal.jsx — Profile share modal.
 *
 * Shows the BusinessCard (white printed card, theme-independent by design)
 * inside the shared Modal chrome (DESIGN.md §8.10).
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
import Modal from './Modal.jsx'

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
    <Modal
      open
      onClose={onClose}
      title={t('share.title')}
      zIndex={10200}
      closeLabel={t('share.close')}
      width={400}
      footer={(
        <div style={{ textAlign: 'center', borderTop: '1px solid var(--color-border)', paddingTop: 12 }}>
          <p style={{
            margin: '0 0 4px',
            fontSize: 'var(--fs-body)',
            color: 'var(--color-text-muted)',
            lineHeight: 1.5,
          }}>
            {t('share.tapToFlip')}
          </p>
          <p style={{
            margin: '0 0 14px',
            fontSize: 'var(--fs-caption)',
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
                minHeight: 44,
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-soft)',
                background: copied ? 'var(--accent-1)' : 'transparent',
                color: copied ? '#fff' : 'var(--color-text)',
                fontSize: 'var(--fs-body)',
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
                  minHeight: 44,
                  borderRadius: 'var(--radius-md)',
                  border: 'none',
                  background: 'var(--accent-1)',
                  color: '#fff',
                  fontSize: 'var(--fs-body)',
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
      )}
    >
      {/* BusinessCard — always white PAPER regardless of app theme (by design) */}
      <BusinessCard user={user} />
    </Modal>
  )
}
