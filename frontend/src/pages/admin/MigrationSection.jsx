/** MigrationSection — pending (unapplied) migrations on the app DB. */
import { useTranslation } from '../../i18n/index.js'
import SectionCard from './SectionCard.jsx'
import styles from './AdminPage.module.css'

export default function MigrationSection({ section }) {
  const { t } = useTranslation()
  const { data, loading, error, reload } = section
  const count = typeof data?.count === 'number' ? data.count : 0
  const names = Array.isArray(data?.unapplied) ? data.unapplied : []
  return (
    <SectionCard
      title={t('admin.migrations.title')}
      loading={loading}
      error={error}
      onRetry={reload}
      right={data && (
        <span className={`${styles.badge} ${count > 0 ? styles.bad : styles.ok}`}>
          {count > 0 ? t('admin.migrations.pending', { n: count }) : t('admin.migrations.clean')}
        </span>
      )}
    >
      {count > 0 && (
        <>
          <ul className={styles.nameList}>
            {names.map(name => <li key={name} className={styles.mono}>{name}</li>)}
          </ul>
          <p className={styles.muted}>{t('admin.migrations.hint')}</p>
        </>
      )}
    </SectionCard>
  )
}
