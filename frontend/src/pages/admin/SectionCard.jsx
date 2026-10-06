/**
 * SectionCard — shared frame for one admin dashboard section.
 *
 * Renders the title, then one of: skeleton (loading) / inline error + retry
 * (DESIGN.md 8.9 tier 2) / children (loaded). `right` is an optional header
 * slot (e.g. a status badge).
 */
import { useTranslation } from '../../i18n/index.js'
import Skeleton from '../../components/Skeleton.jsx'
import styles from './AdminPage.module.css'

export default function SectionCard({ title, loading, error, onRetry, right, skeletonRows = 3, children }) {
  const { t } = useTranslation()
  return (
    <section className={styles.card} aria-busy={loading ? 'true' : undefined}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}>{title}</h2>
        {!loading && !error && right}
      </div>
      {loading && (
        <div className={styles.skeletonCol}>
          {Array.from({ length: skeletonRows }, (_, i) => (
            <Skeleton key={i} height={16} width={i === skeletonRows - 1 ? '60%' : '100%'} />
          ))}
        </div>
      )}
      {!loading && error && (
        <div className={styles.errorBox} role="alert">
          <span>{t('admin.loadError')}</span>
          {onRetry && (
            <button type="button" className={styles.btn} onClick={onRetry}>
              {t('admin.retry')}
            </button>
          )}
        </div>
      )}
      {!loading && !error && children}
    </section>
  )
}
