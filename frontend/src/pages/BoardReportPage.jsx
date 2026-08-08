import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import PersonaReport from '../components/PersonaReport.jsx'
import styles from './BoardReportPage.module.css'
import { useTranslation } from '../i18n/index.js'
import { generateReport } from '../api/projects.js'

/* ── BoardReportPage ────────────────────────────────────────────────────── */
export default function BoardReportPage() {
  const navigate = useNavigate()
  const { boardId } = useParams()
  const locationState = useLocation().state
  const { t } = useTranslation()

  const { board, loading } = useBoard(boardId)

  const [localReport, setLocalReport] = useState(null)
  const [localAxisScores, setLocalAxisScores] = useState(null)
  const [generating, setGenerating] = useState(false)
  const genRef = useRef(false)

  const report = board?.final_report || localReport

  useEffect(() => {
    if (!board) return
    if (board.final_report) return
    if (localReport) return
    if (genRef.current) return
    if (!board.liked_ids?.length) return

    genRef.current = true
    setGenerating(true)

    generateReport(boardId)
      .then(data => {
        setLocalReport(data.final_report)
        setLocalAxisScores(data.axis_scores || null)
      })
      .catch(err => {
        console.error('[BoardReportPage] generateReport failed:', err)
      })
      .finally(() => {
        setGenerating(false)
        genRef.current = false
      })
  }, [board, boardId, localReport])

  /* Loading state */
  if (loading) {
    return (
      <div className={styles.page} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 32, height: 32, borderRadius: '50%',
          border: '3px solid var(--color-border)',
          borderTopColor: '#ec4899',
          animation: 'spin 1.2s linear infinite',
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  /* Board not found */
  if (!board) {
    return (
      <div className={styles.page} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: '40px 20px' }}>
        <p style={{ color: 'var(--color-text-muted)', fontSize: 16, fontWeight: 600, margin: 0 }}>
          {t('board.notFound')}
        </p>
        <button
          onClick={() => navigate(-1)}
          style={{
            padding: '10px 24px',
            borderRadius: 999,
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          {t('board.back')}
        </button>
      </div>
    )
  }

  /* Generating report — show spinner identical to loading spinner */
  if (generating) {
    return (
      <div className={styles.page} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 32, height: 32, borderRadius: '50%',
          border: '3px solid var(--color-border)',
          borderTopColor: '#ec4899',
          animation: 'spin 1.2s linear infinite',
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  /* No report available (generation failed or no liked buildings) */
  if (!report) {
    return (
      <div className={styles.page} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: '40px 20px' }}>
        <p style={{ color: 'var(--color-text-muted)', fontSize: 16, fontWeight: 600, margin: 0 }}>
          {t('board.noReport')}
        </p>
        <button
          onClick={() => navigate(-1)}
          style={{
            padding: '10px 24px',
            borderRadius: 999,
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          {t('board.back')}
        </button>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        {/* 뒤로가기 */}
        <button
          onClick={() => navigate(`/board/${boardId}`)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'none',
            border: 'none',
            color: 'var(--color-text-muted)',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            padding: '0 0 20px',
            fontFamily: 'inherit',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          {t('board.backToDetail')}
        </button>

        <PersonaReport
          boardId={boardId}
          finalReport={report}
          axisScores={locationState?.axisScores || localAxisScores || board?.axis_scores || null}
          reportImage={board?.report_image || null}
          reportImageMime={board?.report_image_mime || null}
        />
      </div>
    </div>
  )
}
