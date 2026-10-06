/**
 * cardShell.js — the single source of truth for the swipe-deck card surface.
 *
 * Originally extracted (2026-08-24) from the now-removed in-session
 * QuestionCard so it and the /assessment personality card rendered the SAME
 * card, not two look-alikes. QuestionCard was removed (FULL-RECOMMEND-1); the
 * question-shaped style exports below are retained because AssessmentCard
 * still consumes them. Change a value here and every consumer moves together.
 *
 * Size is NOT in the static style: it is reactive (hooks/useCardSize.js), so
 * consumers spread `{ width, height }` from useCardSize() over this style —
 * the same source SwipeDeck's ladder and DiscoveryPage's deck wrapper use.
 *
 * Radius is var(--radius-lg) (= 20px, tokens.css), which is the value
 * SwipeCard/SwipeDeck hardcode as `borderRadius: 20`. Referencing the token
 * here is deliberate: it lets a future radius change land in tokens.css.
 */
/** Ground shadow — matches the original calibration-card value. */
export const CARD_SHADOW = '0 25px 50px rgba(0,0,0,0.4)'

/** The card surface itself: footprint, radius, background, border, shadow. */
export const cardShellStyle = {
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
