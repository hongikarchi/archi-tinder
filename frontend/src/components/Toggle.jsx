/**
 * Toggle — reusable controlled switch component.
 *
 * Props:
 *   checked  {bool}    — current on/off state
 *   onChange {fn}      — called with the next bool value
 *   disabled {bool}    — purely disabled (not interactive, visually dimmed)
 *   locked   {bool}    — locked-on (always appears checked, cannot be changed;
 *                        use for mandatory settings like security notifications)
 *   label    {string}  — visible text label (optional)
 *   aria-label {string}— accessible name when no visible label is provided
 *
 * a11y: native <button role="switch"> fires onClick on click + Space + Enter
 *       without extra onKeyDown handlers.
 *
 * Derived from archibe-profile-ref NotificationsForm Toggle.
 * Token map applied: --color-accent-1 → --accent-1, --ease → --motion-ease.
 */
import styles from './Toggle.module.css'

export default function Toggle({
  checked,
  onChange,
  disabled = false,
  locked = false,
  label,
  'aria-label': ariaLabel,
}) {
  const isDisabled = disabled || locked
  const isOn = locked ? true : checked

  const handleClick = () => {
    if (!isDisabled) onChange(!isOn)
  }

  const track = (
    <button
      type="button"
      role="switch"
      aria-checked={isOn}
      aria-label={ariaLabel || label}
      onClick={handleClick}
      disabled={isDisabled}
      className={styles.track}
      style={{
        flexShrink: 0,
        width: 44,
        height: 26,
        padding: 0,
        border: 0,
        borderRadius: 999,
        /* Runtime-dynamic: bg depends on current state */
        background: isOn ? 'var(--accent-1)' : 'var(--color-surface-3)',
        opacity: isDisabled ? 0.55 : 1,
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        position: 'relative',
        transition: `background var(--motion-fast) var(--motion-ease)`,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          position: 'absolute',
          top: 3,
          /* Runtime-dynamic: thumb position depends on state */
          left: isOn ? 21 : 3,
          width: 20,
          height: 20,
          borderRadius: '50%',
          background: '#fff',
          boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
          transition: `left var(--motion-fast) var(--motion-ease)`,
        }}
      />
    </button>
  )

  if (!label) return track

  return (
    <span className={styles.wrapper}>
      {track}
      <span className={styles.label}>{label}</span>
    </span>
  )
}
