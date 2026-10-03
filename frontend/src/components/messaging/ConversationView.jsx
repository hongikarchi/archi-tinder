import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from '../../i18n/index.js'
import Avatar from '../Avatar.jsx'
import FloatingIconButton from '../FloatingIconButton.jsx'
import Skeleton from '../Skeleton.jsx'
import UserActionsMenu from './UserActionsMenu.jsx'
import ReportDialog from './ReportDialog.jsx'
import { listMessages, sendMessage, markConversationRead } from '../../api/messaging.js'
import { VerifyRequiredError } from '../../api/projects.js'
import { refreshUnreadMessages } from '../../hooks/useUnreadMessages.js'
import { formatMessageTime, isConnectedSystem, maxMessageId } from './messagingUtils.js'
import styles from './Messaging.module.css'

const POLL_MS = 4000
const MESSAGE_MAX = 1000
const STICK_THRESHOLD = 80

/**
 * ConversationView — View B of the messages sheet (FULL-MESSAGING-1).
 *
 * Bubbles (mine right / accent, theirs left), `kind:'system'` messages as a
 * centered i18n caption (never DB text), composer (1..1000 chars). On entry
 * the conversation is marked read and the shared unread count refreshed.
 *
 * Polling (D8): ONLY while this view is mounted AND the document is visible,
 * `GET messages/?after=<lastId>` every 4s via a self-rescheduling timeout
 * (no overlapping requests, no setInterval). Stops on unmount (back / close)
 * and while the tab is hidden; resumes immediately on becoming visible.
 */
