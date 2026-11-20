import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Modal from '../Modal.tsx'
import { useTranslation } from '../../i18n/index.ts'
import { getFollowStatus, followUser, unfollowUser } from '../../api/social.ts'
import { openConversation, listConversations } from '../../api/messaging.ts'
import { VerifyRequiredError } from '../../api/projects.ts'
import { useFollowEnabled, useMessagingEnabled } from '../../hooks/useMessagingFeature.ts'
import { getBlockSeq, applyServerBlockedByMe } from './blockedUsers.ts'
import styles from './Messaging.module.css'
import type { FollowStatus } from '../../types/api.ts'

/**
 * FollowCta — the follow / message buttons on ANOTHER user's profile
 * (SNS-FOLLOW-1; replaces the contact-request CTA). Reflects GET
 * users/<id>/follow/:
 *   is_following                  -> [팔로잉] (opens an unfollow confirm) and,
 *                                    only when messaging is also enabled,
 *                                    [메시지 보내기] (opens the conversation).
 *                                    An existing follow survives the target
 *                                    opting out, so is_following wins over
 *                                    can_follow.
 *   Message button = (is_following OR has_conversation) AND messaging enabled.
 *   Without a follow, POST conversations/ would 403, so the existing
 *   conversation is looked up in listConversations() instead.
 *   !following + can_follow       -> [팔로우] ([맞팔로우] when they follow me);
 *                                    plus [메시지 보내기] alongside when an open
 *                                    conversation exists (has_conversation) and
 *                                    messaging is enabled
 *   !following + !can_follow
 *     + has_conversation          -> only [메시지 보내기] (existing conversation
 *                                    partner who opted out of follows)
 *   !following + verify_required  -> [팔로우]; click fires the global
 *                                    'archithon:verify-required' {reason:
 *                                    'messaging'} event (VerifyGateModal), no
 *                                    API call
 *   anything else (self, blocked, guest target, opted-out target)
 *                                 -> renders NOTHING — no disabled button, no
 *                                    hint — so these cases stay visually
 *                                    indistinguishable by design.
 * Follow / unfollow are optimistic: the UI flips at once, a failure rolls back
 * and shows a visible error (a VerifyRequiredError rolls back silently — the
 * global modal explains). Status fetch failure -> retry button (one fetch per
 * click, no auto loop). Loading, FOLLOW flag OFF, or `hidden` / blocked_by_me
 * (I blocked them) -> renders nothing; flag OFF never calls the API.
 * `buttonClassName` lets the host page keep its own CTA styling; `name` is the
 * peer's display handle for the unfollow confirm title.
 */
interface FollowCtaProps {
  userId: number | string
  name?: string
  buttonClassName?: string
  hidden?: boolean
}

type Pending = 'follow' | 'unfollow' | 'message' | null

