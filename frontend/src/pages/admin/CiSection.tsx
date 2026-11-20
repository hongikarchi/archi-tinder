/** CiSection — latest CI conclusion for develop + main (from the version endpoint). */
import { useTranslation } from '../../i18n/index.ts'
import SectionCard from './SectionCard.tsx'
import type { AdminSection } from './useAdminSection.ts'
import type { AdminCiRun, AdminVersionResponse } from '../../types/api.ts'
import styles from './AdminPage.module.css'

function ciTone(run?: AdminCiRun | null) {
  if (!run) return { tone: '', key: 'noRun' }
  if (run.conclusion === 'success') return { tone: styles.ok, key: 'success' }
  if (run.conclusion === 'failure' || run.conclusion === 'timed_out' || run.conclusion === 'cancelled') {
    return { tone: styles.bad, key: 'failure' }
  }
  if (!run.conclusion && run.status && run.status !== 'completed') return { tone: styles.warn, key: 'running' }
  return { tone: styles.warn, key: 'other' }
}

function CiBadge({ label, run }: { label: string, run?: AdminCiRun | null }) {
  const { t } = useTranslation()
  const { tone, key } = ciTone(run)
  const text = `${label} · ${t(`admin.ci.${key}`)}`
  const cls = `${styles.badge} ${tone}`
  // Only link over https — html_url comes from an external API.
  if (run?.html_url && /^https:\/\//.test(run.html_url)) {
    return (
      <a className={cls} href={run.html_url} target="_blank" rel="noopener noreferrer" aria-label={`${text} - ${t('admin.ci.open')}`}>
        {text}
      </a>
    )
  }
  return <span className={cls}>{text}</span>
}

export default function CiSection({ section }: { section: AdminSection<AdminVersionResponse> }) {
  const { t } = useTranslation()
  const { data, loading, error, reload } = section
  const ci: { develop?: AdminCiRun | null, main?: AdminCiRun | null } = data?.github?.ci || {}
  return (
    <SectionCard
      title={t('admin.ci.title')}
      loading={loading}
      error={error}
      onRetry={reload}
      skeletonRows={1}
    >
      <div className={styles.badgeRow}>
        <CiBadge label={t('admin.ci.develop')} run={ci.develop} />
        <CiBadge label={t('admin.ci.main')} run={ci.main} />
      </div>
    </SectionCard>
  )
}
