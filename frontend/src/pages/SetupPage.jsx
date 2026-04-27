import { useState } from 'react'

export default function SetupPage({ projects = [], isSyncing = false, onResume, onNavigateNew, onNavigateUpdate }) {
  const hasProjects = projects.length > 0
  const [step, setStep] = useState('choose')
  const [selectedProject, setSelectedProject] = useState(null)

  function handleSelectProject(project) {
    setSelectedProject(project)
    setStep('filter-choice')
  }

  if (step === 'choose') {
    return (
      <div style={{ height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflow: 'hidden', background: 'var(--color-bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, gap: 16 }}>
        <Header />
        {isSyncing ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 28, height: 28, border: '3px solid var(--color-border)',
              borderTopColor: '#ec4899', borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
            }} />
            <p style={{ color: 'var(--color-text-dim)', fontSize: 13, margin: 0 }}>Loading your projects...</p>
          </div>
        ) : (
          <>
            <p style={{ color: 'var(--color-text-dim)', fontSize: 13, margin: '0 0 8px' }}>What would you like to do?</p>
            {hasProjects && (
              <ChoiceButton
                icon="📁"
                title="Update existing folder"
                desc="Continue swiping on a previous folder"
                onClick={() => setStep('select-project')}
              />
            )}
            <ChoiceButton
              icon="＋"
              title="Create new folder"
              desc="Describe the architecture you want to AI"
              onClick={onNavigateNew}
            />
          </>
        )}
      </div>
    )
  }

  if (step === 'select-project') {
    return (
      <div style={{ height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflowY: 'auto', background: 'var(--color-bg)', padding: '40px 20px 120px' }}>
        <Header />
        <BackButton onClick={() => setStep('choose')} />
        <p style={{ color: 'var(--color-text-dim)', fontSize: 13, textAlign: 'center', margin: '0 0 20px' }}>Select a folder to update</p>
        <div style={{ maxWidth: 480, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {projects.map(p => {
            const likedCount = p.likedBuildings?.length || 0
            const swipedCount = p.swipedIds?.length || 0
            return (
              <button
                key={p.id}
                onClick={() => handleSelectProject(p)}
                style={{
                  background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                  borderRadius: 14, padding: '16px 18px',
                  textAlign: 'left', cursor: 'pointer', fontFamily: 'inherit',
                  color: 'var(--color-text)', transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = '#ec4899'}
                onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--color-border)'}
              >
                <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{p.projectName}</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-dimmer)' }}>
                  {swipedCount} swiped · ♥ {likedCount} saved
                </div>
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  if (step === 'filter-choice') {
    return (
      <div style={{ height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflow: 'hidden', background: 'var(--color-bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, gap: 16 }}>
        <Header />
        <BackButton onClick={() => setStep('select-project')} />
        <p style={{ color: 'var(--color-text)', fontSize: 16, fontWeight: 700, margin: '0 0 4px', textAlign: 'center' }}>
          "{selectedProject?.projectName}"
        </p>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 13, margin: '0 0 8px', textAlign: 'center' }}>
          How would you like to continue?
        </p>
        <ChoiceButton icon="▶" title="Resume swiping" desc="Continue from where you left off" onClick={() => onResume(selectedProject.id)} />
        <ChoiceButton icon="🔍" title="New search" desc="Search for new buildings with AI" onClick={() => onNavigateUpdate(selectedProject.id, selectedProject.projectName)} />
      </div>
    )
  }

  return null
}

function Header() {
  return (
    <div style={{ textAlign: 'center', marginBottom: 8 }}>
      <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0, letterSpacing: '-0.01em' }}>
        <span style={{ color: 'var(--color-text)' }}>Archi</span>
        <span style={{ color: '#ec4899' }}>Tinder</span>
      </h1>
    </div>
  )
}

function BackButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        margin: '8px auto 0', minHeight: 44,
        background: 'none', border: 'none',
        color: 'var(--color-text-dimmer)', fontSize: 13, cursor: 'pointer',
        fontFamily: 'inherit',
      }}
    >
      ← Back
    </button>
  )
}

function ChoiceButton({ icon, title, desc, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', maxWidth: 320,
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 16, padding: '18px 20px',
        display: 'flex', alignItems: 'center', gap: 14,
        cursor: 'pointer', fontFamily: 'inherit',
        textAlign: 'left', transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = '#ec4899'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--color-border)'}
    >
      <span style={{ fontSize: 24 }}>{icon}</span>
      <div>
        <div style={{ color: 'var(--color-text)', fontSize: 14, fontWeight: 700 }}>{title}</div>
        <div style={{ color: 'var(--color-text-dimmer)', fontSize: 12, marginTop: 2 }}>{desc}</div>
      </div>
    </button>
  )
}
