import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import PersonaReportPage from '../components/PersonaReportPage.jsx'
import { useTranslation } from '../i18n/index.js'
import { generateReport, getProjectRecommendations } from '../api/projects.js'
import { useRegeneration } from '../hooks/useRegeneration.jsx'

/* ── BoardReportPage ────────────────────────────────────────────────────── */
// Data + ownership for /board/:boardId/report; all rendering (report body and
// the loading / failure / empty / unavailable states) is the shared
// PersonaReportPage component.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function cardId(card) {
  return card?.image_id || card?.canonical_bld_id || card?.building_id || ''
}

export default function BoardReportPage({ onLogout }) {
  const navigate = useNavigate()
  const { boardId: rawBoardId } = useParams()
  // Same gate as BoardDetailPage: malformed URL param → null, never reaches the API layer.
  const boardId = UUID_RE.test(String(rawBoardId || '')) ? rawBoardId : null
  const location = useLocation()
  const locationState = location.state
  const { t } = useTranslation()

  // Recommendations come from the project-recommendations endpoint (owner AND
  // public-board viewers), not the owner-only session result.
  const { board, loading, error: boardError, reload: reloadBoard } = useBoard(boardId, { fetchResult: false })

  const [localReport, setLocalReport] = useState(null)
  const [localAxisScores, setLocalAxisScores] = useState(null)
  const [genError, setGenError] = useState(false)
  const [recommendations, setRecommendations] = useState([])
  const genRef = useRef(false)

  // Ownership. Same derivation as BoardDetailPage (viewer id from sessionStorage
  // vs the board's owner id) so both pages agree on who owns a board.
  const viewerId = sessionStorage.getItem('archithon_user')
  const boardOwnerId = board?.user?.user_id ?? board?.owner?.user_id
  const isOwner = !!viewerId && String(boardOwnerId) === String(viewerId)

  // localReport (auto-generated or regenerated) wins over the fetched board copy.
  const report = localReport || board?.final_report
  const axisScores = localAxisScores || locationState?.axisScores || board?.axis_scores || null
  // Auto-generate condition, computed once and reused for both the effect
  // guard AND the render branch below — avoids the first-paint flash: while the
  // condition holds but the effect (one tick after paint) hasn't run yet, we
  // still render the "making" skeleton instead of the noReport state.
  //
  // isOwner gate: without it, opening someone else's report-less board fired
  // generateReport against THEIR project — a write on another user's data
  // (and a Gemini call) triggered just by viewing.
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
    // Retry is user-initiated (handleRetry resets the ref).
  }, [shouldAutoGenerate, boardId])

  // Recommendations: fetched once the board is known to be viewable. A failed
  // or empty fetch just hides the section.
  const hasBoard = !!board
  useEffect(() => {
    if (!boardId || !hasBoard) return
    let cancelled = false
    getProjectRecommendations(boardId)
      .then(cards => { if (!cancelled) setRecommendations(cards) })
      .catch(() => { if (!cancelled) setRecommendations([]) })
    return () => { cancelled = true }
  }, [boardId, hasBoard])

  // Owner-only image + report regeneration (viewers get no handlers, so no POST).
  const regen = useRegeneration({
    projectId: boardId,
    enabled: isOwner,
    axisScores,
    onReportRegenerated: data => {
      setLocalReport(data.final_report)
      setLocalAxisScores(data.axis_scores || null)
    },
  })

  // Post-save landing (App.handleBoardSaved navigates with state.saved): toast once,
  // then drop the flag so back/forward doesn't replay it. Waits for ownership
  // because the toast host lives in the owner-only regeneration overlay.
  const savedRef = useRef(!!locationState?.saved)
  const { showToast } = regen
  useEffect(() => {
    if (!savedRef.current || !isOwner) return
    savedRef.current = false
    showToast(t('results.savedToast'))
    const { saved: _saved, ...rest } = locationState || {}
    navigate(location.pathname, { replace: true, state: Object.keys(rest).length ? rest : null })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOwner])

  // 403/404 = private or missing board ("unavailable"); any other failure
  // (network, 5xx, timeout) is a retryable load failure.
  const boardGone = boardError?.status === 403 || boardError?.status === 404
  const loadFailed = !!boardError && !board && !boardGone

  function handleRetry() {
    if (loadFailed) {
      reloadBoard()
      return
    }
    genRef.current = false
    setGenError(false)
  }

  function handleOpenBuilding(card) {
    const id = cardId(card)
    if (!id) return
    navigate(`/buildings/${id}`, { state: { referrer: location.pathname } })
  }

  let state = 'ready'
  if (!boardId) state = 'unavailable'
  else if (loading) state = 'fetching'
  else if (shouldAutoGenerate) state = 'making'
  else if (!board) state = loadFailed ? 'loadFail' : 'unavailable'
  else if (genError) state = 'genFail'
  else if (!report) state = 'noReport'

  // Liked row = the liked subset of the board's buildings (saved-only ones are not "liked").
  const buildings = board?.buildings || []
  const likedIdSet = new Set((board?.liked_ids || []).map(item => String(item?.id ?? item)))
  const likedBuildings = board?.liked_ids ? buildings.filter(b => likedIdSet.has(String(cardId(b)))) : buildings
  const savedIds = (board?.saved_ids || []).map(item => String(item?.id ?? item))

  return (
    <>
    <PersonaReportPage
      state={state}
      role={isOwner ? 'owner' : 'viewer'}
      onLogout={onLogout}
      onBack={() => (state === 'ready' ? navigate(`/board/${boardId}`) : navigate(-1))}
      backLabel={t('board.backToDetail')}
      onRetry={handleRetry}
      onProfile={() => navigate('/user/me')}
      boardId={boardId}
      finalReport={report}
      axisScores={axisScores}
      reportImage={board?.report_image || null}
      reportImageMime={board?.report_image_mime || null}
      meta={{
        visibility: board?.visibility,
        buildingCount: buildings.length,
        reactionCount: board?.reaction_count ?? 0,
        user: board?.user || board?.owner || null,
      }}
      likedBuildings={likedBuildings}
      recommendations={recommendations}
      savedIds={savedIds}
      onOpenBuilding={handleOpenBuilding}
      {...regen.imageProps}
      {...regen.reportProps}
    />
    {regen.overlay}
    </>
  )
}
