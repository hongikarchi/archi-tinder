/**
 * SettingsPage — /settings
 *
 * Row list (프로필 편집, 계정, 알림, 화면 설정, + 관리자 for admins) each navigating to a sub-route.
 * Layout: viewport-locked scroll, glassmorphic sticky header (mirrors ProfileHeader).
 */
import { useNavigate, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from '../../i18n/index.js'
import PageLogoHeader from '../../components/PageLogoHeader.jsx'
import PageTopControls from '../../components/PageTopControls.jsx'
import PageBackButton from '../../components/PageBackButton.jsx'
import PageShell from '../../components/PageShell.jsx'
import PageTitle from '../../components/PageTitle.jsx'
import { useAdminStatus } from '../../hooks/useAdminStatus.js'
import styles from './SettingsPage.module.css'

const ROWS = [
  { key: 'edit-profile',  labelKey: 'settings.rows.editProfile.label',   hintKey: 'settings.rows.editProfile.hint',   path: '/settings/edit-profile' },
  { key: 'account',       labelKey: 'settings.rows.account.label',        hintKey: 'settings.rows.account.hint',        path: '/settings/account' },
  { key: 'notifications', labelKey: 'settings.rows.notifications.label',  hintKey: 'settings.rows.notifications.hint',  path: '/settings/notifications' },
  { key: 'appearance',    labelKey: 'settings.rows.appearance.label',     hintKey: 'settings.rows.appearance.hint',     path: '/settings/appearance' },
]

// ADMIN-DASH-1: shown only when GET /auth/me/ says is_admin === true.
const ADMIN_ROW = { key: 'admin', labelKey: 'settings.rows.admin.label', hintKey: 'settings.rows.admin.hint', path: '/admin' }

export default function SettingsPage({ onLogout }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
  const isAdmin = useAdminStatus() === true
  const rows = isAdmin ? [...ROWS, ADMIN_ROW] : ROWS

  // Show list only at exact /settings; sub-routes render their own layout via Outlet
  const isRoot = location.pathname === '/settings' || location.pathname === '/settings/'

  return (
    <>
      {isRoot && (
        <PageShell
          width="narrow"
          chrome={<>
            <PageLogoHeader />
            <PageTopControls onLogout={onLogout} leading={<PageBackButton inline onClick={() => navigate(-1)} />} />
          </>}
          contentStyle={{ padding: '24px 20px' }}
        >
          <PageTitle>{t('settings.title')}</PageTitle>
          <div className={styles.listCard}>
            {rows.map((row) => (
              <button
                key={row.key}
                type="button"
                onClick={() => navigate(row.path)}
                className={styles.row}
              >
                <span className={styles.rowLabel}>{t(row.labelKey)}</span>
                {row.hintKey && <span className={styles.rowHint}>{t(row.hintKey)}</span>}
                <span className={styles.rowChevron} aria-hidden="true">›</span>
              </button>
            ))}
          </div>

          {/* Bottom padding for TabBar */}
          <div style={{ height: 24 }} />
        </PageShell>
      )}
      <Outlet />
    </>
  )
}
