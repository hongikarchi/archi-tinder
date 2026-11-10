import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import PageTopControls from '../components/PageTopControls.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import Skeleton from '../components/Skeleton.jsx'
import PageTitle from '../components/PageTitle.jsx'
import InboxView from '../components/messaging/InboxView.jsx'
import ConversationView from '../components/messaging/ConversationView.jsx'
import { useTranslation } from '../i18n/index.js'
import { useMessagingEnabled } from '../hooks/useMessagingFeature.js'
import { refreshUnreadMessages } from '../hooks/useUnreadMessages.js'
import {
  listReceivedRequests,
  listConversations,
  acceptContactRequest,
  ignoreContactRequest,
} from '../api/messaging.js'
import { VerifyRequiredError } from '../api/projects.js'
import styles from './MessagesPage.module.css'

/**
 * MessagesPage — the "메시지" TabBar tab (FRONT-MESSAGES-TAB-1).
 *
 *   /messages                    tab root: received requests + conversation list
 *   /messages/:conversationId    conversation (numeric id; anything else -> /messages)
 *
 * Replaces the own-profile pill + bottom sheet. As a tab root the inbox has no
 * back button; the conversation view gets a PageBackButton -> /messages.
 *
 * `/messages` may carry `location.state.peerUserId` (ContactCta "메시지 보내기":
 * the contact-status API returns no conversation id) — once the list is loaded
 * the page jumps to that peer's conversation. A just-accepted request passes
 * `location.state.conversation` so the view opens without waiting for a refetch.
 * Flag OFF -> renders nothing (and makes no request); the tab is hidden too.
 */
