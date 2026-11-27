import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import PageTopControls from '../components/PageTopControls.tsx'
import PageLogoHeader from '../components/PageLogoHeader.tsx'
import PageBackButton from '../components/PageBackButton.tsx'
import Skeleton from '../components/Skeleton.tsx'
import PageTitle from '../components/PageTitle.tsx'
import InboxView from '../components/messaging/InboxView.tsx'
import ConversationView from '../components/messaging/ConversationView.tsx'
import { useTranslation } from '../i18n/index.ts'
import { useMessagingEnabled, useMessagingFeatureLoaded } from '../hooks/useMessagingFeature.ts'
import { refreshUnreadMessages } from '../hooks/useUnreadMessages.ts'
import { listConversations } from '../api/messaging.ts'
import styles from './MessagesPage.module.css'

/**
 * MessagesPage — the "메시지" TabBar tab (FRONT-MESSAGES-TAB-1).
 *
 *   /messages                    tab root: conversation list
 *   /messages/:conversationId    conversation (numeric id; anything else -> /messages)
 *
 * Replaces the own-profile pill + bottom sheet. As a tab root the inbox has no
 * back button; the conversation view gets a PageBackButton -> /messages.
 *
 * A just-opened conversation (FollowCta "메시지 보내기" -> POST conversations/)
 * passes `location.state.conversation` so the view opens without waiting for a
 * list refetch.
 * Flag OFF -> renders nothing (and makes no request); the tab is hidden too.
 * Once the flags are known and messaging is OFF, redirects home (#493).
 */
export default function MessagesPage({ onLogout }) {
  const { t } = useTranslation()
  const enabled = useMessagingEnabled()
  const featureLoaded = useMessagingFeatureLoaded()
  const navigate = useNavigate()
  const location = useLocation()
  const { conversationId: rawId } = useParams()

  // null = inbox, NaN = malformed id
  const convId = rawId == null ? null : (/^\d+$/.test(rawId) ? Number(rawId) : NaN)
  const hint = location.state?.conversation ?? null

  const [loadState, setLoadState] = useState('loading') // 'loading' | 'ready' | 'error'
  const [conversations, setConversations] = useState([])

  const mountedRef = useRef(true)
  const wasInConversationRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoadState('loading')
    try {
      const cv = await listConversations()
      if (!mountedRef.current) return
      setConversations(cv?.results || [])
      setLoadState('ready')
    } catch {
      if (mountedRef.current && !silent) setLoadState('error')
    }
  }, [])

  // Initial load.
  useEffect(() => {
    if (!enabled) return
    load()
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
    navigate(`/messages/${conv.id}`, {
      state: { conversation: { id: conv.id, other: conv.other, closed: conv.closed } },
    })
  }

  // Not loaded yet: render nothing. Answered OFF (e.g. a stale bookmark):
  // leave for the home route instead of a blank page (#493).
  if (!enabled) return featureLoaded ? <Navigate to="/" replace /> : null
  if (Number.isNaN(convId)) return <Navigate to="/messages" replace />

  // Conversation target: the loaded list wins, the navigation hint covers a
  // conversation the list does not contain yet (just created).
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
            conversations={conversations}
            onRetry={() => load()}
            onOpenConversation={openConversation}
          />
        </div>
      )}
    </div>
  )
}