export default function FollowCta({ userId, name, buttonClassName, hidden = false }: FollowCtaProps) {
  const { t } = useTranslation()
  const enabled = useFollowEnabled()
  const messagingEnabled = useMessagingEnabled()
  const navigate = useNavigate()
  const [status, setStatus] = useState<FollowStatus | null>(null) // null = loading / unknown
  const [loadFailed, setLoadFailed] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pending, setPending] = useState<Pending>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  // A write that resolves after the profile switched must not touch the new
  // user's state.
  const userIdRef = useRef(userId)
  userIdRef.current = userId

  useEffect(() => {
    // Fetched even while `hidden` so a block/unblock done elsewhere is noticed;
    // `hidden` stays a dep so a local unblock refetches fresh status.
    if (!enabled || !userId) return undefined
    let cancelled = false
    const s = getBlockSeq()
    getFollowStatus(userId)
      .then(data => {
        if (cancelled) return
        // Server status is authoritative (both ways); stale responses dropped.
        applyServerBlockedByMe(userId, data?.blocked_by_me, s)
        setStatus(data)
        setLoadFailed(false)
      })
      .catch(() => { if (!cancelled) { setStatus(null); setLoadFailed(true) } })
    return () => { cancelled = true }
  }, [enabled, userId, hidden, reloadKey])

  // A guest finished verification in place (App.jsx onPromoted) -> the cached
  // 'verify_required' reason is stale; refetch once.
  useEffect(() => {
    if (!enabled || !userId || hidden) return undefined
    const onVerified = () => setReloadKey(k => k + 1)
    window.addEventListener('archithon:verified', onVerified)
    return () => window.removeEventListener('archithon:verified', onVerified)
  }, [enabled, userId, hidden])

  // New profile -> drop the previous user's status (render-time reset, no
  // effect flicker).
  const [statusUser, setStatusUser] = useState(userId)
  if (statusUser !== userId) {
    setStatusUser(userId)
    setStatus(null)
    setLoadFailed(false)
    setConfirmOpen(false)
    setPending(null)
    setActionError(null)
  }

  // A block/unblock toggle invalidates the rendered status (blocking deletes
  // follows both ways, unblock does not restore them) until the refetch above
  // answers — no stale [팔로잉] flash after an unblock.
  const [statusHidden, setStatusHidden] = useState(hidden)
  if (statusHidden !== hidden) {
    setStatusHidden(hidden)
    setStatus(null)
    setConfirmOpen(false)
    setActionError(null)
  }

  if (!enabled || (!status && !loadFailed)) return null

  function handleRetry() {
    setLoadFailed(false)
    setReloadKey(k => k + 1)
  }

  function handleVerifyRequired() {
    window.dispatchEvent(new CustomEvent('archithon:verify-required', { detail: { reason: 'messaging' } }))
  }

  async function handleFollow() {
    if (pending || !status) return
    const requestedFor = userId
    const prev = status
    setPending('follow')
    setActionError(null)
    setStatus({ ...prev, is_following: true }) // optimistic
    try {
      const res = await followUser(userId)
      if (userIdRef.current !== requestedFor) return
      setStatus(typeof res?.is_following === 'boolean' ? res : { ...prev, is_following: true })
    } catch (err) {
      if (userIdRef.current !== requestedFor) return
      setStatus(cur => (cur ? { ...cur, is_following: prev.is_following } : cur))
      // VerifyRequiredError: the global modal already explains — stay silent.
      if (!(err instanceof VerifyRequiredError)) {
        setActionError('follow.followError')
        // e.g. 400 unavailable: let the server's can_follow replace the stale one.
        setReloadKey(k => k + 1)
      }
    } finally {
      if (userIdRef.current === requestedFor) setPending(null)
    }
  }

  async function handleUnfollowConfirm() {
    if (pending || !status) return
    const requestedFor = userId
    const prev = status
    setConfirmOpen(false)
    setPending('unfollow')
    setActionError(null)
    setStatus({ ...prev, is_following: false, can_follow: true }) // optimistic
    try {
      await unfollowUser(userId)
      if (userIdRef.current !== requestedFor) return
      // can_follow after an unfollow is the server's call (e.g. opted-out
      // target) — refetch instead of guessing.
      setReloadKey(k => k + 1)
    } catch (err) {
      if (userIdRef.current !== requestedFor) return
      setStatus(prev)
      if (!(err instanceof VerifyRequiredError)) setActionError('follow.unfollowError')
    } finally {
      if (userIdRef.current === requestedFor) setPending(null)
    }
  }

  async function handleMessage() {
    if (pending) return
    const requestedFor = userId
    setPending('message')
    setActionError(null)
    try {
      let res: { id: number, other?: unknown, closed?: boolean } | undefined
      if (status?.is_following) {
        res = await openConversation(userId)
      } else {
        const list = await listConversations()
        res = (list?.results || []).find(
          (c: { other?: { user_id?: number | string } }) => String(c.other?.user_id) === String(userId),
        )
      }
      if (userIdRef.current !== requestedFor) return
      if (!res) { setActionError('follow.messageError'); return }
      navigate(`/messages/${res.id}`, {
        state: { conversation: { id: res.id, other: res.other, closed: res.closed } },
      })
    } catch (err) {
      if (userIdRef.current !== requestedFor) return
      if (!(err instanceof VerifyRequiredError)) setActionError('follow.messageError')
    } finally {
      if (userIdRef.current === requestedFor) setPending(null)
    }
  }

  const messageButton = (
    <button type="button" className={buttonClassName} onClick={handleMessage} disabled={pending !== null}>
      {t('messaging.sendMessage')}
    </button>
  )
  const showMessage = !!status && (status.is_following || status.has_conversation) && messagingEnabled

  let buttons = null
  if (hidden || status?.blocked_by_me) {
    buttons = null // I blocked them: hide the buttons only
  } else if (!status) {
    buttons = (
      <button type="button" className={buttonClassName} onClick={handleRetry}>
        {t('messaging.statusLoadFailed')}
      </button>
    )
  } else if (status.is_following) {
    buttons = (
      <div className={styles.followRow}>
        <button
          type="button"
          className={`${styles.btn} ${styles.btnSecondary}`}
          onClick={() => { setActionError(null); setConfirmOpen(true) }}
          disabled={pending !== null}
        >
          {t('follow.following')}
        </button>
        {showMessage && messageButton}
      </div>
    )
  } else if (status.can_follow) {
    const followBtn = (
      <button type="button" className={buttonClassName} onClick={handleFollow} disabled={pending !== null}>
        {t(status.is_followed_by ? 'follow.followBack' : 'follow.follow')}
      </button>
    )
    buttons = showMessage
      ? <div className={styles.followRow}>{followBtn}{messageButton}</div>
      : followBtn
  } else if (status.has_conversation && showMessage) {
    buttons = <div className={styles.followRow}>{messageButton}</div>
  } else if (status.reason === 'verify_required') {
    buttons = (
      <button type="button" className={buttonClassName} onClick={handleVerifyRequired}>
        {t('follow.follow')}
      </button>
    )
  }
  // else: self / blocked / guest target / opted-out target -> nothing at all.

  const showConfirm = confirmOpen && !hidden && !!status?.is_following

  return (
    <>
      {buttons}
      {buttons && actionError && (
        <p className={`${styles.composeError} ${styles.followError}`} role="alert">{t(actionError)}</p>
      )}
      {showConfirm && (
        <Modal
          open
          centered
          onClose={() => setConfirmOpen(false)}
          zIndex={320}
          portal
          title={t('follow.unfollowConfirmTitle', { name: name || t('messaging.unknownUser') })}
          closeLabel={t('messaging.close')}
        >
          <p className={styles.dialogText}>{t('follow.unfollowConfirmBody')}</p>
          <div className={styles.dialogActions}>
            <button type="button" className={`${styles.btn} ${styles.btnSecondary}`} onClick={() => setConfirmOpen(false)}>
              {t('messaging.cancel')}
            </button>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnDestructive}`}
              onClick={handleUnfollowConfirm}
              disabled={pending !== null}
            >
              {t('follow.unfollowConfirm')}
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}
