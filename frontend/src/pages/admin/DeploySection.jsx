/**
 * DeploySection — backend / frontend / GitHub SHAs + drift warnings.
 * FRONTEND_SHA comes from the Vite build-time constant (VERCEL_GIT_COMMIT_SHA,
 * 'local' outside Vercel). Warnings only fire when BOTH sides are known SHAs.
 */
import { useTranslation } from '../../i18n/index.js'
import SectionCard from './SectionCard.jsx'
import styles from './AdminPage.module.css'

const FRONTEND_SHA = typeof __COMMIT_SHA__ === 'string' ? __COMMIT_SHA__ : 'local'

const short = sha => (typeof sha === 'string' && sha ? sha.slice(0, 7) : null)

// Compare by the 7-char prefix so a full vs short SHA never false-alarms.
const differs = (a, b) => {
  const sa = short(a)
  const sb = short(b)
  return Boolean(sa && sb && sa !== sb)
}

function Row({ label, children }) {
  return (
    <div className={styles.kv}>
      <dt className={styles.kvLabel}>{label}</dt>
      <dd className={styles.kvValue}>{children}</dd>
    </div>
  )
}

export default function DeploySection({ section }) {
  const { t } = useTranslation()
  const { data, loading, error, reload } = section
  const backendSha = data?.backend?.sha || null
  const github = data?.github || {}
  const frontendKnown = FRONTEND_SHA && FRONTEND_SHA !== 'local' ? FRONTEND_SHA : null
  const warnFrontend = differs(backendSha, frontendKnown)
  const warnMain = differs(backendSha, github.main_sha)
  const synced = Boolean(backendSha && (frontendKnown || github.main_sha)) && !warnFrontend && !warnMain

  const val = sha => (short(sha) ? <span className={styles.mono}>{short(sha)}</span> : t('admin.unknown'))

  return (
    <SectionCard
      title={t('admin.deploy.title')}
      loading={loading}
      error={error}
      onRetry={reload}
      skeletonRows={5}
    >
      {data && (
        <>
          <div className={styles.badgeRow}>
            {warnFrontend && <span className={`${styles.badge} ${styles.warn}`}>{t('admin.deploy.warnFrontend')}</span>}
            {warnMain && <span className={`${styles.badge} ${styles.warn}`}>{t('admin.deploy.warnMain')}</span>}
            {synced && <span className={`${styles.badge} ${styles.ok}`}>{t('admin.deploy.inSync')}</span>}
          </div>
          <dl className={styles.kvList}>
            <Row label={t('admin.deploy.backend')}>{backendSha ? val(backendSha) : t('admin.deploy.local')}</Row>
            <Row label={t('admin.deploy.frontend')}>
              {FRONTEND_SHA === 'local' ? t('admin.deploy.local') : val(FRONTEND_SHA)}
            </Row>
            <Row label={t('admin.deploy.main')}>{val(github.main_sha)}</Row>
            <Row label={t('admin.deploy.develop')}>{val(github.develop_sha)}</Row>
            <Row label={t('admin.deploy.developAhead')}>
              {typeof github.develop_ahead_by === 'number'
                ? t('admin.deploy.commits', { n: github.develop_ahead_by })
                : t('admin.unknown')}
            </Row>
            {data.backend?.environment && (
              <Row label={t('admin.deploy.environment')}>{data.backend.environment}</Row>
            )}
          </dl>
          {github.error && (
            <p className={styles.muted}>{t('admin.deploy.githubError', { error: github.error })}</p>
          )}
        </>
      )}
    </SectionCard>
  )
}
