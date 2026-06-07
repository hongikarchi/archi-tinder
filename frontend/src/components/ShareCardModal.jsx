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
 * QR sharing is NOT functional. The QR shown is a visual stub only.
 * See FakeQr.jsx.
 *
 * Usage:
 *   <ShareCardModal user={user} onClose={() => setOpen(false)} />
 */

import BusinessCard from './profile/BusinessCard.jsx'

export default function ShareCardModal({ user, onClose }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="프로필 공유 카드"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10200,
        // Themed backdrop (slightly stronger than SaveToBoardModal for card contrast)
        background: 'rgba(0,0,0,0.60)',
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
            프로필 공유
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
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

        {/* Instructional footer — themed text */}
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
            명함을 탭하면 뒤집힙니다
          </p>
          <p style={{
            margin: 0,
            fontSize: 11,
            color: 'var(--color-text-dim)',
            lineHeight: 1.4,
          }}>
            {/* 공유 준비 중 / not yet scannable */}
            QR 공유는 준비 중입니다
          </p>
        </div>
      </div>
    </div>
  )
}
