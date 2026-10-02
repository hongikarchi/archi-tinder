import { useCallback, useEffect, useRef, useState } from 'react'
import Modal from '../Modal.jsx'
import { useTranslation } from '../../i18n/index.js'
import {
  listReceivedRequests,
  listConversations,
  acceptContactRequest,
  ignoreContactRequest,
} from '../../api/messaging.js'
import { VerifyRequiredError } from '../../api/projects.js'
import { refreshUnreadMessages } from '../../hooks/useUnreadMessages.js'
import { useVisualViewportSheetStyle } from '../../hooks/useVisualViewportSheetStyle.js'
import InboxView from './InboxView.jsx'
import ConversationView from './ConversationView.jsx'

/**
 * MessagesSheet — inbox + conversation inside ONE bottom sheet / modal
 * (FULL-MESSAGING-1, D7: no route navigation, so the Discovery leave-warning
 * guard never fires). Reuses the shared `Modal` (sheet on mobile, centered on
 * desktop) in `fill` mode.
 *
 *   View A (inbox)        received requests + conversation list
 *   View B (conversation) bubbles + composer; back arrow returns to View A
 *
 * Mounted only while open (callers render it conditionally). Optional opening
 * target: `initialConversationId` and/or `initialPeerUserId` (the status API
 * returns no conversation id for "connected", so a profile opens by peer).
 * Closing — and returning to the inbox — refreshes the shared unread count.
 */
export default function MessagesSheet({ onClose, initialConversationId = null, initialPeerUserId = null }) {
  const { t } = useTranslation()
  const sheetStyle = useVisualViewportSheetStyle()

  const [loadState, setLoadState] = useState('loading') // 'loading' | 'ready' | 'error'
  const [requests, setRequests] = useState([])
  const [conversations, setConversations] = useState([])
  const [active, setActive] = useState(null) // { id, other, closed }
  const [overlayOpen, setOverlayOpen] = useState(false)
  const [busy, setBusy] = useState(null) // { id, action } of a request being handled
  const [actionError, setActionError] = useState(null)

  const mountedRef = useRef(true)
  const initialTargetRef = useRef(
    initialConversationId != null || initialPeerUserId != null
      ? { id: initialConversationId, peer: initialPeerUserId }
      : null,
  )

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

  // Initial load, then jump straight into the requested conversation if any.
  useEffect(() => {
    let cancelled = false
    load().then(convs => {
      const target = initialTargetRef.current
      if (cancelled || !convs || !target) return
      const conv = convs.find(c =>
        (target.id != null && c.id === target.id) ||
        (target.peer != null && String(c.other?.user_id) === String(target.peer)),
      )
      initialTargetRef.current = null
      if (conv) setActive({ id: conv.id, other: conv.other, closed: conv.closed })
    })
    return () => { cancelled = true }
  }, [load])

  function handleClose() {
    refreshUnreadMessages({ force: true })
    onClose()
  }

  function handleBack() {
    setActive(null)
    setOverlayOpen(false)
    load({ silent: true })
    refreshUnreadMessages({ force: true })
  }

  function handleOpenConversation(conv) {
    setActionError(null)
    setActive({ id: conv.id, other: conv.other, closed: conv.closed })
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
        setActive({ id: res.conversation_id, other: req.sender, closed: false })
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

  return (
    <Modal
      open
      fill
      onClose={handleClose}
      title={active ? undefined : t('messaging.title')}
      ariaLabel={active?.other?.display_name || t('messaging.title')}
      closeLabel={t('messaging.close')}
      closeOnEscape={!overlayOpen}
      panelStyle={sheetStyle}
    >
      {active ? (
        <ConversationView
          key={active.id}
          conversation={active}
          onBack={handleBack}
          onOverlayChange={setOverlayOpen}
        />
      ) : (
        <InboxView
          loadState={loadState}
          requests={requests}
          conversations={conversations}
          busy={busy}
          actionError={actionError}
          onRetry={() => load()}
          onAccept={handleAccept}
          onIgnore={handleIgnore}
          onOpenConversation={handleOpenConversation}
        />
      )}
    </Modal>
  )
}
