/**
 * DiscoveryTriggerCard — injected into the Discovery deck when draftLikeCount
 * reaches the TASTE_NUDGE_THRESHOLD (10). Rendered inside a SwipeGestureFrame so
 * it is swipeable:
 *   RIGHT swipe → promote Discovery draft to a Taste session (→ /swipe)
 *   LEFT  swipe → dismiss, keep swiping Discovery
 *
 * Dimensions match SwipeCard (useCardSize width × height) so the stack layout is
 * identical. Paper business-card language (components/cardLanguage.js).
 *
 * Design "제안 A": the two choice boxes are replaced by blurred grey half-ellipses
 * hugging the left/right card edges (decorative), with the direction labels on top.
 * Layout is percentage-based so it scales with the card height (which is clamped
 * on short viewports): title block at 15%, ellipse centre at 61%, hint 30px from
 * the bottom. Optional `leanStore` (hooks/useTriggerCardLean) strengthens the side
 * the user is dragging toward.
 */
import { useCardSize } from '../hooks/useCardSize.js'
import { useTranslation } from '../i18n/index.js'
import { useTriggerCardLean } from '../hooks/useTriggerCardLean.js'
import {
  INK,
  paperFaceStyle,
  monoLabelStyle,
  cardMetaStyle,
} from './cardLanguage.js'
import styles from './DiscoveryTriggerCard.module.css'

export default function DiscoveryTriggerCard({ leanStore }) {
  const { t } = useTranslation()
  const { width: CARD_WIDTH, height: CARD_HEIGHT } = useCardSize()
  const lean = useTriggerCardLean(leanStore)
  return (
    <div
      className={styles.card}
      data-lean={lean || undefined}
      style={{
        ...paperFaceStyle({ radius: 20, padding: 0 }),
        width: CARD_WIDTH,
        height: CARD_HEIGHT,
        position: 'relative',
        overflow: 'hidden',
        userSelect: 'none',
        WebkitUserSelect: 'none',
        boxSizing: 'border-box',
      }}
    >
      {/* Decorative half-ellipses (clipped by the card) */}
      <div className={`${styles.moon} ${styles.moonLeft}`} aria-hidden="true">
        <div className={styles.blob} />
      </div>
      <div className={`${styles.moon} ${styles.moonRight}`} aria-hidden="true">
        <div className={styles.blob} />
      </div>

      {/* Title + body */}
      <div style={{
        position: 'absolute', top: '15%', left: 22, right: 22, textAlign: 'center',
      }}>
        <h2 style={{
          fontFamily: 'var(--font-family)',
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: '-0.01em',
          color: INK.strong,
          lineHeight: 1.25,
          margin: '0 0 10px',
        }}>
          {t('discovery.triggerCard.title')}
        </h2>
        <p style={{
          ...cardMetaStyle,
          lineHeight: 1.55,
          textAlign: 'center',
          wordBreak: 'keep-all',
          textWrap: 'balance',
        }}>
          {t('discovery.triggerCard.body')}
        </p>
      </div>

      {/* Direction labels (non-interactive — swipe is the only input) */}
      <div className={`${styles.lab} ${styles.labLeft}`}>
        <span className={styles.arrow}>←</span>
        <span className={styles.labText}>
          {t('discovery.triggerCard.continueLeft1')}<br />{t('discovery.triggerCard.continueLeft2')}
        </span>
      </div>
      <div className={`${styles.lab} ${styles.labRight}`}>
        <span className={styles.arrow}>→</span>
        <span className={styles.labText}>
          {t('discovery.triggerCard.continueRight1')}<br />{t('discovery.triggerCard.continueRight2')}
        </span>
      </div>

      {/* Bottom hint */}
      <p style={{
        ...monoLabelStyle,
        position: 'absolute', left: 0, right: 0, bottom: 30, textAlign: 'center',
      }}>
        {t('discovery.triggerCard.swipeHint')}
      </p>
    </div>
  )
}
