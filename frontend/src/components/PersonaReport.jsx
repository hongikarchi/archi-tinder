import { useState, useEffect } from 'react'
import { generateReport, generateReportImage } from '../api/projects.js'
import styles from '../pages/BoardReportPage.module.css'
import { useTranslation } from '../i18n/index.js'

/* ── RadarChart ─────────────────────────────────────────────────────────── */
function RadarChart({ scores }) {
  const { t } = useTranslation()
  const cx = 100, cy = 100, R = 80
  const axes = [
    { key: 'form' },
    { key: 'materiality' },
    { key: 'scale' },
    { key: 'energy' },
    { key: 'tradition' },
  ]
  const N = axes.length
  const angle = (i) => (Math.PI * 2 * i) / N - Math.PI / 2

  const toXY = (i, r) => ({
    x: cx + r * Math.cos(angle(i)),
    y: cy + r * Math.sin(angle(i)),
  })

  const gridLevels = [0.25, 0.5, 0.75, 1.0]

  const gridPoints = (level) =>
    axes.map((_, i) => toXY(i, R * level))
      .map(p => `${p.x},${p.y}`)
      .join(' ')

  // score -1.0~1.0 → r 0~R
  const valuePoints = axes
    .map((ax, i) => {
      const s = scores[ax.key] ?? 0
      const r = R * (s + 1.0) / 2.0
      return toXY(i, r)
    })
    .map(p => `${p.x},${p.y}`)
    .join(' ')

  return (
    <svg viewBox="0 0 200 200" width="200" height="200">
      {/* 그리드 */}
      {gridLevels.map(level => (
        <polygon
          key={level}
          points={gridPoints(level)}
          fill="none"
          stroke="var(--color-border-soft)"
          strokeWidth="0.8"
        />
      ))}
      {/* 축선 */}
      {axes.map((_, i) => {
        const outer = toXY(i, R)
        return (
          <line
            key={i}
            x1={cx} y1={cy}
            x2={outer.x} y2={outer.y}
            stroke="var(--color-border-soft)"
            strokeWidth="0.8"
          />
        )
      })}
      {/* 값 폴리곤 */}
      <polygon
        points={valuePoints}
        style={{
          fill: 'color-mix(in srgb, var(--accent-1) 20%, transparent)',
          stroke: 'var(--accent-1)',
        }}
        strokeWidth="1.5"
      />
      {/* 레이블 */}
      {axes.map((ax, i) => {
        const labelR = R + 16
        const pos = toXY(i, labelR)
        return (
          <text
            key={ax.key}
            x={pos.x}
            y={pos.y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="9"
            fill="var(--color-text-muted)"
            fontWeight="600"
          >
            {t(`persona.axis.${ax.key}`)}
          </text>
        )
      })}
    </svg>
  )
}

/* ── Constants ──────────────────────────────────────────────────────────── */
const DEFAULT_AXES = { form: 0, materiality: 0, scale: 0, energy: 0, tradition: 0 }

const SPECTRUM_AXES = [
  { key: 'form',        leftKey: 'persona.spectrum.form.left',        rightKey: 'persona.spectrum.form.right' },
  { key: 'materiality', leftKey: 'persona.spectrum.materiality.left', rightKey: 'persona.spectrum.materiality.right' },
  { key: 'scale',       leftKey: 'persona.spectrum.scale.left',       rightKey: 'persona.spectrum.scale.right' },
  { key: 'energy',      leftKey: 'persona.spectrum.energy.left',      rightKey: 'persona.spectrum.energy.right' },
  { key: 'tradition',   leftKey: 'persona.spectrum.tradition.left',   rightKey: 'persona.spectrum.tradition.right' },
]

/* ── PersonaReport ──────────────────────────────────────────────────────── */
/**
 * Props:
 *   boardId         string  - API 호출에 사용 (null이면 재생성 버튼 비활성화)
 *   finalReport     object  - { persona_type, one_liner, description, dominant_programs, dominant_styles, dominant_materials }
 *   axisScores      object  - { form, materiality, scale, energy, tradition } (null이면 DEFAULT_AXES 사용)
 *   reportImage     string  - base64 이미지 데이터 (null 가능)
 *   reportImageMime string  - 예: 'image/png'
 *   onReportUpdate  func    - optional. (data: { final_report, axis_scores }) => void
 *                             called after a successful regenerate so the parent
 *                             (e.g. ResultsPage) can persist the fresh report into
 *                             its own project state — otherwise a remount/navigate
 *                             back re-renders the stale pre-regenerate report.
 */
export default function PersonaReport({ boardId, finalReport, axisScores, reportImage, reportImageMime, onReportUpdate }) {
  const { t } = useTranslation()
  const [localImage, setLocalImage] = useState(reportImage || null)
  const [localMime, setLocalMime] = useState(reportImageMime || null)
  const [localAxisScores, setLocalAxisScores] = useState(axisScores || DEFAULT_AXES)
  const [localReport, setLocalReport] = useState(null)
  const [imgGenLoading, setImgGenLoading] = useState(false)
  const [imgError, setImgError] = useState(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState(null)

  // Sync when props change (e.g. image loads asynchronously after initial render)
  useEffect(() => { if (axisScores) setLocalAxisScores(axisScores) }, [axisScores])
  useEffect(() => { if (reportImage) setLocalImage(reportImage) }, [reportImage])
  useEffect(() => { if (reportImageMime) setLocalMime(reportImageMime) }, [reportImageMime])

  const report = localReport || finalReport || {}
  const scores = localAxisScores

  async function handleGenerateImage() {
    if (imgGenLoading || !boardId) return
    setImgGenLoading(true)
    setImgError(null)
    try {
      // Explicit user intent (button click) must bypass the backend cache.
      const res = await generateReportImage(boardId, { regenerate: true })
      if (res?.image_data) {
        setLocalImage(res.image_data)
        if (res.mime_type) setLocalMime(res.mime_type)
      } else {
        setImgError(t('persona.imgError'))
      }
    } catch (e) {
      setImgError(e?.data?.detail || e?.message || t('persona.imgError'))
    } finally {
      setImgGenLoading(false)
    }
  }

  async function handleRegenerateReport() {
    if (reportLoading || !boardId) return
    setReportLoading(true)
    setReportError(null)
    try {
      // Explicit user intent (button click) must bypass the backend cache.
      const res = await generateReport(boardId, { regenerate: true })
      if (res?.final_report) setLocalReport(res.final_report)
      if (res?.axis_scores) setLocalAxisScores(res.axis_scores)
      if (res?.final_report || res?.axis_scores) {
        onReportUpdate?.({ final_report: res.final_report, axis_scores: res.axis_scores })
      }
    } catch {
      setReportError(t('persona.reportError'))
    } finally {
      setReportLoading(false)
    }
  }

  return (
    <>
      {/* PERSONA REPORT 레이블 */}
      <p style={{
        color: 'var(--color-text-muted)',
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        margin: '0 0 8px',
      }}>
        Persona Report
      </p>

      {/* 페르소나 이름 */}
      <h1 style={{
        color: 'var(--color-text)',
        fontSize: 'clamp(24px, 5vw, 32px)',
        fontWeight: 700,
        margin: '0 0 8px',
        lineHeight: 1.15,
      }}>
        {report.persona_type}
      </h1>

      {/* 한 줄 설명 */}
      <p style={{
        color: 'var(--accent-1)',
        fontSize: 15,
        fontWeight: 600,
        margin: '0 0 12px',
        lineHeight: 1.5,
      }}>
        {report.one_liner}
      </p>

      {/* 상세 description */}
      {report.description && (
        <p style={{
          color: 'var(--color-text-dim)',
          fontSize: 14,
          lineHeight: 1.65,
          margin: '0 0 16px',
        }}>
          {report.description}
        </p>
      )}

      {/* 태그 목록 */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 24 }}>
        {(report.dominant_programs || []).map(tag => (
          <span key={tag} style={{
            padding: '4px 10px',
            borderRadius: 999,
            background: 'color-mix(in srgb, var(--accent-1) 10%, transparent)',
            border: '1px solid color-mix(in srgb, var(--accent-1) 22%, transparent)',
            color: 'var(--accent-1)',
            fontSize: 11,
            fontWeight: 700,
          }}>
            {tag}
          </span>
        ))}
        {(report.dominant_styles || []).map(tag => (
          <span key={tag} style={{
            padding: '4px 10px',
            borderRadius: 999,
            background: 'rgba(99,102,241,0.1)',
            border: '1px solid rgba(99,102,241,0.22)',
            color: 'var(--color-text-dim)',
            fontSize: 11,
            fontWeight: 700,
          }}>
            {tag}
          </span>
        ))}
        {(report.dominant_materials || []).map(tag => (
          <span key={tag} style={{
            padding: '4px 10px',
            borderRadius: 999,
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid var(--color-border-soft)',
            color: 'var(--color-text-dim)',
            fontSize: 11,
            fontWeight: 700,
          }}>
            {tag}
          </span>
        ))}
      </div>

      {/* 구분선 */}
      <div style={{ height: 1, background: 'var(--color-border)', marginBottom: 24 }} />

      {/* 취향 분석 섹션 */}
      <h2 style={{
        color: 'var(--color-text)',
        fontSize: 16,
        fontWeight: 700,
        margin: '0 0 20px',
        letterSpacing: '-0.01em',
      }}>
        {t('persona.tasteSection')}
      </h2>

      {/* 레이더 차트 */}
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
        <RadarChart scores={scores} />
      </div>

      {/* 양극 스펙트럼 바 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 24 }}>
        {SPECTRUM_AXES.map(ax => {
          const score = scores[ax.key] ?? 0
          const pct = ((score + 1) / 2) * 100
          return (
            <div key={ax.key}>
              <p style={{
                color: 'var(--color-text)',
                fontSize: 13,
                fontWeight: 600,
                margin: '0 0 4px',
              }}>
                {t(`persona.axis.${ax.key}`)}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--color-text-muted)', fontSize: 10, fontWeight: 600, minWidth: 48, textAlign: 'right' }}>
                  {t(ax.leftKey)}
                </span>
                <div className={styles.spectrumBar} style={{ flex: 1 }}>
                  <div
                    className={styles.spectrumDot}
                    style={{ left: `${pct}%` }}
                  />
                </div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: 10, fontWeight: 600, minWidth: 48 }}>
                  {t(ax.rightKey)}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* 구분선 */}
      <div style={{ height: 1, background: 'var(--color-border)', marginBottom: 24 }} />

      {/* 이미지 생성 영역 */}
      <h2 style={{
        color: 'var(--color-text)',
        fontSize: 16,
        fontWeight: 700,
        margin: '0 0 16px',
        letterSpacing: '-0.01em',
      }}>
        {t('persona.imageSection')}
      </h2>

      {localImage ? (
        <div style={{ position: 'relative', marginBottom: 14 }}>
          <img
            src={`data:${localMime || 'image/png'};base64,${localImage}`}
            alt="Persona"
            style={{
              width: '100%',
              minHeight: 200,
              objectFit: 'cover',
              borderRadius: 12,
              display: 'block',
            }}
          />
          <a
            href={`data:${localMime || 'image/png'};base64,${localImage}`}
            download={`persona-${boardId || 'report'}.${(localMime || 'image/png').split('/')[1] || 'png'}`}
            style={{
              position: 'absolute',
              bottom: 10,
              right: 10,
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '7px 14px',
              borderRadius: 999,
              background: 'var(--color-scrim-soft)',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
              color: '#fff',
              fontSize: 12,
              fontWeight: 700,
              textDecoration: 'none',
              fontFamily: 'inherit',
              border: '1px solid rgba(255,255,255,0.18)',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            {t('persona.imageSave')}
          </a>
        </div>
      ) : (
        <div style={{
          width: '100%',
          height: 200,
          borderRadius: 12,
          background: 'var(--color-surface-2)',
          border: '2px dashed var(--color-border-soft)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 14,
        }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
        </div>
      )}

      <button
        type="button"
        onClick={handleGenerateImage}
        disabled={imgGenLoading || !boardId}
        style={{
          width: '100%',
          minHeight: 44,
          padding: '12px 24px',
          borderRadius: 999,
          background: (imgGenLoading || !boardId)
            ? 'var(--color-surface-2)'
            : 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
          color: (imgGenLoading || !boardId) ? 'var(--color-text-muted)' : '#fff',
          border: 'none',
          fontSize: 14,
          fontWeight: 700,
          cursor: (imgGenLoading || !boardId) ? 'default' : 'pointer',
          fontFamily: 'inherit',
          marginBottom: 16,
        }}
      >
        {imgGenLoading ? t('persona.imgGenerating') : localImage ? t('persona.imgRegenerate') : t('persona.imgGenerate')}
      </button>

      {imgError && (
        <p style={{ color: 'var(--color-destructive, #ef4444)', fontSize: 12, marginBottom: 12, lineHeight: 1.5 }}>
          {imgError}
        </p>
      )}

      {/* 리포트 재생성 버튼 */}
      <button
        type="button"
        onClick={handleRegenerateReport}
        disabled={reportLoading || !boardId}
        style={{
          width: '100%',
          minHeight: 44,
          padding: '12px 24px',
          borderRadius: 999,
          background: 'var(--color-surface)',
          color: 'var(--color-text-muted)',
          border: '1px solid var(--color-border)',
          fontSize: 13,
          fontWeight: 600,
          cursor: (reportLoading || !boardId) ? 'default' : 'pointer',
          fontFamily: 'inherit',
        }}
      >
        {reportLoading ? t('persona.reportRegenerating') : t('persona.reportRegenerate')}
      </button>

      {reportError && (
        <p style={{
          color: 'var(--color-destructive, #D73A49)',
          fontSize: 13,
          fontWeight: 600,
          margin: '10px 0 0',
          textAlign: 'center',
        }}>
          {reportError}
        </p>
      )}
    </>
  )
}
