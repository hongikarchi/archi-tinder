/**
 * ChoiceCard — the one two-choice swipe card shared by:
 *   - Discovery trigger card (10 likes)
 *   - Discovery 50-card cap card
 *   - Taste action card (SwipePage)
 * Paper business-card language (components/cardLanguage.js). Swipe-only: the
 * direction labels are decorative, the owner wraps this in a SwipeGestureFrame.
 *
 * Layout is percentage-based so it scales with the (clamped) card height:
 * title block centred at 35%, ellipses at 47-85%, labels centred at 66%.
 * Optional `leanStore` (hooks/useCardLean) strengthens the side being dragged.
 */
import { useCardSize } from '../hooks/useCardSize.js'
import { useCardLean } from '../hooks/useCardLean.js'
import {
  INK,
  MONO,
  LS_CAPS,
  paperFaceStyle,
  wordmarkStyle,
  monoLabelStyle,
} from './cardLanguage.js'
import styles from './ChoiceCard.module.css'

export default function ChoiceCard({ stamp, title, body, left, right, hint, leanStore }) {
  const { width: CARD_WIDTH, height: CARD_HEIGHT } = useCardSize()
  const lean = useCardLean(leanStore)
  return (
    <div
      className={styles.card}
      data-lean={lean || undefined}
      data-choice-card=""
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

      {/* Top row: wordmark + mono stamp */}
      <div style={{
        position: 'absolute', top: 24, left: 22, right: 22,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={wordmarkStyle}>ARCHIBE</span>
        <span style={{
          fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: LS_CAPS, color: INK.mid,
        }}>
          {stamp}
        </span>
      </div>

      {/* Title + body */}
      <div style={{
        position: 'absolute', left: 22, right: 22, top: '35%',
        transform: 'translateY(-50%)',
        display: 'flex', flexDirection: 'column', gap: 10, textAlign: 'center',
      }}>
        <h2 style={{
          fontFamily: 'var(--font-family)',
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: '-0.01em',
          color: INK.strong,
          lineHeight: 1.35,
          margin: 0,
        }}>
          {title}
        </h2>
        {body && (
          <p style={{
            fontFamily: 'var(--font-family)',
            fontSize: 13,
            fontWeight: 400,
            color: INK.muted,
            lineHeight: 1.55,
            margin: 0,
            textAlign: 'center',
            wordBreak: 'keep-all',
            textWrap: 'balance',
          }}>
            {body}
          </p>
        )}
      </div>

      {/* Direction labels (non-interactive — swipe is the only input) */}
      <div className={`${styles.lab} ${styles.labLeft}`}>
        <span className={styles.arrow}>←</span>
        <span className={styles.labText}>
          {left.line1}<br />{left.line2}
        </span>
      </div>
      <div className={`${styles.lab} ${styles.labRight}`}>
        <span className={styles.arrow}>→</span>
        <span className={styles.labText}>
          {right.line1}<br />{right.line2}
        </span>
      </div>

      {/* Bottom hint */}
      <p style={{
        ...monoLabelStyle,
        position: 'absolute', left: 0, right: 0, bottom: 24, textAlign: 'center',
      }}>
        {hint}
      </p>
    </div>
  )
}
