/**
 * AssessmentPage.jsx
 * 20-question personality assessment — one question at a time, Likert 5-point.
 * Route: /assessment (ProtectedRoute)
 */

import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSpring, animated } from '@react-spring/web'
import { physics } from '../lib/tinderCard.js'
import { CARD_WIDTH } from '../components/cardShell.js'
import { QUESTIONS } from '../constants/assessmentQuestions.js'
import { TYPE_LABELS } from '../constants/personalityTypes.js'
import { submitAssessment } from '../api/personality.js'
import PentagonChart from '../components/PentagonChart.jsx'
import AssessmentCard from '../components/AssessmentCard.jsx'
import SwipeDeck from '../components/SwipeDeck.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'
import { SWIPE_PREVENT_ALL } from '../components/swipeGestureConfig.js'
import {
  loadAssessmentDraft,
  saveAssessmentDraft,
  clearAssessmentDraft,
} from '../utils/assessmentDraft.js'
import styles from './AssessmentPage.module.css'

// Aliased the same way lib/tinderCard.js does it — the shared ESLint config
// does not count a JSX member expression as a use of `animated`.
const AnimatedDiv = animated.div

const TOTAL = QUESTIONS.length

// Answered cards always leave toward the same edge (requirement: one
// consistent direction). 'left' matches DiscoveryPage's "pass" exit.
const EXIT_DIRECTION = 'left'

