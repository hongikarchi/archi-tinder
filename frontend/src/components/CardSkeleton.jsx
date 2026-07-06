/**
 * CardSkeleton.jsx — business-card-styled deck loading skeleton.
 *
 * Replaces the per-page `LoadingCard` implementations previously duplicated in
 * DiscoveryPage.jsx and SwipePage.jsx (shimmer + mascot + dots). Uses the
 * card-language "paper card" visual (see components/cardLanguage.js) + the
 * `.lp-skel` pulse animation (index.css) — no shimmer, no mascot.
 */

import { CARD_HEIGHT, CARD_WIDTH } from './SwipeCard.jsx'
import { useTranslation } from '../i18n/index.js'
import {
  MONO,
  INK,
  paperFaceStyle,
  wordmarkStyle,
} from './cardLanguage.js'

export default function CardSkeleton({ label }) {
  const { t } = useTranslation()

  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      style={{
        ...paperFaceStyle({ radius: 20 }),
        position: 'absolute',
        top: 0,
        left: 0,
        width: CARD_WIDTH,
        height: CARD_HEIGHT,
        justifyContent: 'space-between',
      }}
    >
      {/* Top: real wordmark */}
      <div style={wordmarkStyle}>ARCHIBE</div>

      {/* Middle: skeleton rows + mono caption */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div className="lp-skel" style={{ height: 26, width: '62%', animationDelay: '0s' }} />
        <div className="lp-skel" style={{ height: 13, width: '38%', animationDelay: '0.15s' }} />
        <div className="lp-skel" style={{ height: 13, width: '52%', animationDelay: '0.3s' }} />
        <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 500, color: INK.muted, marginTop: 4 }}>
          {label ?? t('discovery.loading')}
        </span>
      </div>

      {/* Footer: two mono blocks left, monogram-stamp-shaped skeleton right */}
      <footer style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 14 }}>
        <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="lp-skel" style={{ height: 12, width: 96 }} />
          <div className="lp-skel" style={{ height: 11, width: 72 }} />
        </div>
        <div className="lp-skel" style={{ flexShrink: 0, width: 72, height: 72, borderRadius: 4 }} />
      </footer>
    </div>
  )
}
