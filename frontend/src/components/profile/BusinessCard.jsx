/**
 * BusinessCard.jsx — Shareable profile card.
 *
 * Design intent: "a white paper card — always white regardless of app theme,
 * it's a printed card." Click to flip (3D rotateY).
 *
 * INTENTIONAL design exception — the PAPER/INK/BORDER constants below are
 * HARDCODED and must NOT be re-tokenized to themed CSS variables. They represent
 * the printed-card artifact; the card stays white-on-dark-ink across all 4 app
 * themes. Only the modal chrome (backdrop, instructional text) is themed.
 *
 * Fields mapped from UserProfileSerializer:
 *   display_name   → name on front & back (textTransform:uppercase via CSS, 26px/700)
 *   role           → role line (user.role directly, 13px/700/INK1, plain)
 *   affiliation    → affiliation line (user.affiliation directly, 13px/400/INK3, plain)
 *   handle         → @handle monospace row (12px/600/INK2; omitted if absent)
 *   external_links → items[] rows (instagram / email / website — filter empties)
 *   user_id        → QR userId (encodes public profile URL)
 *
 * QR: see ProfileQr.jsx — real scannable QR encoding the public profile URL.
 */

import { useState } from 'react'
import ProfileQr from './ProfileQr.jsx'

// ─── Printed-card constants (intentionally hardcoded — never tokenize) ───────
// These are theme-independent printed-card colors — white paper + dark ink.
// They must NOT reference CSS variables or any themed token.
const PAPER  = '#FFFFFF'
const INK1   = '#0A0A0A'
const INK2   = '#3D3D3D'
const INK3   = '#8C8C8C'
const BORDER = '#E6E6E3'
// Letter-spacing inline values (we have no --ls-* tokens — hardcoded per task spec)
const LS_WORDMARK = '0.18em'
const LS_TIGHT    = '-0.01em'
const LS_CAPS     = '0.06em'
// Monospace stack — no --mono token in tokens.css, hardcoded
const MONO = "'ui-monospace', 'SFMono-Regular', Menlo, monospace"
const GAP  = 8  // uniform text-row gap (px)
// ─────────────────────────────────────────────────────────────────────────────

const wordmarkStyle = {
  fontFamily: 'var(--font-family)',
  fontSize: 12,
  fontWeight: 500,
  letterSpacing: LS_WORDMARK,
  color: INK1,
  lineHeight: 1,
  textTransform: 'uppercase',
}

// Both faces share this base — white paper card with real-card shadow
const faceBase = {
  position: 'absolute',
  inset: 0,
  background: PAPER,
  color: INK1,
  border: `1px solid ${BORDER}`,
  borderRadius: 10,
  padding: '30px 28px',
  boxShadow:
    '0 1px 0 rgba(0,0,0,0.05) inset, 0 12px 28px rgba(0,0,0,0.18), 0 24px 56px rgba(0,0,0,0.18)',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  backfaceVisibility: 'hidden',
  WebkitBackfaceVisibility: 'hidden',
}

const LINK_LABELS = { instagram: 'INSTAGRAM', email: 'EMAIL', website: 'WEBSITE' }

