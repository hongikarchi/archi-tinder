/**
 * PageBackButton — shared floating circular back button, top-left.
 *
 * Design port (.claude/plans/canvas-design-port.md §6d item 6): every mock
 * replaces the app's old sticky glassmorphic header bar (back button left ·
 * centered title · spacer right) with a plain in-flow left-aligned title and
 * relocates "back" to a floating circular button at the canvas top-left
 * (verified zero `position:sticky` headers across the checked boards, e.g.
 * `settings-account.html`).
 *
 * Positioning is OWNED by this component (every caller wants the same spot),
 * mirroring PageTopControls' exact precedent: the mock uses
 * `position:absolute` inside its own 1440x900 canvas; the real app has no
 * positioned ancestor at that level, so `fixed` is the faithful equivalent.
 *
 * `onClick` is passed through unchanged — this component owns layout only,
 * never the navigation behavior. Callers keep their existing handler
 * (`navigate(-1)`, a custom back guard, etc.) exactly as before.
 */
export default function PageBackButton({ onClick, label = 'Back', icon, style }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="pressable"
      style={{ ...wrapStyle, ...style }}
    >
      {icon || (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="19" y1="12" x2="5" y2="12" />
          <polyline points="12 19 5 12 12 5" />
        </svg>
      )}
    </button>
  )
}

// ── Styles ──────────────────────────────────────────────────────────────────
// Layout / one-off values -> inline per DESIGN.md §4.

const wrapStyle = {
  position: 'fixed',
  top: 14,
  left: 16,
  zIndex: 300,
  width: 34,
  height: 34,
  borderRadius: '50%',
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border-soft)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'var(--color-text-dim)',
  cursor: 'pointer',
}
