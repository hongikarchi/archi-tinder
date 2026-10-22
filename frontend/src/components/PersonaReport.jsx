import { useState } from 'react'
import { PersonaReportBody } from './PersonaReportPage.jsx'
import { useRegeneration } from '../hooks/useRegeneration.jsx'

/**
 * PersonaReport — thin compatibility wrapper around the shared report page
 * body (PersonaReportPage.jsx). Kept so ResultsPage keeps building until the
 * result-cards work (WP3) replaces it. Renders the owner view (the ResultsPage
 * caller is the project owner).
 *
 * Regeneration is behaviour-preserving: image refresh + the footer "리포트 재생성"
 * link come from useRegeneration. After a successful report regeneration the
 * new report/axis scores are kept in local state (shown immediately) and also
 * handed to `onReportUpdate({ final_report, axis_scores })` so the caller can
 * persist them into its own project state.
 */
export default function PersonaReport({
  boardId, finalReport, axisScores, reportImage, reportImageMime,
  onReportUpdate, canRegenerate = true,
}) {
  const [localReport, setLocalReport] = useState(null)
  const [localAxisScores, setLocalAxisScores] = useState(null)

  const report = localReport || finalReport
  const scores = localAxisScores || axisScores

  const regen = useRegeneration({
    projectId: boardId,
    enabled: canRegenerate,
    axisScores: scores,
    onReportRegenerated: data => {
      setLocalReport(data.final_report)
      setLocalAxisScores(data.axis_scores || null)
      onReportUpdate?.({ final_report: data.final_report, axis_scores: data.axis_scores })
    },
  })

  return (
    <>
      <PersonaReportBody
        role="owner"
        boardId={boardId}
        finalReport={report}
        axisScores={scores}
        reportImage={reportImage}
        reportImageMime={reportImageMime}
        {...regen.imageProps}
        {...regen.reportProps}
      />
      {regen.overlay}
    </>
  )
}
