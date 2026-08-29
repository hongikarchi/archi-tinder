import {
  cardShellStyle,
  questionCardBodyStyle,
  questionTitleStyle,
  questionBadgeStyle,
  questionOptionStyle,
} from './cardShell.js'
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
      ...cardShellStyle,
      ...questionCardBodyStyle,
      justifyContent: 'center',
      alignItems: 'center',
    }}>

      {/* Badge */}
      <p style={questionBadgeStyle}>
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
      <p style={questionTitleStyle}>
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
          style={questionOptionStyle}
        >
          A. {trigger.option_a}
        </button>

        <button
          onClick={() => onAnswer('B')}
          style={questionOptionStyle}
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
