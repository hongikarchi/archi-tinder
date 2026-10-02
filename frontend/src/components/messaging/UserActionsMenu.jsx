import { useEffect, useRef, useState } from 'react'
import Modal from '../Modal.jsx'
import FloatingIconButton from '../FloatingIconButton.jsx'
import ReportDialog from './ReportDialog.jsx'
import { useTranslation } from '../../i18n/index.js'
import { blockUser, unblockUser } from '../../api/messaging.js'
import { VerifyRequiredError } from '../../api/projects.js'
import { markBlocked, markUnblocked, useBlockedUser } from './blockedUsers.js'
import styles from './Messaging.module.css'

/**
 * UserActionsMenu — the "..." menu with Block / Report for one user
 * (FULL-MESSAGING-1). Used in the conversation header and on another user's
 * profile. Renders a 28px FloatingIconButton (44px hit area, DESIGN.md §3.2),
 * a small dropdown, a block-confirm dialog and a report dialog.
 *
 * `onBlocked` fires after a successful block (parent closes the conversation
 * UI / hides the contact CTA); `onUnblocked` after a successful unblock. After blocking, the same menu item flips to
 * "Unblock" for the rest of the session — the API has no block-status read, so
 * the state lives in the shared `blockedUsers` store (every menu instance for
 * this user agrees, even after the conversation sheet is reopened).
 * `onOverlayChange(open)` lets a host sheet suspend its own ESC-to-close while
 * the dropdown or a dialog owns Escape.
 */
export default function UserActionsMenu({ userId, name, onBlocked, onUnblocked, onOverlayChange }) {
  const { t } = useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [reportOpen, setReportOpen] = useState(false)
  const blocked = useBlockedUser(userId)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const wrapRef = useRef(null)

  const overlay = menuOpen || confirmOpen || reportOpen
  useEffect(() => {
    onOverlayChange?.(overlay)
  }, [overlay, onOverlayChange])
  useEffect(() => () => onOverlayChange?.(false), [onOverlayChange])

  // dropdown: close on outside press / Escape
  useEffect(() => {
    if (!menuOpen) return undefined
    function onPointer(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setMenuOpen(false)
    }
    function onKey(e) {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [menuOpen])

  async function handleBlockConfirm() {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await blockUser(userId)
      markBlocked(userId)
      setConfirmOpen(false)
      onBlocked?.()
    } catch (err) {
      if (err instanceof VerifyRequiredError) setConfirmOpen(false)
      else setError('messaging.blockError')
    } finally {
      setBusy(false)
    }
  }

  async function handleUnblock() {
    setMenuOpen(false)
    try {
      await unblockUser(userId)
      markUnblocked(userId)
      onUnblocked?.()
    } catch {
      /* best-effort — the item stays "Unblock" so the user can retry */
    }
  }

  return (
    <div className={styles.menuWrap} ref={wrapRef}>
      <FloatingIconButton
        onClick={() => setMenuOpen(o => !o)}
        ariaLabel={t('messaging.more')}
        title={t('messaging.more')}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden="true">
          <circle cx="5" cy="12" r="1.8" />
          <circle cx="12" cy="12" r="1.8" />
          <circle cx="19" cy="12" r="1.8" />
        </svg>
      </FloatingIconButton>

      {menuOpen && (
        <div className={styles.menu} role="menu">
          {blocked ? (
            <button type="button" role="menuitem" className={styles.menuItem} onClick={handleUnblock}>
              {t('messaging.unblock')}
            </button>
          ) : (
            <button
              type="button"
              role="menuitem"
              className={`${styles.menuItem} ${styles.menuItemDanger}`}
              onClick={() => { setMenuOpen(false); setError(null); setConfirmOpen(true) }}
            >
              {t('messaging.block')}
            </button>
          )}
          <button
            type="button"
            role="menuitem"
            className={styles.menuItem}
            onClick={() => { setMenuOpen(false); setReportOpen(true) }}
          >
            {t('messaging.report')}
          </button>
        </div>
      )}

      {confirmOpen && (
        <Modal
          open
          centered
          onClose={() => setConfirmOpen(false)}
          zIndex={320}
          portal
          title={t('messaging.blockConfirmTitle', { name })}
          closeLabel={t('messaging.close')}
        >
          <p className={styles.dialogText}>{t('messaging.blockConfirmBody')}</p>
          {error && <p className={styles.composeError} role="alert">{t(error)}</p>}
          <div className={styles.dialogActions}>
            <button type="button" className={`${styles.btn} ${styles.btnSecondary}`} onClick={() => setConfirmOpen(false)}>
              {t('messaging.cancel')}
            </button>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnDestructive}`}
              onClick={handleBlockConfirm}
              disabled={busy}
            >
              {t('messaging.blockConfirm')}
            </button>
          </div>
        </Modal>
      )}

      {reportOpen && (
        <ReportDialog targetType="user" targetId={userId} onClose={() => setReportOpen(false)} />
      )}
    </div>
  )
}
