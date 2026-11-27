import { useEffect, useRef, useState } from 'react'
import Modal from '../Modal.tsx'
import FloatingIconButton from '../FloatingIconButton.tsx'
import ReportDialog from './ReportDialog.tsx'
import { useTranslation } from '../../i18n/index.ts'
import { blockUser, unblockUser } from '../../api/messaging.ts'
import { joinFollowStatus } from '../../api/social.ts'
import { useFollowEnabled } from '../../hooks/useMessagingFeature.ts'
import { VerifyRequiredError } from '../../api/projects.ts'
import { markBlocked, markUnblocked, useBlockedUser, getBlockSeq, applyServerBlockedByMe } from './blockedUsers.ts'
import styles from './Messaging.module.css'

/**
 * UserActionsMenu — the "..." menu with Block / Report for one user
 * (FULL-MESSAGING-1). Used in the conversation header and on another user's
 * profile. Renders a 28px FloatingIconButton (44px hit area, DESIGN.md §3.2),
 * a small dropdown, a block-confirm dialog and a report dialog.
 *
 * `onBlocked` fires after a successful block (parent closes the conversation
 * UI / hides the follow CTA); `onUnblocked` after a successful unblock. After
 * blocking, the same menu item flips to "Unblock". State lives in the shared
 * `blockedUsers` store (every menu instance for this user agrees); on mount it
 * is seeded from `blocked_by_me` on users/<id>/follow/ so a refresh still
 * offers "Unblock" (#372). Block/report are reachable
 * with either the messaging or the follow flag (the hosts decide whether to
 * mount the menu); the follow-status seed read 404s while the follow flag is
 * off, so it only runs with the follow flag — otherwise the menu works from
 * the local store alone.
 */
interface UserActionsMenuProps {
  userId: number | string
  name?: string
  onBlocked?: () => void
  onUnblocked?: () => void
}

export default function UserActionsMenu({ userId, name, onBlocked, onUnblocked }: UserActionsMenuProps) {
  const { t } = useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [reportOpen, setReportOpen] = useState(false)
  const followEnabled = useFollowEnabled()
  const blocked = useBlockedUser(userId)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  // The server status is authoritative: sync the session store both ways
  // (block/unblock done on another device/tab included). A response issued before
  // a local block/unblock is dropped via the seq check. Joins FollowCta's read
  // on the profile page; the seq used is the one from when that read started.
  useEffect(() => {
    // users/<id>/follow/ answers 404 while the follow flag is off.
    if (!followEnabled || !userId) return undefined
    let cancelled = false
    const { promise, meta } = joinFollowStatus(userId, getBlockSeq())
    promise
      .then(data => { if (!cancelled) applyServerBlockedByMe(userId, data?.blocked_by_me, meta as number) })
      .catch(() => {}) // non-critical: the menu works without the status read
    return () => { cancelled = true }
  }, [followEnabled, userId])

  // dropdown: close on outside press / Escape
  useEffect(() => {
    if (!menuOpen) return undefined
    function onPointer(e: PointerEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    function onKey(e: KeyboardEvent) {
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
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await unblockUser(userId)
      markUnblocked(userId)
      setMenuOpen(false)
      onUnblocked?.()
    } catch {
      // keep the menu open so the failure is visible and the user can retry
      setError('messaging.unblockError')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={styles.menuWrap} ref={wrapRef}>
      <FloatingIconButton
        onClick={() => { setError(null); setMenuOpen(o => !o) }}
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
            <button type="button" role="menuitem" className={styles.menuItem} onClick={handleUnblock} disabled={busy}>
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
          {error && !confirmOpen && <p className={styles.composeError} role="alert">{t(error)}</p>}
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
