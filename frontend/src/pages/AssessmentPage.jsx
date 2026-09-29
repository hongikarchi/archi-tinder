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
import { TYPE_CODES } from '../constants/personalityTypes.js'
import { useTranslation } from '../i18n/index.js'
import { submitAssessment } from '../api/personality.js'
import PentagonChart from '../components/PentagonChart.jsx'
import AssessmentCard from '../components/AssessmentCard.jsx'
import SwipeDeck from '../components/SwipeDeck.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'
import { SWIPE_PREVENT_ALL } from '../components/swipeGestureConfig.js'
import PageTopControls from '../components/PageTopControls.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
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

export default function AssessmentPage({ onLogout }) {
  const navigate = useNavigate()
  const { t } = useTranslation()

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
  // busy — any card transition is running; blocks every input.
  const [busy, setBusy] = useState(false)
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

    setResumed(false)

    const question = QUESTIONS[currentQ]
    const stored = question.reversed ? rawValue * -1 : rawValue
    const updated = [...responses]
    updated[currentQ] = stored
    setResponses(updated)

    // Same exit as a Discovery/Taste swipe: the vendored tinderCard fork's
    // animateOut (easeInOutCubic, duration clamped to 480-680ms, travel =
    // viewport diagonal, rotation = x * 45deg). Always runs — reduced-motion
    // does not gate interaction motion (standing project rule).
    await cardRef.current?.swipe(EXIT_DIRECTION)

    if (isLast) {
      await doSubmit(updated)
    } else {
      setCurrentQ(q => q + 1)
    }

    busyRef.current = false
    setBusy(false)
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

    const finish = () => {
      busyRef.current = false
      setBusy(false)
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
      setSubmitError(err.message || t('assessmentPage.submitFailed'))
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
        <PageTopControls onLogout={onLogout} />
        <PageBackButton onClick={() => navigate('/user/me')} label={t('assessmentPage.goToProfile')} />
        <PageLogoHeader padding="0 0 6px" marginBottom={8} />

        <div className={styles.resultBody}>
          <p className={styles.typeCode}>{result.type_code}</p>
          <p className={styles.typeLabel}>
            {TYPE_CODES.includes(result.type_code)
              ? t(`personality.types.${result.type_code}`)
              : t('personality.typeFallback')}
          </p>

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
            {t('assessmentPage.viewDiscoveryFeed')}
          </button>

          <button
            type="button"
            className={styles.secondaryBtn}
            onClick={() => navigate('/user/me')}
          >
            {t('assessmentPage.backToProfile')}
          </button>
        </div>
      </div>
    )
  }

  // Assessment screen
  return (
    <div className={styles.page}>
      <PageTopControls onLogout={onLogout} />
      <PageBackButton onClick={() => navigate(-1)} label={t('assessmentPage.goBack')} />

      {/* Header — Arch|ibe logo + "Tuning taste"-style progress row, matching
          SwipePage's top region (PageLogoHeader -> info row -> 4px track). */}
      <div style={{ textAlign: 'center', width: '100%' }}>
        <PageLogoHeader padding="0 0 6px" marginBottom={8} />
        <div style={{ maxWidth: CARD_WIDTH, margin: '0 auto' }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
            marginBottom: 5,
          }}>
            <span style={{
              fontSize: 13, fontWeight: 600, color: 'var(--color-text)',
              lineHeight: 1.2,
            }}>
              {t('assessmentPage.header')}
            </span>
            <span style={{
              fontSize: 12, fontWeight: 500, color: 'var(--color-text-dim)',
            }}>
              {currentQ + 1} / {TOTAL}
            </span>
          </div>

          <div className={styles.progressTrack} role="progressbar" aria-valuenow={answered} aria-valuemin={0} aria-valuemax={TOTAL}>
            <div className={styles.progressFill} style={{ width: `${progress}%` }} />
          </div>

          {/* Resumed run — tells the user why they are not on question 1. */}
          {resumed && (
            <p className={styles.resumeNote} role="status">
              {t('assessmentPage.resumeNote')}
            </p>
          )}
        </div>
      </div>

      <div className={styles.body}>
        {/* Same deck the Discovery/Taste tabs use: SwipeDeck draws the static
            under-card ladder + ground shadow at SwipeCard's CARD_WIDTH /
            CARD_HEIGHT, and each card sits in a SwipeGestureFrame (the shared
            TinderCard wrapper). Dragging is disabled via SWIPE_PREVENT_ALL —
            answers come from tapping an option — but the imperative
            cardRef.swipe() exit still runs the identical animateOut. */}
        <SwipeDeck active>
          {[deck[1], deck[0]].filter(Boolean).map(q => {
            const isTop = q === deck[0]
            return (
              <AnimatedDiv
                key={`${q.id}-${retryKey}`}
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
            {t('assessmentPage.prevQuestion')}
          </button>
        )}

        {submitting && (
          <p className={styles.submittingText} role="status">{t('assessmentPage.submitting')}</p>
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
              {t('assessmentPage.retry')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
