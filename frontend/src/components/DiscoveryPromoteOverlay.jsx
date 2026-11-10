import { useTranslation } from '../i18n/index.js'
import styles from './DiscoveryPromoteOverlay.module.css'

// Blocking overlay for the trigger-card right-swipe promote call.
// phase: 'loading' | 'error'. Captures all pointer input over the card stack.
export default function DiscoveryPromoteOverlay({ phase, onRetry, onBack }) {
  const { t } = useTranslation()
  if (phase === 'error') {
    return (
      <div className={styles.overlay} role="alert" style={{ cursor: 'default' }}>
        <div className={styles.msg}>{t('discovery.toastAnalysisFailed')}</div>
        <div className={styles.actions}>
          <button type="button" className={`${styles.btn} ${styles.primary}`} onClick={onRetry}>
            {t('discovery.retry')}
          </button>
          <button type="button" className={`${styles.btn} ${styles.secondary}`} onClick={onBack}>
            {t('discovery.backToDiscovery')}
          </button>
        </div>
      </div>
    )
  }
  return (
    <div className={styles.overlay} role="status" aria-live="polite">
      <div className={styles.ring} style={{ animation: 'spin 0.8s linear infinite' }} />
      <div className={styles.msg}>{t('discovery.tasteAnalyzing')}</div>
    </div>
  )
}
