import { useState, useEffect, useRef, Component } from 'react'
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
  return {
    typologies: filters.typologies || [],
    min_area: filters.minArea !== undefined ? filters.minArea : (filters.min_area || 0),
    max_area: filters.maxArea !== undefined ? filters.maxArea : (filters.max_area || Infinity),
  }
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
function TabBar({ tab, onSelect, swipeEnabled }) {
  const tabs = [
    { id: 'home',    icon: '＋',  label: 'New'     },
    { id: 'swipe',   icon: '🃏',  label: 'Swipe'   },
    { id: 'folders', icon: '📁',  label: 'Folders' },
  ]
  return (
    <nav style={{
      position: 'fixed', bottom: 0, left: 0, right: 0,
      display: 'flex', zIndex: 100,
      background: 'var(--color-nav-bg)',
      backdropFilter: 'blur(16px)',
      borderTop: '1px solid var(--color-border)',
    }}>
      {tabs.map(t => {
        const active = tab === t.id
        const disabled = t.id === 'swipe' && !swipeEnabled
        return (
          <button
            key={t.id}
            onClick={() => !disabled && onSelect(t.id)}
            style={{
              flex: 1, padding: '12px 0 16px', border: 'none', background: 'none',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
              cursor: disabled ? 'default' : 'pointer',
              color: disabled ? 'var(--color-nav-disabled)' : active ? 'var(--color-text)' : 'var(--color-nav-inactive)',
              transition: 'color 0.2s', position: 'relative', fontFamily: 'inherit',
            }}
          >
            <span style={{ fontSize: 20, lineHeight: 1 }}>{t.icon}</span>
            <span style={{ fontSize: 10, fontWeight: active ? 700 : 400 }}>{t.label}</span>
            {active && (
              <span style={{
                position: 'absolute', bottom: 0, width: 28, height: 2,
                background: 'var(--color-text)', borderRadius: 2,
              }} />
            )}
          </button>
        )
      })}
    </nav>
  )
}

/* ── Theme Toggle Button ─────────────────────────────────────────────────── */
function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      onClick={onToggle}
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border-soft)',
        borderRadius: 8, padding: '5px 10px',
        color: 'var(--color-text-dim)', fontSize: 15, cursor: 'pointer',
        fontFamily: 'inherit', lineHeight: 1,
        transition: 'background 0.2s',
      }}
    >
      {theme === 'dark' ? '☀️' : '🌙'}
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
      const backendProjects = await api.listProjects()
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
  }

  if (!userId) {
    return <LoginPage onLogin={handleLogin} theme={theme} onToggleTheme={toggleTheme} />
  }

  return (
    <ErrorBoundary>
      <div style={{ height: '100vh', overflow: 'hidden' }}>

        {/* Header controls */}
        <div style={{ position: 'fixed', top: 14, right: 16, zIndex: 200, display: 'flex', gap: 8 }}>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <button
            onClick={handleLogout}
            style={{
              background: 'var(--color-surface)', border: '1px solid var(--color-border-soft)',
              borderRadius: 8, padding: '5px 12px',
              color: 'var(--color-text-dim)', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            Logout
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

      </div>

      <TabBar tab={tab} onSelect={handleSelectTab} swipeEnabled={!!activeProject} />
    </ErrorBoundary>
  )
}
