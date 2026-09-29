/**
 * EmptyState — shared "no data at all" pattern (DESIGN.md §8.9 tier 1: Empty
 * component — friendly illustration + one-line description + Primary CTA).
 *
 * `icon`: an optional node (an SVG, `<BuildingIconEmpty/>`, etc).
 * `title`: `--fs-emphasis` (16) / `--fw-semibold`.
 * `body`: `--fs-body` (14), dim (`--color-text-dim`).
 * `actionLabel` + `onAction`: renders a flat-accent CTA button (DESIGN.md
 * §8.1 colors, radius `--radius-md`, 44px min-height) — the component OWNS
 * this button's style so every empty-state CTA across the app matches,
 * rather than each caller re-styling its own button.
 */
export default function EmptyState({ icon, title, body, actionLabel, onAction, style }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '80px 20px',
        gap: 16,
        textAlign: 'center',
        ...style,
      }}
    >
      {icon}
      {title && (
        <p
          style={{
            margin: 0,
            color: 'var(--color-text)',
            fontSize: 'var(--fs-emphasis)',
            fontWeight: 'var(--fw-semibold)',
          }}
        >
          {title}
        </p>
      )}
      {body && (
        <p
          style={{
            margin: 0,
            color: 'var(--color-text-dim)',
            fontSize: 'var(--fs-body)',
          }}
        >
          {body}
        </p>
      )}
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          style={{
            marginTop: 4,
            minHeight: 44,
            padding: '0 24px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            background: 'var(--accent-1)',
            color: '#fff',
            fontSize: 'var(--fs-body)',
            fontWeight: 'var(--fw-semibold)',
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}
