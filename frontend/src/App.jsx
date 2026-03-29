import { useState, useEffect, useRef, Component } from 'react'
import DebugOverlay from './components/DebugOverlay.jsx'
import SetupPage from './pages/SetupPage.jsx'
import ProjectSetupPage from './pages/ProjectSetupPage.jsx'
import LLMSearchPage from './pages/LLMSearchPage.jsx'
import SwipePage from './pages/SwipePage.jsx'
import FavoritesPage from './pages/FavoritesPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import * as api from './api/client.js'
import { clearSessions } from './api/localSession.js'

function normalizeFilters(filters) {
  if (!filters) return {}
  const out = {}
  // Structured filters from LLM parse-query — pass through
  if (filters.program)           out.program           = filters.program
  if (filters.location_country)  out.location_country  = filters.location_country
  if (filters.material)          out.material          = filters.material
  if (filters.mood)              out.mood              = filters.mood
  if (filters.year_min  != null) out.year_min          = filters.year_min
  if (filters.year_max  != null) out.year_max          = filters.year_max
  // Area — accept all naming conventions (frontend, LLM area_min, backend min_area)
  const minArea = filters.min_area ?? filters.minArea ?? filters.area_min ?? null
  const maxArea = filters.max_area ?? filters.maxArea ?? filters.area_max ?? null
  if (minArea != null) out.min_area = minArea
  if (maxArea != null) out.max_area = maxArea
  return out
}

/* ── Error Boundary ─────────────────────────────────────────────────────── */
class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(e) { return { error: e } }
  render() {
    if (this.state.error) return (
      <div style={{ color: 'var(--color-text)', padding: 24, background: 'var(--color-bg)', minHeight: '100vh' }}>
        <h2>Something went wrong</h2>
        <pre style={{ color: 'tomato', marginTop: 12, whiteSpace: 'pre-wrap', fontSize: 12 }}>
          {this.state.error.toString()}
        </pre>
      </div>
    )
    return this.props.children
  }
}

/* ── Tab Bar ─────────────────────────────────────────────────────────────── */
const TAB_ICONS = {
  home: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <line x1="12" y1="8" x2="12" y2="16" />
      <line x1="8" y1="12" x2="16" y2="12" />
    </svg>
  ),
  swipe: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="6" width="16" height="13" rx="2" />
      <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
    </svg>
  ),
  folders: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
    </svg>
  ),
}

function TabBar({ tab, onSelect, swipeEnabled }) {
  const tabs = [
    { id: 'home',    label: 'New'     },
    { id: 'swipe',   label: 'Swipe'   },
    { id: 'folders', label: 'Library' },
  ]
  return (
    <nav style={{
      position: 'fixed', bottom: 0, left: 0, right: 0,
      display: 'flex', zIndex: 100, height: 64,
      background: 'var(--color-nav-bg)',
      backdropFilter: 'blur(20px)',
      borderTop: '1px solid var(--color-border)',
    }}>
      {tabs.map(t => {
        const active   = tab === t.id
        const disabled = t.id === 'swipe' && !swipeEnabled
        return (
          <button
            key={t.id}
            onClick={() => !disabled && onSelect(t.id)}
            style={{
              flex: 1, border: 'none', background: 'none',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
              cursor: disabled ? 'default' : 'pointer', fontFamily: 'inherit',
              color: disabled ? 'var(--color-nav-disabled)' : active ? '#ec4899' : 'var(--color-nav-inactive)',
              transition: 'color 0.18s',
              paddingBottom: 4,
            }}
          >
            <div style={{
              width: 40, height: 28, borderRadius: 14,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: active ? 'rgba(236,72,153,0.12)' : 'transparent',
              transition: 'background 0.18s',
            }}>
              {TAB_ICONS[t.id]}
            </div>
            <span style={{ fontSize: 10, fontWeight: active ? 600 : 400, letterSpacing: '0.02em' }}>
              {t.label}
            </span>
          </button>
        )
      })}
    </nav>
  )
}

/* ── Theme Toggle Button ─────────────────────────────────────────────────── */
function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === 'dark'
  return (
    <button
      onClick={onToggle}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      style={{
        width: 34, height: 34, borderRadius: '50%',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border-soft)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', cursor: 'pointer',
        transition: 'background 0.2s, color 0.2s',
      }}
      onMouseEnter={e => { e.currentTarget.style.color = 'var(--color-text)' }}
      onMouseLeave={e => { e.currentTarget.style.color = 'var(--color-text-dim)' }}
    >
      {isDark ? (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
      ) : (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  )
}

