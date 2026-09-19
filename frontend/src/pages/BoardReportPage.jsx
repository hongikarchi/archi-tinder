import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import PersonaReport from '../components/PersonaReport.jsx'
import styles from './BoardReportPage.module.css'
import { useTranslation } from '../i18n/index.js'
import { generateReport } from '../api/projects.js'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'

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

  // Ownership. Same derivation as BoardDetailPage (viewer id from sessionStorage
  // vs the board's owner id) so both pages agree on who owns a board.
  const viewerId = sessionStorage.getItem('archithon_user')
  const boardOwnerId = board?.user?.user_id ?? board?.owner?.user_id
  const isOwner = !!viewerId && String(boardOwnerId) === String(viewerId)

  const report = board?.final_report || localReport
  // Auto-generate condition, computed once and reused for both the effect
  // guard AND the render branch below — this is what avoids the first-paint
  // flash: while the condition holds but the effect (fired via useEffect,
  // one tick after paint) hasn't run yet, we still render the spinner
  // instead of the noReport state.
  //
  // isOwner gate: without it, opening someone else's report-less board fired
  // generateReport against THEIR project — a write on another user's data
  // (and a Gemini call) triggered just by viewing. Non-owners now fall through
  // to the existing no-report state instead.
  const shouldAutoGenerate = !!(
    isOwner && board && !report && !genError && board.liked_ids?.length > 0
  )

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
        <PageBackButton onClick={() => navigate(-1)} />
        <PageTopControls onLogout={onLogout} />
        <p style={{ color: 'var(--color-text-muted)', fontSize: 16, fontWeight: 600, margin: 0 }}>
          {t('board.notFound')}
        </p>
      </div>
    )
  }

  /* Auto-generate failed — distinct copy + retry from the "no report at all" state */
  if (genError) {
    return (
      <div className={styles.page} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: '40px 20px' }}>
        <PageBackButton onClick={() => navigate(-1)} />
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
        </div>
      </div>
    )
  }

  /* No report available (no liked buildings — generation never attempted) */
  if (!report) {
    return (
      <div className={styles.page} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: '40px 20px' }}>
        <PageBackButton onClick={() => navigate(-1)} />
        <PageTopControls onLogout={onLogout} />
        <p style={{ color: 'var(--color-text-muted)', fontSize: 16, fontWeight: 600, margin: 0 }}>
          {t('board.noReport')}
        </p>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <PageBackButton onClick={() => navigate(`/board/${boardId}`)} label={t('board.backToDetail')} />
      <PageLogoHeader />
      <PageTopControls onLogout={onLogout} />
      <div className={styles.container}>
        <PersonaReport
          boardId={boardId}
          canRegenerate={isOwner}
          finalReport={report}
          axisScores={locationState?.axisScores || localAxisScores || board?.axis_scores || null}
          reportImage={board?.report_image || null}
          reportImageMime={board?.report_image_mime || null}
        />
      </div>
    </div>
  )
}
