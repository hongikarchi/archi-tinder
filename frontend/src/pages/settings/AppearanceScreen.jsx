/**
 * AppearanceScreen — /settings/appearance
 *
 * Wraps the existing self-contained AppearanceSettings component.
 * Theme/font/language wiring is unchanged — all lives inside AppearanceSettings.
 */
import { useNavigate } from 'react-router-dom'
import AppearanceSettings from '../../components/AppearanceSettings.jsx'
import { IconBack } from '../../components/icons.jsx'
import styles from './AppearanceScreen.module.css'

export default function AppearanceScreen() {
  const navigate = useNavigate()

  return (
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
        <h2 className={styles.headerTitle}>화면 설정</h2>
        <div style={{ width: 44 }} />
      </div>

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>
        <AppearanceSettings />
      </div>

      <div style={{ height: 24 }} />
    </div>
  )
}
