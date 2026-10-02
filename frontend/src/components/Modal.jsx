import { useEffect, useId, useRef } from 'react'
import FloatingIconButton from './FloatingIconButton.jsx'
import styles from './Modal.module.css'

/**
 * Modal — shared Modal/Sheet (DESIGN.md §8.10): auto-selects per environment
 * — centered modal (desktop >=769px, max-width 480/radius-md) or bottom
 * sheet (mobile <=768px, top corners radius-xl, 36x4 handle, max-height
 * 85vh, slide-up on `--motion-flip`/`--motion-ease`). Backdrop is always
 * `--color-scrim-modal` (0.4).
 *
 * Close = a top-right `FloatingIconButton`. Closes on ESC, on a backdrop
 * click, or via the close button. Focuses the dialog panel on open;
 * `role="dialog" aria-modal aria-labelledby` (via `useId`) on the panel.
 *
 * `zIndex` — NOT hardcoded, because callers stack at different layers today
 * (e.g. VerifyGateModal at 10100, above SaveToBoardModal) — losing that
 * would break layering when this replaces a caller's own backdrop.
 *
 * Adopted so far (UI-CONSISTENCY-B Phase 2b): `VerifyGateModal`. Phase 3
 * migrated every other modal in the app (`ShareCardModal`, `SaveToBoardModal`,
 * `SaveBoardModal`, `SurpriseBoardModal`, `WorkDetailModal`, plus SwipePage's
 * exit/dismiss confirm popups and DiscoveryPage's leave-warning modal).
 *
 * `centered` (Phase 3 addition, backward-compatible — default false keeps
 * every existing caller's mobile bottom-sheet behavior unchanged): forces the
 * centered-modal layout at every viewport width instead of auto-switching to
 * a bottom sheet on mobile. For small interrupt-style confirm dialogs (e.g.
 * SwipePage's exit/dismiss popups) a bottom sheet reads as an unrelated
 * gesture mid-swipe-session — centered-always matches the existing UX.
 *
 * `closeOnEscape` (Phase 3 addition, backward-compatible — default true):
 * set false when a caller deliberately wants Escape to NOT bubble to this
 * Modal because it stacks under another open Modal that should own Escape
 * (e.g. SaveBoardModal staying open under VerifyGateModal at zIndex 10100 so
 * the user's in-progress name/visibility choices survive verification).
 *
 * FULL-MESSAGING-1 additions (all backward-compatible, default off):
 *  - `ariaLabel`  — accessible name when no `title` is rendered (a caller that
 *    draws its own header row inside the body).
 *  - `fill`       — fixed-height flex-column panel (body fills the remaining
 *    height and the caller scrolls inside it) for chat-style sheets whose
 *    composer must stay pinned at the bottom.
 *  - `panelStyle` — extra inline style on the panel; used to pass the
 *    `--modal-max-h` / `--modal-kb-inset` custom properties from
 *    `useVisualViewportSheetStyle` so a mobile sheet clears the keyboard.
 */
export default function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  zIndex = 300,
  closeLabel = 'Close',
  width = 480,
  className = '',
  centered = false,
  closeOnEscape = true,
  ariaLabel,
  fill = false,
  panelStyle,
}) {
  const titleId = useId()
  const panelRef = useRef(null)

  useEffect(() => {
    if (!open || !closeOnEscape) return
    function onKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose, closeOnEscape])

  useEffect(() => {
    if (open) panelRef.current?.focus()
  }, [open])

  if (!open) return null

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div
      className={`${styles.backdrop} ${centered ? styles.centered : ''}`}
      style={{ zIndex }}
      onClick={handleBackdropClick}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-label={title ? undefined : ariaLabel}
        tabIndex={-1}
        className={`${styles.panel} ${centered ? styles.centered : ''} ${fill ? styles.fill : ''} ${className}`}
        style={{ '--modal-max-width': `${width}px`, ...panelStyle }}
      >
        <div className={styles.handle} aria-hidden="true" />

        <FloatingIconButton
          onClick={onClose}
          ariaLabel={closeLabel}
          style={{ position: 'absolute', top: 12, right: 12 }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </FloatingIconButton>

        {title && <h2 id={titleId} className={styles.title}>{title}</h2>}

        <div className={styles.body}>{children}</div>

        {footer && <div className={styles.footer}>{footer}</div>}
      </div>
    </div>
  )
}
