import styles from './FloatingIconButton.module.css'

/**
 * FloatingIconButton — shared 28px floating circle icon button.
 *
 * DESIGN.md §3.2: every floating/overlay circle (back, logout, share, bell,
 * settings, carousel arrows, modal close, photo-hero buttons) renders through
 * ONE component — no page builds its own circle. Visual size stays
 * `--icon-btn-size` (28px); the `--icon-btn-hit` (44px) mobile touch target
 * is an invisible expanded hit area (`::before` in the CSS module) that never
 * affects layout or visual size.
 *
 * Icon convention: pass a `--icon-size` (16px) SVG, `strokeWidth="2"`,
 * `fill="none" stroke="currentColor"` as `children`. The module CSS also
 * force-sizes any child `<svg>` to `--icon-size`, so callers keep their
 * existing literal `width="16" height="16"` (already normalized) without it
 * ever drifting from the token.
 *
 * `variant`:
 *  - `'surface'` (default) — `var(--color-surface)` background,
 *    `var(--color-border-soft)` border, `var(--color-text-dim)` icon (the
 *    colors PageBackButton originally shipped).
 *  - `'onPhoto'` — translucent dark glass (`--color-scrim*` tokens) + white
 *    icon, for a button sitting directly on a photo with no card chrome
 *    underneath it.
 *
 * Positioning is NEVER owned by this component — callers pass `style`
 * (position/top/left/right/zIndex), exactly as every call site did before
 * extraction.
 *
 * `className` is MERGED (not replaced) with the component's own classes.
 * This matters beyond cosmetics: `lib/tinderCard.js` gates touch-drag
 * handling on `element.className.includes('pressable')`, so this component
 * always keeps `pressable` in the final class list — dropping it would
 * silently break drag on any button that sits inside a tinder-card ancestor.
 */
export default function FloatingIconButton({
  onClick,
  ariaLabel,
  children,
  variant = 'surface',
  className = '',
  style,
  type = 'button',
  ...rest
}) {
  const variantClass = variant === 'onPhoto' ? styles.onPhoto : ''
  const finalClassName = [styles.btn, variantClass, 'pressable', className]
    .filter(Boolean)
    .join(' ')

  return (
    <button
      type={type}
      onClick={onClick}
      aria-label={ariaLabel}
      className={finalClassName}
      style={style}
      {...rest}
    >
      {children}
    </button>
  )
}
