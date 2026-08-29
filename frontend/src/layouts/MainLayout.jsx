import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import TabBar from '../components/TabBar.jsx'
import DebugOverlay from '../components/DebugOverlay.jsx'
import SwipePage from '../pages/SwipePage.jsx'
import PageTopControls from '../components/PageTopControls.jsx'

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

  // PageTopControls (shared language/theme/logout cluster) is now rendered
  // per-page — see components/PageTopControls.jsx docblock + canvas-design-
  // port.md. MainLayout no longer owns a top-right cluster shown across every
  // route; every page under this layout that needs it renders
  // <PageTopControls onLogout=.../> directly (DiscoveryPage, SwipePage,
  // AssessmentPage, PeopleDiscoveryPage, and the other PageLogoHeader pages
  // that had no colliding top-right chrome). The one exception MainLayout
  // still owns directly is its own inline "no active project" screen below
  // (isSwipe && !activeProject) — that screen has no page component of its
  // own to render the cluster, so MainLayout renders it there.

  return (
    <div style={{ height: '100vh', overflow: 'hidden' }}>

      {/* Home sub-routes — only visible when not on swipe */}
      <div style={{ display: !isSwipe ? 'block' : 'none' }}>
        <Outlet />
      </div>

      {/* SwipePage — always mounted, shown/hidden via display */}
      <div style={{ display: isSwipe && activeProject ? 'block' : 'none' }}>
        <SwipePage
          key={activeProjectId}
          onLogout={onLogout}
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
        <>
          <PageTopControls onLogout={onLogout} />
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
                background: 'var(--accent-1)',
                color: '#fff', fontSize: 14, fontWeight: 600,
                border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              Start Taste Analysis
            </button>
          </div>
        </>
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
