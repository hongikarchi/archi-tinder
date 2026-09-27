import { useState, useEffect, Fragment } from 'react'
import { generateReport, generateReportImage } from '../api/projects.js'
import TasteSpectrum from './TasteSpectrum.jsx'
import { useTranslation } from '../i18n/index.js'
import { localizeReport } from '../utils/reportText.js'

/* ── Constants ──────────────────────────────────────────────────────────── */
// Form is intentionally excluded — see TasteSpectrum.jsx.
const DEFAULT_AXES = { materiality: 0, scale: 0, energy: 0, tradition: 0 }

/* ── PersonaReport ──────────────────────────────────────────────────────── */
/**
 * Props:
 *   boardId         string  - API 호출에 사용 (null이면 재생성 버튼 비활성화)
 *   canRegenerate   bool    - 뷰어가 이 보드의 소유자인가. false면 이미지/리포트
 *                             재생성 버튼을 아예 렌더하지 않는다 — 남의 리포트를
 *                             덮어쓰는 조작이므로 비활성 표시가 아니라 제거.
 *                             기본 true: 소유자 화면(ResultsPage 등) 호출부 무영향.
 *   finalReport     object  - { persona_type, one_liner, description, pattern_paragraph, dominant_programs, dominant_styles, dominant_materials }
 *   axisScores      object  - { materiality, scale, energy, tradition }; each value is
 *                             null | number (legacy) | { score, dots, n, iqr, confidence }
 *                             (null이면 DEFAULT_AXES 사용). form은 표시하지 않음 — TasteSpectrum.jsx 참조.
 *   reportImage     string  - base64 이미지 데이터 (null 가능)
 *   reportImageMime string  - 예: 'image/png'
 *   onReportUpdate  func    - optional. (data: { final_report, axis_scores }) => void
 *                             called after a successful regenerate so the parent
 *                             (e.g. ResultsPage) can persist the fresh report into
 *                             its own project state — otherwise a remount/navigate
 *                             back re-renders the stale pre-regenerate report.
 */
export default function PersonaReport({ boardId, finalReport, axisScores, reportImage, reportImageMime,
  onReportUpdate, canRegenerate = true }) {
  const { t, language } = useTranslation()
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

  // localizeReport swaps persona_type/one_liner/pattern_paragraph/description
  // to the current UI language from report.i18n when present — instant, no
  // API call. Old single-language reports (no i18n block) pass through as-is.
  const report = localizeReport(localReport || finalReport || {}, language)
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

      {/* 패턴 문단 — 스와이프 패턴에 대한 사실적 설명. description 위에 표시.
          구버전 리포트(pattern_paragraph 없음)는 그대로 description만 렌더. */}
      {report.pattern_paragraph && (
        <p style={{
          color: 'var(--color-text-dim)',
          fontSize: 14,
          lineHeight: 1.65,
          margin: '0 0 12px',
        }}>
          {report.pattern_paragraph}
        </p>
      )}

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
            background: 'color-mix(in srgb, var(--accent-2) 10%, transparent)',
            border: '1px solid color-mix(in srgb, var(--accent-2) 22%, transparent)',
            color: 'var(--accent-2)',
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
            background: 'var(--color-tag-bg)',
            border: '1px solid var(--color-tag-border)',
            color: 'var(--color-tag-label)',
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

      {/* 취향 스펙트럼 범례 */}
      <p style={{
        color: 'var(--color-text-muted)',
        fontSize: 12,
        lineHeight: 1.6,
        margin: '0 0 16px',
      }}>
        {t('persona.spectrumLegend').split('\n').map((line, i, arr) => (
          <Fragment key={i}>
            {line}
            {i < arr.length - 1 && <br />}
          </Fragment>
        ))}
      </p>

      {/* 양극 스펙트럼 시각화 */}
      <div style={{ marginBottom: 24 }}>
        <TasteSpectrum axisScores={scores} />
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

      {/* Regenerate controls — owner only.
          These POST to the board's project (image + report overwrite), so a
          non-owner must not merely see them disabled; they are not rendered.
          The report itself stays fully readable either way. */}
      {canRegenerate && (<>
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
            : 'var(--accent-1)',
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
      </>)}
    </>
  )
}
