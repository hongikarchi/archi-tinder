/**
 * AdminPage — ADMIN-DASH-1 operator dashboard (/admin).
 *
 * Sections load independently (one useAdminSection per endpoint) so a failing
 * endpoint only blanks its own card. The version endpoint feeds two cards
 * (deploy + CI) via a single request.
 */
import { useNavigate } from 'react-router-dom'
import { getAdminFlags, getAdminMigrations, getAdminStats, getAdminVersion } from '../../api/admin.ts'
import { useTranslation } from '../../i18n/index.ts'
import PageLogoHeader from '../../components/PageLogoHeader.tsx'
import PageTopControls from '../../components/PageTopControls.tsx'
import PageBackButton from '../../components/PageBackButton.tsx'
import PageShell from '../../components/PageShell.tsx'
import PageTitle from '../../components/PageTitle.tsx'
import { useAdminSection } from './useAdminSection.ts'
import DeploySection from './DeploySection.tsx'
import MigrationSection from './MigrationSection.tsx'
import CiSection from './CiSection.tsx'
import FlagsSection from './FlagsSection.tsx'
import StatsSection from './StatsSection.tsx'
import AuditSection from './AuditSection.tsx'
import ServicesSection from './ServicesSection.tsx'
import ContestsSection from './ContestsSection.tsx'
import styles from './AdminPage.module.css'

interface AdminPageProps {
  onLogout?: () => void
}

export default function AdminPage({ onLogout }: AdminPageProps) {
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
        <ContestsSection />
      </div>
      <div style={{ marginTop: 16 }}>
        <AuditSection />
      </div>
    </PageShell>
  )
}
