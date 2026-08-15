import { useRef, useState, useEffect } from 'react'
import SwipeCard, { CARD_WIDTH, CARD_HEIGHT } from '../components/SwipeCard.jsx'
import QuestionCard from '../components/QuestionCard.jsx'
import SwipeGestureFrame from '../components/SwipeGestureFrame.jsx'
import CardSkeleton from '../components/CardSkeleton.jsx'
import SwipeDeck from '../components/SwipeDeck.jsx'
import deckStyles from '../components/SwipeDeck.module.css'
import { isActionCard } from '../utils/appHelpers.js'
import { useSwipeOrchestration } from '../hooks/useSwipeOrchestration.js'
import { useKeyboardSwipe } from '../hooks/useKeyboardSwipe.js'
import { useTranslation } from '../i18n/index.js'
import {
  INK,
  MONO,
  LS_CAPS,
  paperFaceStyle,
  wordmarkStyle,
  monoLabelStyle,
  cardMetaStyle,
} from '../components/cardLanguage.js'

/* ── ActionCard ──────────────────────────────────────────────────────────── */
// Rendered when card_type === 'action' (backend-emitted when session converges).
// The user opts in to the report by right-swiping (like), or keeps exploring
// by left-swiping (pass). The hint text at the bottom makes this explicit.
// FRONT-FLOW-2: retheme from the indigo-purple gradient card to the paper
// business-card language (components/cardLanguage.js), mirroring
// DiscoveryTriggerCard.jsx's composition (wordmark row + mono stamp, ink
// title, meta body, mono hint row). Swipe semantics/props unchanged.
function ActionCard({ card }) {
  const { t } = useTranslation()
  const message  = card.action_card_message  || t('swipe.actionCard.message')
  const subtitle = card.action_card_subtitle || t('swipe.actionCard.subtitle')
  return (
    <div style={{
      ...paperFaceStyle({ radius: 20, padding: '24px 22px' }),
      position: 'absolute', top: 0, left: 0,
      width: CARD_WIDTH, height: CARD_HEIGHT,
      justifyContent: 'space-between',
      userSelect: 'none',
      boxSizing: 'border-box',
    }}>
      {/* Top: wordmark row + mono stamp */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={wordmarkStyle}>ARCHIBE</span>
        <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: LS_CAPS, color: INK.mid }}>
          {t('swipe.actionCard.stamp')}
        </span>
      </div>

      {/* Middle: title + body */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, textAlign: 'center' }}>
        <h2 style={{
          fontFamily: 'var(--font-family)',
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: '-0.01em',
          color: INK.strong,
          lineHeight: 1.35,
          margin: 0,
        }}>
          {message}
        </h2>

        {subtitle && (
          <p style={{ ...cardMetaStyle, textAlign: 'center' }}>
            {subtitle}
          </p>
        )}
      </div>

      {/* Bottom hint */}
      <p style={{ ...monoLabelStyle, textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
        <span>{t('swipe.actionCard.continueHint')}</span>
        <span style={{ color: INK.dim }}>·</span>
        <span>{t('swipe.actionCard.viewResultsHint')}</span>
      </p>
    </div>
  )
}

/* ── ConfidenceBar (swipe progress toward Aha! moment) ──────────────────── */
const TARGET_SWIPES = 15 // Product promise: 10-15 swipes → Aha!

function ConfidenceBar({ phase, progress }) {
  // `value` (confidence [0,1]) is intentionally omitted from destructuring —
  // the bar is now driven purely by swipe count, not confidence.
  // The prop remains valid on the call site; callers need no changes.
  // progress: full progress object for swipe count display.

  const swipeCount =
    progress?.swipe_count ??
    ((progress?.like_count ?? 0) + (progress?.dislike_count ?? 0))

  let pct
  let stageLabel

  if (phase === 'converged' || phase === 'completed') {
    pct = 100
    stageLabel = 'Taste found'
  } else if (phase === 'analyzing') {
    pct = Math.min(Math.round((swipeCount / TARGET_SWIPES) * 100), 95)
    stageLabel = 'Tuning taste'
  } else if (phase === 'exploring') {
    pct = Math.min(Math.round((swipeCount / TARGET_SWIPES) * 100), 95)
    stageLabel = 'Exploring'
  } else {
    // Unknown / loading phase — fall back to swipe-count progress.
    pct = Math.min(Math.round((swipeCount / TARGET_SWIPES) * 100), 95)
    stageLabel = 'Calibrating…'
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
        <span style={{
          fontSize: 12, fontWeight: 500, color: 'var(--color-text-dim)',
        }}>
          {pct}%
        </span>
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
          background: 'var(--accent-1)',
          borderRadius: 999,
          transition: 'width 300ms ease',
        }} />
      </div>
    </div>
  )
}

/* ── ExitConfirmPopup ────────────────────────────────────────────────────── */
function ExitConfirmPopup({ onNewProject, onHome, onCancel }) {
  const primaryBtnRef = useRef(null)
  const { t } = useTranslation()

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
          {t('swipe.exitConfirm.title')}
        </h2>
        <p style={{
          color: 'var(--color-text-dim)', fontSize: 13, fontWeight: 500,
          textAlign: 'center', margin: '0 0 12px', lineHeight: 1.5,
        }}>
          {t('swipe.exitConfirm.body')}
        </p>
        <button
          ref={primaryBtnRef}
          onClick={onNewProject}
          style={{
            padding: '13px 24px', borderRadius: 12,
            background: 'var(--accent-1)', color: '#fff',
            fontSize: 14, fontWeight: 600, border: 'none',
            cursor: 'pointer', fontFamily: 'inherit', minHeight: 44,
          }}
        >
          {t('swipe.exitConfirm.newProject')}
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
          {t('swipe.exitConfirm.home')}
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
          {t('swipe.exitConfirm.cancel')}
        </button>
      </div>
    </div>
  )
}

