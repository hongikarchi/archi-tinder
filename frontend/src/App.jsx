import { useState, useEffect, useRef, Component } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation, useParams } from 'react-router-dom'
import MainLayout from './layouts/MainLayout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import SetupPage from './pages/SetupPage.jsx'
import ProjectSetupPage from './pages/ProjectSetupPage.jsx'
import LLMSearchPage from './pages/LLMSearchPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import * as api from './api/client.js'

function normalizeFilters(filters) {
  if (!filters) return {}
  const out = {}
  // Structured filters from LLM parse-query -- pass through
  if (filters.program)           out.program           = filters.program
  if (filters.location_country)  out.location_country  = filters.location_country
  if (filters.material)          out.material          = filters.material
  if (filters.style)             out.style             = filters.style
  if (filters.year_min  != null) out.year_min          = filters.year_min
  if (filters.year_max  != null) out.year_max          = filters.year_max
  // Area -- accept all naming conventions (frontend, LLM area_min, backend min_area)
  const minArea = filters.min_area ?? filters.minArea ?? filters.area_min ?? null
  const maxArea = filters.max_area ?? filters.maxArea ?? filters.area_max ?? null
  if (minArea != null) out.min_area = minArea
  if (maxArea != null) out.max_area = maxArea
  return out
}

