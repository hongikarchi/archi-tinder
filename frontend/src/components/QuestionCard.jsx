import { CARD_WIDTH, CARD_HEIGHT } from './SwipeCard.jsx'
import { useTranslation } from '../i18n/index.js'

/**
 * QuestionCard — displayed in place of TinderCard when the backend triggers
 * an in-session taste-calibration question.
 *
 * Props:
 *   trigger   { type, axis, question, option_a, option_b }
 *   onAnswer  (option: "A" | "B" | "skip") => void
 */
export default function QuestionCard({ trigger, onAnswer }) {
  const { t } = useTranslation()
  if (!trigger) return null

  return (
    <div style={{
      width: CARD_WIDTH,
      height: CARD_HEIGHT,
      borderRadius: 20,
      overflow: 'hidden',
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      padding: '32px 24px',
      gap: 24,
      boxSizing: 'border-box',
    }}>

      {/* Badge */}
      <p style={{
        fontSize: 11,
        fontWeight: 500,
        color: 'var(--color-text-dim)',
        margin: 0,
        letterSpacing: '0.04em',
      }}>
        {t('swipe.questionCard.calibrating')}
      </p>

      {/* Swipe hint — gesture-friendly per DESIGN.md §4 */}
      <p style={{
        fontSize: 12,
        fontWeight: 500,
        color: 'var(--color-text-muted)',
        margin: 0,
        letterSpacing: '0.03em',
      }}>
        {t('swipe.questionCard.swipeHint')}
      </p>

      {/* Question text */}
      <p style={{
        fontSize: 18,
        fontWeight: 700,
        color: 'var(--color-text)',
        textAlign: 'center',
        lineHeight: 1.4,
        margin: 0,
      }}>
        {trigger.question}
      </p>

      {/* Answer buttons */}
      <div style={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}>
        <button
          onClick={() => onAnswer('A')}
          style={{
            padding: '14px 20px',
            borderRadius: 12,
            fontSize: 14,
            fontWeight: 600,
            background: 'var(--color-surface-2)',
            color: 'var(--color-text)',
            border: '1px solid var(--color-border)',
            cursor: 'pointer',
            fontFamily: 'inherit',
            width: '100%',
            minHeight: 48,
            textAlign: 'left',
          }}
        >
          A. {trigger.option_a}
        </button>

        <button
          onClick={() => onAnswer('B')}
          style={{
            padding: '14px 20px',
            borderRadius: 12,
            fontSize: 14,
            fontWeight: 600,
            background: 'var(--color-surface-2)',
            color: 'var(--color-text)',
            border: '1px solid var(--color-border)',
            cursor: 'pointer',
            fontFamily: 'inherit',
            width: '100%',
            minHeight: 48,
            textAlign: 'left',
          }}
        >
          B. {trigger.option_b}
        </button>
      </div>

      {/* Skip */}
      <button
        onClick={() => onAnswer('skip')}
        style={{
          fontSize: 12,
          color: 'var(--color-text-dim)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '8px',
          marginTop: 4,
          fontFamily: 'inherit',
        }}
      >
        {t('swipe.questionCard.skip')}
      </button>

    </div>
  )
}
