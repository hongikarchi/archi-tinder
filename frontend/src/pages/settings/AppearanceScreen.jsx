/**
 * AppearanceScreen — /settings/appearance
 *
 * Wraps the existing self-contained AppearanceSettings component.
 * Theme/font/language wiring is unchanged — all lives inside AppearanceSettings.
 */
import { useNavigate } from 'react-router-dom'
import AppearanceSettings from '../../components/AppearanceSettings.jsx'
import { useTranslation } from '../../i18n/index.js'
import PageLogoHeader from '../../components/PageLogoHeader.jsx'
import PageTopControls from '../../components/PageTopControls.jsx'
import PageBackButton from '../../components/PageBackButton.jsx'
import styles from './AppearanceScreen.module.css'

export default function AppearanceScreen({ onLogout }) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  return (
    <div className={styles.page}>
      <PageBackButton onClick={() => navigate(-1)} />
      <PageLogoHeader />
      <PageTopControls onLogout={onLogout} />

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>
        <h2 className={styles.headerTitle}>{t('settings.appearance')}</h2>
        <AppearanceSettings />
      </div>

      <div style={{ height: 24 }} />
    </div>
  )
}
