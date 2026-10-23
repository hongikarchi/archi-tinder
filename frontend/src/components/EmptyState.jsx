import styles from './EmptyState.module.css'

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
 *
 * `neutral`: persona-report variant — icon in a surface-2 circle, `hint` line,
 * pill CTA and an optional text button (`secondaryLabel` + `onSecondary`).
 */
export default function EmptyState({
  icon, title, body, actionLabel, onAction, style,
  neutral = false, hint, secondaryLabel, onSecondary,
}) {
  if (neutral) {
    // Neutral variant (persona report states, DESIGN.md §8.9): icon circle on
    // surface-2, pill CTA, optional hint + text button. No red.
    return (
      <div className={styles.neutral} style={style}>
        {icon && <div className={styles.iconCircle} aria-hidden="true">{icon}</div>}
        {title && <h2 className={styles.title}>{title}</h2>}
        {body && <p className={styles.body}>{body}</p>}
        {hint && <p className={styles.hint}>{hint}</p>}
        {actionLabel && onAction && (
          <button type="button" className={styles.pill} onClick={onAction}>{actionLabel}</button>
        )}
        {secondaryLabel && onSecondary && (
          <button type="button" className={styles.textBtn} onClick={onSecondary}>{secondaryLabel}</button>
        )}
      </div>
    )
  }
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
