import { useState, useEffect, useRef } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useTheme } from './hooks/useTheme.js'
import MainLayout from './layouts/MainLayout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import ProjectSetupPage from './pages/ProjectSetupPage.jsx'
import LLMSearchPage from './pages/LLMSearchPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import UserProfilePage from './pages/UserProfilePage.jsx'
import FirmProfilePage from './pages/FirmProfilePage.jsx'
import BoardDetailPage from './pages/BoardDetailPage.jsx'
import ResultsPage from './pages/ResultsPage.jsx'
import BuildingDetailPage from './pages/BuildingDetailPage.jsx'
import DiscoveryPage from './pages/DiscoveryPage.jsx'
import VerifyGateModal from './components/VerifyGateModal.jsx'
import LikedProjectsPage from './pages/LikedProjectsPage.jsx'
import FollowListPage from './pages/userProfile/FollowListPage.jsx'
import * as api from './api/client.js'
import { createProject } from './api/projects.js'
import { normalizeFilters, classifySwipeError, isActionCard, extractLikedIds, extractSavedIds } from './utils/appHelpers.js'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import LLMSearchUpdateWrapper from './components/LLMSearchUpdateWrapper.jsx'

/* ── App ─────────────────────────────────────────────────────────────────── */
export default function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const { hydrate } = useTheme()

  const [userId, setUserId] = useState(() => sessionStorage.getItem('archithon_user') || null)
  const [wizardData, setWizardData] = useState(null)

  const [currentCard, setCurrentCard] = useState(null)
  const [cardResetToken, setCardResetToken] = useState(0)
  const [prefetchCard, setPrefetchCard] = useState(null)
  const [prefetchCard2, setPrefetchCard2] = useState(null)
  const [sessionProgress, setSessionProgress] = useState(null)
  const [isSwipeLoading, setIsSwipeLoading] = useState(false)
  const imagePreloadCache = useRef(new Set())
  const [isSessionCompleted, setIsSessionCompleted] = useState(false)
  const [isResultLoading, setIsResultLoading] = useState(false)
  const [swipeError, setSwipeError] = useState(null)
  // Tracks in-flight recordSwipe() calls. Button gates on this so the
  // "Finish & View Report" button can't fire before the backend save settles.
  const [swipePending, setSwipePending] = useState(0)
  const [activeProjectId, setActiveProjectId] = useState(() => {
    const id = sessionStorage.getItem('archithon_user')
    return localStorage.getItem(`archithon_activeId_${id}`) || null
  })
  const [projects, setProjects] = useState(() => {
    const id = sessionStorage.getItem('archithon_user')
    return JSON.parse(localStorage.getItem(`archithon_projects_${id}`) || '[]')
  })

  // VerifyGateModal — shown when guest hits the 3-board limit
  const [verifyGateOpen, setVerifyGateOpen] = useState(false)
  // Pending board-create payload from SaveToBoardModal (Fix 3 Option A).
  // Stored when VerifyRequiredError fires during board creation; retried on promote.
  const [pendingBoardCreate, setPendingBoardCreate] = useState(null)
  // Tracks whether a SurpriseBoardModal board-create was interrupted by verify gate.
  // After promote we show a toast asking the user to re-open the modal (Fix 3 Option B).
  const [surprisePending, setSurprisePending] = useState(false)
  // Global toast state (type: 'info' | 'success' | 'warning' | 'error')
  const [globalToast, setGlobalToast] = useState(null) // {message, type}
  // Pending in-session question triggered by the backend after a swipe
  const [pendingQuestion, setPendingQuestion] = useState(null)

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

  // Listen for verify-required event dispatched by api/projects.js createProject()
  useEffect(() => {
    const onVerifyRequired = () => setVerifyGateOpen(true)
    window.addEventListener('archithon:verify-required', onVerifyRequired)
    return () => window.removeEventListener('archithon:verify-required', onVerifyRequired)
  }, [])

  // Capture pending board-create payload from SaveToBoardModal (Fix 3 Option A)
  useEffect(() => {
    const onPendingCreate = (e) => {
      if (e?.detail) setPendingBoardCreate(e.detail)
    }
    window.addEventListener('archithon:pending-board-create', onPendingCreate)
    return () => window.removeEventListener('archithon:pending-board-create', onPendingCreate)
  }, [])

  // Capture surprise-board pending flag (Fix 3 Option B)
  useEffect(() => {
    const onSurprisePending = () => setSurprisePending(true)
    window.addEventListener('archithon:verify-required:surprise-pending', onSurprisePending)
    return () => window.removeEventListener('archithon:verify-required:surprise-pending', onSurprisePending)
  }, [])

  // Auto-dismiss global toast after 3s (DESIGN.md §8.11 toast-duration default)
  useEffect(() => {
    if (!globalToast) return
    const timer = setTimeout(() => setGlobalToast(null), 3000)
    return () => clearTimeout(timer)
  }, [globalToast])

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

  // Auto-navigate when the backend declares a terminal state OR the user has
  // swiped meaningfully past the target window. The post-target floor mirrors
  // SwipePage's beyondTargetFloor so users on dislike-heavy paths don't get
  // stranded (backend convergence can be withheld by the recent-likes gate).
  useEffect(() => {
    if (location.pathname !== '/swipe') return
    const phase = sessionProgress?.phase
    const swipeCount = sessionProgress?.swipe_count ?? sessionProgress?.current_round ?? 0
    const targetSwipes = Math.max(1, sessionProgress?.target_swipes ?? 10)
    const beyondTargetFloor = swipeCount >= targetSwipes + 5
    const backendDone = isSessionCompleted || phase === 'converged' || beyondTargetFloor
    if (!backendDone) return
    const sessionId = projects.find(p => p.id === activeProjectId)?.sessionId
    if (!sessionId) return
    navigate('/result/' + sessionId)
  }, [isSessionCompleted, sessionProgress?.phase, sessionProgress?.swipe_count, sessionProgress?.current_round]) // eslint-disable-line react-hooks/exhaustive-deps

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
  const swipeLog = useRef([])
  const swipeCount = useRef(0)
  const swipeRetryCount = useRef(0)
  const currentCardRef = useRef(null)
  const activeProjectIdRef = useRef(null)

  // Keep currentCardRef in sync so setTimeout closures can read live card identity
  useEffect(() => { currentCardRef.current = currentCard }, [currentCard])
  // Keep activeProjectIdRef in sync so setTimeout closures detect project-switch / session-end
  useEffect(() => { activeProjectIdRef.current = activeProjectId }, [activeProjectId])
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
      img.onload = img.onerror = () => {
        imagePreloadCache.current.add(url)
        resolve()
      }
      img.src = url
    })
  }

  // Populate frontend card state from a session state or start response.
  function applySessionResponse(projectId, result) {
    setCurrentCard(result.next_image)
    setSessionProgress({
      ...result.progress,
      filter_relaxed: result.filter_relaxed || false,
      confidence: result.confidence ?? null,
      can_continue: result.can_continue ?? false, // S3: pass through from backend
    })
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

  async function initSession(projectId, filters, filterPriority = [], seedIds = [], existingSessionId = null, currentHint = null, visualDescription = null, projectName = 'Untitled', rawQuery = '', imageFocus = null) {
    setPendingQuestion(null)
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
        name: projectName,
        filters: normalizeFilters(filters),
        filter_priority: filterPriority,
        seed_ids: seedIds,
        visual_description: visualDescription || undefined,
        raw_query: rawQuery || '',
        image_focus: imageFocus,
      })
      applySessionResponse(projectId, result)
      return result
    } catch (err) {
      setCurrentCard(null)
      setPrefetchCard(null)
      setPrefetchCard2(null)
      setSwipeError(err.message || 'Failed to start session')
    } finally {
      setIsSwipeLoading(false)
    }
  }

  async function handleStart(projectName, preloadedImages, llmFilters = {}, filterPriority = [], visualDescription = null, visibility = 'private', rawQuery = '', imageFocus = null) {
    const projectId = `proj_${Date.now()}`
    const seedIds = (preloadedImages || []).map(c => c.image_id).filter(Boolean)
    const newProject = {
      id: projectId, projectName, filters: llmFilters || {},
      likedBuildings: [], swipedIds: [],
      predictedLikes: [],
      sessionId: null, createdAt: new Date().toISOString(),
      deckImages: preloadedImages || null,
      visibility,
    }
    setWizardData(null)
    setProjects(prev => [...prev, newProject])
    setActiveProjectId(projectId)
    navigate('/swipe')
    const result = await initSession(projectId, llmFilters || {}, filterPriority, seedIds, null, null, visualDescription, projectName, rawQuery || '', imageFocus)
    if (visibility !== 'private' && result?.project_id) {
      api.updateProject(result.project_id, { visibility }).catch(err =>
        console.error('[App] updateProject visibility sync failed:', err)
      )
    }
  }

  async function handleSwipeCard(action) {
    if (swipeLock.current) {
      // Card may have flown off-screen during the lock window.
      // Force TinderCard remount so it reappears centered instead of going blank.
      setCardResetToken(t => t + 1)
      return
    }
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

    // -- Diagnostic log entry (populated as swipe progresses) --
    const _dbg = {
      n: ++swipeCount.current,
      action,
      cardId: swipedCard.image_id?.slice(-8) ?? '?',
      instant: canInstantSwap,
      instantReason: !savedPrefetch ? 'no_pf'
        : (canInstantSwap ? (isActionCard(savedPrefetch) ? 'action' : 'cached') : 'miss'),
      apiMs: 0,
      preloadMs: null,
      nextId: null,
      nextBlocked: false,
      fallback: false,
      pf: null,
      pf2: null,
      totalMs: 0,
      err: null,
      ts: Date.now(),
    }

    // Mark swipe in-flight — prevents "Finish & View Report" button from firing
    // while recordSwipe() is pending (optimistic bump can reach isAt100 instantly).
    setSwipePending(n => n + 1)

    if (canInstantSwap) {
      setCurrentCard(savedPrefetch)
      setPrefetchCard(prefetchCard2)  // shift queue
      setPrefetchCard2(null)
      // Optimistic like_count bump so the unified progress bar advances in lockstep
      // with the visible card. Server response at line ~387 replaces with authoritative state.
      if (action === 'like') {
        setSessionProgress(p => p ? { ...p, like_count: (p.like_count ?? 0) + 1 } : p)
      }
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

      const _apiT0 = Date.now()
      try {
        result = await api.recordSwipe(swipePayload)
      } catch (firstErr) {
        if (classifySwipeError(firstErr).kind !== 'network') throw firstErr
        // Retry once on network error
        result = await api.recordSwipe(swipePayload)
      }
      _dbg.apiMs = Date.now() - _apiT0

      // Backend confirmed -- now update local state
      setProjects(prev => prev.map(p => {
        if (p.id !== activeProjectId) return p
        return {
          ...p,
          swipedIds: newSwipedIds,
          likedBuildings: action === 'like' ? [...p.likedBuildings, swipedCard] : p.likedBuildings,
        }
      }))

      swipeRetryCount.current = 0
      setSwipeError(null)
      if (result.question_trigger) {
        setPendingQuestion(result.question_trigger)
      }
      setSessionProgress({
        ...result.progress,
        confidence: result.confidence ?? null,
        can_continue: result.can_continue ?? false,
      })

      if (result.is_analysis_completed) {
        setIsSessionCompleted(true)
        setCurrentCard(null)
        setPrefetchCard(null)
        setPrefetchCard2(null)
        setSessionProgress(prev => ({
          ...(prev || {}),
          ...result.progress,
          confidence: result.confidence ?? null,
          can_continue: result.can_continue ?? false,
        }))
        setIsResultLoading(true)
        try {
          const backendId = project?.backendId
          const [resultData, reportData] = await Promise.all([
            api.getResult({ session_id: project.sessionId }),
            backendId ? api.generateReport(backendId).catch(() => null) : Promise.resolve(null),
          ])
          setProjects(prev => prev.map(p => p.id === activeProjectId ? {
            ...p,
            predictedLikes: resultData.predicted_like_images || [],
            ...(reportData?.final_report ? { finalReport: reportData.final_report } : {}),
          } : p))
        } catch {
          // ResultsPage will attempt a fresh GET /result/ on entry.
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
          const _nextBlocked = !!(result.next_image && isActionCard(result.next_image))
          _dbg.nextId = result.next_image?.image_id?.slice(-8) ?? null
          _dbg.nextBlocked = _nextBlocked
          _dbg.pf = result.prefetch_image?.image_id?.slice(-8) ?? null
          _dbg.pf2 = result.prefetch_image_2?.image_id?.slice(-8) ?? null
          if (result.next_image && !_nextBlocked) {
            setPrefetchCard2(result.next_image)
            if (result.next_image.image_url) preloadImage(result.next_image.image_url)
          } else {
            setPrefetchCard2(null)
          }
        } else {
          // Non-instant path: rebuild queue from backend response entirely.
          _dbg.nextId = result.next_image?.image_id?.slice(-8) ?? null
          _dbg.pf = result.prefetch_image?.image_id?.slice(-8) ?? null
          _dbg.pf2 = result.prefetch_image_2?.image_id?.slice(-8) ?? null
          if (result.next_image) {
            // Wait for the image to download before showing the card so the
            // transition from LoadingCard lands with the image already visible.
            const _plT0 = Date.now()
            await preloadImage(result.next_image.image_url)
            _dbg.preloadMs = Date.now() - _plT0
            setCurrentCard(result.next_image)
          } else if (!result.is_analysis_completed) {
            // Pool temporarily exhausted — fall back to getSessionState (same as page refresh).
            // This re-runs the recommendation engine and returns the correct next card,
            // preventing the frozen/blank state caused by null next_image.
            _dbg.fallback = true
            try {
              const fresh = await api.getSessionState(project.sessionId)
              applySessionResponse(activeProjectId, fresh)
              return
            } catch {
              // If getSessionState also fails, leave currentCard=null (LoadingCard stays,
              // user sees "No more buildings" after loading clears in finally).
            }
          }
          setPrefetchCard(result.prefetch_image || null)
          setPrefetchCard2(result.prefetch_image_2 || null)
          preloadImage(result.prefetch_image?.image_url)
          preloadImage(result.prefetch_image_2?.image_url)
        }
      }
    } catch (e) {
      _dbg.err = e?.message ?? 'unknown'
      // Only revert UI if we hadn't already swapped to a different card
      // When canInstantSwap was true, user is already looking at savedPrefetch -- don't revert
      if (!canInstantSwap) {
        setCurrentCard(swipedCard)
        setPrefetchCard(savedPrefetch)
        setPrefetchCard2(savedPrefetch2)
      }
      const { kind, message } = classifySwipeError(e)
      if (kind === 'auth') {
        // core.js already dispatches on 401 — only dispatch here for 403
        if (e?.status !== 401) {
          window.dispatchEvent(new Event('archithon:session-expired'))
        }
      } else if (kind === 'network' && !canInstantSwap && swipeRetryCount.current < 1) {
        // Auto-retry once on network error, only when card was reverted (non-instant path)
        const retryCardId = swipedCard?.image_id
        const retryProjectId = activeProjectId
        swipeRetryCount.current += 1
        if (message) setSwipeError(message)
        setTimeout(() => {
          // Only retry if user hasn't switched cards OR changed/ended the project
          const cardMatches = currentCardRef.current?.image_id === retryCardId
          const projectMatches = activeProjectIdRef.current === retryProjectId
          if (cardMatches && projectMatches) {
            handleSwipeCard(action)
          } else {
            swipeRetryCount.current = 0
            setSwipeError(null)
          }
        }, 1500)
      } else {
        swipeRetryCount.current = 0
        if (message) setSwipeError(message)
      }
    } finally {
      _dbg.totalMs = Date.now() - _dbg.ts
      const log = swipeLog.current
      if (log.length >= 10) log.shift()
      log.push(_dbg)
      setSwipePending(n => Math.max(0, n - 1))
      setIsSwipeLoading(false)
      swipeLock.current = false
    }
  }

  async function handleExtendSession() {
    if (swipeLock.current) return
    const project = projects.find(p => p.id === activeProjectId)
    if (!project?.sessionId) return

    swipeLock.current = true
    setIsSwipeLoading(true)
    try {
      const result = await api.recordSwipe({
        session_id: project.sessionId,
        image_id: (project.swipedIds || []).slice(-1)[0] || '',
        action: 'like',
        client_buffer_ids: [],
        extend: true,
      })

      setIsSessionCompleted(false)
      setCurrentCard(result.next_image)
      setPrefetchCard(result.prefetch_image || null)
      setPrefetchCard2(result.prefetch_image_2 || null)
      setSessionProgress({
        ...result.progress,
        confidence: result.confidence ?? null,
        can_continue: result.can_continue ?? false,
      })
      if (result.next_image?.image_url) preloadImage(result.next_image.image_url)
      if (result.prefetch_image?.image_url) preloadImage(result.prefetch_image.image_url)
      if (result.prefetch_image_2?.image_url) preloadImage(result.prefetch_image_2.image_url)
    } catch (e) {
      const { kind, message } = classifySwipeError(e)
      if (kind === 'auth') {
        // core.js already dispatches on 401 — only dispatch here for 403
        if (e?.status !== 401) {
          window.dispatchEvent(new Event('archithon:session-expired'))
        }
      } else if (message) {
        setSwipeError(message)
      }
    } finally {
      setIsSwipeLoading(false)
      swipeLock.current = false
    }
  }

  async function handleQuestionAnswer(option) {
    const q = pendingQuestion
    setPendingQuestion(null)
    if (!activeProject?.sessionId) return
    api.submitQuestionResponse({
      session_id: activeProject.sessionId,
      question_type: q.type,
      axis: q.axis ?? null,
      selected_option: option,
    }).catch(() => {})
  }

  async function handleUpdateWithImages(id, preloadedImages, llmFilters = {}, filterPriority = [], visualDescription = null, imageFocus = null) {
    const project = projects.find(p => p.id === id)
    if (!project) return
    const seedIds = (preloadedImages || []).map(c => c.image_id).filter(Boolean)
    setWizardData(null)
    setActiveProjectId(id)
    setProjects(prev => prev.map(p => p.id === id ? { ...p, deckImages: preloadedImages } : p))
    navigate('/swipe')
    await initSession(id, llmFilters || project.filters, filterPriority, seedIds, null, null, visualDescription, project.projectName, '', imageFocus)
  }

  async function handleLogin(user) {
    // user may be a string (mock) or an object from backend {user_id, display_name, access, refresh}
    const id = typeof user === 'object' ? (user.user_id || user.id || String(user)) : String(user)
    if (typeof user === 'object' && user.access) {
      api.setTokens(user.access, user.refresh)
    }
    sessionStorage.setItem('archithon_user', id)
    setUserId(id)
    if (typeof user === 'object') hydrate(user.theme, user.font)
    setCurrentCard(null)
    setSessionProgress(null)
    setIsSessionCompleted(false)
    setWizardData(null)
    navigate('/')

    // Sync projects from backend (if JWT available)
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
          visibility: p.visibility || 'private',
          filters: p.filters || {},
          likedBuildings: extractLikedIds(p.liked_ids).map(bid => cardMap[bid]).filter(Boolean),
          swipedIds: [...extractLikedIds(p.liked_ids), ...(p.disliked_ids || [])],
          predictedLikes: [],
          savedIds: extractSavedIds(p.saved_ids),
          finalReport: p.final_report || null,
          reportImage: p.report_image || null,
          sessionId: p.latest_session_id || null,
          latestSessionMeta: p.latest_session_meta || null,
          createdAt: p.created_at,
          deckImages: null,
        }))
        setProjects(mapped)
        setActiveProjectId(null)
        return
      }
    } catch {
      // Project sync failed -- falling back to localStorage
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

  // Resume an interrupted swipe session from a board card.
  // boardId == project_id (String). Looks up the local project entry to get
  // its filters + stored sessionId, then navigates to /swipe.
  async function handleResumeProject(boardId) {
    const id = String(boardId)
    const project = projects.find(p => p.id === id)
    if (!project) return
    setActiveProjectId(id)
    navigate('/swipe')
    await initSession(id, project.filters, [], [], project.sessionId || null, null, null, project.projectName)
  }

  // Start a fresh swipe session for an existing project, discarding the old session.
  async function handleNewProjectSession(boardId) {
    const id = String(boardId)
    const project = projects.find(p => p.id === id)
    if (!project) return
    // Clear stored sessionId so initSession creates a brand-new session
    setProjects(prev => prev.map(p => p.id === id ? { ...p, sessionId: null, latestSessionMeta: null } : p))
    setActiveProjectId(id)
    navigate('/swipe')
    await initSession(id, project.filters, [], [], null, null, null, project.projectName)
  }

  const sharedLayoutProps = {
    userId,
    onLogout: handleLogout,
    activeProject,
    activeProjectId,
    currentCard,
    sessionProgress,
    isSessionCompleted,
    isSwipeLoading,
    isResultLoading,
    swipePending,
    onSwipe: handleSwipeCard,
    onExtendSession: handleExtendSession,
    onViewResults: () => {
      if (activeProject?.sessionId) navigate('/result/' + activeProject.sessionId)
      else navigate('/user/me')
    },
    cardResetToken,
    onExitToNewProject: () => {
      const hasLikes = (activeProject?.likedBuildings?.length ?? 0) > 0
      const backendId = activeProject?.backendId
      if (!hasLikes && backendId) api.deleteProject(backendId).catch(() => {})
      setActiveProjectId(null)
      navigate('/new')
    },
    onExitToHome: () => {
      const hasLikes = (activeProject?.likedBuildings?.length ?? 0) > 0
      const backendId = activeProject?.backendId
      if (!hasLikes && backendId) api.deleteProject(backendId).catch(() => {})
      setActiveProjectId(null)
      navigate('/discovery')
    },
    onResumeProject: handleResumeProject,
    onNewProjectSession: handleNewProjectSession,
    questionTrigger: pendingQuestion,
    onQuestionAnswer: handleQuestionAnswer,
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
          <Route index element={<Navigate to="/discovery" replace />} />
          <Route path="discovery" element={<DiscoveryPage />} />
          <Route path="new" element={
            <ProjectSetupPage
              onBack={() => navigate('/discovery')}
              onNext={({ projectName, minArea, maxArea, visibility }) => {
                setWizardData({ projectName, minArea, maxArea, visibility })
                navigate('/search')
              }}
            />
          } />
          <Route path="search" element={
            <LLMSearchPage
              mode="new"
              projectName={wizardData?.projectName}
              visibility={wizardData?.visibility}
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
          <Route path="library" element={<Navigate to="/user/me" replace />} />
          <Route path="library/:folderId" element={<Navigate to="/user/me" replace />} />
          <Route path="user/me" element={<UserProfilePage {...sharedLayoutProps} />} />
          <Route path="user/:userId" element={<UserProfilePage {...sharedLayoutProps} />} />
          <Route path="user/:userId/followers" element={<FollowListPage mode="followers" />} />
          <Route path="user/:userId/following" element={<FollowListPage mode="following" />} />
          <Route path="office/:officeId" element={<FirmProfilePage {...sharedLayoutProps} />} />
          <Route path="result/:sessionId" element={<ResultsPage projects={projects} setProjects={setProjects} />} />
          <Route path="buildings/:buildingId" element={<BuildingDetailPage />} />
          <Route path="board/:boardId" element={<BoardDetailPage />} />
          <Route path="liked-projects" element={<LikedProjectsPage />} />
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

      {globalToast && (
        <div style={{
          position: 'fixed',
          bottom: 'calc(64px + 16px)',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'color-mix(in srgb, var(--color-surface, #F6F8FA) 72%, transparent)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          border: globalToast.type === 'success'
            ? '1px solid var(--accent-2, #8250DF)'
            : globalToast.type === 'error'
              ? '1px solid var(--color-destructive, #D73A49)'
              : '1px solid var(--color-border, rgba(0,0,0,0.08))',
          borderRadius: 999,
          padding: '10px 16px',
          fontSize: 14,
          fontWeight: 500,
          color: 'var(--color-text, #1F2328)',
          zIndex: 9998,
          pointerEvents: 'none',
          whiteSpace: 'nowrap',
          boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
        }}>
          {globalToast.message}
        </div>
      )}

      {verifyGateOpen && (
        <VerifyGateModal
          onClose={() => {
            setVerifyGateOpen(false)
            setPendingBoardCreate(null)
            setSurprisePending(false)
          }}
          onPromoted={async (user, merged) => {
            setVerifyGateOpen(false)

            if (merged) {
              // Branch 1: guest deleted, merged into existing verified account.
              // Re-run full login flow to re-sync userId, projects, localStorage.
              if (user) await handleLogin(user)
              setGlobalToast({ message: 'Verified — your existing account is now loaded.', type: 'success' })
              setPendingBoardCreate(null)
              setSurprisePending(false)
              return
            }

            // Branch 2: in-place promote (guest user_id preserved, is_guest → false).
            // Update user object if provided (e.g. re-fetch /auth/me/ to refresh state).
            if (user) {
              const id = user.user_id || user.id
              if (id) sessionStorage.setItem('archithon_user', String(id))
              if (user.access) api.setTokens(user.access, user.refresh)
            }

            // Retry pending SaveToBoardModal board-create (Fix 3 Option A).
            if (pendingBoardCreate) {
              try {
                await createProject(pendingBoardCreate)
                setGlobalToast({ message: 'Board created! You can now save to it.', type: 'success' })
              } catch {
                setGlobalToast({ message: 'Verified! Please try creating the board again.', type: 'info' })
              } finally {
                setPendingBoardCreate(null)
              }
            } else if (surprisePending) {
              // Fix 3 Option B: fat payload — prompt user to re-open the surprise modal.
              setGlobalToast({ message: 'Verified! Please try saving the board again.', type: 'success' })
              setSurprisePending(false)
            } else {
              setGlobalToast({ message: 'Verified! You can now create boards.', type: 'success' })
            }
          }}
        />
      )}
    </ErrorBoundary>
  )
}