export default function BusinessCard({ user }) {
  const [flipped, setFlipped] = useState(false)

  // ─── Field derivations ───────────────────────────────────────────────────
  const displayName     = user?.display_name || ''
  const roleLine        = user?.role || null
  const affiliationLine = user?.affiliation || null
  // handle: @handle if present, omit entirely if absent (do NOT show #user_id)
  const handle = user?.handle ? `@${user.handle}` : null

  // items from external_links — filter empty values
  const items = Object.entries(user?.external_links || {})
    .filter(([, v]) => (v || '').trim())
    .map(([k, v]) => ({ label: LINK_LABELS[k] || k.toUpperCase(), value: v }))

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div style={{ perspective: 1400, width: '100%', maxWidth: 340, margin: '8px auto 16px', aspectRatio: '5 / 7' }}>
      <div
        role="button"
        aria-label={flipped ? 'Business card back — tap to flip to front' : 'Business card front — tap to flip'}
        tabIndex={0}
        onClick={() => setFlipped(f => !f)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setFlipped(f => !f) } }}
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          cursor: 'pointer',
          transformStyle: 'preserve-3d',
          transition: 'transform var(--motion-flip) var(--motion-ease)',
          transform: flipped ? 'rotateY(180deg)' : 'none',
          outline: 'none',
        }}
      >
        {/* ── FRONT face ──────────────────────────────────────────────────── */}
        <div style={{ ...faceBase, justifyContent: 'space-between' }}>
          {/* Wordmark — brand name top */}
          <div style={wordmarkStyle}>ARCHIBE</div>

          {/* Middle block: name / role / affiliation */}
          <section style={{ display: 'flex', flexDirection: 'column', gap: GAP }}>
            <div style={{
              fontSize: 26,
              fontWeight: 700,
              letterSpacing: LS_TIGHT,
              color: INK1,
              lineHeight: 1.05,
              textTransform: 'uppercase',
              fontFamily: 'var(--font-family)',
            }}>
              {displayName}
            </div>

            {roleLine && (
              <div style={{
                fontSize: 13,
                fontWeight: 700,
                color: INK1,
                lineHeight: 1.4,
                fontFamily: 'var(--font-family)',
              }}>
                {roleLine}
              </div>
            )}

            {affiliationLine && (
              <div style={{
                fontSize: 13,
                fontWeight: 400,
                color: INK3,
                lineHeight: 1.4,
                fontFamily: 'var(--font-family)',
              }}>
                {affiliationLine}
              </div>
            )}
          </section>

          {/* Footer: left handle+items, right QR stub (72px) */}
          <footer style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 14 }}>
            {/* Left: handle + external link items */}
            <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: GAP }}>
              {handle && (
                <div style={{
                  fontFamily: MONO,
                  fontSize: 12,
                  fontWeight: 600,
                  color: INK2,
                  lineHeight: 1.3,
                  whiteSpace: 'nowrap',
                }}>
                  {handle}
                </div>
              )}
              {items.map(({ label, value }) => (
                <div key={label} style={{
                  fontFamily: MONO,
                  fontSize: 11,
                  fontWeight: 500,
                  color: INK3,
                  lineHeight: 1.3,
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  gap: 6,
                }}>
                  <span style={{ textTransform: 'uppercase', letterSpacing: LS_CAPS, opacity: 0.7 }}>{label}</span>
                  <span>{value}</span>
                </div>
              ))}
            </div>

            {/* Right: real scannable QR (72px) */}
            <div style={{ flexShrink: 0, width: 72, height: 72 }}>
              <ProfileQr userId={user?.user_id} size={72} />
            </div>
          </footer>
        </div>

        {/* ── BACK face ───────────────────────────────────────────────────── */}
        <div style={{ ...faceBase, transform: 'rotateY(180deg)', justifyContent: 'space-between' }}>
          {/* Wordmark top-left */}
          <div style={{ ...wordmarkStyle, alignSelf: 'flex-start' }}>ARCHIBE</div>

          {/* Centered large QR (160px) — scan to open profile */}
          <section style={{ margin: 'auto 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
            <div style={{ padding: 10, background: PAPER, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ProfileQr userId={user?.user_id} size={160} />
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
                fontSize: 14,
                fontWeight: 600,
                letterSpacing: LS_TIGHT,
                color: INK2,
                textTransform: 'uppercase',
                fontFamily: 'var(--font-family)',
              }}>
                {displayName}
              </div>
              {affiliationLine && (
                <div style={{
                  fontSize: 12,
                  fontWeight: 400,
                  color: INK3,
                  marginTop: GAP,
                  fontFamily: 'var(--font-family)',
                }}>
                  {affiliationLine}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