/* ── App ─────────────────────────────────────────────────────────────────── */
export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('archithon_theme') || 'dark')
  const [userId, setUserId] = useState(() => sessionStorage.getItem('archithon_user') || null)
  const [tab, setTab] = useState(() => sessionStorage.getItem('archithon_tab') || 'home')
  const [setupKey, setSetupKey] = useState(0)
  const [folderOpenId, setFolderOpenId] = useState(() => sessionStorage.getItem('archithon_folderOpenId') || null)
  const [llmContext, setLlmContext] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('archithon_llmContext')) } catch { return null }
  })

  const [currentCard, setCurrentCard] = useState(null)
  const [sessionProgress, setSessionProgress] = useState(null)
  const [isSwipeLoading, setIsSwipeLoading] = useState(false)
  const [isSessionCompleted, setIsSessionCompleted] = useState(false)
  const [activeProjectId, setActiveProjectId] = useState(() => {
    const id = sessionStorage.getItem('archithon_user')
    return localStorage.getItem(`archithon_activeId_${id}`) || null
  })
  const [projects, setProjects] = useState(() => {
    const id = sessionStorage.getItem('archithon_user')
    return JSON.parse(localStorage.getItem(`archithon_projects_${id}`) || '[]')
  })

  // Apply theme to <html> element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('archithon_theme', theme)
  }, [theme])

  // If session has a user but no access token, clear immediately
  useEffect(() => {
    if (userId && !api.getToken()) {
      handleLogout()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Listen for session-expired event dispatched by api/client.js
  useEffect(() => {
    const onExpired = () => handleLogout()
    window.addEventListener('archithon:session-expired', onExpired)
    return () => window.removeEventListener('archithon:session-expired', onExpired)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!userId) return
    localStorage.setItem(`archithon_projects_${userId}`, JSON.stringify(projects))
  }, [projects, userId])

  useEffect(() => {
    if (!userId) return
    if (activeProjectId) localStorage.setItem(`archithon_activeId_${userId}`, activeProjectId)
    else localStorage.removeItem(`archithon_activeId_${userId}`)
  }, [activeProjectId, userId])

  const activeProject = projects.find(p => p.id === activeProjectId) || null

  // Persist nav state so F5 restores the current page
  useEffect(() => { sessionStorage.setItem('archithon_tab', tab) }, [tab])
  useEffect(() => {
    if (llmContext) sessionStorage.setItem('archithon_llmContext', JSON.stringify(llmContext))
    else sessionStorage.removeItem('archithon_llmContext')
  }, [llmContext])
  useEffect(() => {
    if (folderOpenId) sessionStorage.setItem('archithon_folderOpenId', folderOpenId)
    else sessionStorage.removeItem('archithon_folderOpenId')
  }, [folderOpenId])

  // On refresh, re-init swipe session if the user was on the swipe tab
  const swipeRestored = useRef(false)
  const loggingOut = useRef(false)
  useEffect(() => {
    if (swipeRestored.current) return
    if (tab === 'swipe' && activeProjectId && userId) {
      const project = projects.find(p => p.id === activeProjectId)
      if (project) {
        swipeRestored.current = true
        initSession(activeProjectId, project.filters, project.swipedIds, false, 'keep', project.deckImages || null)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function toggleTheme() {
    setTheme(t => t === 'dark' ? 'light' : 'dark')
  }

  function handleSelectTab(newTab) {
    if (newTab === 'home') { setSetupKey(k => k + 1); setLlmContext(null) }
    if (newTab === 'folders') setFolderOpenId(null)
    setTab(newTab)
  }

  async function initSession(projectId, filters, swipedIds, isNew, filterMode = 'keep', preloadedImages = null) {
    setIsSwipeLoading(true)
    setIsSessionCompleted(false)
    const result = await api.startSession({
      user_id: userId,
      project_id: projectId,
      is_new_project: isNew,
      filter_mode: filterMode,
      filters: normalizeFilters(filters),
      swiped_image_ids: swipedIds || [],
      preloaded_images: preloadedImages || null,
    })
    setProjects(prev => prev.map(p => {
      if (p.id !== projectId) return p
      return {
        ...p,
        sessionId: result.session_id,
        backendId: result.project_id || p.backendId || null,
      }
    }))
    setCurrentCard(result.next_image)
    setSessionProgress(result.progress)
    if (!result.next_image) setIsSessionCompleted(true)
    setIsSwipeLoading(false)
  }

  async function handleStart(projectName, preloadedImages, llmFilters = {}) {
    const projectId = `proj_${Date.now()}`
    const newProject = {
      id: projectId, projectName, filters: llmFilters || {},
      likedBuildings: [], swipedIds: [],
      predictedLikes: [], analysisReport: null,
      sessionId: null, createdAt: new Date().toISOString(),
      deckImages: preloadedImages || null,
    }
    setLlmContext(null)
    setProjects(prev => [...prev, newProject])
    setActiveProjectId(projectId)
    await initSession(projectId, llmFilters || {}, [], true, 'keep', preloadedImages)
    setTab('swipe')
  }

  async function handleSwipeCard(action) {
    if (!currentCard || !activeProjectId) return
    const project = projects.find(p => p.id === activeProjectId)
    if (!project?.sessionId) return

    setIsSwipeLoading(true)
    const newSwipedIds = [...(project.swipedIds || []), currentCard.image_id]

    const result = await api.recordSwipe({
      session_id: project.sessionId,
      user_id: userId,
      project_id: activeProjectId,
      image_id: currentCard.image_id,
      action,
      swiped_image_ids: newSwipedIds,
    })

    setProjects(prev => prev.map(p => {
      if (p.id !== activeProjectId) return p
      return {
        ...p,
        swipedIds: newSwipedIds,
        likedBuildings: action === 'like' ? [...p.likedBuildings, currentCard] : p.likedBuildings,
      }
    }))

    setSessionProgress(result.progress)

    if (result.is_analysis_completed) {
      setIsSessionCompleted(true)
      setCurrentCard(null)
      const resultData = await api.getResult({
        session_id: project.sessionId,
        user_id: userId,
        project_id: activeProjectId,
      })
      setProjects(prev => prev.map(p => p.id === activeProjectId ? {
        ...p,
        predictedLikes: resultData.predicted_like_images || [],
        analysisReport: resultData.analysis_report || null,
      } : p))
    } else {
      setCurrentCard(result.next_image)
    }

    setIsSwipeLoading(false)
  }

  async function handleResumeProject(id) {
    const project = projects.find(p => p.id === id)
    if (!project) return
    setLlmContext(null)
    setActiveProjectId(id)
    await initSession(id, project.filters, project.swipedIds, false, 'keep', project.deckImages || null)
    setTab('swipe')
  }

  async function handleUpdateWithImages(id, preloadedImages, llmFilters = {}) {
    const project = projects.find(p => p.id === id)
    if (!project) return
    setLlmContext(null)
    setActiveProjectId(id)
    setProjects(prev => prev.map(p => p.id === id ? { ...p, deckImages: preloadedImages } : p))
    await initSession(id, llmFilters || project.filters, project.swipedIds, false, 'modify', preloadedImages)
    setTab('swipe')
  }

  function handleDeleteProject(id) {
    const project = projects.find(p => p.id === id)
    if (project?.backendId) {
      api.deleteProject(project.backendId).catch(console.error)
    }
    setProjects(prev => prev.filter(p => p.id !== id))
    if (activeProjectId === id) {
      setActiveProjectId(null)
      setCurrentCard(null)
      setSessionProgress(null)
      setIsSessionCompleted(false)
      setTab('home')
    }
  }

  async function handleGenerateReport(projectId) {
    const project = projects.find(p => p.id === projectId)
    const backendId = project?.backendId || (project?.id?.includes('-') ? project.id : null)
    if (!backendId) return
    try {
      const { final_report } = await api.generateReport(backendId)
      setProjects(prev => prev.map(p => p.id === projectId ? { ...p, finalReport: final_report } : p))
    } catch (err) {
      console.error('[App] generateReport failed:', err)
    }
  }

  async function handleLogin(user) {
    // user may be a string (mock) or an object from backend {user_id, display_name, access, refresh}
    const id = typeof user === 'object' ? (user.user_id || user.id || String(user)) : String(user)
    if (typeof user === 'object' && user.access) {
      api.setTokens(user.access, user.refresh)
    }
    sessionStorage.setItem('archithon_user', id)
    setUserId(id)
    setCurrentCard(null)
    setSessionProgress(null)
    setIsSessionCompleted(false)
    setLlmContext(null)
    setFolderOpenId(null)
    setTab('home')
    sessionStorage.removeItem('archithon_llmContext')
    sessionStorage.removeItem('archithon_folderOpenId')

    // Sync projects from backend (if JWT available)
    try {
      const { results: backendProjects } = await api.listProjects()
      if (backendProjects.length > 0) {
        const allLikedIds = [...new Set(backendProjects.flatMap(p => p.liked_ids || []))]
        const allCards = await api.getBuildings(allLikedIds)
        const cardMap = Object.fromEntries(allCards.map(c => [c.image_id, c]))
        const mapped = backendProjects.map(p => ({
          id: String(p.project_id),
          backendId: String(p.project_id),
          projectName: p.name,
          filters: p.filters || {},
          likedBuildings: (p.liked_ids || []).map(bid => cardMap[bid]).filter(Boolean),
          swipedIds: [...(p.liked_ids || []), ...(p.disliked_ids || [])],
          predictedLikes: [],
          analysisReport: p.analysis_report || null,
          finalReport: p.final_report || null,
          sessionId: null,
          createdAt: p.created_at,
          deckImages: null,
        }))
        setProjects(mapped)
        setActiveProjectId(null)
        return
      }
    } catch (err) {
      console.error('[App] project sync failed, falling back to localStorage:', err)
    }
    setProjects(JSON.parse(localStorage.getItem(`archithon_projects_${id}`) || '[]'))
    setActiveProjectId(localStorage.getItem(`archithon_activeId_${id}`) || null)
  }

  function handleLogout() {
    if (loggingOut.current) return
    loggingOut.current = true
    const refresh = localStorage.getItem('archithon_refresh')
    api.logout(refresh)   // blacklists refresh token, clears JWT from localStorage
    clearSessions()       // clears in-memory local session state (spec F7)
    sessionStorage.removeItem('archithon_user')
    sessionStorage.removeItem('archithon_tab')
    sessionStorage.removeItem('archithon_llmContext')
    sessionStorage.removeItem('archithon_folderOpenId')
    setUserId(null)
    setProjects([])
    setActiveProjectId(null)
    setCurrentCard(null)
    setSessionProgress(null)
    setIsSessionCompleted(false)
    setLlmContext(null)
    loggingOut.current = false
  }

  if (!userId) {
    return <LoginPage onLogin={handleLogin} theme={theme} onToggleTheme={toggleTheme} />
  }

  return (
    <ErrorBoundary>
      <div style={{ height: '100vh', overflow: 'hidden' }}>

        {/* Header controls */}
        <div style={{ position: 'fixed', top: 14, right: 16, zIndex: 200, display: 'flex', gap: 6, alignItems: 'center' }}>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <button
            onClick={handleLogout}
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

        {tab === 'home' && !llmContext && (
          <SetupPage
            key={setupKey}
            projects={projects}
            onResume={handleResumeProject}
            onNavigateNew={() => setLlmContext({ mode: 'new', step: 'setup' })}
            onNavigateUpdate={(id, name) => setLlmContext({ mode: 'update', step: 'chat', projectId: id, projectName: name })}
          />
        )}

        {tab === 'home' && llmContext?.mode === 'new' && llmContext?.step === 'setup' && (
          <ProjectSetupPage
            onBack={() => setLlmContext(null)}
            onNext={({ projectName, minArea, maxArea }) =>
              setLlmContext({ mode: 'new', step: 'chat', projectName, minArea, maxArea })
            }
          />
        )}

        {tab === 'home' && llmContext?.step === 'chat' && (
          <LLMSearchPage
            mode={llmContext.mode}
            projectId={llmContext.projectId}
            projectName={llmContext.projectName}
            minArea={llmContext.minArea}
            maxArea={llmContext.maxArea}
            onBack={() =>
              llmContext.mode === 'new'
                ? setLlmContext({ mode: 'new', step: 'setup' })
                : setLlmContext(null)
            }
            onStart={handleStart}
            onUpdate={handleUpdateWithImages}
          />
        )}

        <div style={{ display: tab === 'swipe' && activeProject ? 'block' : 'none' }}>
          <SwipePage
            key={activeProjectId}
            currentCard={currentCard}
            progress={sessionProgress}
            isCompleted={isSessionCompleted}
            isLoading={isSwipeLoading}
            projectName={activeProject?.projectName}
            onSwipe={handleSwipeCard}
            onViewResults={() => { setFolderOpenId(activeProjectId); setTab('folders') }}
          />
        </div>

        <div style={{ display: tab === 'folders' ? 'block' : 'none' }}>
          <FavoritesPage
            projects={projects}
            onDeleteProject={handleDeleteProject}
            onResumeProject={handleResumeProject}
            onGenerateReport={handleGenerateReport}
            openId={folderOpenId}
            onOpenIdChange={setFolderOpenId}
          />
        </div>

        {tab === 'swipe' && !activeProject && (
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
              onClick={() => handleSelectTab('home')}
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

      </div>

      <TabBar tab={tab} onSelect={handleSelectTab} swipeEnabled={!!activeProject} />
    </ErrorBoundary>
  )
}
