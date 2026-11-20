/**
 * DiscoveryCapCard — shown when the Discovery like cap (50) is reached.
 *   RIGHT swipe → promote to Taste (blocking overlay flow)
 *   LEFT  swipe → go to the Profile tab (through the Discovery leave guard)
 * Visuals live in the shared ChoiceCard.
 */
import { useTranslation } from '../i18n/index.ts'
import ChoiceCard from './ChoiceCard.tsx'
import type { CardLeanStore } from '../hooks/useCardLean.ts'

export default function DiscoveryCapCard({ leanStore }: { leanStore?: CardLeanStore | null }) {
  const { t } = useTranslation()
  return (
    <ChoiceCard
      leanStore={leanStore}
      stamp={t('discovery.capCard.stamp')}
      title={t('discovery.capCard.title')}
      body={t('discovery.capCard.body')}
      left={{ line1: t('discovery.capCard.leftLine1'), line2: t('discovery.capCard.leftLine2') }}
      right={{ line1: t('discovery.capCard.rightLine1'), line2: t('discovery.capCard.rightLine2') }}
      hint={t('discovery.triggerCard.swipeHint')}
    />
  )
}
