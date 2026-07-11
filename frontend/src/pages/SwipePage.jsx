import { useRef, useState, useEffect } from 'react'
import TutorialPopup from '../components/TutorialPopup.jsx'
import SwipeCard, { CARD_WIDTH, CARD_HEIGHT } from '../components/SwipeCard.jsx'
import QuestionCard from '../components/QuestionCard.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'
import CardSkeleton from '../components/CardSkeleton.jsx'
import { isActionCard } from '../utils/appHelpers.js'
import { useSwipeOrchestration } from '../hooks/useSwipeOrchestration.js'
import { useKeyboardSwipe } from '../hooks/useKeyboardSwipe.js'

/* ── ActionCard ──────────────────────────────────────────────────────────── */
// Rendered when card_type === 'action' (backend-emitted when session converges).
// The user opts in to the report by right-swiping (like), or keeps exploring
// by left-swiping (pass). The hint text at the bottom makes this explicit.
function ActionCard({ card }) {
  const message  = card.action_card_message  || '취향이 충분히 모였어요!'
  const subtitle = card.action_card_subtitle || '지금 결과를 확인하거나 계속 탐색할 수 있어요'
  return (
    <div style={{
      position: 'absolute', top: 0, left: 0,
      width: CARD_WIDTH, height: CARD_HEIGHT,
      borderRadius: 20, overflow: 'hidden',
      background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 45%, #4c1d95 100%)',
      boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      gap: 16, padding: '32px 28px',
      userSelect: 'none',
    }}>
      {/* Decorative sparkle */}
      <div style={{ fontSize: 56, lineHeight: 1 }}>✨</div>

      {/* Main message */}
      <h2 style={{
        color: '#fff', fontSize: 22, fontWeight: 700,
        textAlign: 'center', margin: 0, lineHeight: 1.35,
      }}>
        {message}
      </h2>

      {/* Subtitle */}
      {subtitle && (
        <p style={{
          color: 'rgba(255,255,255,0.7)', fontSize: 14, fontWeight: 400,
          textAlign: 'center', margin: 0, lineHeight: 1.5,
        }}>
          {subtitle}
        </p>
      )}

      {/* Swipe hint — bottom of card */}
      <div style={{
        position: 'absolute', bottom: 28, left: 0, right: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        color: 'rgba(255,255,255,0.45)', fontSize: 12, letterSpacing: '0.03em',
      }}>
        <span>← 계속 탐색</span>
        <span style={{ color: 'rgba(255,255,255,0.25)' }}>·</span>
        <span>결과 보기 →</span>
      </div>
    </div>
  )
}

/* ── ConfidenceBar (persona-report readiness / response consistency) ─────── */
function ConfidenceBar({ value, phase, progress }) {
  // value: confidence [0,1] = 1 - avg(recent ΔV)/threshold — rises on consistency,
  //        falls on inconsistency (persona-report readiness metric).
  //        null = early exploring, not enough data yet.
  // progress: full progress object for swipe count display.
  let pct = 0
  let stageLabel = 'Loading…'

  if (phase === 'converged' || phase === 'completed') {
    pct = 100
    stageLabel = 'Taste found'
  } else if (phase === 'analyzing') {
    if (value != null) {
      // Bar driven purely by confidence (can rise or fall).
      pct = Math.round(value * 100)
      stageLabel = 'Tuning taste'
    } else {
      // Confidence not yet established — show faint baseline so bar isn't empty.
      pct = 4
      stageLabel = 'Calibrating…'
    }
  } else if (phase === 'exploring') {
    if (value != null) {
      pct = Math.round(value * 100)
    } else {
      pct = 4
    }
    stageLabel = 'Exploring'
  } else if (value != null) {
    // Unknown/other phase but confidence is available.
    pct = Math.round(value * 100)
    stageLabel = 'Tuning taste'
  } else {
    // No phase and no confidence — show minimal baseline.
    pct = 4
    stageLabel = 'Calibrating…'
  }

  // Swipe count label: plain count, no /target denominator.
  let swipeCountLabel = ''
  if (progress?.swipe_count != null) {
    swipeCountLabel = `${progress.swipe_count} swipes`
  } else if (progress?.like_count != null && progress?.dislike_count != null) {
    swipeCountLabel = `${progress.like_count + progress.dislike_count} swipes`
  } else if (progress?.like_count != null) {
    swipeCountLabel = `${progress.like_count} ♥`
  }

  return (
    <div style={{ width: '100%' }}>
      {/* Two-column info row above the bar */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        marginBottom: 5,
      }}>
        <span style={{
          fontSize: 13, fontWeight: 600, color: 'var(--color-text)',
          lineHeight: 1.2,
        }}>
          {stageLabel}
        </span>
        {swipeCountLabel ? (
          <span style={{
            fontSize: 12, fontWeight: 500, color: 'var(--color-text-dim)',
          }}>
            {swipeCountLabel}
          </span>
        ) : null}
      </div>

      {/* Bar */}
      <div style={{
        height: 4, borderRadius: 999,
        background: 'var(--color-progress-track)',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: '#ec4899',
          borderRadius: 999,
          transition: 'width 300ms ease',
        }} />
      </div>

      {/* Percent below bar, right-aligned */}
      <div style={{
        fontSize: 11,
        color: 'var(--color-text-dim)',
        textAlign: 'right',
        marginTop: 4,
      }}>
        {pct}%
      </div>
    </div>
  )
}

