/**
 * SettingsPage — /settings
 *
 * Three-row list (계정, 알림, 화면 설정) each navigating to a sub-route.
 * Layout: viewport-locked scroll, glassmorphic sticky header (mirrors ProfileHeader).
 */
import { useNavigate, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from '../../i18n/index.js'
import PageLogoHeader from '../../components/PageLogoHeader.jsx'
import PageTopControls from '../../components/PageTopControls.jsx'
import PageBackButton from '../../components/PageBackButton.jsx'
import styles from './SettingsPage.module.css'

const ROWS = [
  { key: 'edit-profile',  labelKey: 'settings.rows.editProfile.label',   hintKey: 'settings.rows.editProfile.hint',   path: '/settings/edit-profile' },
  { key: 'account',       labelKey: 'settings.rows.account.label',        hintKey: 'settings.rows.account.hint',        path: '/settings/account' },
  { key: 'notifications', labelKey: 'settings.rows.notifications.label',  hintKey: 'settings.rows.notifications.hint',  path: '/settings/notifications' },
  { key: 'appearance',    labelKey: 'settings.rows.appearance.label',     hintKey: 'settings.rows.appearance.hint',     path: '/settings/appearance' },
]

export default function SettingsPage({ onLogout }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()

  // Show list only at exact /settings; sub-routes render their own layout via Outlet
  const isRoot = location.pathname === '/settings' || location.pathname === '/settings/'

  return (
    <>
      {isRoot && (
        <div className={styles.page}>
          <PageBackButton onClick={() => navigate(-1)} />
          <PageLogoHeader />
          <PageTopControls onLogout={onLogout} />

          {/* Settings list */}
          <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>
            <h2 className={styles.headerTitle}>{t('settings.title')}</h2>
            <div className={styles.listCard}>
              {ROWS.map((row) => (
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
          </div>

          {/* Bottom padding for TabBar */}
          <div style={{ height: 24 }} />
        </div>
      )}
      <Outlet />
    </>
  )
}
