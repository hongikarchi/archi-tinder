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
import PageShell from '../../components/PageShell.jsx'
import PageTitle from '../../components/PageTitle.jsx'

export default function AppearanceScreen({ onLogout }) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  return (
    <PageShell
      width="narrow"
      chrome={<>
        <PageBackButton onClick={() => navigate(-1)} />
        <PageLogoHeader />
        <PageTopControls onLogout={onLogout} />
      </>}
      contentStyle={{ padding: '24px 20px' }}
    >
      <PageTitle>{t('settings.appearance')}</PageTitle>
      <AppearanceSettings />

      <div style={{ height: 24 }} />
    </PageShell>
  )
}
