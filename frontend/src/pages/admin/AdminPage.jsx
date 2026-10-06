/**
 * AdminPage — ADMIN-DASH-1 operator dashboard (/admin).
 *
 * Sections load independently (one useAdminSection per endpoint) so a failing
 * endpoint only blanks its own card. The version endpoint feeds two cards
 * (deploy + CI) via a single request.
 */
import { useNavigate } from 'react-router-dom'
import { getAdminFlags, getAdminMigrations, getAdminStats, getAdminVersion } from '../../api/admin.js'
import { useTranslation } from '../../i18n/index.js'
import PageLogoHeader from '../../components/PageLogoHeader.jsx'
import PageTopControls from '../../components/PageTopControls.jsx'
import PageBackButton from '../../components/PageBackButton.jsx'
import PageShell from '../../components/PageShell.jsx'
import PageTitle from '../../components/PageTitle.jsx'
import { useAdminSection } from './useAdminSection.js'
import DeploySection from './DeploySection.jsx'
import MigrationSection from './MigrationSection.jsx'
import CiSection from './CiSection.jsx'
import FlagsSection from './FlagsSection.jsx'
import StatsSection from './StatsSection.jsx'
import AuditSection from './AuditSection.jsx'
import ServicesSection from './ServicesSection.jsx'
import styles from './AdminPage.module.css'

export default function AdminPage({ onLogout }) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const version = useAdminSection(getAdminVersion)
  const migrations = useAdminSection(getAdminMigrations)
  const flags = useAdminSection(getAdminFlags)
  const stats = useAdminSection(getAdminStats)

  return (
    <PageShell
      width="wide"
      chrome={<>
        <PageLogoHeader />
        <PageTopControls onLogout={onLogout} leading={<PageBackButton inline label={t('admin.back')} onClick={() => navigate('/settings')} />} />
      </>}
      contentStyle={{ padding: '24px 20px' }}
    >
      <PageTitle>{t('admin.title')}</PageTitle>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))',
          gap: 16,
          alignItems: 'start',
        }}
      >
        <DeploySection section={version} />
        <CiSection section={version} />
        <div style={{ gridColumn: '1 / -1', minWidth: 0 }}>
          <ServicesSection />
        </div>
        <MigrationSection section={migrations} />
        <FlagsSection section={flags} />
        <StatsSection section={stats} />
        <section className={styles.card}>
          <h2 className={styles.cardTitle}>{t('admin.tools.title')}</h2>
          <button type="button" className={styles.linkRow} onClick={() => navigate('/admin/db-check')}>
            <span>
              {t('admin.tools.dbCheck')}
              <span className={styles.flagDesc}>{t('admin.tools.dbCheckHint')}</span>
            </span>
            <span className={styles.chevron} aria-hidden="true">›</span>
          </button>
        </section>
      </div>
      <div style={{ marginTop: 16 }}>
        <AuditSection />
      </div>
    </PageShell>
  )
}
