/**
 * DiscoveryTriggerCard — injected into the Discovery deck when draftLikeCount
 * reaches the TASTE_NUDGE_THRESHOLD (10). Rendered inside a SwipeGestureFrame:
 *   RIGHT swipe → promote Discovery draft to a Taste session (→ /swipe)
 *   LEFT  swipe → dismiss, keep swiping Discovery
 * Visuals live in the shared ChoiceCard.
 */
import { useTranslation } from '../i18n/index.js'
import ChoiceCard from './ChoiceCard.jsx'

export default function DiscoveryTriggerCard({ leanStore }) {
  const { t } = useTranslation()
  return (
    <ChoiceCard
      leanStore={leanStore}
      stamp={t('discovery.triggerCard.stamp')}
      title={t('discovery.triggerCard.title')}
      body={t('discovery.triggerCard.body')}
      left={{
        line1: t('discovery.triggerCard.continueLeft1'),
        line2: t('discovery.triggerCard.continueLeft2'),
      }}
      right={{
        line1: t('discovery.triggerCard.continueRight1'),
        line2: t('discovery.triggerCard.continueRight2'),
      }}
      hint={t('discovery.triggerCard.swipeHint')}
    />
  )
}
