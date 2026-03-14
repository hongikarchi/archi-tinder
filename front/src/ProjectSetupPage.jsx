import { useState } from 'react'

const SCALE_MIN = 0
const SCALE_MAX = 100000
const SCALE_STEP = 1000

export default function ProjectSetupPage({ onBack, onNext }) {
  const [projectName, setProjectName] = useState('')
  const [minArea, setMinArea] = useState(SCALE_MIN)
  const [maxArea, setMaxArea] = useState(SCALE_MAX)

  const canProceed = projectName.trim().length > 0

  function handleNext() {
    if (!canProceed) return
    onNext({ projectName: projectName.trim(), minArea, maxArea })
  }

  const areaActive = minArea > SCALE_MIN || maxArea < SCALE_MAX

  return (
    <div style={{ minHeight: '100vh', background: '#0f0f0f', display: 'flex', flexDirection: 'column' }}>

      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        background: 'rgba(15,17,21,0.9)',
        backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <button onClick={onBack} style={{
          background: 'none', border: 'none', color: '#6b7280',
          fontSize: 13, cursor: 'pointer', fontFamily: 'inherit',
        }}>← 뒤로</button>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <span style={{ color: '#fff', fontSize: 16, fontWeight: 700 }}>새 프로젝트</span>
        </div>
        <div style={{ width: 40 }} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, padding: '40px 24px 120px', maxWidth: 480, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>

        {/* 폴더 이름 */}
        <div style={{ marginBottom: 40 }}>
          <p style={{ color: '#9ca3af', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 10px' }}>
            폴더 이름
          </p>
          <input
            type="text"
            value={projectName}
            onChange={e => setProjectName(e.target.value)}
            placeholder='예: "졸업 프로젝트", "미술관 레퍼런스"'
            autoFocus
            style={{
              width: '100%', boxSizing: 'border-box',
              background: '#1c1c1c', color: '#fff',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 12, padding: '14px 16px',
              fontSize: 15, outline: 'none', fontFamily: 'inherit',
            }}
            onFocus={e => e.target.style.borderColor = 'rgba(255,255,255,0.3)'}
            onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
          />
        </div>

        {/* 규모 슬라이더 */}
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
            <p style={{ color: '#9ca3af', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>
              건물 규모
            </p>
            {areaActive && (
              <button
                onClick={() => { setMinArea(SCALE_MIN); setMaxArea(SCALE_MAX) }}
                style={{ background: 'none', border: 'none', color: '#4b5563', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' }}
              >
                초기화
              </button>
            )}
          </div>

          <p style={{ color: areaActive ? '#a5b4fc' : '#6b7280', fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>
            {areaActive
              ? `${minArea.toLocaleString()} m² — ${maxArea.toLocaleString()} m²`
              : '제한 없음'}
          </p>

          <DualRangeSlider
            min={SCALE_MIN} max={SCALE_MAX} step={SCALE_STEP}
            minVal={minArea} maxVal={maxArea}
            onChange={(lo, hi) => { setMinArea(lo); setMaxArea(hi) }}
            active={areaActive}
          />

          {/* 규모 레이블 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10 }}>
            {['소규모', '', '중규모', '', '대규모'].map((label, i) => (
              <span key={i} style={{ color: '#374151', fontSize: 10 }}>{label}</span>
            ))}
          </div>
        </div>

      </div>

      {/* 하단 버튼 */}
      <div style={{
        position: 'fixed', bottom: 64, left: 0, right: 0,
        padding: '16px 20px',
        background: 'linear-gradient(to top, #0f0f0f 70%, transparent)',
      }}>
        <button
          onClick={handleNext}
          disabled={!canProceed}
          style={{
            width: '100%', maxWidth: 480, display: 'block', margin: '0 auto',
            padding: '16px 0', borderRadius: 16, border: 'none',
            background: canProceed ? 'linear-gradient(135deg, #3b82f6, #8b5cf6)' : '#1f2937',
            color: canProceed ? '#fff' : '#4b5563',
            fontSize: 15, fontWeight: 700,
            cursor: canProceed ? 'pointer' : 'default',
            fontFamily: 'inherit',
          }}
        >
          AI 검색으로 이동 →
        </button>
      </div>

    </div>
  )
}

/* ── Dual Range Slider ───────────────────────────────────────────────────── */
function DualRangeSlider({ min, max, step, minVal, maxVal, onChange, active }) {
  const pct = v => ((v - min) / (max - min)) * 100
  const fillLeft = pct(minVal)
  const fillRight = 100 - pct(maxVal)
  const minZ = minVal > max - step ? 3 : 1

  return (
    <div style={{ position: 'relative', height: 28 }}>
      <div style={{
        position: 'absolute', top: '50%', left: 0, right: 0,
        height: 4, background: '#1f2937', borderRadius: 2, transform: 'translateY(-50%)',
      }}>
        <div style={{
          position: 'absolute', top: 0, bottom: 0, borderRadius: 2,
          background: active ? 'linear-gradient(to right, #3b82f6, #8b5cf6)' : '#374151',
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
