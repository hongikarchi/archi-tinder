import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import TabBar from '../components/TabBar.jsx'
import DebugOverlay from '../components/DebugOverlay.jsx'
import SwipePage from '../pages/SwipePage.jsx'
import { discoveryNavigationGuard } from '../utils/discoveryGuard.js'

export default function MainLayout({
  userId, onLogout,
  activeProject, activeProjectId,
  currentCard, cardResetToken, sessionProgress, isSessionCompleted, isSwipeLoading, isResultLoading, swipePending,
  keepExploringChosen,
  onSwipe, onViewResults, onExtendSession,
  onExitToNewProject, onExitToHome,
  questionTrigger = null,
  onQuestionAnswer,
  nextCard = null,
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const pathname = location.pathname

  const isSwipe = pathname === '/swipe'
  const isProfile = pathname.startsWith('/user')

  return (
    <div style={{ height: '100vh', overflow: 'hidden' }}>

      {/* Header controls — hidden on pages that own their sticky header (profile/office/matched/board) */}
      <div style={{ position: 'fixed', top: 14, right: 16, zIndex: 200, display: (isProfile || pathname.startsWith('/office') || pathname.startsWith('/matched') || pathname.startsWith('/board') || pathname.startsWith('/buildings') || pathname.startsWith('/settings')) ? 'none' : 'flex', gap: 6, alignItems: 'center' }}>
        <button
          onClick={() => {
            if (discoveryNavigationGuard.check) {
              discoveryNavigationGuard.check('logout', onLogout)
            } else {
              onLogout()
            }
          }}
          title="Log out"
          style={{
            width: 34, height: 34, borderRadius: '50%',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border-soft)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--color-text-dim)', cursor: 'pointer',
            transition: 'color 0.2s',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = '#f87171' }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--color-text-dim)' }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>

      {/* Home sub-routes — only visible when not on swipe */}
      <div style={{ display: !isSwipe ? 'block' : 'none' }}>
        <Outlet />
      </div>

      {/* SwipePage — always mounted, shown/hidden via display */}
      <div style={{ display: isSwipe && activeProject ? 'block' : 'none' }}>
        <SwipePage
          key={activeProjectId}
          currentCard={currentCard}
          cardResetToken={cardResetToken}
          progress={sessionProgress}
          isCompleted={isSessionCompleted}
          isLoading={isSwipeLoading}
          isResultLoading={isResultLoading}
          swipePending={swipePending}
          keepExploringChosen={keepExploringChosen}
          projectName={activeProject?.projectName}
          onSwipe={onSwipe}
          onViewResults={onViewResults}
          onExtendSession={onExtendSession}
          onExitToNewProject={onExitToNewProject}
          onExitToHome={onExitToHome}
          questionTrigger={questionTrigger}
          onQuestionAnswer={onQuestionAnswer}
          nextCard={nextCard}
        />
      </div>

      {/* No active project on swipe tab */}
      {isSwipe && !activeProject && (
        <div style={{
          height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', background: 'var(--color-bg)', display: 'flex',
          flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 12, padding: 24,
        }}>
          <div style={{ fontSize: 48 }}>🃏</div>
          <p style={{ fontSize: 16, fontWeight: 700, margin: 0, letterSpacing: '0.2em', color: 'var(--color-text)' }}>ARCHIBE</p>
          <p style={{ color: 'var(--color-text-dimmer)', fontSize: 13 }}>Start a taste analysis to begin swiping</p>
          <button
            onClick={() => navigate('/search')}
            style={{
              marginTop: 8, padding: '12px 28px', borderRadius: 12,
              background: 'linear-gradient(135deg,#ec4899,#f43f5e)',
              color: '#fff', fontSize: 14, fontWeight: 600,
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            Start Taste Analysis
          </button>
        </div>
      )}

      {typeof window !== 'undefined' && (window.__debugMode || localStorage.getItem('__debugMode') === 'true') && (
        <DebugOverlay
          userId={userId}
          session={sessionProgress ? {
            id: activeProject?.sessionId || null,
            round: sessionProgress.current_round,
            total: sessionProgress.total_rounds,
            phase: sessionProgress.phase,
            like_count: sessionProgress.like_count,
            confidence: sessionProgress.confidence,
            can_continue: sessionProgress.can_continue,
          } : null}
        />
      )}

      <TabBar />
    </div>
  )
}