export default function MessagesPage({ onLogout }) {
  const { t } = useTranslation()
  const enabled = useMessagingEnabled()
  const navigate = useNavigate()
  // latest-ref: navigate's identity changes per route transition (BrowserRouter);
  // keeping it out of effect deps avoids a redundant non-silent reload.
  const navigateRef = useRef(navigate)
  navigateRef.current = navigate
  const location = useLocation()
  const { conversationId: rawId } = useParams()

  // null = inbox, NaN = malformed id
  const convId = rawId == null ? null : (/^\d+$/.test(rawId) ? Number(rawId) : NaN)
  const hint = location.state?.conversation ?? null

  const [loadState, setLoadState] = useState('loading') // 'loading' | 'ready' | 'error'
  const [requests, setRequests] = useState([])
  const [conversations, setConversations] = useState([])
  const [busy, setBusy] = useState(null) // { id, action } of a request being handled
  const [actionError, setActionError] = useState(null)

  const mountedRef = useRef(true)
  const peerRef = useRef(location.state?.peerUserId ?? null)
  const wasInConversationRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoadState('loading')
    try {
      const [rq, cv] = await Promise.all([listReceivedRequests(), listConversations()])
      if (!mountedRef.current) return null
      const convs = cv?.results || []
      setRequests(rq?.results || [])
      setConversations(convs)
      setLoadState('ready')
      return convs
    } catch {
      if (mountedRef.current && !silent) setLoadState('error')
      return null
    }
  }, [])

  // Initial load, then jump to the requested peer's conversation if any.
  useEffect(() => {
    if (!enabled) return undefined
    let cancelled = false
    load().then(convs => {
      const peer = peerRef.current
      if (cancelled || !convs || peer == null) return
      peerRef.current = null
      const conv = convs.find(c => String(c.other?.user_id) === String(peer))
      if (conv) {
        navigateRef.current(`/messages/${conv.id}`, {
          replace: true,
          state: { conversation: { id: conv.id, other: conv.other, closed: conv.closed } },
        })
      }
    })
    return () => { cancelled = true }
  }, [enabled, load])

  // Returning from a conversation (back button, browser back, tab re-tap):
  // resync the list and the shared unread count.
  useEffect(() => {
    if (convId != null) {
      wasInConversationRef.current = true
      return
    }
    if (!wasInConversationRef.current) return
    wasInConversationRef.current = false
    load({ silent: true })
    refreshUnreadMessages({ force: true })
  }, [convId, load])

  function openConversation(conv) {
    setActionError(null)
    navigate(`/messages/${conv.id}`, {
      state: { conversation: { id: conv.id, other: conv.other, closed: conv.closed } },
    })
  }

  async function handleAccept(req) {
    if (busy) return
    setBusy({ id: req.id, action: 'accept' })
    setActionError(null)
    try {
      const res = await acceptContactRequest(req.id)
      if (!mountedRef.current) return
      setRequests(prev => prev.filter(r => r.id !== req.id))
      refreshUnreadMessages({ force: true })
      if (res?.conversation_id != null) {
        load({ silent: true })
        navigate(`/messages/${res.conversation_id}`, {
          state: { conversation: { id: res.conversation_id, other: req.sender, closed: false } },
        })
      } else {
        load({ silent: true })
      }
    } catch (err) {
      if (!mountedRef.current || err instanceof VerifyRequiredError) return
      if (err?.status === 409) {
        // already handled elsewhere — drop the stale card and resync
        setRequests(prev => prev.filter(r => r.id !== req.id))
        load({ silent: true })
      } else {
        setActionError('messaging.requestActionError')
      }
    } finally {
      if (mountedRef.current) setBusy(null)
    }
  }

  async function handleIgnore(req) {
    if (busy) return
    setBusy({ id: req.id, action: 'ignore' })
    setActionError(null)
    try {
      await ignoreContactRequest(req.id)
      if (!mountedRef.current) return
      setRequests(prev => prev.filter(r => r.id !== req.id))
      refreshUnreadMessages({ force: true })
    } catch (err) {
      if (!mountedRef.current || err instanceof VerifyRequiredError) return
      if (err?.status === 409) setRequests(prev => prev.filter(r => r.id !== req.id))
      else setActionError('messaging.requestActionError')
    } finally {
      if (mountedRef.current) setBusy(null)
    }
  }

  // Flag OFF (or not loaded yet): nothing to show, nothing requested.
  if (!enabled) return null
  if (Number.isNaN(convId)) return <Navigate to="/messages" replace />

  // Conversation target: the loaded list wins, the navigation hint covers a
  // conversation the list does not contain yet (just accepted / just created).
  let active = null
  if (convId != null) {
    const fromList = conversations.find(c => c.id === convId)
    if (fromList) active = { id: fromList.id, other: fromList.other, closed: fromList.closed }
    else if (hint && hint.id === convId) active = hint
    // list is ready and the id is unknown (not mine / gone) -> back to the inbox
    else if (loadState === 'ready') return <Navigate to="/messages" replace />
  }

  // Cold deep link (/messages/:id, no state): list still loading, conversation
  // unknown -> neutral shell instead of flashing the inbox title + skeleton.
  // A failed load falls through to the inbox error state (retry re-resolves).
  const resolvingDeepLink = convId != null && !active && loadState === 'loading'

  return (
    <div className={styles.page}>
      <PageTopControls
        onLogout={onLogout}
        leading={active
          ? <PageBackButton inline label={t('messaging.back')} onClick={() => navigate('/messages')} />
          : undefined}
      />

      {/* Header — inbox is a tab root (no back button); a conversation gets one */}
      <header className={styles.header}>
        <PageLogoHeader />
      </header>

      {resolvingDeepLink ? (
        <div className={`${styles.body} ${styles.bodyConversation}`} aria-busy="true">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 16 }}>
            <Skeleton width="55%" height={36} radius="var(--radius-md)" />
            <Skeleton width="45%" height={36} radius="var(--radius-md)" style={{ alignSelf: 'flex-end' }} />
            <Skeleton width="60%" height={36} radius="var(--radius-md)" />
          </div>
        </div>
      ) : active ? (
        <div className={`${styles.body} ${styles.bodyConversation}`}>
          <ConversationView
            key={active.id}
            conversation={active}
            onOpenProfile={userId => navigate(`/user/${userId}`)}
          />
        </div>
      ) : (
        <div className={styles.body}>
          <PageTitle style={{ margin: '12px 0 12px' }}>{t('messaging.title')}</PageTitle>
          <InboxView
            loadState={loadState}
            requests={requests}
            conversations={conversations}
            busy={busy}
            actionError={actionError}
            onRetry={() => load()}
            onAccept={handleAccept}
            onIgnore={handleIgnore}
            onOpenConversation={openConversation}
          />
        </div>
      )}
    </div>
  )
}
