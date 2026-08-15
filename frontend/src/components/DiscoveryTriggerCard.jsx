/**
 * DiscoveryTriggerCard — injected into the Discovery deck when draftLikeCount
 * reaches the TASTE_NUDGE_THRESHOLD (10). Rendered inside a SwipeGestureFrame so
 * it is swipeable:
 *   RIGHT swipe → promote Discovery draft to a Taste session (→ /swipe)
 *   LEFT  swipe → dismiss, keep swiping Discovery
 *
 * Dimensions match SwipeCard (CARD_WIDTH × CARD_HEIGHT) so the stack layout is
 * identical. FRONT-FLOW-1: retheme from the blue-purple accent-gradient card to
 * the paper business-card language (components/cardLanguage.js) — same brand
 * identity as LoginPage. The paper look intentionally contrasts with the photo
 * cards around it in the deck (interstitial), same idiom as the login deck.
 */
import { CARD_WIDTH, CARD_HEIGHT } from './SwipeCard.jsx'
import { useTranslation } from '../i18n/index.js'
import {
  INK,
  MONO,
  LS_CAPS,
  paperFaceStyle,
  wordmarkStyle,
  monoLabelStyle,
  cardMetaStyle,
  inkSecondaryStyle,
} from './cardLanguage.js'

export default function DiscoveryTriggerCard() {
  const { t } = useTranslation()
  return (
    <div
      style={{
        ...paperFaceStyle({ radius: 20, padding: '24px 22px' }),
        width: CARD_WIDTH,
        height: CARD_HEIGHT,
        justifyContent: 'space-between',
        position: 'relative',
        userSelect: 'none',
        WebkitUserSelect: 'none',
        boxSizing: 'border-box',
      }}
    >
      {/* Top: wordmark row + mono stamp */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={wordmarkStyle}>ARCHIBE</span>
        <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: LS_CAPS, color: INK.mid }}>
          {t('discovery.triggerCard.stamp')}
        </span>
      </div>

      {/* Middle: title + body */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, textAlign: 'center' }}>
        <h2 style={{
          fontFamily: 'var(--font-family)',
          fontSize: 26,
          fontWeight: 700,
          letterSpacing: '-0.01em',
          color: INK.strong,
          lineHeight: 1.2,
          margin: 0,
        }}>
          {t('discovery.triggerCard.title')}
        </h2>
        <p style={{ ...cardMetaStyle, textAlign: 'center' }}>
          {t('discovery.triggerCard.bodyLine1')}<br />{t('discovery.triggerCard.bodyLine2')}
        </p>
      </div>

      {/* Bottom: two direction affordances (non-interactive — swipe is the only input) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', gap: 10, width: '100%' }}>
          {/* LEFT — continue Discovery (muted ink) */}
          <div style={{
            ...inkSecondaryStyle(false),
            flex: 1,
            flexDirection: 'column',
            gap: 4,
            color: INK.muted,
            borderColor: INK.dim,
            cursor: 'default',
          }}>
            <span style={{ fontSize: 18, lineHeight: 1 }}>←</span>
            <span style={{ fontSize: 12, fontWeight: 500, lineHeight: 1.4, color: INK.muted }}>
              {t('discovery.triggerCard.continueLeft1')}<br />{t('discovery.triggerCard.continueLeft2')}
            </span>
          </div>

          {/* RIGHT — promote to Taste (strong ink, emphasized action) */}
          <div style={{
            ...inkSecondaryStyle(false),
            flex: 1,
            flexDirection: 'column',
            gap: 4,
            cursor: 'default',
          }}>
            <span style={{ fontSize: 18, lineHeight: 1 }}>→</span>
            <span style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.4, color: INK.strong }}>
              {t('discovery.triggerCard.continueRight1')}<br />{t('discovery.triggerCard.continueRight2')}
            </span>
          </div>
        </div>

        {/* Bottom hint */}
        <p style={{ ...monoLabelStyle, textAlign: 'center' }}>
          {t('discovery.triggerCard.swipeHint')}
        </p>
      </div>
    </div>
  )
}
