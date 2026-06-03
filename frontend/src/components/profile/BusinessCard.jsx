/**
 * BusinessCard.jsx — Shareable profile card.
 *
 * Design intent: "a white paper card — always white regardless of app theme,
 * it's a printed card."
 *
 * INTENTIONAL design exception — the PAPER/INK/BORDER constants below are
 * HARDCODED and must NOT be re-tokenized to themed CSS variables. They represent
 * the printed-card artifact; the card stays white-on-dark-ink across all 4 app
 * themes. Only the modal chrome (backdrop, instructional text) is themed.
 *
 * Fields mapped from UserProfileSerializer:
 *   display_name   → name on front (UPPERCASED, 26px/700)
 *   mbti           → "role" line (persona type label, if absent uses mbti, else omitted)
 *   persona_summary.one_liner → "affiliation" line (italic, INK3, omit if absent)
 *   external_links → items[] rows (instagram / email / website — filter empties)
 *   user_id        → QR seed + handle display
 *
 * NOT scannable QR: see FakeQr.jsx stub note.
 */

import { useState } from 'react'
import FakeQr from './FakeQr.jsx'

// ─── Printed-card constants (intentionally hardcoded — never tokenize) ───────
const PAPER  = '#FFFFFF'
const INK1   = '#0A0A0A'
const INK2   = '#3D3D3D'
const INK3   = '#8C8C8C'
const BORDER = '#E6E6E3'
// Letter-spacing inline values (we have no token for these — per task spec)
const LS_WORDMARK = '0.18em'
const LS_TIGHT    = '-0.01em'
const LS_CAPS     = '0.06em'
const MONO        = "'ui-monospace', 'SFMono-Regular', Menlo, monospace"
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
function faceBase() {
  return {
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
}

export default function BusinessCard({ user }) {
  const [flipped, setFlipped] = useState(false)

  // ─── Field derivations ───────────────────────────────────────────────────
  const displayName = user?.display_name || ''

  // role line: persona_type if available, else MBTI if available, else omit
  const personaType = user?.persona_summary?.persona_type || null
  const roleLine = personaType || user?.mbti || null

  // affiliation line: one_liner from persona, else omit
  const affiliationLine = user?.persona_summary?.one_liner || null

  // handle: id-based label, omit if no user_id
  const handle = user?.user_id ? `#${user.user_id}` : null

  // items from external_links — filter empty values
  const LINK_LABELS = { instagram: 'Instagram', email: 'Email', website: 'Website' }
  const items = Object.entries(user?.external_links || {})
    .filter(([, v]) => (v || '').trim())
    .map(([k, v]) => ({ label: LINK_LABELS[k] || k, value: v }))

  // QR seed (user_id as string for determinism)
  const qrSeed = String(user?.user_id || 'archivibe')
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
          transition: `transform var(--motion-flip) var(--motion-ease)`,
          transform: flipped ? 'rotateY(180deg)' : 'none',
          outline: 'none',
        }}
      >
        {/* ── FRONT face ──────────────────────────────────────────────────── */}
        <div style={faceBase()}>
          {/* Wordmark top */}
          <div style={{ ...wordmarkStyle, marginBottom: 'auto' }}>
            ArchiTinder
          </div>

          {/* Middle block: name / role / affiliation */}
          <div style={{ margin: '0 0 24px' }}>
            <div style={{
              fontSize: 26,
              fontWeight: 700,
              letterSpacing: LS_TIGHT,
              color: INK1,
              lineHeight: 1.1,
              textTransform: 'uppercase',
              marginBottom: 8,
              fontFamily: 'var(--font-family)',
            }}>
              {displayName}
            </div>

            {roleLine && (
              <div style={{
                fontSize: 13,
                color: INK2,
                letterSpacing: LS_CAPS,
                textTransform: 'uppercase',
                fontFamily: 'var(--font-family)',
                marginBottom: 4,
              }}>
                {roleLine}
              </div>
            )}

            {affiliationLine && (
              <div style={{
                fontSize: 13,
                color: INK3,
                fontFamily: 'var(--font-family)',
                fontStyle: 'italic',
              }}>
                {affiliationLine}
              </div>
            )}
          </div>

          {/* Footer: left handle+items, right QR stub */}
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8 }}>
            {/* Left: handle + items */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, minWidth: 0 }}>
              {handle && (
                <div style={{
                  fontFamily: MONO,
                  fontSize: 10,
                  color: INK3,
                  letterSpacing: LS_CAPS,
                  marginBottom: 4,
                }}>
                  {handle}
                </div>
              )}
              {items.map(({ label, value }) => (
                <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <span style={{
                    fontFamily: MONO,
                    fontSize: 8,
                    color: INK3,
                    letterSpacing: LS_CAPS,
                    textTransform: 'uppercase',
                  }}>
                    {label}
                  </span>
                  <span style={{
                    fontFamily: MONO,
                    fontSize: 10,
                    color: INK2,
                    wordBreak: 'break-all',
                    lineHeight: 1.3,
                  }}>
                    {value}
                  </span>
                </div>
              ))}
            </div>

            {/* Right: QR stub (72px) — NOT scannable */}
            <div style={{ flexShrink: 0 }}>
              <FakeQr seed={qrSeed} size={72} color={INK1} />
            </div>
          </div>
        </div>

        {/* ── BACK face ───────────────────────────────────────────────────── */}
        <div style={{ ...faceBase(), transform: 'rotateY(180deg)', justifyContent: 'space-between', alignItems: 'center' }}>
          {/* Wordmark top */}
          <div style={{ ...wordmarkStyle, alignSelf: 'flex-start' }}>
            ArchiTinder
          </div>

          {/* Centered large QR stub — NOT scannable */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <FakeQr seed={qrSeed} size={160} color={INK1} />
            {/* Not-yet-functional notice */}
            <div style={{
              fontFamily: MONO,
              fontSize: 9,
              color: INK3,
              letterSpacing: LS_CAPS,
              textTransform: 'uppercase',
              textAlign: 'center',
            }}>
              {/* 공유 준비 중 / not yet scannable */}
              공유 준비 중
            </div>
          </div>

          {/* Name + affiliation bottom */}
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 15,
              fontWeight: 700,
              letterSpacing: LS_TIGHT,
              color: INK1,
              fontFamily: 'var(--font-family)',
              textTransform: 'uppercase',
              marginBottom: 4,
            }}>
              {displayName}
            </div>
            {affiliationLine && (
              <div style={{
                fontSize: 11,
                color: INK3,
                fontFamily: 'var(--font-family)',
                fontStyle: 'italic',
              }}>
                {affiliationLine}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
