import Modal from './Modal.jsx'
import { MONO, INK, LS_CAPS, LS_TIGHT } from './cardLanguage.js'
import { useTranslation } from '../i18n/index.js'
import styles from './LeaveDiscoveryModal.module.css'

/**
 * LeaveDiscoveryModal — Discovery leave-warning, restyled in the card language
 * (stamp / title / body / two pills over blurred half-ellipses). Presentational:
 * DiscoveryPage owns the open state and the stay / leave logic.
 *
 *  - `likeCount`  draft likes at open time (stamp "N LIKES")
 *  - `converged`  likeCount >= TASTE_NUDGE_THRESHOLD (picks title + body copy)
 *  - `promoting`  leave is auto-promoting to Taste: both pills disabled and the
 *                 leave pill shows a spinner + "Saving…"
 *  - `onStay`     "Keep exploring" and Modal close (Esc / backdrop / X)
 *  - `onLeave`    "Leave anyway"
 */
export default function LeaveDiscoveryModal({ likeCount, converged, promoting, onStay, onLeave }) {
  const { t } = useTranslation()
  const title = converged ? t('discovery.leaveModal.titleConverged') : t('discovery.leaveModal.titleDraft')
  const body = converged ? t('discovery.leaveModal.bodyConverged') : t('discovery.leaveModal.bodyDraft')

  return (
    <Modal
      open
      onClose={onStay}
      zIndex={1000}
      closeLabel={t('modalB3.close')}
      width={480}
      ariaLabel={title}
    >
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 18 }}>
        <span style={{
          fontFamily: MONO,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: LS_CAPS,
          color: INK.mid,
        }}>
          {t('discovery.leaveModal.stamp', { n: likeCount })}
        </span>
      </div>

      <h2 style={{
        margin: '0 0 10px',
        textAlign: 'center',
        fontSize: 18,
        fontWeight: 700,
        letterSpacing: LS_TIGHT,
        lineHeight: 1.35,
        color: 'var(--color-text)',
      }}>
        {title}
      </h2>

      <p style={{
        margin: 0,
        textAlign: 'center',
        fontSize: 13,
        lineHeight: 1.55,
        color: 'var(--color-text-muted)',
        wordBreak: 'keep-all',
        textWrap: 'balance',
      }}>
        {body}
      </p>

      <div className={styles.choices}>
        <div className={styles.moons} aria-hidden="true">
          <div className={`${styles.moon} ${styles.moonLeft}`}><div className={styles.blob} /></div>
          <div className={`${styles.moon} ${styles.moonRight}`}><div className={styles.blob} /></div>
        </div>
        <div className={styles.row}>
          <button
            type="button"
            className={`${styles.pill} ${styles.ghost}`}
            onClick={onLeave}
            disabled={promoting}
          >
            {promoting ? (
              <>
                <span
                  aria-hidden="true"
                  style={{
                    display: 'inline-block',
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    border: '2px solid color-mix(in srgb, var(--color-text) 18%, transparent)',
                    borderTopColor: 'var(--color-text)',
                    animation: 'spin 0.8s linear infinite',
                  }}
                />
                {t('discovery.leaveModal.saving')}
              </>
            ) : t('discovery.leaveModal.leave')}
          </button>
          <button
            type="button"
            className={`${styles.pill} ${styles.solid}`}
            onClick={onStay}
            disabled={promoting}
          >
            {t('discovery.leaveModal.stay')}
          </button>
        </div>
      </div>
    </Modal>
  )
}