/* ── ExitConfirmPopup ────────────────────────────────────────────────────── */
function ExitConfirmPopup({ onNewProject, onHome, onCancel }) {
  const primaryBtnRef = useRef(null)

  // Auto-focus primary button on mount
  useEffect(() => { primaryBtnRef.current?.focus() }, [])

  // Dismiss on Escape
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(10,10,12,0.65)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        zIndex: 10001,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '0 24px',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="exit-confirm-title"
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          borderRadius: 20,
          padding: '28px 24px 24px',
          width: '100%',
          maxWidth: 360,
          display: 'flex', flexDirection: 'column', gap: 8,
          boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
        }}
      >
        <h2 id="exit-confirm-title" style={{
          color: 'var(--color-text)', fontSize: 17, fontWeight: 700,
          margin: '0 0 4px', textAlign: 'center',
        }}>
          현재 세션을 종료할까요?
        </h2>
        <p style={{
          color: 'var(--color-text-dim)', fontSize: 13, fontWeight: 500,
          textAlign: 'center', margin: '0 0 12px', lineHeight: 1.5,
        }}>
          지금까지의 좋아요는 저장돼요. 새 프로젝트를 시작하거나 홈으로 돌아갈 수 있어요.
        </p>
        <button
          ref={primaryBtnRef}
          onClick={onNewProject}
          style={{
            padding: '13px 24px', borderRadius: 12,
            background: '#ec4899', color: '#fff',
            fontSize: 14, fontWeight: 600, border: 'none',
            cursor: 'pointer', fontFamily: 'inherit', minHeight: 44,
          }}
        >
          새 프로젝트 시작
        </button>
        <button
          onClick={onHome}
          style={{
            padding: '13px 24px', borderRadius: 12,
            background: 'var(--color-surface-2)', color: 'var(--color-text)',
            fontSize: 14, fontWeight: 600,
            border: '1px solid var(--color-border)',
            cursor: 'pointer', fontFamily: 'inherit', minHeight: 44,
          }}
        >
          홈으로
        </button>
        <button
          onClick={onCancel}
          style={{
            padding: '10px 24px', borderRadius: 12,
            background: 'transparent', color: 'var(--color-text-dim)',
            fontSize: 13, fontWeight: 500, border: 'none',
            cursor: 'pointer', fontFamily: 'inherit', minHeight: 40,
          }}
        >
          취소
        </button>
      </div>
    </div>
  )
}

