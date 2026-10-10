import { useState } from 'react'
import Modal from '../Modal.jsx'
import { useTranslation } from '../../i18n/index.js'
import styles from './PosterReportModal.module.css'

/**
 * PosterReportModal — confirm step for the in-app poster takedown report.
 * Built on the shared Modal (DESIGN.md §8.10), portaled to document.body so it
 * stacks above the PosterLightbox overlay. `onSubmit(reason)` is async; the
 * caller owns the API call, the toast and what happens to the poster.
 */
export default function PosterReportModal({ open, onClose, onSubmit, zIndex = 1100 }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState(false)

  async function handleSubmit() {
    if (pending) return
    setPending(true)
    try {
      await onSubmit(reason.trim())
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={pending ? () => {} : onClose}
      title={t('contest.takedown.reportTitle')}
      closeLabel={t('contest.poster.close')}
      centered
      portal
      zIndex={zIndex}
      footer={(
        <div className={styles.actions}>
          <button type="button" className={styles.secondary} onClick={onClose} disabled={pending}>
            {t('contest.takedown.cancel')}
          </button>
          <button type="button" className={styles.destructive} onClick={handleSubmit} disabled={pending}>
            {t('contest.takedown.submit')}
          </button>
        </div>
      )}
    >
      <p className={styles.body}>{t('contest.takedown.reportBody')}</p>
      <label className={styles.label} htmlFor="contest-poster-report-reason">
        {t('contest.takedown.reasonLabel')}
      </label>
      <textarea
        id="contest-poster-report-reason"
        className={styles.textarea}
        value={reason}
        onChange={e => setReason(e.target.value)}
        placeholder={t('contest.takedown.reasonPlaceholder')}
        maxLength={500}
        rows={3}
        disabled={pending}
      />
    </Modal>
  )
}
