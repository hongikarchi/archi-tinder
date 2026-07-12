/**
 * DiscoveryTriggerCard — injected into the Discovery deck when draftLikeCount
 * reaches the TASTE_NUDGE_THRESHOLD (10). Rendered inside a SwipeGestureFrame so
 * it is swipeable:
 *   RIGHT swipe → promote Discovery draft to a Taste session (→ /swipe)
 *   LEFT  swipe → dismiss, keep swiping Discovery
 *
 * Dimensions match SwipeCard (CARD_WIDTH × CARD_HEIGHT) so the stack layout is
 * identical. Styling follows DESIGN.md §8.1 (Primary CTA gradient) + §1.2 accent
 * tokens + §3.5 motion tokens.
 */
import { CARD_WIDTH, CARD_HEIGHT } from './SwipeCard.jsx'
import { useTranslation } from '../i18n/index.js'

export default function DiscoveryTriggerCard() {
  const { t } = useTranslation()
  return (
    <div
      style={{
        width: CARD_WIDTH,
        height: CARD_HEIGHT,
        borderRadius: 'var(--radius-lg, 20px)',
        overflow: 'hidden',
        background: 'linear-gradient(135deg, var(--accent-1, #0969DA), var(--accent-2, #8250DF))',
        boxShadow: '0 12px 32px rgba(0,0,0,0.3)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 32,
        padding: '32px 24px',
        position: 'relative',
        userSelect: 'none',
        WebkitUserSelect: 'none',
      }}
    >
      {/* Main message */}
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontSize: 48,
          lineHeight: 1,
          marginBottom: 16,
        }}>
          ✨
        </div>
        <h2 style={{
          fontSize: 22,
          fontWeight: 700,
          color: '#fff',
          margin: '0 0 10px',
          letterSpacing: '-0.02em',
          lineHeight: 1.3,
        }}>
          {t('discovery.triggerCard.title')}
        </h2>
        <p style={{
          fontSize: 14,
          fontWeight: 400,
          color: 'rgba(255,255,255,0.78)',
          margin: 0,
          lineHeight: 1.5,
        }}>
          {t('discovery.triggerCard.bodyLine1')}<br />{t('discovery.triggerCard.bodyLine2')}
        </p>
      </div>

      {/* Swipe affordances */}
      <div style={{
        display: 'flex',
        gap: 12,
        width: '100%',
      }}>
        {/* LEFT direction — continue Discovery */}
        <div style={{
          flex: 1,
          background: 'rgba(255,255,255,0.15)',
          border: '1px solid rgba(255,255,255,0.25)',
          borderRadius: 'var(--radius-md, 12px)',
          padding: '12px 10px',
          textAlign: 'center',
        }}>
          <div style={{
            fontSize: 20,
            marginBottom: 6,
            color: '#fff',
          }}>
            ←
          </div>
          <div style={{
            fontSize: 12,
            fontWeight: 500,
            color: 'rgba(255,255,255,0.9)',
            lineHeight: 1.4,
          }}>
            {t('discovery.triggerCard.continueLeft1')}<br />{t('discovery.triggerCard.continueLeft2')}
          </div>
        </div>

        {/* RIGHT direction — promote to Taste */}
        <div style={{
          flex: 1,
          background: 'rgba(255,255,255,0.22)',
          border: '1px solid rgba(255,255,255,0.4)',
          borderRadius: 'var(--radius-md, 12px)',
          padding: '12px 10px',
          textAlign: 'center',
        }}>
          <div style={{
            fontSize: 20,
            marginBottom: 6,
            color: '#fff',
          }}>
            →
          </div>
          <div style={{
            fontSize: 12,
            fontWeight: 600,
            color: '#fff',
            lineHeight: 1.4,
          }}>
            {t('discovery.triggerCard.continueRight1')}<br />{t('discovery.triggerCard.continueRight2')}
          </div>
        </div>
      </div>

      {/* Bottom hint */}
      <p style={{
        position: 'absolute',
        bottom: 18,
        left: 0,
        right: 0,
        textAlign: 'center',
        margin: 0,
        fontSize: 11,
        fontWeight: 500,
        color: 'rgba(255,255,255,0.5)',
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
      }}>
        swipe to choose
      </p>
    </div>
  )
}
