import { useState } from 'react'
import Modal from '../Modal.jsx'
import { useTranslation } from '../../i18n/index.js'
import { reportTarget } from '../../api/messaging.js'
import { VerifyRequiredError } from '../../api/projects.js'
import styles from './Messaging.module.css'

const REASON_MAX = 500

/**
 * ReportDialog — optional-reason report form (FULL-MESSAGING-1).
 * `targetType`: 'user' | 'profile' | 'message'. System messages must never be
 * passed here (the backend rejects kind=system) — callers only offer the
 * report affordance on kind=user messages.
 * Always a centered modal above the messages sheet (zIndex 320 > 300).
 */
export default function ReportDialog({ targetType, targetId, onClose }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit() {
    if (submitting) return
    setSubmitting(true)
    setError(null)
    try {
      await reportTarget({ targetType, targetId, reason: reason.trim() })
      setDone(true)
    } catch (err) {
      if (err instanceof VerifyRequiredError) {
        onClose()
        return
      }
      setError(err?.status === 429 ? 'messaging.reportRate' : 'messaging.reportError')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open
      centered
      onClose={onClose}
      zIndex={320}
      title={t('messaging.reportTitle')}
      closeLabel={t('messaging.close')}
    >
      {done ? (
        <>
          <p className={styles.dialogText}>{t('messaging.reportDone')}</p>
          <div className={styles.dialogActions}>
            <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={onClose}>
              {t('messaging.close')}
            </button>
          </div>
        </>
      ) : (
        <>
          <label className={styles.dialogLabel} htmlFor="messaging-report-reason">
            {t('messaging.reportReasonLabel')}
          </label>
          <textarea
            id="messaging-report-reason"
            className={`${styles.textarea} ${styles.textareaTall}`}
            value={reason}
            maxLength={REASON_MAX}
            placeholder={t('messaging.reportReasonPlaceholder')}
            onChange={e => setReason(e.target.value)}
            readOnly={submitting}
          />
          {error && <p className={styles.composeError} role="alert" style={{ marginTop: 8 }}>{t(error)}</p>}
          <div className={styles.dialogActions}>
            <button type="button" className={`${styles.btn} ${styles.btnSecondary}`} onClick={onClose}>
              {t('messaging.cancel')}
            </button>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnPrimary}`}
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? t('messaging.sending') : t('messaging.reportSubmit')}
            </button>
          </div>
        </>
      )}
    </Modal>
  )
}
