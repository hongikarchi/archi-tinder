import { useState } from 'react'

const SCALE_MIN = 0
const SCALE_MAX = 100000
const SCALE_STEP = 1000

export default function ProjectSetupPage({ onBack, onNext }) {
  const [projectName, setProjectName] = useState('')
  const [minArea, setMinArea] = useState(SCALE_MIN)
  const [maxArea, setMaxArea] = useState(SCALE_MAX)

  const canProceed = projectName.trim().length > 0
  const areaActive = minArea > SCALE_MIN || maxArea < SCALE_MAX

  function handleNext() {
    if (!canProceed) return
    onNext({ projectName: projectName.trim(), minArea, maxArea })
  }

  return (
    <div style={{ height: 'calc(100vh - 64px)', overflow: 'hidden', background: 'var(--color-bg)', display: 'flex', flexDirection: 'column' }}>

      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-header-bg)',
        backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <button onClick={onBack} style={{
          background: 'none', border: 'none', color: 'var(--color-text-dim)',
          fontSize: 13, cursor: 'pointer', fontFamily: 'inherit',
        }}>← Back</button>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <span style={{ color: 'var(--color-text)', fontSize: 16, fontWeight: 700 }}>New Project</span>
        </div>
        <div style={{ width: 40 }} />
      </div>

      <div style={{ flex: 1, padding: '40px 24px 120px', maxWidth: 480, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 40 }}>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 10px' }}>
            Folder Name
          </p>
          <input
            type="text"
            value={projectName}
            onChange={e => setProjectName(e.target.value)}
            placeholder='e.g. "Graduation Project", "Museum References"'
            autoFocus
            style={{
              width: '100%', boxSizing: 'border-box',
              background: 'var(--color-surface-2)', color: 'var(--color-text)',
              border: '1px solid var(--color-border-soft)',
              borderRadius: 12, padding: '14px 16px',
              fontSize: 15, outline: 'none', fontFamily: 'inherit',
            }}
            onFocus={e => e.target.style.borderColor = '#ec4899'}
            onBlur={e => e.target.style.borderColor = 'var(--color-border-soft)'}
          />
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
            <p style={{ color: 'var(--color-text-muted)', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>
              Building Scale
            </p>
            {areaActive && (
              <button
                onClick={() => { setMinArea(SCALE_MIN); setMaxArea(SCALE_MAX) }}
                style={{ background: 'none', border: 'none', color: 'var(--color-text-dimmer)', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' }}
              >
                Reset
              </button>
            )}
          </div>

          <p style={{ color: areaActive ? '#f9a8d4' : 'var(--color-text-dim)', fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>
            {areaActive
              ? `${minArea.toLocaleString()} m² — ${maxArea.toLocaleString()} m²`
              : 'No limit'}
          </p>

          <DualRangeSlider
            min={SCALE_MIN} max={SCALE_MAX} step={SCALE_STEP}
            minVal={minArea} maxVal={maxArea}
            onChange={(lo, hi) => { setMinArea(lo); setMaxArea(hi) }}
            active={areaActive}
          />

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10 }}>
            {['Small', '', 'Medium', '', 'Large'].map((label, i) => (
              <span key={i} style={{ color: 'var(--color-text-dimmest)', fontSize: 10 }}>{label}</span>
            ))}
          </div>
        </div>

      </div>

      <div style={{
        position: 'fixed', bottom: 64, left: 0, right: 0,
        padding: '16px 20px',
        background: 'linear-gradient(to top, var(--color-bg) 70%, transparent)',
      }}>
        <button
          onClick={handleNext}
          disabled={!canProceed}
          style={{
            width: '100%', maxWidth: 480, display: 'block', margin: '0 auto',
            padding: '16px 0', borderRadius: 16, border: 'none',
            background: canProceed ? 'linear-gradient(135deg, #ec4899, #f43f5e)' : 'var(--color-progress-track)',
            color: canProceed ? '#fff' : 'var(--color-text-dimmer)',
            fontSize: 15, fontWeight: 700,
            cursor: canProceed ? 'pointer' : 'default',
            fontFamily: 'inherit',
          }}
        >
          Go to AI Search →
        </button>
      </div>

    </div>
  )
}

function DualRangeSlider({ min, max, step, minVal, maxVal, onChange, active }) {
  const pct = v => ((v - min) / (max - min)) * 100
  const fillLeft = pct(minVal)
  const fillRight = 100 - pct(maxVal)
  const minZ = minVal > max - step ? 3 : 1

  return (
    <div style={{ position: 'relative', height: 28 }}>
      <div style={{
        position: 'absolute', top: '50%', left: 0, right: 0,
        height: 4, background: 'var(--color-progress-track)', borderRadius: 2, transform: 'translateY(-50%)',
      }}>
        <div style={{
          position: 'absolute', top: 0, bottom: 0, borderRadius: 2,
          background: active ? 'linear-gradient(to right, #ec4899, #f43f5e)' : 'var(--color-text-dimmest)',
          left: `${fillLeft}%`, right: `${fillRight}%`,
          transition: 'background 0.2s',
        }} />
      </div>
      <input type="range" className="range-thumb" min={min} max={max} step={step}
        value={minVal} style={{ zIndex: minZ }}
        onChange={e => onChange(Math.min(Number(e.target.value), maxVal - step), maxVal)}
      />
      <input type="range" className="range-thumb" min={min} max={max} step={step}
        value={maxVal} style={{ zIndex: 2 }}
        onChange={e => onChange(minVal, Math.max(Number(e.target.value), minVal + step))}
      />
    </div>
  )
}
