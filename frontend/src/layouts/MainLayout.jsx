import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import TabBar from '../components/TabBar.jsx'
import ThemeToggle from '../components/ThemeToggle.jsx'
import DebugOverlay from '../components/DebugOverlay.jsx'
import SwipePage from '../pages/SwipePage.jsx'
import FavoritesPage from '../pages/FavoritesPage.jsx'

export default function MainLayout({
  theme, onToggleTheme, userId, onLogout,
  projects, activeProject, activeProjectId,
  currentCard, sessionProgress, isSessionCompleted, isSwipeLoading, isResultLoading,
  onSwipe, onViewResults, onResumeProject, onDeleteProject, onGenerateReport, onImageGenerated,
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const pathname = location.pathname

  const isHome = pathname === '/' || pathname === '/new' || pathname.startsWith('/search')
  const isSwipe = pathname === '/swipe'
  const isLibrary = pathname.startsWith('/library')

  const libraryMatch = pathname.match(/^\/library\/(.+)$/)
  const folderId = libraryMatch ? libraryMatch[1] : null

  return (
    <div style={{ height: '100vh', overflow: 'hidden' }}>

      {/* Header controls */}
      <div style={{ position: 'fixed', top: 14, right: 16, zIndex: 200, display: 'flex', gap: 6, alignItems: 'center' }}>
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        <button
          onClick={onLogout}
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

      {/* Home sub-routes — only visible when on home paths */}
      <div style={{ display: isHome ? 'block' : 'none' }}>
        <Outlet />
      </div>

      {/* SwipePage — always mounted, shown/hidden via display */}
      <div style={{ display: isSwipe && activeProject ? 'block' : 'none' }}>
        <SwipePage
          key={activeProjectId}
          currentCard={currentCard}
          progress={sessionProgress}
          isCompleted={isSessionCompleted}
          isLoading={isSwipeLoading}
          isResultLoading={isResultLoading}
          projectName={activeProject?.projectName}
          onSwipe={onSwipe}
          onViewResults={onViewResults}
        />
      </div>

      {/* FavoritesPage — always mounted, shown/hidden via display */}
      <div style={{ display: isLibrary ? 'block' : 'none' }}>
        <FavoritesPage
          projects={projects}
          onDeleteProject={onDeleteProject}
          onResumeProject={onResumeProject}
          onGenerateReport={onGenerateReport}
          onImageGenerated={onImageGenerated}
          openId={folderId}
          onOpenIdChange={(id) => {
            if (id) navigate('/library/' + id)
            else navigate('/library')
          }}
        />
      </div>

      {/* No active project on swipe tab */}
      {isSwipe && !activeProject && (
        <div style={{
          height: 'calc(100vh - 64px)', background: 'var(--color-bg)', display: 'flex',
          flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 12, padding: 24,
        }}>
          <div style={{ fontSize: 48 }}>🃏</div>
          <p style={{ fontSize: 16, fontWeight: 900, margin: 0 }}>
            <span style={{ color: 'var(--color-text)' }}>Archi</span>
            <span style={{ color: '#ec4899' }}>Tinder</span>
          </p>
          <p style={{ color: 'var(--color-text-dimmer)', fontSize: 13 }}>Create a new session from the Home tab</p>
          <button
            onClick={() => navigate('/')}
            style={{
              marginTop: 8, padding: '12px 28px', borderRadius: 12,
              background: 'linear-gradient(135deg,#ec4899,#f43f5e)',
              color: '#fff', fontSize: 14, fontWeight: 600,
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            Go to Home
          </button>
        </div>
      )}

      {typeof window !== 'undefined' && (window.__debugMode || localStorage.getItem('__debugMode') === 'true') && (
        <DebugOverlay
          userId={userId}
          session={sessionProgress ? {
            id: activeProject?.sessionId || null,
            round: sessionProgress.current,
            total: sessionProgress.total,
          } : null}
        />
      )}

      <TabBar swipeEnabled={!!activeProject} />
    </div>
  )
}
