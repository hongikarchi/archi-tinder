import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResults } from '../hooks/useResults.js'
import { resolveProjectBackendId } from '../utils/resolveProjectBackendId.js'
import { useTranslation } from '../i18n/index.js'
import { generateReport } from '../api/projects.js'
import ResultCards, { ResultsStage, ResultStateCard } from '../components/ResultCards.jsx'

// /result/:sessionId — 3 swipeable result cards (FULL-REPORT-UI-1 WP3, #445).
// Liked buildings + recommendations live on the shared report page
// (/board/:id/report), reached through the closing card's CTA.
export default function ResultsPage({ projects, setProjects, onReportGenerated, onLogout, onRequestSave }) {
  const navigate = useNavigate()
  const { sessionId } = useParams()
  const { t } = useTranslation()
  const { error, loading, project } = useResults(sessionId, projects, setProjects)
  const backendId = resolveProjectBackendId(project)
  const hasLikes = !!(project?.likedBuildings?.length)

  // Auto-repair: when the report is missing (e.g. a prior generation failure),
  // fire ONE generateReport call. Guarded by a ref so it fires at most once per
  // mount — a failure surfaces an inline error + retry button instead of
  // silently retrying forever.
  const reportRepairRef = useRef(false)
  const [reportRepairError, setReportRepairError] = useState(false)
  const [reportRepairing, setReportRepairing] = useState(false)

  function attemptReportRepair() {
    // No liked buildings yet → backend always 400s ('No liked buildings yet');
    // retrying can never succeed, so skip generation and fall through to the
    // neutral zero-likes card instead of a dead-end error+retry state.
    if (!backendId || project?.finalReport || reportRepairRef.current) return
    if (!(project?.likedBuildings?.length)) return
    reportRepairRef.current = true
    setReportRepairing(true)
    setReportRepairError(false)
    generateReport(backendId)
      .then(data => {
        if (data?.final_report) {
          setProjects(prev => prev.map(p => (
            p.id === project.id
              ? {
                  ...p,
                  finalReport: data.final_report,
                  ...(data.axis_scores ? { axisScores: data.axis_scores } : {}),
                }
              : p
          )))
          onReportGenerated?.(project, data)
        } else {
          setReportRepairError(true)
        }
      })
      .catch(err => {
        console.error('[ResultsPage] generateReport retry failed:', err)
        setReportRepairError(true)
      })
      .finally(() => {
        setReportRepairing(false)
      })
  }

  useEffect(() => {
    attemptReportRepair()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendId, project?.finalReport])

  function handleReportRetry() {
    reportRepairRef.current = false
    attemptReportRepair()
  }

  // Taste/swipe tab — same destination the other "continue exploring" paths use.
  const startExploring = () => navigate('/search')

  let content
  if (project?.finalReport && backendId) {
    // CTA: a temp board opens the save sheet (→ shared report page after saving);
    // an already-saved board goes straight to the shared report page.
    content = (
      <ResultCards
        project={project}
        backendId={backendId}
        ctaLabel={project.isTemp ? t('results.saveAndProfile') : t('results.goToProfile')}
        onCta={() => {
          if (project.isTemp) onRequestSave?.(project)
          else navigate(`/board/${backendId}/report`)
        }}
      />
    )
  } else if (!project) {
    // Unknown / invalid session: nothing to show. While the lookup is still
    // running show the skeleton; otherwise a neutral card that points back to exploring.
    content = loading && !error
      ? <ResultStateCard kind="loading" />
      : (
        <ResultStateCard
          kind="fail"
          title={t('results.reportError')}
          body={error === 'invalid_session_id' ? t('results.invalidSession') : t('results.reportErrorBody')}
          actionLabel={t('results.startExploring')}
          onAction={startExploring}
        />
      )
  } else if (reportRepairError || (hasLikes && !backendId && !loading)) {
    // Without a backend id retry is a no-op, so that sub-case points back to exploring.
    const canRetry = !!backendId
    content = (
      <ResultStateCard
        kind="fail"
        title={t('results.reportError')}
        body={t('results.reportErrorBody')}
        actionLabel={canRetry ? t('results.retry') : t('results.startExploring')}
        onAction={canRetry ? (reportRepairing ? undefined : handleReportRetry) : startExploring}
      />
    )
  } else if (!hasLikes) {
    content = (
      <ResultStateCard
        kind="empty"
        title={t('results.personaFallbackType')}
        body={t('results.personaFallbackLine')}
        hint={t('results.emptyHint')}
        actionLabel={t('results.startExploring')}
        onAction={startExploring}
      />
    )
  } else {
    content = <ResultStateCard kind="loading" />
  }

  return (
    <ResultsStage onLogout={onLogout} onBack={() => navigate('/')}>
      {content}
    </ResultsStage>
  )
}
