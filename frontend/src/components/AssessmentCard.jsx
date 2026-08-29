/**
 * AssessmentCard — one personality-assessment question rendered as a swipe-deck
 * card.
 *
 * Shares its entire surface with the Taste/Discovery calibration card
 * (QuestionCard.jsx): both spread the same `cardShellStyle` /
 * `questionCardBodyStyle` / `questionTitleStyle` / `questionBadgeStyle` /
 * `questionOptionStyle` from cardShell.js, which in turn takes its footprint
 * from SwipeCard's CARD_WIDTH/CARD_HEIGHT. Nothing here re-declares a radius,
 * shadow, padding or font size of its own.
 *
 * Every interactive element carries the `pressable` class: the vendored
 * tinderCard fork calls preventDefault() on touchstart unless the event's
 * srcElement className includes it (lib/tinderCard.js), which would otherwise
 * swallow taps and the option-list scroll on touch devices.
 */
import {
  cardShellStyle,
  questionCardBodyStyle,
  questionTitleStyle,
  questionBadgeStyle,
  questionOptionStyle,
} from './cardShell.js'
import { LIKERT_LABELS, LIKERT_VALUES } from '../constants/assessmentQuestions.js'
import styles from './AssessmentCard.module.css'

/**
 * Props:
 *   question   { id, axis, reversed, text_ko }
 *   selected   stored response for this question (null = unanswered)
 *   disabled   true while the card is flying out — blocks double answers
 *   onAnswer   (rawLikertValue) => void
 */
export default function AssessmentCard({ question, selected, disabled, onAnswer }) {
  if (!question) return null

  return (
    <div style={{ ...cardShellStyle, ...questionCardBodyStyle, justifyContent: 'center' }}>

      {/* Badge */}
      <p style={{ ...questionBadgeStyle, textAlign: 'center' }}>
        가까운 정도를 선택하세요
      </p>

      {/* Question text */}
      <p style={questionTitleStyle}>{question.text_ko}</p>

      {/* Likert options — unchanged 5-point scale, -2..+2 */}
      <div
        className={`${styles.options} pressable`}
        role="group"
        aria-label="답변 선택"
      >
        {LIKERT_VALUES.map((val, idx) => {
          const stored = question.reversed ? val * -1 : val
          const isSelected = selected === stored
          return (
            <button
              key={val}
              type="button"
              disabled={disabled}
              className={`${styles.option} ${isSelected ? styles.optionSelected : ''} pressable`}
              style={questionOptionStyle}
              onClick={() => onAnswer(val)}
              aria-pressed={isSelected}
            >
              <span className={`${styles.val} pressable`}>{val > 0 ? `+${val}` : val}</span>
              <span className={`${styles.label} pressable`}>{LIKERT_LABELS[idx]}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
