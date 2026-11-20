import type { ReactNode } from 'react'
import styles from './CoverIconButton.module.css'

/**
 * CoverIconButton — 32px translucent-black glass circle (same family as the
 * BoardCover owner chips, no border) inside a 44px transparent hit area.
 * `confirm` switches to a lighter white glass (name edit pending save).
 * Children = 14px white stroke icon.
 */
interface CoverIconButtonProps {
  onClick?: () => void
  disabled?: boolean
  ariaLabel?: string
  ariaPressed?: boolean
  confirm?: boolean
  dimmed?: boolean
  children?: ReactNode
}

export default function CoverIconButton({ onClick, disabled, ariaLabel, ariaPressed, confirm = false, dimmed = false, children }: CoverIconButtonProps) {
  return (
    <button
      type="button"
      className={styles.hit}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      style={{ opacity: dimmed ? 0.4 : 1 }}
    >
      <span className={`${styles.glass} ${confirm ? styles.confirm : ''}`}>{children}</span>
    </button>
  )
}