export default function ConversationView({ conversation, onBack, onOverlayChange }) {
  const { t, language } = useTranslation()
  const { id: conversationId, other } = conversation
  const otherName = other?.display_name || t('messaging.unknownUser')

  const [loadState, setLoadState] = useState('loading') // 'loading' | 'ready' | 'error'
  const [messages, setMessages] = useState([])
  const [closed, setClosed] = useState(Boolean(conversation.closed))
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [reportMessageId, setReportMessageId] = useState(null)
  const [menuOverlay, setMenuOverlay] = useState(false)

  const listRef = useRef(null)
  const textareaRef = useRef(null)
  const stickRef = useRef(true)
  const lastIdRef = useRef(0)
  const closedRef = useRef(Boolean(conversation.closed))

  // Mirror `closed` so the poll loop can stop scheduling once closed.
  useEffect(() => { closedRef.current = closed }, [closed])

  // Tell the host sheet when a dropdown/dialog owns Escape.
  const overlay = menuOverlay || reportMessageId != null
  useEffect(() => {
    onOverlayChange?.(overlay)
  }, [overlay, onOverlayChange])

  // Append (dedupe by id) WITHOUT touching the poll cursor. Used by the send
  // path: advancing the cursor to our own message id would make the next poll
  // (`id > after`) skip a peer message that landed between the last poll and
  // our send. Our own message comes back in the next poll and is deduped.
  const appendMessages = useCallback(list => {
    if (!list.length) return
    setMessages(prev => {
      const seen = new Set(prev.map(m => m.id))
      const add = list.filter(m => !seen.has(m.id))
      return add.length ? [...prev, ...add] : prev
    })
  }, [])

  // Poll results only: append AND advance the cursor.
  const mergeIncoming = useCallback(incoming => {
    if (!incoming.length) return
    appendMessages(incoming)
    lastIdRef.current = maxMessageId(incoming, lastIdRef.current)
  }, [appendMessages])

  const markReadAndRefresh = useCallback(() => {
    markConversationRead(conversationId)
      .catch(() => { /* best-effort */ })
      .then(() => refreshUnreadMessages({ force: true }))
  }, [conversationId])

  // Initial load + read-on-enter
  useEffect(() => {
    let cancelled = false
    setLoadState('loading')
    lastIdRef.current = 0
    listMessages(conversationId)
      .then(data => {
        if (cancelled) return
        const results = data?.results || []
        setMessages(results)
        lastIdRef.current = maxMessageId(results)
        if (data?.closed) { closedRef.current = true; setClosed(true) }
        stickRef.current = true
        setLoadState('ready')
        markReadAndRefresh()
      })
      .catch(() => { if (!cancelled) setLoadState('error') })
    return () => { cancelled = true }
  }, [conversationId, reloadKey, markReadAndRefresh])

  // Incremental polling — open + visible only
  useEffect(() => {
    if (loadState !== 'ready') return undefined
    let stopped = false
    let timer = null
    let busy = false

    function schedule() {
      if (stopped || closedRef.current || document.visibilityState !== 'visible') return
      timer = setTimeout(tick, POLL_MS)
    }

    async function tick() {
      timer = null
      if (stopped || busy || closedRef.current || document.visibilityState !== 'visible') return
      busy = true
      try {
        const data = await listMessages(conversationId, { after: lastIdRef.current || undefined })
        if (stopped) return
        const incoming = data?.results || []
        mergeIncoming(incoming)
        if (data?.closed) { closedRef.current = true; setClosed(true) }
        if (incoming.some(m => !m.is_mine)) markReadAndRefresh()
      } catch (err) {
        if (err?.status === 404) { stopped = true; return } // gone / feature off — stop quietly
      } finally {
        busy = false
      }
      schedule()
    }

    function onVisibilityChange() {
      if (document.visibilityState === 'visible') {
        if (!timer && !busy && !closedRef.current) tick()
      } else if (timer) {
        clearTimeout(timer)
        timer = null
      }
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    schedule()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [loadState, conversationId, mergeIncoming, markReadAndRefresh])

  // Keep pinned to the newest message unless the user scrolled up.
  useLayoutEffect(() => {
    const el = listRef.current
    if (el && stickRef.current) el.scrollTop = el.scrollHeight
  }, [messages.length, loadState, closed])

  function handleScroll() {
    const el = listRef.current
    if (!el) return
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_THRESHOLD
  }

  // Auto-grow composer (capped by CSS max-height)
  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 2}px` // +2 = border (border-box)
  }, [draft])

  async function handleSend() {
    const body = draft.trim()
    if (!body || sending || closed) return
    setSending(true)
    setSendError(null)
    try {
      const msg = await sendMessage(conversationId, body)
      appendMessages([{ ...msg, is_mine: msg?.is_mine ?? true }])
      stickRef.current = true
      setDraft('')
    } catch (err) {
      if (err instanceof VerifyRequiredError) return
      const detail = err?.data?.detail
      if (err?.status === 403 && (detail === 'conversation_closed' || detail === 'blocked')) {
        closedRef.current = true
        setClosed(true)
        setSendError(detail === 'blocked' ? 'messaging.sendErrorBlocked' : 'messaging.sendErrorClosed')
      } else if (err?.status === 429) {
        setSendError('messaging.sendErrorRate')
      } else {
        setSendError('messaging.sendError')
      }
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e) {
    // Enter sends, Shift+Enter = newline; never while an IME (Korean) is composing.
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      handleSend()
    }
  }

  const reportable = reportMessageId != null
    ? messages.find(m => m.id === reportMessageId && m.kind === 'user')
    : null

  return (
    <>
      <div className={styles.convHeader}>
        <FloatingIconButton onClick={onBack} ariaLabel={t('messaging.back')} title={t('messaging.back')}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </FloatingIconButton>
        <div className={styles.convTitle}>
          <Avatar src={other?.avatar_url} name={other?.display_name} size={32} />
          <h3 className={styles.convName}>{otherName}</h3>
        </div>
        {other?.user_id != null && (
          <UserActionsMenu
            userId={other.user_id}
            name={otherName}
            onBlocked={() => { closedRef.current = true; setClosed(true); setSendError(null) }}
            onOverlayChange={setMenuOverlay}
          />
        )}
      </div>

      <div ref={listRef} className={styles.list} onScroll={handleScroll} aria-live="polite">
        {loadState === 'loading' && (
          <div aria-busy="true" style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '8px 0' }}>
            <Skeleton width="55%" height={36} radius="var(--radius-md)" />
            <Skeleton width="45%" height={36} radius="var(--radius-md)" style={{ alignSelf: 'flex-end' }} />
            <Skeleton width="60%" height={36} radius="var(--radius-md)" />
          </div>
        )}

        {loadState === 'error' && (
          <div className={styles.errorBox} role="alert">
            <span>{t('messaging.conversationLoadError')}</span>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnSecondary}`}
              onClick={() => setReloadKey(k => k + 1)}
            >
              {t('messaging.retry')}
            </button>
          </div>
        )}

        {loadState === 'ready' && messages.map((m, i) => {
          if (m.kind === 'system') {
            if (!isConnectedSystem(m)) return null
            return <div key={m.id} className={styles.systemMsg}>{t('messaging.connectedText')}</div>
          }
          const mine = Boolean(m.is_mine)
          const next = messages[i + 1]
          const showTime = !next || next.kind !== 'user' || Boolean(next.is_mine) !== mine ||
            formatMessageTime(next.created_at, language) !== formatMessageTime(m.created_at, language)
          return (
            <div key={m.id} className={`${styles.msgRow} ${mine ? styles.msgRowMine : ''}`}>
              <div className={styles.msgCol}>
                <p className={`${styles.bubble} ${mine ? styles.bubbleMine : styles.bubbleTheirs}`}>{m.body}</p>
                {showTime && <span className={styles.msgTime}>{formatMessageTime(m.created_at, language)}</span>}
              </div>
              {!mine && (
                <button
                  type="button"
                  className={styles.msgReportBtn}
                  onClick={() => setReportMessageId(m.id)}
                  aria-label={t('messaging.reportMessage')}
                  title={t('messaging.reportMessage')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
                    <line x1="4" y1="22" x2="4" y2="15" />
                  </svg>
                </button>
              )}
            </div>
          )
        })}
      </div>

      {closed ? (
        <div className={styles.closedNotice} role="status">{t('messaging.closedNotice')}</div>
      ) : (
        <div className={styles.composer}>
          {sendError && <p className={styles.composeError} role="alert">{t(sendError)}</p>}
          <div className={styles.composerRow}>
            <textarea
              ref={textareaRef}
              className={styles.textarea}
              rows={1}
              value={draft}
              maxLength={MESSAGE_MAX}
              placeholder={t('messaging.inputPlaceholder')}
              aria-label={t('messaging.inputPlaceholder')}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              readOnly={sending}
              disabled={loadState !== 'ready'}
            />
            <button
              type="button"
              className={`${styles.btn} ${styles.btnPrimary}`}
              onClick={handleSend}
              disabled={sending || !draft.trim() || loadState !== 'ready'}
            >
              {sending ? t('messaging.sending') : t('messaging.send')}
            </button>
          </div>
          {draft.length > MESSAGE_MAX - 100 && (
            <p className={styles.counter}>{draft.length}/{MESSAGE_MAX}</p>
          )}
        </div>
      )}

      {reportable && (
        <ReportDialog targetType="message" targetId={reportable.id} onClose={() => setReportMessageId(null)} />
      )}
    </>
  )
}