/* ── DismissConfirmPopup ─────────────────────────────────────────────────── */
function DismissConfirmPopup({ onConfirm, onCancel }) {
  const primaryBtnRef = useRef(null)

  // Auto-focus primary button on mount
  useEffect(() => { primaryBtnRef.current?.focus() }, [])

  // Dismiss on Escape
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(10,10,12,0.65)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        zIndex: 10001,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '0 24px',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dismiss-confirm-title"
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          borderRadius: 20,
          padding: '28px 24px 24px',
          width: '100%',
          maxWidth: 360,
          display: 'flex', flexDirection: 'column', gap: 8,
          boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
        }}
      >
        <h2 id="dismiss-confirm-title" style={{
          color: 'var(--color-text)', fontSize: 17, fontWeight: 700,
          margin: '0 0 4px', textAlign: 'center',
        }}>
          이 건물을 보지 않을까요?
        </h2>
        <p style={{
          color: 'var(--color-text-dim)', fontSize: 13, fontWeight: 500,
          textAlign: 'center', margin: '0 0 12px', lineHeight: 1.5,
        }}>
          왼쪽 스와이프 = 다시 추천 안 됨. 한 번 더 확인할게요.
        </p>
        <button
          ref={primaryBtnRef}
          onClick={onConfirm}
          style={{
            padding: '13px 24px', borderRadius: 12,
            background: 'var(--color-surface-2)', color: 'var(--color-text)',
            fontSize: 14, fontWeight: 600,
            border: '1px solid var(--color-border)',
            cursor: 'pointer', fontFamily: 'inherit', minHeight: 44,
          }}
        >
          건너뛰기
        </button>
        <button
          onClick={onCancel}
          style={{
            padding: '10px 24px', borderRadius: 12,
            background: 'transparent', color: 'var(--color-text-dim)',
            fontSize: 13, fontWeight: 500, border: 'none',
            cursor: 'pointer', fontFamily: 'inherit', minHeight: 40,
          }}
        >
          취소
        </button>
      </div>
    </div>
  )
}

