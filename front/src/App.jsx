import { useState, useEffect, Component } from 'react'
import SetupPage from './SetupPage'
import ProjectSetupPage from './ProjectSetupPage'
import LLMSearchPage from './LLMSearchPage'
import SwipePage from './SwipePage'
import FavoritesPage from './FavoritesPage'
import LoginPage from './LoginPage'
import * as api from './api.js'

/* ── 필터 정규화 (frontend minArea/maxArea → API min_area/max_area) ─────── */
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
      <div style={{ color: '#fff', padding: 24, background: '#111', minHeight: '100vh' }}>
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
      background: 'rgba(12,12,12,0.97)',
      backdropFilter: 'blur(16px)',
      borderTop: '1px solid rgba(255,255,255,0.07)',
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
              color: disabled ? '#2d2d2d' : active ? '#fff' : '#555',
              transition: 'color 0.2s', position: 'relative', fontFamily: 'inherit',
            }}
          >
            <span style={{ fontSize: 20, lineHeight: 1 }}>{t.icon}</span>
            <span style={{ fontSize: 10, fontWeight: active ? 700 : 400 }}>{t.label}</span>
            {active && (
              <span style={{
                position: 'absolute', bottom: 0, width: 28, height: 2,
                background: '#fff', borderRadius: 2,
              }} />
            )}
          </button>
        )
      })}
    </nav>
  )
}