function isNetworkError(err) {
  return err instanceof TypeError || !err.status
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

/* ── LLMSearch update-mode wrapper ──────────────────────────────────────── */
function LLMSearchUpdateWrapper({ wizardData, onBack, onStart, onUpdate }) {
  const { projectId } = useParams()
  return (
    <LLMSearchPage
      mode="update"
      projectId={projectId}
      projectName={wizardData?.projectName}
      onBack={onBack}
      onStart={onStart}
      onUpdate={onUpdate}
    />
  )
}

/* ── App ─────────────────────────────────────────────────────────────────── */
export default function App() {
  const navigate = useNavigate()
  const location = useLocation()

  const [theme, setTheme] = useState(() => localStorage.getItem('archithon_theme') || 'dark')
  const [userId, setUserId] = useState(() => sessionStorage.getItem('archithon_user') || null)
  const [setupKey, setSetupKey] = useState(0)
  const [wizardData, setWizardData] = useState(null)

  const [currentCard, setCurrentCard] = useState(null)
  const [prefetchCard, setPrefetchCard] = useState(null)
  const [prefetchCard2, setPrefetchCard2] = useState(null)
  const [sessionProgress, setSessionProgress] = useState(null)
  const [isSwipeLoading, setIsSwipeLoading] = useState(false)
  const imagePreloadCache = useRef(new Set())
  const [isSessionCompleted, setIsSessionCompleted] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [isResultLoading, setIsResultLoading] = useState(false)
  const [swipeError, setSwipeError] = useState(null)
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

  // Auto-dismiss swipe error toast after 3 seconds
  useEffect(() => {
    if (!swipeError) return
    const timer = setTimeout(() => setSwipeError(null), 3000)
    return () => clearTimeout(timer)
  }, [swipeError])

  const activeProject = projects.find(p => p.id === activeProjectId) || null

  // On refresh, re-init swipe session if the user was on the swipe route
  const swipeRestored = useRef(false)
  const loggingOut = useRef(false)
  const swipeLock = useRef(false)
  useEffect(() => {
    if (swipeRestored.current) return
    if (location.pathname === '/swipe' && activeProjectId && userId) {
      const project = projects.find(p => p.id === activeProjectId)
      if (project) {
        swipeRestored.current = true
        initSession(activeProjectId, project.filters)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function preloadImage(url) {
    if (!url || imagePreloadCache.current.has(url)) return Promise.resolve()
    return new Promise(resolve => {
      const img = new Image()
      img.onload = img.onerror = () => { imagePreloadCache.current.add(url); resolve() }
      img.src = url
    })
  }

  function toggleTheme() {
    setTheme(t => t === 'dark' ? 'light' : 'dark')
  }

  async function initSession(projectId, filters, filterPriority = [], seedIds = []) {
    setIsSwipeLoading(true)
    setIsSessionCompleted(false)
    const result = await api.startSession({
      project_id: projectId,
      filters: normalizeFilters(filters),
      filter_priority: filterPriority,
      seed_ids: seedIds,
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
    setSessionProgress({ ...result.progress, filter_relaxed: result.filter_relaxed || false })
    if (!result.next_image) setIsSessionCompleted(true)
    if (result.next_image?.image_url) preloadImage(result.next_image.image_url)
    if (result.prefetch_image) {
      setPrefetchCard(result.prefetch_image)
      preloadImage(result.prefetch_image.image_url)
    }
    if (result.prefetch_image_2) {
      setPrefetchCard2(result.prefetch_image_2)
      preloadImage(result.prefetch_image_2.image_url)
    }
    setIsSwipeLoading(false)
  }

  async function handleStart(projectName, preloadedImages, llmFilters = {}, filterPriority = []) {
    const projectId = `proj_${Date.now()}`
    const seedIds = (preloadedImages || []).map(c => c.image_id).filter(Boolean)
    const newProject = {
      id: projectId, projectName, filters: llmFilters || {},
      likedBuildings: [], swipedIds: [],
      predictedLikes: [],
      sessionId: null, createdAt: new Date().toISOString(),
      deckImages: preloadedImages || null,
    }
    setWizardData(null)
    setProjects(prev => [...prev, newProject])
    setActiveProjectId(projectId)
    navigate('/swipe')
    await initSession(projectId, llmFilters || {}, filterPriority, seedIds)
  }

  async function handleSwipeCard(action) {
    if (swipeLock.current) return
    swipeLock.current = true

    if (!currentCard || !activeProjectId) {
      swipeLock.current = false
      return
    }
    const project = projects.find(p => p.id === activeProjectId)
    if (!project?.sessionId) {
      swipeLock.current = false
      return
    }

    const swipedCard = currentCard
    const savedPrefetch = prefetchCard
    const savedPrefetch2 = prefetchCard2
    const newSwipedIds = [...(project.swipedIds || []), swipedCard.image_id]

    // Optimistic UI: show prefetch card immediately for smooth UX
    const canInstantSwap = savedPrefetch && imagePreloadCache.current.has(savedPrefetch.image_url)
    if (canInstantSwap) {
      setCurrentCard(savedPrefetch)
      setPrefetchCard(prefetchCard2)  // shift queue
      setPrefetchCard2(null)
    } else {
      setCurrentCard(null)
      setIsSwipeLoading(true)
    }

    try {
      let result
      const swipePayload = {
        session_id: project.sessionId,
        image_id: swipedCard.image_id,
        action,
      }

      try {
        result = await api.recordSwipe(swipePayload)
      } catch (firstErr) {
        if (!isNetworkError(firstErr)) throw firstErr
        // Retry once on network error
        result = await api.recordSwipe(swipePayload)
      }

      // Backend confirmed -- now update local state
      setProjects(prev => prev.map(p => {
        if (p.id !== activeProjectId) return p
        return {
          ...p,
          swipedIds: newSwipedIds,
          likedBuildings: action === 'like' ? [...p.likedBuildings, swipedCard] : p.likedBuildings,
        }
      }))

      setSessionProgress(result.progress)

      if (result.is_analysis_completed) {
        setIsSessionCompleted(true)
        setCurrentCard(null)
        setPrefetchCard(null)
        setPrefetchCard2(null)
        setIsResultLoading(true)
        try {
          const resultData = await api.getResult({
            session_id: project.sessionId,
          })
          setProjects(prev => prev.map(p => p.id === activeProjectId ? {
            ...p,
            predictedLikes: resultData.predicted_like_images || [],
          } : p))
        } finally {
          setIsResultLoading(false)
        }
      } else {
        if (canInstantSwap) {
          // DON'T overwrite currentCard — user is already looking at savedPrefetch
          // Only update the prefetch queue from backend response
          setPrefetchCard(result.prefetch_image || null)
          setPrefetchCard2(result.prefetch_image_2 || null)
          if (result.prefetch_image?.image_url) preloadImage(result.prefetch_image.image_url)
          if (result.prefetch_image_2?.image_url) preloadImage(result.prefetch_image_2.image_url)
        } else {
          setCurrentCard(result.next_image)
          setPrefetchCard(result.prefetch_image)
          setPrefetchCard2(result.prefetch_image_2 || null)
          preloadImage(result.next_image?.image_url)
          preloadImage(result.prefetch_image?.image_url)
          preloadImage(result.prefetch_image_2?.image_url)
        }
      }
    } catch (err) {
      console.error('[App] swipe failed:', err)
      // Revert UI -- put the swiped card back
      setCurrentCard(swipedCard)
      setPrefetchCard(savedPrefetch)
      setPrefetchCard2(savedPrefetch2)
      setSwipeError('Swipe failed. Please try again.')
    } finally {
      setIsSwipeLoading(false)
      swipeLock.current = false
    }
  }

  async function handleResumeProject(id) {
    const project = projects.find(p => p.id === id)
    if (!project) return
    setWizardData(null)
    setActiveProjectId(id)
    navigate('/swipe')
    await initSession(id, project.filters)
  }

  async function handleUpdateWithImages(id, preloadedImages, llmFilters = {}, filterPriority = []) {
    const project = projects.find(p => p.id === id)
    if (!project) return
    const seedIds = (preloadedImages || []).map(c => c.image_id).filter(Boolean)
    setWizardData(null)
    setActiveProjectId(id)
    setProjects(prev => prev.map(p => p.id === id ? { ...p, deckImages: preloadedImages } : p))
    navigate('/swipe')
    await initSession(id, llmFilters || project.filters, filterPriority, seedIds)
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
      navigate('/')
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
    setWizardData(null)
    navigate('/')

    // Sync projects from backend (if JWT available)
    setIsSyncing(true)
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
    } finally {
      setIsSyncing(false)
    }
    setProjects(JSON.parse(localStorage.getItem(`archithon_projects_${id}`) || '[]'))
    setActiveProjectId(localStorage.getItem(`archithon_activeId_${id}`) || null)
  }

  function handleLogout() {
    if (loggingOut.current) return
    loggingOut.current = true
    const refresh = localStorage.getItem('archithon_refresh')
    api.logout(refresh)   // blacklists refresh token, clears JWT from localStorage
    sessionStorage.removeItem('archithon_user')
    setUserId(null)
    setProjects([])
    setActiveProjectId(null)
    setCurrentCard(null)
    setSessionProgress(null)
    setIsSessionCompleted(false)
    setWizardData(null)
    loggingOut.current = false
    navigate('/login')
  }

  const sharedLayoutProps = {
    theme,
    onToggleTheme: toggleTheme,
    userId,
    onLogout: handleLogout,
    projects,
    isSyncing,
    activeProject,
    activeProjectId,
    currentCard,
    sessionProgress,
    isSessionCompleted,
    isSwipeLoading,
    isResultLoading,
    onSwipe: handleSwipeCard,
    onViewResults: () => navigate('/library/' + activeProjectId),
    onResumeProject: handleResumeProject,
    onDeleteProject: handleDeleteProject,
    onGenerateReport: handleGenerateReport,
  }

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={
          userId ? <Navigate to="/" replace /> : <LoginPage onLogin={handleLogin} theme={theme} onToggleTheme={toggleTheme} />
        } />

        <Route element={
          <ProtectedRoute userId={userId}>
            <MainLayout {...sharedLayoutProps} />
          </ProtectedRoute>
        }>
          <Route index element={
            <SetupPage
              key={setupKey}
              projects={projects}
              isSyncing={isSyncing}
              onResume={handleResumeProject}
              onNavigateNew={() => {
                setSetupKey(k => k + 1)
                navigate('/new')
              }}
              onNavigateUpdate={(id, name) => {
                setWizardData({ projectId: id, projectName: name })
                navigate('/search/' + id)
              }}
            />
          } />
          <Route path="new" element={
            <ProjectSetupPage
              onBack={() => navigate('/')}
              onNext={({ projectName, minArea, maxArea }) => {
                setWizardData({ projectName, minArea, maxArea })
                navigate('/search')
              }}
            />
          } />
          <Route path="search" element={
            <LLMSearchPage
              mode="new"
              projectName={wizardData?.projectName}
              onBack={() => navigate('/new')}
              onStart={handleStart}
              onUpdate={handleUpdateWithImages}
            />
          } />
          <Route path="search/:projectId" element={
            <LLMSearchUpdateWrapper
              wizardData={wizardData}
              onBack={() => navigate('/')}
              onStart={handleStart}
              onUpdate={handleUpdateWithImages}
            />
          } />
          <Route path="swipe" element={null} />
          <Route path="library" element={null} />
          <Route path="library/:folderId" element={null} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {swipeError && (
        <div style={{
          position: 'fixed', bottom: 80, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(220, 38, 38, 0.92)', color: '#fff', padding: '10px 20px',
          borderRadius: 8, fontSize: 14, fontWeight: 500, zIndex: 9999,
          pointerEvents: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        }}>
          {swipeError}
        </div>
      )}
    </ErrorBoundary>
  )
}