/* ── DismissConfirmPopup ─────────────────────────────────────────────────── */
function DismissConfirmPopup({ onConfirm, onCancel }) {
  const primaryBtnRef = useRef(null)
  const { t } = useTranslation()

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
        background: 'rgba(0,0,0,0.4)',
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
          borderRadius: 'var(--radius-lg)',
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
          {t('swipe.dismissConfirm.title')}
        </h2>
        <p style={{
          color: 'var(--color-text-dim)', fontSize: 13, fontWeight: 500,
          textAlign: 'center', margin: '0 0 12px', lineHeight: 1.5,
        }}>
          {t('swipe.dismissConfirm.body')}
        </p>
        <button
          ref={primaryBtnRef}
          onClick={onConfirm}
          style={{
            padding: '13px 24px', borderRadius: 'var(--radius-md)',
            background: 'var(--color-surface-2)', color: 'var(--color-text)',
            fontSize: 14, fontWeight: 600,
            border: '1px solid var(--color-border)',
            cursor: 'pointer', fontFamily: 'inherit', minHeight: 44,
          }}
        >
          {t('swipe.dismissConfirm.skip')}
        </button>
        <button
          onClick={onCancel}
          style={{
            padding: '10px 24px', borderRadius: 'var(--radius-md)',
            background: 'transparent', color: 'var(--color-text-dim)',
            fontSize: 13, fontWeight: 500, border: 'none',
            cursor: 'pointer', fontFamily: 'inherit', minHeight: 40,
          }}
        >
          {t('swipe.dismissConfirm.cancel')}
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
  nextCard = null,
}) {
  const { t } = useTranslation()
  const cardRef = useRef(null)
  const questionCardRef = useRef(null)
  const swipedCardId = useRef(null)
  const hasShownDismissTutorial = useRef(!!localStorage.getItem('archithon_dismiss_tutorial_seen'))
  const pendingDismissDir = useRef(null)
  const [localResetTick, setLocalResetTick] = useState(0)
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
  // Stranding fix: a dislike-heavy session may never converge (no action card
  // ever shown) and isCompleted never flips — without this clause the user has
  // NO exit to the results page at all. Once swipeCount overshoots the target
  // by 5, surface the button regardless of convergence state (still a button,
  // not auto-navigation — the user must choose to leave).
  const swipeCount = progress?.swipe_count ?? ((progress?.like_count ?? 0) + (progress?.dislike_count ?? 0))
  const targetSwipes = Math.max(1, progress?.target_swipes ?? 10)
  const isAt100 = keepExploringChosen || isCompleted || swipeCount >= targetSwipes + 5

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
      if (!cardRef.current) return
      if (dir === 'left' && !hasShownDismissTutorial.current && !isActionCard(currentCard)) {
        pendingDismissDir.current = dir
        setShowDismissConfirm(true)
        return
      }
      swipedCardId.current = currentCard?.image_id
      pendingAction.current = dir === 'right' ? 'like' : 'dislike'
      cardRef.current.swipe(dir)
    },
    guardCondition: () =>
      !!(questionTrigger || isLoading || !cardRef.current || !currentCard || showExitConfirm ||
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
    setLocalResetTick(n => n + 1)
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
                background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
                color: '#fff',
                fontSize: 14,
                fontWeight: 700,
                border: 'none',
                cursor: (isResultLoading || swipePending > 0) ? 'default' : 'pointer',
                fontFamily: 'inherit',
                boxShadow: '0 4px 16px color-mix(in srgb, var(--accent-1) 35%, transparent)',
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
              {t('swipe.emptyDeck')}
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
                background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
                color: '#fff',
                fontSize: 14,
                fontWeight: 700,
                border: 'none',
                cursor: (isResultLoading || swipePending > 0) ? 'default' : 'pointer',
                fontFamily: 'inherit',
                boxShadow: '0 4px 16px color-mix(in srgb, var(--accent-1) 35%, transparent)',
                opacity: (isResultLoading || swipePending > 0) ? 0.6 : 1,
                transition: 'opacity 0.2s',
              }}
            >
              {isResultLoading ? 'Preparing report...' : 'Finish & View Report →'}
            </button>
          </div>
        )}

        {/* Card */}
        <SwipeDeck
          nextCard={!questionTrigger && currentCard && !isActionCard(currentCard) ? nextCard : null}
          active={!!currentCard}
        >
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
                {/* Wrapper keyed by image_id ONLY (not cardResetToken/localResetTick) —
                    the entrance animation should replay when a NEW card is promoted,
                    not when a dismiss-cancel remounts the SAME card back to center. */}
                <div key={currentCard.image_id} className={deckStyles.promote} style={{ position: 'absolute', inset: 0 }}>
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
                </div>
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
        </SwipeDeck>

        </div>{/* end center wrapper */}

        {/* Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, flexShrink: 0 }}>
          <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, margin: 0 }}>← skip · tap card · save →</p>
        </div>

      </div>
    </>
  )
}
