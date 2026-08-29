/**
 * cardShell.js — the single source of truth for the swipe-deck card surface.
 *
 * Extracted from QuestionCard.jsx (2026-08-24) so the Taste/Discovery
 * calibration card and the /assessment personality card render the SAME card,
 * not two look-alikes. Change a value here and both move together.
 *
 * Size comes from SwipeCard's CARD_WIDTH/CARD_HEIGHT — the same constants
 * SwipeDeck's static ladder and DiscoveryPage's deck wrapper use, so a card
 * built on this shell drops into a SwipeDeck at exactly the ladder's footprint.
 *
 * Radius is var(--radius-lg) (= 20px, tokens.css), which is the value
 * SwipeCard/SwipeDeck hardcode as `borderRadius: 20`. Referencing the token
 * here is deliberate: it lets a future radius change land in tokens.css.
 */
import { CARD_WIDTH, CARD_HEIGHT } from './SwipeCard.jsx'

export { CARD_WIDTH, CARD_HEIGHT }

/** Ground shadow — matches QuestionCard's original value. */
export const CARD_SHADOW = '0 25px 50px rgba(0,0,0,0.4)'

/** The card surface itself: footprint, radius, background, border, shadow. */
export const cardShellStyle = {
  width: CARD_WIDTH,
  height: CARD_HEIGHT,
  borderRadius: 'var(--radius-lg)',
  overflow: 'hidden',
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  boxShadow: CARD_SHADOW,
  display: 'flex',
  flexDirection: 'column',
  boxSizing: 'border-box',
}

/** Inner padding + rhythm shared by every question-shaped card. */
export const questionCardBodyStyle = {
  padding: '32px 24px',
  gap: 24,
}

/** Question prompt typography. */
export const questionTitleStyle = {
  fontSize: 18,
  fontWeight: 700,
  color: 'var(--color-text)',
  textAlign: 'center',
  lineHeight: 1.4,
  margin: 0,
}

/** Small dim label above the prompt (badge / hint row). */
export const questionBadgeStyle = {
  fontSize: 11,
  fontWeight: 500,
  color: 'var(--color-text-dim)',
  margin: 0,
  letterSpacing: '0.04em',
}

/** Answer-option button base. Hover/active/selected live in the CSS module. */
export const questionOptionStyle = {
  padding: '14px 20px',
  borderRadius: 'var(--radius-md)',
  fontSize: 14,
  fontWeight: 600,
  background: 'var(--color-surface-2)',
  color: 'var(--color-text)',
  border: '1px solid var(--color-border)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  width: '100%',
  minHeight: 48,
  textAlign: 'left',
}
