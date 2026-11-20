/**
 * AppearanceScreen — /settings/appearance
 *
 * Wraps the existing self-contained AppearanceSettings component.
 * Theme/font/language wiring is unchanged — all lives inside AppearanceSettings.
 */
import { useNavigate } from 'react-router-dom'
import AppearanceSettings from '../../components/AppearanceSettings.tsx'
import { useTranslation } from '../../i18n/index.ts'
import PageLogoHeader from '../../components/PageLogoHeader.tsx'
import PageTopControls from '../../components/PageTopControls.tsx'
import PageBackButton from '../../components/PageBackButton.tsx'
import PageShell from '../../components/PageShell.tsx'
import PageTitle from '../../components/PageTitle.tsx'

interface ScreenProps {
  onLogout?: () => void
}

export default function AppearanceScreen({ onLogout }: ScreenProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  return (
    <PageShell
      width="narrow"
      chrome={<>
        <PageLogoHeader />
        <PageTopControls onLogout={onLogout} leading={<PageBackButton inline onClick={() => navigate(-1)} />} />
      </>}
      contentStyle={{ padding: '24px 20px' }}
    >
      <PageTitle>{t('settings.appearance')}</PageTitle>
      <AppearanceSettings />

      <div style={{ height: 24 }} />
    </PageShell>
  )
}
