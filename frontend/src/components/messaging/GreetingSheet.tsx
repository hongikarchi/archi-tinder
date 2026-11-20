import { useState, type CSSProperties } from 'react'
import Modal from '../Modal.tsx'
import { useTranslation } from '../../i18n/index.ts'
import { sendContactRequest } from '../../api/messaging.ts'
import { VerifyRequiredError } from '../../api/projects.ts'
import { useVisualViewportSheetStyle } from '../../hooks/useVisualViewportSheetStyle.ts'
import type { ContactRequestResult } from '../../types/api.ts'
import styles from './Messaging.module.css'

const GREETING_MAX = 100

/**
 * GreetingSheet — "관심 있어요" request sheet: optional greeting (<= 100
 * chars, live counter) + send. Calls POST contact-requests/ itself and hands
 * the result to `onSent` ({status:'sent'} | {status:'connected', conversation_id}).
 * Mobile bottom sheet that clears the on-screen keyboard.
 */
interface GreetingSheetProps {
  recipientId: number | string
  onClose: () => void
  onSent: (res: ContactRequestResult) => void
}

export default function GreetingSheet({ recipientId, onClose, onSent }: GreetingSheetProps) {
  const { t } = useTranslation()
  const sheetStyle = useVisualViewportSheetStyle()
  const [greeting, setGreeting] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSend() {
    if (sending) return
    setSending(true)
    setError(null)
    try {
      const res = await sendContactRequest(recipientId, greeting.trim())
      onSent(res)
    } catch (err) {
      if (err instanceof VerifyRequiredError) {
        onClose()
        return
      }
      const detail = (err as any)?.data?.detail // TODO(ts): ApiError type
      if ((err as any)?.status === 429) setError('messaging.requestRate')
      else if (detail === 'recipient_unavailable') setError('messaging.requestUnavailable')
      else if (detail === 'assessment_required') setError('messaging.assessmentRequiredHint')
      else if (detail === 'self_request') setError('messaging.requestSelf')
      else setError('messaging.requestError')
      setSending(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t('messaging.greetingTitle')}
      closeLabel={t('messaging.close')}
      panelStyle={sheetStyle as CSSProperties}
      portal
    >
      <p className={styles.dialogText}>{t('messaging.greetingBody')}</p>
      <textarea
        className={`${styles.textarea} ${styles.textareaTall}`}
        value={greeting}
        maxLength={GREETING_MAX}
        placeholder={t('messaging.greetingPlaceholder')}
        aria-label={t('messaging.greetingLabel')}
        onChange={e => setGreeting(e.target.value)}
        readOnly={sending}
      />
      <p className={styles.counter} aria-live="off">{greeting.length}/{GREETING_MAX}</p>
      {error && <p className={styles.composeError} role="alert" style={{ marginTop: 8 }}>{t(error)}</p>}
      <div className={styles.dialogActions}>
        <button
          type="button"
          className={`${styles.btn} ${styles.btnPrimary}`}
          onClick={handleSend}
          disabled={sending}
        >
          {sending ? t('messaging.sending') : t('messaging.greetingSend')}
        </button>
      </div>
    </Modal>
  )
}
