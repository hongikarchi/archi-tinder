import { useState, useEffect, useRef, Component } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation, useParams } from 'react-router-dom'
import MainLayout from './layouts/MainLayout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import SetupPage from './pages/SetupPage.jsx'
import ProjectSetupPage from './pages/ProjectSetupPage.jsx'
import LLMSearchPage from './pages/LLMSearchPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import UserProfilePage from './pages/UserProfilePage.jsx'
import FirmProfilePage from './pages/FirmProfilePage.jsx'
import * as api from './api/client.js'

function normalizeFilters(filters) {
  if (!filters) return {}
  const out = {}
  // Structured filters from LLM parse-query -- pass through
  if (filters.program) out.program = filters.program
  if (filters.location_country) out.location_country = filters.location_country
  if (filters.material) out.material = filters.material
  if (filters.style) out.style = filters.style
  if (filters.year_min != null) out.year_min = filters.year_min
  if (filters.year_max != null) out.year_max = filters.year_max
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

// Action cards have image_url = '' and don't need image preload.
// Treat them as "always instant-swappable" so they advance the queue smoothly.
function isActionCard(card) {
  return !!card && (card.card_type === 'action' || card.image_id === '__action_card__')
}

// Backend changed Project.liked_ids shape: list[str] -> list[{id, intensity}].
// This helper accepts either shape and returns plain id strings, so older sessions
// (pre-migration data still in browser cache) and new responses both work.
function extractLikedIds(rawLikedIds) {
  if (!Array.isArray(rawLikedIds)) return []
  return rawLikedIds
    .map(entry => (typeof entry === 'string' ? entry : entry?.id))
    .filter(Boolean)
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

  // Persist current card id to localStorage per active project so refresh can
  // restore the exact card the user was looking at (not just the backend's last
  // next_image). Cleared when currentCard becomes null or session completes.
  useEffect(() => {
    if (!userId || !activeProjectId) return
    const key = `archithon_currentCard_${userId}_${activeProjectId}`
    if (currentCard?.image_id && currentCard.image_id !== '__action_card__') {
      localStorage.setItem(key, currentCard.image_id)
    } else if (!currentCard) {
      localStorage.removeItem(key)
    }
  }, [currentCard, userId, activeProjectId])

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
        // Pass the stored sessionId so initSession tries to resume first,
        // then falls back to creating a new session if resume fails.
        // Also pass the persisted currentCard hint so the resume returns the
        // exact card the user was looking at, not the backend's last selection.
        const hintKey = `archithon_currentCard_${userId}_${activeProjectId}`
        const currentHint = localStorage.getItem(hintKey) || null
        initSession(activeProjectId, project.filters, [], [], project.sessionId || null, currentHint)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function preloadImage(url) {
    if (!url || imagePreloadCache.current.has(url)) return Promise.resolve()
    return new Promise(resolve => {
      const img = new Image()
      const timeout = setTimeout(() => {
        imagePreloadCache.current.add(url)
        resolve()
      }, 1500)
      img.onload = img.onerror = () => {
        clearTimeout(timeout)
        imagePreloadCache.current.add(url)
        resolve()
      }
      img.src = url
    })
  }

  function toggleTheme() {
    setTheme(t => t === 'dark' ? 'light' : 'dark')
  }

  // Populate frontend card state from a session state or start response.
  function applySessionResponse(projectId, result) {
    setCurrentCard(result.next_image)
    setSessionProgress({ ...result.progress, filter_relaxed: result.filter_relaxed || false })
    if (result.is_analysis_completed || !result.next_image) {
      setIsSessionCompleted(!!result.is_analysis_completed || !result.next_image)
    } else {
      setIsSessionCompleted(false)
    }
    if (result.next_image?.image_url) preloadImage(result.next_image.image_url)
    if (result.prefetch_image) {
      setPrefetchCard(result.prefetch_image)
      preloadImage(result.prefetch_image.image_url)
    } else {
      setPrefetchCard(null)
    }
    if (result.prefetch_image_2) {
      setPrefetchCard2(result.prefetch_image_2)
      preloadImage(result.prefetch_image_2.image_url)
    } else {
      setPrefetchCard2(null)
    }
    if (result.session_id) {
      setProjects(prev => prev.map(p => {
        if (p.id !== projectId) return p
        return {
          ...p,
          sessionId: result.session_id,
          backendId: result.project_id || p.backendId || null,
        }
      }))
    }
  }

  async function initSession(projectId, filters, filterPriority = [], seedIds = [], existingSessionId = null, currentHint = null) {
    setIsSwipeLoading(true)
    setIsSessionCompleted(false)
    try {
      // Try to resume an existing session first (preserves progress across refresh)
      if (existingSessionId) {
        try {
          const resumed = await api.getSessionState(existingSessionId, currentHint)
          applySessionResponse(projectId, resumed)
          return
        } catch {
          // Session not found (404), expired, or other failure -- fall through to new session
        }
      }

      const result = await api.startSession({
        project_id: projectId,
        filters: normalizeFilters(filters),
        filter_priority: filterPriority,
        seed_ids: seedIds,
      })
      applySessionResponse(projectId, result)
    } catch (err) {
      setCurrentCard(null)
      setPrefetchCard(null)
      setPrefetchCard2(null)
      setSwipeError(err.message || 'Failed to start session')
    } finally {
      setIsSwipeLoading(false)
    }
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

    // Optimistic UI: show prefetch card immediately for smooth UX.
    // Action cards are always instant-swappable (no image to preload).
    const canInstantSwap = !!savedPrefetch && (
      isActionCard(savedPrefetch) ||
      imagePreloadCache.current.has(savedPrefetch.image_url)
    )
    if (canInstantSwap) {
      setCurrentCard(savedPrefetch)
      setPrefetchCard(prefetchCard2)  // shift queue
      setPrefetchCard2(null)
    } else {
      // Keep the current card visible with a loading overlay instead of
      // replacing it with null. Setting currentCard to null was the root cause
      // of Bug 1 (cards stop loading) -- if the user tried to interact while
      // null, the handler returned early and never recovered.
      setIsSwipeLoading(true)
    }

    try {
      // Tell the backend which cards the frontend has prefetched in its visible queue.
      // The backend merges these into exposed_ids before card selection, so it
      // never re-selects a card the user already has loaded. This is the core fix
      // for "cards stop loading" and "same card appears twice" bugs.
      const clientBufferIds = [savedPrefetch, savedPrefetch2]
        .filter(c => c && c.image_id && !isActionCard(c))
        .map(c => c.image_id)

      let result
      const swipePayload = {
        session_id: project.sessionId,
        image_id: swipedCard.image_id,
        action,
        client_buffer_ids: clientBufferIds,
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
          // User is looking at savedPrefetch (already swapped to currentCard).
          // Queue was shifted: prefetch=savedPrefetch2, prefetch_2=null.
          // Backend's result.next_image is the card that should come AFTER the
          // entire frontend buffer (backend's exposed_ids now includes [swiped,
          // savedPrefetch, savedPrefetch2, result.next_image]).
          // Use result.next_image as the new prefetch_2 (tail-fill the queue).
          // IGNORE result.prefetch_image and result.prefetch_image_2 on the
          // instant-swap path -- they describe the backend's view of rounds past
          // savedPrefetch, but the frontend only advances one step per swipe.
          // Using them would overwrite the frontend's authoritative queue and
          // cause drift (the root cause of "cards stop loading" and "same card
          // twice" bugs before this fix).
          if (result.next_image) {
            setPrefetchCard2(result.next_image)
            if (result.next_image.image_url) preloadImage(result.next_image.image_url)
          } else {
            setPrefetchCard2(null)
          }
        } else {
          // Non-instant path: rebuild queue from backend response entirely.
          // If next_image is null and session isn't completed, keep the card
          // in loading state (swiped card was already animated away by TinderCard).
          if (result.next_image) {
            setCurrentCard(result.next_image)
          } else if (!result.is_analysis_completed) {
            // Edge case: no next card but session not done (pool temporarily exhausted)
            // Keep whatever is visible; the loading overlay will clear in finally block
          }
          setPrefetchCard(result.prefetch_image || null)
          setPrefetchCard2(result.prefetch_image_2 || null)
          preloadImage(result.next_image?.image_url)
          preloadImage(result.prefetch_image?.image_url)
          preloadImage(result.prefetch_image_2?.image_url)
        }
      }
    } catch {
      // Only revert UI if we hadn't already swapped to a different card
      // When canInstantSwap was true, user is already looking at savedPrefetch -- don't revert
      if (!canInstantSwap) {
        setCurrentCard(swipedCard)
        setPrefetchCard(savedPrefetch)
        setPrefetchCard2(savedPrefetch2)
      }
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
    // Try to resume the stored session, fall back to new session on failure
    await initSession(id, project.filters, [], [], project.sessionId || null)
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
      api.deleteProject(project.backendId).catch(() => { })
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
    const { final_report } = await api.generateReport(backendId)
    setProjects(prev => prev.map(p => p.id === projectId ? { ...p, finalReport: final_report } : p))
  }

  function handleImageGenerated(projectId, imageData) {
    setProjects(prev => prev.map(p => p.id === projectId ? { ...p, reportImage: imageData } : p))
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
        const allLikedIds = [...new Set(backendProjects.flatMap(p => extractLikedIds(p.liked_ids)))]
        const allCards = await api.getBuildings(allLikedIds)
        const cardMap = Object.fromEntries(allCards.map(c => [c.image_id, c]))
        const mapped = backendProjects.map(p => ({
          id: String(p.project_id),
          backendId: String(p.project_id),
          projectName: p.name,
          filters: p.filters || {},
          likedBuildings: extractLikedIds(p.liked_ids).map(bid => cardMap[bid]).filter(Boolean),
          swipedIds: [...extractLikedIds(p.liked_ids), ...(p.disliked_ids || [])],
          predictedLikes: [],
          finalReport: p.final_report || null,
          reportImage: p.report_image || null,
          sessionId: null,
          createdAt: p.created_at,
          deckImages: null,
        }))
        setProjects(mapped)
        setActiveProjectId(null)
        return
      }
    } catch {
      // Project sync failed -- falling back to localStorage
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
    onImageGenerated: handleImageGenerated,
  }

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={
          userId ? <Navigate to="/" replace /> : <LoginPage onLogin={handleLogin} />
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
          <Route path="user/me" element={<UserProfilePage {...sharedLayoutProps} />} />
          <Route path="office/:officeId" element={<FirmProfilePage {...sharedLayoutProps} />} />
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
