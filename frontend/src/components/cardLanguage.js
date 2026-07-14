/**
 * cardLanguage.js — shared "paper business-card" visual language.
 *
 * Extracted from the visual vocabulary of `components/profile/BusinessCard.jsx`
 * but INTENTIONALLY not imported from it (BusinessCard's PAPER/INK constants
 * are hardcoded white-paper-always, an intentional printed-artifact exception —
 * see BusinessCard.jsx header comment). This module is theme-adaptive: paper
 * and ink map onto existing themed CSS variables so the "card" look inverts
 * correctly across all 4 app themes (light paper + dark ink in light themes,
 * dark paper + light ink in dark themes).
 *
 * Pure JS — no JSX, no imports. Consumed via inline `style={{...}}` per
 * DESIGN.md §4 hybrid rule (inline styles own one-off / dynamic values;
 * CSS variables own themeable values).
 */

// ── Typographic invariants ──────────────────────────────────────────────────
export const MONO = "'ui-monospace', 'SFMono-Regular', Menlo, monospace"
export const LS_WORDMARK = '0.18em'
export const LS_TIGHT    = '-0.01em'
export const LS_CAPS     = '0.06em'
export const CARD_GAP    = 8

// ── Ink role map (theme-adaptive) ───────────────────────────────────────────
export const INK = {
  strong: 'var(--color-text)',
  mid:    'var(--color-text-2)',
  muted:  'var(--color-text-muted)',
  dim:    'var(--color-text-dim)',
}

// ── Paper surface ────────────────────────────────────────────────────────────
export const PAPER = 'var(--color-surface)'
export const PAPER_BORDER = 'var(--color-border-soft)'
export const PAPER_SHADOW =
  '0 1px 0 rgba(0,0,0,0.05) inset, 0 12px 28px rgba(0,0,0,0.18), 0 24px 56px rgba(0,0,0,0.18)'

/**
 * paperFaceStyle — factory for the base "paper card face" container style.
 * @param {{radius?: number, padding?: string}} opts
 */
export function paperFaceStyle({ radius = 20, padding = '26px 24px' } = {}) {
  return {
    background: PAPER,
    color: INK.strong,
    border: `1px solid ${PAPER_BORDER}`,
    borderRadius: radius,
    padding,
    boxShadow: PAPER_SHADOW,
    boxSizing: 'border-box',
    display: 'flex',
    flexDirection: 'column',
  }
}

// ── Type-role style objects ─────────────────────────────────────────────────
// Shared wordmark style — consumed by CardSkeleton.jsx (Discovery/Swipe
// loading skeletons). Hierarchy vs. other card text is expressed via
// size/weight/letter-spacing only (DESIGN.md §2.5a single-font policy) — this
// stays on the base font family, never MONO.
export const wordmarkStyle = {
  fontFamily: 'var(--font-family)',
  fontSize: 12,
  fontWeight: 500,
  letterSpacing: LS_WORDMARK,
  color: INK.strong,
  lineHeight: 1,
  textTransform: 'uppercase',
}

// LOGIN-REWORK-1: login page renders the wordmark as the brand/logo — bigger
// + bolder than the shared skeleton wordmark. Login-scoped so CardSkeleton
// (Discovery/Swipe loading) keeps the original 12px/500 wordmark.
export const loginWordmarkStyle = {
  ...wordmarkStyle,
  fontSize: 24,
  fontWeight: 700,
  letterSpacing: '0.14em',
}

// LOGIN-REWORK-1: base-font label style — for eyebrow/question/instructional
// text that must NOT sit on MONO (DESIGN.md §2.5a). MONO is reserved for
// intentional business-card meta accents (@id row, JOINED/stamp) only.
export const baseLabelStyle = {
  fontFamily: 'var(--font-family)',
  fontSize: 11,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: LS_CAPS,
  color: INK.muted,
  lineHeight: 1.3,
  margin: 0,
}

export const cardNameStyle = {
  fontFamily: 'var(--font-family)',
  fontSize: 26,
  fontWeight: 700,
  letterSpacing: LS_TIGHT,
  color: INK.strong,
  lineHeight: 1.05,
  textTransform: 'uppercase',
  margin: 0,
}

export const cardRoleStyle = {
  fontFamily: 'var(--font-family)',
  fontSize: 13,
  fontWeight: 700,
  color: INK.strong,
  lineHeight: 1.4,
  margin: 0,
}

export const cardMetaStyle = {
  fontFamily: 'var(--font-family)',
  fontSize: 13,
  fontWeight: 400,
  color: INK.muted,
  lineHeight: 1.4,
  margin: 0,
}

export const monoRowStyle = {
  fontFamily: MONO,
  fontSize: 12,
  fontWeight: 600,
  color: INK.mid,
  lineHeight: 1.3,
}

export const monoLabelStyle = {
  fontFamily: MONO,
  fontSize: 11,
  fontWeight: 500,
  textTransform: 'uppercase',
  letterSpacing: LS_CAPS,
  color: INK.muted,
  lineHeight: 1.3,
  margin: 0,
}

// LOGIN-REWORK-1: fine print is informational (consent/policy text the user
// reads to understand what they're agreeing to) — base font per DESIGN.md
// §2.5a, not MONO. Hierarchy vs. body text comes from size/color only.
export const finePrintStyle = {
  fontFamily: 'var(--font-family)',
  fontSize: 11,
  fontWeight: 400,
  color: INK.dim,
  lineHeight: 1.55,
  margin: 0,
}

// ── Ink button factories ─────────────────────────────────────────────────────
export function inkPrimaryStyle(disabled) {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
    padding: '14px 16px',
    border: 0,
    borderRadius: 'var(--radius-md)',
    background: INK.strong,
    color: 'var(--color-bg)',
    fontSize: 14,
    fontWeight: 600,
    fontFamily: 'inherit',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.55 : 1,
  }
}

export function inkSecondaryStyle(disabled) {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    padding: '14px 16px',
    borderRadius: 'var(--radius-md)',
    border: `1px solid ${INK.strong}`,
    background: 'transparent',
    color: INK.strong,
    fontSize: 14,
    fontWeight: 600,
    fontFamily: 'inherit',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.55 : 1,
  }
}

export function inkGhostStyle(disabled) {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 42,
    padding: '14px 16px',
    borderRadius: 'var(--radius-md)',
    border: '1px solid transparent',
    background: 'transparent',
    color: INK.dim,
    fontSize: 13,
    fontWeight: 600,
    fontFamily: 'inherit',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.55 : 1,
  }
}

// ── Paper input style ────────────────────────────────────────────────────────
export const paperInputStyle = {
  minHeight: 46,
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--color-border-soft)',
  background: 'transparent',
  color: INK.strong,
  padding: '0 13px',
  fontSize: 15,
  fontFamily: 'inherit',
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
}
