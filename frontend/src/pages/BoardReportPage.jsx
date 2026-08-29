import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import PersonaReport from '../components/PersonaReport.jsx'
import styles from './BoardReportPage.module.css'
import { useTranslation } from '../i18n/index.js'
import { generateReport } from '../api/projects.js'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'

function Spinner() {
  return (
    <div style={{
      width: 32, height: 32, borderRadius: '50%',
      border: '3px solid var(--color-border)',
      borderTopColor: 'var(--accent-1)',
      animation: 'spin 1.2s linear infinite',
    }} />
  )
}

/* ── BoardReportPage ────────────────────────────────────────────────────── */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export default function BoardReportPage({ onLogout }) {
  const navigate = useNavigate()
  const { boardId: rawBoardId } = useParams()
  // Same gate as BoardDetailPage: malformed URL param → null, never reaches the API layer.
  const boardId = UUID_RE.test(String(rawBoardId || '')) ? rawBoardId : null
  const locationState = useLocation().state
  const { t } = useTranslation()

  const { board, loading } = useBoard(boardId)

  const [localReport, setLocalReport] = useState(null)
  const [localAxisScores, setLocalAxisScores] = useState(null)
  const [genError, setGenError] = useState(false)
  const genRef = useRef(false)

  const report = board?.final_report || localReport
  // Auto-generate condition, computed once and reused for both the effect
  // guard AND the render branch below — this is what avoids the first-paint
  // flash: while the condition holds but the effect (fired via useEffect,
  // one tick after paint) hasn't run yet, we still render the spinner
  // instead of the noReport state.
  const shouldAutoGenerate = !!(board && !report && !genError && board.liked_ids?.length > 0)

  useEffect(() => {
    if (!shouldAutoGenerate) return
    if (genRef.current) return
    genRef.current = true

    generateReport(boardId)
      .then(data => {
        if (data?.final_report) {
          setLocalReport(data.final_report)
          setLocalAxisScores(data.axis_scores || null)
        } else {
          setGenError(true)
        }
      })
      .catch(err => {
        console.error('[BoardReportPage] generateReport failed:', err)
        setGenError(true)
      })
    // No finally-reset of genRef — auto-generate fires at most once per mount.
    // Retry is user-initiated via the button below (handleRetry resets the ref).
  }, [shouldAutoGenerate, boardId])

  function handleRetry() {
    genRef.current = false
    setGenError(false)
  }

  /* Loading state (board fetch) OR auto-generate in flight (incl. pre-effect paint) */
  if (loading || shouldAutoGenerate) {
    return (
      <div className={styles.page} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <PageTopControls onLogout={onLogout} />
        <Spinner />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  /* Board not found */
  if (!board) {
    return (
      <div className={styles.page} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: '40px 20px' }}>
        <PageTopControls onLogout={onLogout} />
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

  /* Auto-generate failed — distinct copy + retry from the "no report at all" state */
  if (genError) {
    return (
      <div className={styles.page} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: '40px 20px' }}>
        <PageTopControls onLogout={onLogout} />
        <p style={{ color: 'var(--color-destructive, #D73A49)', fontSize: 16, fontWeight: 600, margin: 0, textAlign: 'center' }}>
          {t('board.reportGenError')}
        </p>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={handleRetry}
            style={{
              padding: '10px 24px',
              borderRadius: 999,
              background: 'var(--accent-1)',
              border: 'none',
              color: '#fff',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {t('board.retry')}
          </button>
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
      </div>
    )
  }

  /* No report available (no liked buildings — generation never attempted) */
  if (!report) {
    return (
      <div className={styles.page} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: '40px 20px' }}>
        <PageTopControls onLogout={onLogout} />
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
      <PageLogoHeader />
      <PageTopControls onLogout={onLogout} />
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
