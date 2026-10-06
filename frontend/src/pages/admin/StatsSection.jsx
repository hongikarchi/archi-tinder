/** StatsSection — DB stat tiles. Each block can be null (that query failed) without hiding the rest. */
import { useTranslation } from '../../i18n/index.js'
import SectionCard from './SectionCard.jsx'
import styles from './AdminPage.module.css'

const GROUPS = [
  { key: 'users', fields: ['total', 'google_verified', 'guest', 'new_7d', 'new_30d'] },
  { key: 'works', fields: ['total', 'published', 'rejected', 'processing'] },
  { key: 'reports', fields: ['total', 'last_7d'] },
  { key: 'sessions', fields: ['last_24h', 'last_7d', 'converged_7d'] },
  { key: 'buildings', fields: ['publishable'] },
]

export default function StatsSection({ section }) {
  const { t, language } = useTranslation()
  const { data, loading, error, reload } = section
  const fmt = n => (typeof n === 'number' ? n.toLocaleString(language === 'ko' ? 'ko-KR' : 'en-US') : '-')
  return (
    <SectionCard
      title={t('admin.stats.title')}
      loading={loading}
      error={error}
      onRetry={reload}
      skeletonRows={4}
    >
      {data && GROUPS.map(group => {
        const block = data[group.key]
        return (
          <div key={group.key} className={styles.statGroup}>
            <h3 className={styles.statGroupTitle}>{t(`admin.stats.${group.key}`)}</h3>
            {block ? (
              <div className={styles.tiles}>
                {group.fields.map(field => (
                  <div key={field} className={styles.tile}>
                    <span className={styles.tileValue}>{fmt(block[field])}</span>
                    <span className={styles.tileLabel}>{t(`admin.stats.fields.${field}`)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.muted}>{t('admin.stats.blockFailed')}</p>
            )}
          </div>
        )
      })}
    </SectionCard>
  )
}
