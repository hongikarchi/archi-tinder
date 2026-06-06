/**
 * SettingsPage — /settings
 *
 * Three-row list (계정, 알림, 화면 설정) each navigating to a sub-route.
 * Layout: viewport-locked scroll, glassmorphic sticky header (mirrors ProfileHeader).
 */
import { useNavigate, Outlet, useLocation } from 'react-router-dom'
import { IconBack } from '../../components/icons.jsx'
import styles from './SettingsPage.module.css'

const ROWS = [
  { key: 'account',       label: '계정',      hint: '핸들 · 로그인 정보',  path: '/settings/account' },
  { key: 'notifications', label: '알림',      hint: '푸시 · 이메일',       path: '/settings/notifications' },
  { key: 'appearance',    label: '화면 설정', hint: '테마 · 폰트 · 언어',  path: '/settings/appearance' },
]

export default function SettingsPage() {
  const navigate = useNavigate()
  const location = useLocation()

  // Show list only at exact /settings; sub-routes render their own layout via Outlet
  const isRoot = location.pathname === '/settings' || location.pathname === '/settings/'

  return (
    <>
      {isRoot && (
        <div className={styles.page}>
          {/* Glassmorphic sticky header */}
          <div className={styles.header}>
            <button
              type="button"
              onClick={() => navigate(-1)}
              aria-label="Back"
              className={styles.iconBtn}
            >
              <IconBack width={20} height={20} />
            </button>
            <h2 className={styles.headerTitle}>Settings</h2>
            {/* Spacer to keep title centered */}
            <div style={{ width: 44 }} />
          </div>

          {/* Settings list */}
          <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>
            <div className={styles.listCard}>
              {ROWS.map((row) => (
                <button
                  key={row.key}
                  type="button"
                  onClick={() => navigate(row.path)}
                  className={styles.row}
                >
                  <span className={styles.rowLabel}>{row.label}</span>
                  {row.hint && <span className={styles.rowHint}>{row.hint}</span>}
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