/* ── App ─────────────────────────────────────────────────────────────────── */
export default function App() {
  const [userId, setUserId] = useState(() => sessionStorage.getItem('archithon_user') || null)
  const [tab, setTab] = useState('home')
  const [setupKey, setSetupKey] = useState(0)
  const [folderOpenId, setFolderOpenId] = useState(null)
  // llmContext: null
  //   | { mode: 'new', step: 'setup' }
  //   | { mode: 'new', step: 'chat', projectName, minArea, maxArea }
  //   | { mode: 'update', step: 'chat', projectId, projectName }
  const [llmContext, setLlmContext] = useState(null)

  // 세션 기반 스와이프 상태
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

  /* ── Tab 선택 ─────────────────────────────────────────────────────────── */
  function handleSelectTab(newTab) {
    if (newTab === 'home') { setSetupKey(k => k + 1); setLlmContext(null) }
    if (newTab === 'folders') setFolderOpenId(null)
    setTab(newTab)
  }

  /* ── 세션 시작 헬퍼 ────────────────────────────────────────────────────── */
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
    setProjects(prev => prev.map(p => p.id === projectId ? { ...p, sessionId: result.session_id } : p))
    setCurrentCard(result.next_image)
    setSessionProgress(result.progress)
    if (!result.next_image) setIsSessionCompleted(true)
    setIsSwipeLoading(false)
  }

  /* ── Handlers ─────────────────────────────────────────────────────────── */
  async function handleStart(projectName, preloadedImages) {
    const projectId = `proj_${Date.now()}`
    const newProject = {
      id: projectId,
      projectName,
      filters: {},
      likedBuildings: [],
      swipedIds: [],
      predictedLikes: [],
      analysisReport: null,
      sessionId: null,
      createdAt: new Date().toISOString(),
    }
    setLlmContext(null)
    setProjects(prev => [...prev, newProject])
    setActiveProjectId(projectId)
    await initSession(projectId, {}, [], true, 'keep', preloadedImages)
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
      // 최종 결과 조회
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
    await initSession(id, project.filters, project.swipedIds, false, 'keep')
    setTab('swipe')
  }

  async function handleUpdateWithImages(id, preloadedImages) {
    const project = projects.find(p => p.id === id)
    if (!project) return
    setLlmContext(null)
    setActiveProjectId(id)
    await initSession(id, project.filters, project.swipedIds, false, 'modify', preloadedImages)
    setTab('swipe')
  }

  function handleDeleteProject(id) {
    setProjects(prev => prev.filter(p => p.id !== id))
    if (activeProjectId === id) {
      setActiveProjectId(null)
      setCurrentCard(null)
      setSessionProgress(null)
      setIsSessionCompleted(false)
      setTab('home')
    }
  }

  function handleLogin(id) {
    sessionStorage.setItem('archithon_user', id)
    setUserId(id)
    setProjects(JSON.parse(localStorage.getItem(`archithon_projects_${id}`) || '[]'))
    setActiveProjectId(localStorage.getItem(`archithon_activeId_${id}`) || null)
    setCurrentCard(null)
    setSessionProgress(null)
    setIsSessionCompleted(false)
    setLlmContext(null)
    setTab('home')
  }

  function handleLogout() {
    sessionStorage.removeItem('archithon_user')
    setUserId(null)
    setProjects([])
    setActiveProjectId(null)
    setCurrentCard(null)
    setSessionProgress(null)
    setIsSessionCompleted(false)
    setLlmContext(null)
  }

  if (!userId) {
    return <LoginPage onLogin={handleLogin} />
  }

  return (
    <ErrorBoundary>
      <div style={{ paddingBottom: 64 }}>

        {/* Logout */}
        <div style={{ position: 'fixed', top: 14, right: 16, zIndex: 200 }}>
          <button
            onClick={handleLogout}
            style={{
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8, padding: '5px 12px',
              color: '#6b7280', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            로그아웃
          </button>
        </div>

        {/* Home / Setup */}
        {tab === 'home' && !llmContext && (
          <SetupPage
            key={setupKey}
            projects={projects}
            onResume={handleResumeProject}
            onNavigateNew={() => setLlmContext({ mode: 'new', step: 'setup' })}
            onNavigateUpdate={(id, name) => setLlmContext({ mode: 'update', step: 'chat', projectId: id, projectName: name })}
          />
        )}

        {/* 신규 프로젝트 설정 (이름 + 규모) */}
        {tab === 'home' && llmContext?.mode === 'new' && llmContext?.step === 'setup' && (
          <ProjectSetupPage
            onBack={() => setLlmContext(null)}
            onNext={({ projectName, minArea, maxArea }) =>
              setLlmContext({ mode: 'new', step: 'chat', projectName, minArea, maxArea })
            }
          />
        )}

        {/* LLM Search Page */}
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

        {/* Swipe */}
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

        {/* Folders */}
        <div style={{ display: tab === 'folders' ? 'block' : 'none' }}>
          <FavoritesPage
            projects={projects}
            onDeleteProject={handleDeleteProject}
            onResumeProject={handleResumeProject}
            openId={folderOpenId}
            onOpenIdChange={setFolderOpenId}
          />
        </div>

        {/* Swipe tab but no active project */}
        {tab === 'swipe' && !activeProject && (
          <div style={{
            minHeight: '100vh', background: '#0f0f0f', display: 'flex',
            flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            gap: 12, padding: 24,
          }}>
            <div style={{ fontSize: 48 }}>🃏</div>
            <p style={{ fontSize: 16, fontWeight: 900, margin: 0 }}>
              <span style={{ color: '#fff' }}>Archi</span><span style={{ color: '#3b82f6' }}>Tinder</span>
            </p>
            <p style={{ color: '#4b5563', fontSize: 13 }}>Create a new session from the Home tab</p>
            <button
              onClick={() => handleSelectTab('home')}
              style={{
                marginTop: 8, padding: '12px 28px', borderRadius: 12,
                background: 'linear-gradient(135deg,#3b82f6,#8b5cf6)',
                color: '#fff', fontSize: 14, fontWeight: 600,
                border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              Go to Home
            </button>
          </div>
        )}

      </div>

      <TabBar
        tab={tab}
        onSelect={handleSelectTab}
        swipeEnabled={!!activeProject}
      />
    </ErrorBoundary>
  )
}
