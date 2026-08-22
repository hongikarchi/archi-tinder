/**
 * AssessmentPage.jsx
 * 20-question personality assessment — one question at a time, Likert 5-point.
 * Route: /assessment (ProtectedRoute)
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { QUESTIONS, LIKERT_LABELS, LIKERT_VALUES } from '../constants/assessmentQuestions.js'
import { TYPE_LABELS } from '../constants/personalityTypes.js'
import { submitAssessment } from '../api/personality.js'
import PentagonChart from '../components/PentagonChart.jsx'
import styles from './AssessmentPage.module.css'

const TOTAL = QUESTIONS.length

export default function AssessmentPage() {
  const navigate = useNavigate()

  const [currentQ, setCurrentQ] = useState(0)
  const [responses, setResponses] = useState(Array(TOTAL).fill(null))
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [showResult, setShowResult] = useState(false)
  const [submitError, setSubmitError] = useState(null)

  const question = QUESTIONS[currentQ]
  const progress = (currentQ / TOTAL) * 100
  const isLast = currentQ === TOTAL - 1

  function handleAnswer(rawValue) {
    const stored = question.reversed ? rawValue * -1 : rawValue
    const updated = [...responses]
    updated[currentQ] = stored

    if (!isLast) {
      setResponses(updated)
      setCurrentQ(q => q + 1)
    } else {
      setResponses(updated)
    }
  }

  function handleLastConfirm() {
    if (responses[currentQ] === null) return
    doSubmit(responses)
  }

  async function doSubmit(finalResponses) {
    setSubmitting(true)
    setSubmitError(null)
    try {
      const data = await submitAssessment(finalResponses)
      setResult(data)
      setShowResult(true)
    } catch (err) {
      setSubmitError(err.message || '제출에 실패했어요. 다시 시도해주세요.')
    } finally {
      setSubmitting(false)
    }
  }

  function vectorFrom(p) {
    if (!p) return null
    return [p.axis_1, p.axis_2, p.axis_3, p.axis_4, p.axis_5]
  }

  // Result screen
  if (showResult && result) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <button
            type="button"
            className={styles.backBtn}
            onClick={() => navigate('/user/me')}
            aria-label="프로필로 이동"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <h1 className={styles.title}>성향 진단 결과</h1>
        </header>

        <div className={styles.resultBody}>
          <p className={styles.typeCode}>{result.type_code}</p>
          <p className={styles.typeLabel}>{TYPE_LABELS[result.type_code] || '나만의 건축 성향'}</p>

          <div className={styles.chartWrap}>
            <PentagonChart
              myVector={vectorFrom(result)}
              size={200}
            />
          </div>

          <button
            type="button"
            className={styles.ctaBtn}
            onClick={() => navigate('/people')}
          >
            발견 피드 보기 →
          </button>

          <button
            type="button"
            className={styles.secondaryBtn}
            onClick={() => navigate('/user/me')}
          >
            프로필로 돌아가기
          </button>
        </div>
      </div>
    )
  }

  // Assessment screen
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button
          type="button"
          className={styles.backBtn}
          onClick={() => navigate(-1)}
          aria-label="뒤로가기"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h1 className={styles.title}>성향 진단</h1>
        <span className={styles.qCount}>{currentQ + 1} / {TOTAL}</span>
      </header>

      {/* Progress bar */}
      <div className={styles.progressTrack} role="progressbar" aria-valuenow={currentQ} aria-valuemin={0} aria-valuemax={TOTAL}>
        <div className={styles.progressFill} style={{ width: `${progress}%` }} />
      </div>

      <div className={styles.body}>
        <p className={styles.questionText}>{question.text_ko}</p>

        <div className={styles.likertGrid} role="group" aria-label="답변 선택">
          {LIKERT_VALUES.map((val, idx) => {
            const stored = question.reversed ? val * -1 : val
            const isSelected = responses[currentQ] === stored
            return (
              <button
                key={val}
                type="button"
                className={`${styles.likertBtn} ${isSelected ? styles.likertBtnSelected : ''}`}
                onClick={() => handleAnswer(val)}
                aria-pressed={isSelected}
              >
                <span className={styles.likertVal}>{val > 0 ? `+${val}` : val}</span>
                <span className={styles.likertLabel}>{LIKERT_LABELS[idx]}</span>
              </button>
            )
          })}
        </div>

        {/* Last question confirm button */}
        {isLast && (
          <button
            type="button"
            className={styles.submitBtn}
            onClick={handleLastConfirm}
            disabled={responses[currentQ] === null || submitting}
          >
            {submitting ? '제출 중...' : '완료'}
          </button>
        )}

        {submitError && (
          <p className={styles.errorText} role="alert">{submitError}</p>
        )}
      </div>
    </div>
  )
}