// Reduced-motion fallback: the card cross-fades instead of flying. Kept at
// --motion-fast (180ms, tokens.css) so the answer->next-question rhythm stays
// close to the animated path without the travel.
const REDUCED_FADE_MS = 180

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default function AssessmentPage() {
  const navigate = useNavigate()

  // Read once, on mount. Refresh / browser-back / typing the URL all remount
  // this component, so without this the run restarted at question 1 every time.
  // App.jsx keeps the signed-in id in sessionStorage under this key.
  const [userId] = useState(() => sessionStorage.getItem('archithon_user') || null)
  const [draft] = useState(() => loadAssessmentDraft(userId, TOTAL))

  const [currentQ, setCurrentQ] = useState(() => draft?.currentQ ?? 0)
  const [responses, setResponses] = useState(
    () => draft?.responses ?? Array(TOTAL).fill(null)
  )
  // Surfaces a one-line "이어서 진행 중" note; dismissed on the first answer.
  const [resumed, setResumed] = useState(() => draft !== null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [showResult, setShowResult] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  // busy   — any card transition is running; blocks every input.
  // exiting — narrower: the top card is flying OUT (forward). Drives the
  //           reduced-motion fade, which must not apply to a card coming back.
  const [busy, setBusy] = useState(false)
  const [exiting, setExiting] = useState(false)
  const [entering, setEntering] = useState(false)
  // Bumped on submit failure to remount the last card, so a card that already
  // flew off-screen comes back centered instead of staying gone.
  const [retryKey, setRetryKey] = useState(0)

  const busyRef = useRef(false)
  const cardRef = useRef(null)

  // "Previous question" re-entry. The card is dropped off-screen on the same
  // edge answers leave by (EXIT_DIRECTION = left) and springs back to centre
  // with physics.animateBack — the very config tinderCard.js uses to snap a
  // released drag back into the deck, so the return reads as the exit undone.
  const [{ backX }, backSpring] = useSpring(() => ({
    backX: 0,
    config: physics.animateBack,
  }))

  const isLast = currentQ === TOTAL - 1
  // Progress tracks answers, not the visible index, so the bar advances the
  // moment an option is tapped and eases (--motion-normal) while the card flies.
  const answered = responses.filter(r => r !== null).length
  const progress = (answered / TOTAL) * 100

  // Persist progress so refresh / back / a typed URL resumes where the user
  // left off. Mirrors App.jsx's `archithon_currentCard_${userId}_...` effect:
  // write on change, and let the helper clear the slot when there is nothing to
  // resume. Skipped once the result screen is up — that run is finished and its
  // draft was already cleared by doSubmit.
  useEffect(() => {
    if (!userId || showResult) return
    saveAssessmentDraft(userId, { currentQ, responses })
  }, [userId, currentQ, responses, showResult])

  // Top card + the one underneath it, mirroring DiscoveryPage's deck: both are
  // rendered in identical keyed wrappers so React reuses the DOM node when the
  // under card is promoted to top (no remount, no flicker).
  const deck = [QUESTIONS[currentQ], QUESTIONS[currentQ + 1]].filter(Boolean)

  async function handleAnswer(rawValue) {
    if (busyRef.current || submitting) return
    busyRef.current = true
    setBusy(true)
    setExiting(true)

    setResumed(false)

    const question = QUESTIONS[currentQ]
    const stored = question.reversed ? rawValue * -1 : rawValue
    const updated = [...responses]
    updated[currentQ] = stored
    setResponses(updated)

    if (prefersReducedMotion()) {
      await new Promise(resolve => setTimeout(resolve, REDUCED_FADE_MS))
    } else {
      // Same exit as a Discovery/Taste swipe: the vendored tinderCard fork's
      // animateOut (easeInOutCubic, duration clamped to 480-680ms, travel =
      // viewport diagonal, rotation = x * 45deg).
      await cardRef.current?.swipe(EXIT_DIRECTION)
    }

    if (isLast) {
      await doSubmit(updated)
    } else {
      setCurrentQ(q => q + 1)
    }

    busyRef.current = false
    setBusy(false)
    setExiting(false)
  }

  /**
   * Step back one question. The answer already given is kept (the card returns
   * with its option still selected) so this reads as "review / change", not
   * "erase". Re-answering overwrites it and moves forward again.
   */
  function handleBack() {
    if (busyRef.current || submitting || currentQ === 0) return
    busyRef.current = true
    setBusy(true)
    setEntering(true)

    const finish = () => {
      busyRef.current = false
      setBusy(false)
      setEntering(false)
    }

    if (prefersReducedMotion()) {
      setCurrentQ(q => q - 1)
      setTimeout(finish, REDUCED_FADE_MS)
      return
    }

    // Start fully off-screen on the edge answered cards leave by, then spring
    // home. window.innerWidth + CARD_WIDTH clears the deck no matter where it
    // sits horizontally.
    backSpring.set({ backX: -(window.innerWidth + CARD_WIDTH) })
    setCurrentQ(q => q - 1)
    backSpring.start({ backX: 0, config: physics.animateBack, onRest: finish })
  }

  async function doSubmit(finalResponses) {
    setSubmitting(true)
    setSubmitError(null)
    try {
      const data = await submitAssessment(finalResponses)
      // Completed run: drop the draft so a NEW assessment starts at question 1
      // instead of resuming the one that was just submitted.
      clearAssessmentDraft(userId)
      setResult(data)
      setShowResult(true)
    } catch (err) {
      setSubmitError(err.message || '제출에 실패했어요. 다시 시도해주세요.')
      // The last card already left the screen — remount it so retrying has
      // something to answer.
      setRetryKey(k => k + 1)
    } finally {
      setSubmitting(false)
    }
  }

  function handleRetry() {
    if (submitting) return
    doSubmit(responses)
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
      <div className={styles.progressTrack} role="progressbar" aria-valuenow={answered} aria-valuemin={0} aria-valuemax={TOTAL}>
        <div className={styles.progressFill} style={{ width: `${progress}%` }} />
      </div>

      <div className={styles.body}>
        {/* Resumed run — tells the user why they are not on question 1. */}
        {resumed && (
          <p className={styles.resumeNote} role="status">
            이전에 진행하던 곳부터 이어서 진행합니다
          </p>
        )}

        {/* Same deck the Discovery/Taste tabs use: SwipeDeck draws the static
            under-card ladder + ground shadow at SwipeCard's CARD_WIDTH /
            CARD_HEIGHT, and each card sits in a SwipeGestureFrame (the shared
            TinderCard wrapper). Dragging is disabled via SWIPE_PREVENT_ALL —
            answers come from tapping an option — but the imperative
            cardRef.swipe() exit still runs the identical animateOut. */}
        <SwipeDeck active>
          {[deck[1], deck[0]].filter(Boolean).map(q => {
            const isTop = q === deck[0]
            const cls = [
              isTop && exiting ? styles.exitingCard : '',
              isTop && entering ? styles.enteringCard : '',
            ].filter(Boolean).join(' ')
            return (
              <AnimatedDiv
                key={`${q.id}-${retryKey}`}
                className={cls || undefined}
                style={{
                  position: 'absolute', inset: 0,
                  zIndex: isTop ? 5 : 4,
                  pointerEvents: isTop && !busy ? 'auto' : 'none',
                  // Only the top card carries the back-entry spring; the under
                  // card must stay put in the ladder.
                  x: isTop ? backX : 0,
                }}
                aria-hidden={!isTop}
              >
                <SwipeGestureFrame
                  ref={isTop ? cardRef : null}
                  preventSwipe={SWIPE_PREVENT_ALL}
                >
                  <AssessmentCard
                    question={q}
                    selected={isTop ? responses[currentQ] : responses[currentQ + 1]}
                    disabled={!isTop || busy || submitting}
                    onAnswer={handleAnswer}
                  />
                </SwipeGestureFrame>
              </AnimatedDiv>
            )
          })}
        </SwipeDeck>

        {/* Previous question. Hidden on the first card so the control never
            appears dead. The header's back arrow still leaves the page. */}
        {currentQ > 0 && (
          <button
            type="button"
            className={styles.prevBtn}
            onClick={handleBack}
            disabled={busy || submitting}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            이전 문항
          </button>
        )}

        {submitting && (
          <p className={styles.submittingText} role="status">제출 중...</p>
        )}

        {submitError && (
          <div className={styles.errorBlock}>
            <p className={styles.errorText} role="alert">{submitError}</p>
            <button
              type="button"
              className={styles.submitBtn}
              onClick={handleRetry}
              disabled={submitting}
            >
              다시 제출
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
