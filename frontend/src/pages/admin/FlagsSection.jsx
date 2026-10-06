/** FlagsSection — read-only feature flag table (label, description, ON/OFF or provider value). */
import { useTranslation } from '../../i18n/index.js'
import SectionCard from './SectionCard.jsx'
import styles from './AdminPage.module.css'

function FlagValue({ value }) {
  const { t } = useTranslation()
  if (typeof value === 'boolean') {
    return (
      <span className={`${styles.badge} ${value ? styles.ok : ''}`}>
        {value ? t('admin.flags.on') : t('admin.flags.off')}
      </span>
    )
  }
  return <span className={`${styles.badge} ${styles.mono}`}>{value == null ? '-' : String(value)}</span>
}

export default function FlagsSection({ section }) {
  const { t } = useTranslation()
  const { data, loading, error, reload } = section
  const flags = Array.isArray(data?.flags) ? data.flags : []
  return (
    <SectionCard
      title={t('admin.flags.title')}
      loading={loading}
      error={error}
      onRetry={reload}
      skeletonRows={5}
      right={<span className={styles.muted}>{t('admin.flags.readonly')}</span>}
    >
      {flags.length === 0 ? (
        <p className={styles.muted}>{t('admin.flags.empty')}</p>
      ) : (
        <div className={styles.tableScroll}>
          <table className={styles.table}>
            <tbody>
              {flags.map(flag => (
                <tr key={flag.key}>
                  <td>
                    {flag.label_ko}
                    {flag.description_ko && <span className={styles.flagDesc}>{flag.description_ko}</span>}
                    <span className={`${styles.flagKey} ${styles.mono}`}>{flag.key}</span>
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap', paddingRight: 0 }}>
                    <FlagValue value={flag.value} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}