/* ── SwipePage ───────────────────────────────────────────────────────────── */
export default function SwipePage({
  currentCard, cardResetToken = 0, progress, isCompleted, isLoading, isResultLoading = false, swipePending = 0,
  keepExploringChosen = false,
  projectName, onSwipe, onViewResults, onExtendSession, // eslint-disable-line no-unused-vars
  onExitToNewProject, onExitToHome,
  questionTrigger = null,
  onQuestionAnswer,
}) {
  const cardRef = useRef(null)
  const questionCardRef = useRef(null)
  const swipedCardId = useRef(null)
  const hasShownDismissTutorial = useRef(!!localStorage.getItem('archithon_dismiss_tutorial_seen'))
  const pendingDismissDir = useRef(null)
  const [localResetTick, setLocalResetTick] = useState(0)
  const [showTutorial, setShowTutorial] = useState(() => !localStorage.getItem('archithon_tutorial_dismissed'))
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [showDismissConfirm, setShowDismissConfirm] = useState(false)

  const phase            = progress?.phase
  const filter_relaxed   = progress?.filter_relaxed || false
  const confidence       = progress?.confidence ?? null
  // isAt100: show the top "Finish & View Report" button once the user has
  // PASSED the action card (keepExploringChosen) or the pool is exhausted
  // (isCompleted). Order on a fresh session: converge → action card →
  // left-swipe sets keepExploringChosen → button appears. On resume,
  // keepExploringChosen is restored from backend action_card_shown
  // (App.jsx applySessionResponse) so the button shows immediately.
  const isAt100 = keepExploringChosen || isCompleted

  const { pendingActionRef: pendingAction, onTinderSwipe, onCardLeftScreen } = useSwipeOrchestration({
    likeAction: 'like',
    dismissAction: 'dislike',
    onBeforeSwipe: (dir) => {
      // F4: intercept first-ever left swipe to show dismiss tutorial.
      // Skip for action cards — left-swipe on an action card means "keep exploring",
      // not "skip this building", so the dismiss tutorial is not applicable.
      if (dir === 'left' && !hasShownDismissTutorial.current && !isActionCard(currentCard)) {
        // Restore card to center BEFORE showing popup so cancel path has no flicker
        cardRef.current?.restoreCard()
        pendingDismissDir.current = dir
        swipedCardId.current = null
        setShowDismissConfirm(true)
        return true  // intercepted
      }
      swipedCardId.current = currentCard?.image_id
      return false
    },
    onCommit: (action) => onSwipe(action),
  })

  useKeyboardSwipe({
    onSwipe: (dir) => {
      if (dir === 'left' && !hasShownDismissTutorial.current && !isActionCard(currentCard)) {
        pendingDismissDir.current = dir
        setShowDismissConfirm(true)
        return
      }
      swipedCardId.current = currentCard?.image_id
      pendingAction.current = dir === 'right' ? 'like' : 'dislike'
      cardRef.current?.swipe(dir)
    },
    guardCondition: () =>
      !!(questionTrigger || isLoading || !currentCard || showTutorial || showExitConfirm ||
         showDismissConfirm || pendingAction.current || swipedCardId.current === currentCard?.image_id),
  })

  function handleDismissConfirm() {
    hasShownDismissTutorial.current = true
    localStorage.setItem('archithon_dismiss_tutorial_seen', '1')
    setShowDismissConfirm(false)
    const dir = pendingDismissDir.current
    pendingDismissDir.current = null
    if (dir && cardRef.current) {
      pendingAction.current = 'dislike'
      swipedCardId.current = currentCard?.image_id
      cardRef.current.swipe('left')
    }
  }

  function handleDismissCancel() {
    pendingDismissDir.current = null
    pendingAction.current = null
    swipedCardId.current = null
    setShowDismissConfirm(false)
    // Force TinderCard remount to restore card to center
    setLocalResetTick(t => t + 1)
  }

  // When cardResetToken changes the TinderCard was force-remounted after a
  // locked swipe. Clear the guard refs so the same card can be swiped again.
  useEffect(() => {
    swipedCardId.current = null
    pendingAction.current = null
  }, [cardResetToken]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!isLoading && !currentCard) {
    // Pool exhausted (or is_analysis_completed with no next card).
    // Top "Finish & View Report" button (isAt100) is always visible here.
    // Show a brief inline prompt; no full-screen takeover.
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        overflow: 'hidden',
        background: 'var(--color-bg)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '20px 16px',
        position: 'relative',
      }}>
        {/* Exit button */}
        <button
          onClick={() => setShowExitConfirm(true)}
          aria-label="Exit session"
          style={{
            position: 'absolute', top: 12, left: 16,
            width: 32, height: 32, borderRadius: '50%',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--color-text-dim)', cursor: 'pointer',
            zIndex: 10,
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 1 0 .49-4.95" />
          </svg>
        </button>

        {/* Header / confidence bar */}
        <div style={{ textAlign: 'center', width: '100%' }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 14px', letterSpacing: '-0.01em' }}>
            {projectName
              ? <span style={{ color: 'var(--color-text)' }}>{projectName}</span>
              : <span style={{ color: 'var(--color-text)', letterSpacing: '0.2em' }}>ARCHIBE</span>}
          </h1>
          <div style={{ maxWidth: CARD_WIDTH, margin: '0 auto' }}>
            <ConfidenceBar value={confidence} phase={phase} progress={progress} />
          </div>
        </div>

        {/* Finish button + empty-deck notice */}
        <div style={{
          flex: 1,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 16, width: '100%',
        }}>
          <div style={{ width: CARD_WIDTH, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <button
              onClick={onViewResults}
              disabled={isResultLoading || swipePending > 0}
              style={{
                width: '100%',
                padding: '13px 20px',
                borderRadius: 14,
                background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                color: '#fff',
                fontSize: 14,
                fontWeight: 700,
                border: 'none',
                cursor: (isResultLoading || swipePending > 0) ? 'default' : 'pointer',
                fontFamily: 'inherit',
                boxShadow: '0 4px 16px rgba(236,72,153,0.35)',
                opacity: (isResultLoading || swipePending > 0) ? 0.6 : 1,
                transition: 'opacity 0.2s',
                minHeight: 44,
              }}
            >
              {isResultLoading ? 'Preparing report...' : 'Finish & View Report →'}
            </button>
            <p style={{
              color: 'var(--color-text-dim)',
              fontSize: 13,
              textAlign: 'center',
              margin: 0,
              lineHeight: 1.5,
            }}>
              더 볼 카드가 없어요 · 위에서 결과를 확인하세요
            </p>
          </div>
        </div>

        {showExitConfirm && (
          <ExitConfirmPopup
            onNewProject={() => { setShowExitConfirm(false); onExitToNewProject?.() }}
            onHome={() => { setShowExitConfirm(false); onExitToHome?.() }}
            onCancel={() => setShowExitConfirm(false)}
          />
        )}
      </div>
    )
  }

  return (
    <>
      <TutorialPopup visible={showTutorial} onClose={() => setShowTutorial(false)} />

      {showExitConfirm && (
        <ExitConfirmPopup
          onNewProject={() => { setShowExitConfirm(false); onExitToNewProject?.() }}
          onHome={() => { setShowExitConfirm(false); onExitToHome?.() }}
          onCancel={() => setShowExitConfirm(false)}
        />
      )}

      {showDismissConfirm && (
        <DismissConfirmPopup
          onConfirm={handleDismissConfirm}
          onCancel={handleDismissCancel}
        />
      )}

      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'flex-start', height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflow: 'hidden',
        background: 'var(--color-bg)', padding: '20px 16px',
        position: 'relative',
      }}>

        {/* F3 — Exit button, top-left floating (moved from right to avoid Logout button occlusion) */}
        <button
          onClick={() => setShowExitConfirm(true)}
          aria-label="Exit session"
          style={{
            position: 'absolute', top: 12, left: 16,
            width: 32, height: 32, borderRadius: '50%',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--color-text-dim)', cursor: 'pointer',
            zIndex: 10,
          }}
        >
          {/* Restart / new-session icon */}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 1 0 .49-4.95" />
          </svg>
        </button>

        {/* Header */}
        <div style={{ textAlign: 'center', width: '100%' }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 14px', letterSpacing: '-0.01em' }}>
            {projectName
              ? <span style={{ color: 'var(--color-text)' }}>{projectName}</span>
              : <span style={{ color: 'var(--color-text)', letterSpacing: '0.2em' }}>ARCHIBE</span>}
          </h1>
          <div style={{ maxWidth: CARD_WIDTH, margin: '0 auto' }}>
            <ConfidenceBar value={confidence} phase={phase} progress={progress} />
            {filter_relaxed && (
              <p style={{ color: 'var(--color-text-dimmer)', fontSize: 11, marginTop: 6, textAlign: 'center' }}>
                Filters were relaxed to find more buildings
              </p>
            )}
          </div>
        </div>

        {/* Card + finish button — vertically centered in remaining space */}
        <div style={{
          flex: 1,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 12, width: '100%',
        }}>

        {isAt100 && (
          <div style={{ width: CARD_WIDTH }}>
            <button
              onClick={onViewResults}
              disabled={isResultLoading || swipePending > 0}
              style={{
                width: '100%',
                padding: '12px 20px',
                borderRadius: 14,
                background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
                color: '#fff',
                fontSize: 14,
                fontWeight: 700,
                border: 'none',
                cursor: (isResultLoading || swipePending > 0) ? 'default' : 'pointer',
                fontFamily: 'inherit',
                boxShadow: '0 4px 16px rgba(236,72,153,0.35)',
                opacity: (isResultLoading || swipePending > 0) ? 0.6 : 1,
                transition: 'opacity 0.2s',
              }}
            >
              {isResultLoading ? 'Preparing report...' : 'Finish & View Report →'}
            </button>
          </div>
        )}

        {/* Card */}
        <div style={{ width: CARD_WIDTH, height: CARD_HEIGHT, position: 'relative' }}>
          {currentCard ? (
            questionTrigger ? (
              /* Wrap QuestionCard in SwipeGestureFrame so right swipe = 'A' (Yes)
                 and left swipe = 'B' (No). Buttons remain as accessible fallback. */
              <SwipeGestureFrame
                ref={questionCardRef}
                key={`question_${questionTrigger.axis ?? ''}_${questionTrigger.type}`}
                onSwipe={(dir) => {
                  if (dir === 'right') onQuestionAnswer('A')
                  else if (dir === 'left') onQuestionAnswer('B')
                }}
                onCardLeftScreen={() => {}}
              >
                <QuestionCard
                  trigger={questionTrigger}
                  onAnswer={onQuestionAnswer}
                />
              </SwipeGestureFrame>
            ) : (
              <>
                <SwipeGestureFrame
                  ref={cardRef}
                  key={`${currentCard.image_id}_${cardResetToken}_${localResetTick}`}
                  onSwipe={onTinderSwipe}
                  onCardLeftScreen={onCardLeftScreen}
                >
                  {isActionCard(currentCard) ? (
                    <ActionCard card={currentCard} />
                  ) : (
                    <SwipeCard
                      card={currentCard}
                      onGalleryClose={() => {}}
                    />
                  )}
                </SwipeGestureFrame>
                {isLoading && (
                  <div style={{
                    position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    borderRadius: 20, background: 'rgba(0,0,0,0.15)', pointerEvents: 'none',
                  }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: '50%',
                      border: '3px solid rgba(255,255,255,0.2)',
                      borderTopColor: '#fff',
                      animation: 'spin 0.8s linear infinite',
                    }} />
                  </div>
                )}
              </>
            )
          ) : isLoading ? (
            <CardSkeleton />
          ) : null}
        </div>

        </div>{/* end center wrapper */}

        {/* Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, flexShrink: 0 }}>
          <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, margin: 0 }}>← skip · tap card · save →</p>
        </div>

      </div>
    </>
  )
}
