import { useState } from 'react'

// ── step: 'choose' | 'select-project' | 'filter-choice'
export default function SetupPage({ projects = [], onResume, onNavigateNew, onNavigateUpdate }) {
  const hasProjects = projects.length > 0
  const [step, setStep] = useState('choose')
  const [selectedProject, setSelectedProject] = useState(null)

  function handleSelectProject(project) {
    setSelectedProject(project)
    setStep('filter-choice')
  }

  function handleKeepFilters() {
    onResume(selectedProject.id)
  }

  function handleChangeFilters() {
    onNavigateUpdate(selectedProject.id, selectedProject.projectName)
  }

  /* ── 1. 신규 vs 기존 선택 ─────────────────────────────────────────────── */
  if (step === 'choose') {
    return (
      <div style={{ minHeight: '100vh', background: '#0f0f0f', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, gap: 16 }}>
        <Header />
        <p style={{ color: '#6b7280', fontSize: 13, margin: '0 0 8px' }}>무엇을 하시겠어요?</p>
        {hasProjects && (
          <ChoiceButton
            icon="📁"
            title="기존 폴더 업데이트"
            desc="이전에 만든 폴더에 이어서 스와이프"
            onClick={() => setStep('select-project')}
          />
        )}
        <ChoiceButton
          icon="＋"
          title="신규 폴더 생성"
          desc="AI에게 원하는 건축물을 설명해보세요"
          onClick={onNavigateNew}
        />
      </div>
    )
  }

  /* ── 2. 기존 폴더 목록 선택 ──────────────────────────────────────────── */
  if (step === 'select-project') {
    return (
      <div style={{ minHeight: '100vh', background: '#0f0f0f', padding: '40px 20px 120px' }}>
        <Header />
        <BackButton onClick={() => setStep('choose')} />
        <p style={{ color: '#6b7280', fontSize: 13, textAlign: 'center', margin: '0 0 20px' }}>업데이트할 폴더를 선택하세요</p>
        <div style={{ maxWidth: 480, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {projects.map(p => {
            const likedCount = p.likedBuildings?.length || 0
            const swipedCount = p.swipedIds?.length || 0
            return (
              <button
                key={p.id}
                onClick={() => handleSelectProject(p)}
                style={{
                  background: '#1a1a1a', border: '1px solid #2a2a2a',
                  borderRadius: 14, padding: '16px 18px',
                  textAlign: 'left', cursor: 'pointer', fontFamily: 'inherit',
                  color: '#fff', transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = '#3b82f6'}
                onMouseLeave={e => e.currentTarget.style.borderColor = '#2a2a2a'}
              >
                <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{p.projectName}</div>
                <div style={{ fontSize: 12, color: '#4b5563' }}>
                  {swipedCount}개 스와이프 · ♥ {likedCount}개 저장
                </div>
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  /* ── 3. 필터 유지 vs 변경 ─────────────────────────────────────────────── */
  if (step === 'filter-choice') {
    return (
      <div style={{ minHeight: '100vh', background: '#0f0f0f', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, gap: 16 }}>
        <Header />
        <BackButton onClick={() => setStep('select-project')} />
        <p style={{ color: '#fff', fontSize: 16, fontWeight: 700, margin: '0 0 4px', textAlign: 'center' }}>
          "{selectedProject?.projectName}"
        </p>
        <p style={{ color: '#6b7280', fontSize: 13, margin: '0 0 8px', textAlign: 'center' }}>
          어떻게 하시겠어요?
        </p>
        <ChoiceButton icon="▶" title="이어서 스와이프" desc="기존 상태에서 계속 진행" onClick={handleKeepFilters} />
        <ChoiceButton icon="🔍" title="새로 검색" desc="AI로 새 건물을 검색해서 추가" onClick={handleChangeFilters} />
      </div>
    )
  }

  return null
}

/* ── Header ──────────────────────────────────────────────────────────────── */
function Header() {
  return (
    <div style={{ textAlign: 'center', marginBottom: 8 }}>
      <h1 style={{ fontSize: 28, fontWeight: 900, margin: 0, letterSpacing: '-0.01em' }}>
        <span style={{ color: '#fff' }}>Archi</span><span style={{ color: '#3b82f6' }}>Tinder</span>
      </h1>
    </div>
  )
}

/* ── BackButton ──────────────────────────────────────────────────────────── */
function BackButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'block', margin: '8px auto 0',
        background: 'none', border: 'none',
        color: '#4b5563', fontSize: 13, cursor: 'pointer',
        fontFamily: 'inherit',
      }}
    >
      ← 뒤로
    </button>
  )
}

/* ── ChoiceButton ────────────────────────────────────────────────────────── */
function ChoiceButton({ icon, title, desc, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', maxWidth: 320,
        background: '#1a1a1a', border: '1px solid #2a2a2a',
        borderRadius: 16, padding: '18px 20px',
        display: 'flex', alignItems: 'center', gap: 14,
        cursor: 'pointer', fontFamily: 'inherit',
        textAlign: 'left', transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = '#3b82f6'}
      onMouseLeave={e => e.currentTarget.style.borderColor = '#2a2a2a'}
    >
      <span style={{ fontSize: 24 }}>{icon}</span>
      <div>
        <div style={{ color: '#fff', fontSize: 14, fontWeight: 700 }}>{title}</div>
        <div style={{ color: '#4b5563', fontSize: 12, marginTop: 2 }}>{desc}</div>
      </div>
    </button>
  )
}
