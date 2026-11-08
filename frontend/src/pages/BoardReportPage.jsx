import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import PersonaReportPage from '../components/PersonaReportPage.jsx'
import Toast from '../components/Toast.jsx'
import EditActionBar from './boardDetail/EditActionBar.jsx'
import {
  ReportNotice, OwnerMeta, ViewerMeta, OwnerTools, ViewerTools, TitleEdit, EditGrid, DeleteFooter,
} from './boardReport/BoardReportParts.jsx'
import { useTranslation } from '../i18n/index.js'
import { generateReport, getProjectRecommendations } from '../api/projects.js'
import { useRegeneration } from '../hooks/useRegeneration.jsx'
import { useBoardEdit } from '../hooks/useBoardEdit.js'
import { useBoardReaction } from '../hooks/useBoardReaction.js'
import { staleReason, countDistinctLiked } from '../utils/reportStale.js'
import { isLegacyAxisScores } from '../utils/axisScores.js'
import { localizeReport } from '../utils/reportText.js'
import { resolveCoverTitle, isNameDirty } from '../utils/boardCoverTitle.js'
import { shareBoardLink } from '../utils/shareBoard.js'

/* ── BoardReportPage ────────────────────────────────────────────────────── */
// The merged board page for boards WITH a persona report (chosen by BoardRoute at
// /board/:boardId). One body (PersonaReportBody) in two modes:
//   owner  — stale/legacy notice, tools row (continue / edit / share), visibility
//            chip, edit mode (rename + delete buildings), delete-board footer
//   viewer — read-only: owner link, reaction pill, share (public boards only)
// Board data comes from BoardRoute's single useBoard call (`boardData`).
const NOTICE_KEYS = {
  added: 'persona.noticeAdded',
  removed: 'persona.noticeRemoved',
  changed: 'persona.noticeChanged',
}
const TOAST_MS = 2000

function cardId(card) {
  return card?.image_id || card?.canonical_bld_id || card?.building_id || ''
}

export default function BoardReportPage({ boardId, boardData, onResume, onLogout }) {
  const navigate = useNavigate()
  const location = useLocation()
  const locationState = location.state
  const { t, language } = useTranslation()

  const { board, loading, error: boardError, reload: reloadBoard, recommendedArchitects = [] } = boardData

  const [localReport, setLocalReport] = useState(null)
  const [localAxisScores, setLocalAxisScores] = useState(null)
  const [genError, setGenError] = useState(false)
  const [recommendations, setRecommendations] = useState([])
  const genRef = useRef(false)
  const aliveRef = useRef(true)
  // Deleted-liked count at the time of the last regeneration: deletions beyond it
  // make the report stale again (the notice offers the manual regenerate).
  const [regenBaseline, setRegenBaseline] = useState(0)
  const deletedCountRef = useRef(0)
  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false }
  }, [])

  // Ownership. Same derivation as BoardDetailPage (viewer id from sessionStorage
  // vs the board's owner id) so both pages agree on who owns a board.
  const viewerId = sessionStorage.getItem('archithon_user')
  const boardOwnerId = board?.user?.user_id ?? board?.owner?.user_id
  const isOwner = !!viewerId && String(boardOwnerId) === String(viewerId)

  // localReport (auto-generated or regenerated) wins over the fetched board copy.
  const report = localReport || board?.final_report
  const axisScores = localAxisScores || locationState?.axisScores || board?.axis_scores || null
  // Auto-generate condition, computed once and reused for both the effect
  // guard AND the render branch below — avoids the first-paint flash.
  // isOwner gate: viewing someone else's board must never trigger a write.
  const shouldAutoGenerate = !!(
    isOwner && board && !report && !genError && board.liked_ids?.length > 0
  )

  // A stale report is never regenerated automatically: the top notice offers the
  // manual "지금 재생성" button (the only regenerate path).
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

  // Recommendations: owners and (public-board) viewers. A failed or empty fetch
  // just hides the section.
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
      setRegenBaseline(deletedCountRef.current)
    },
  })

  // Viewers have no regeneration overlay, so they get their own tiny toast.
  const [viewerToast, setViewerToast] = useState(null)
  const viewerToastTimer = useRef(null)
  useEffect(() => () => clearTimeout(viewerToastTimer.current), [])
  const showToast = useCallback(text => {
    if (isOwner) { regen.showToast(text); return }
    setViewerToast({ text, key: Date.now() })
    clearTimeout(viewerToastTimer.current)
    viewerToastTimer.current = setTimeout(() => setViewerToast(null), TOAST_MS)
  }, [isOwner, regen])

  const localized = report ? localizeReport(report, language) : null
  const fallbackTitle = resolveCoverTitle({
    boardName: '', personaType: localized?.persona_type, defaultName: t('board.defaultName'),
  })

  // Owner edit state + handlers (shared with BoardDetailPage).
  const edit = useBoardEdit({
    boardId, board, isOwner,
    getFallbackTitle: () => fallbackTitle,
    showToast,
  })
  const reaction = useBoardReaction(board)
  useEffect(() => { deletedCountRef.current = edit.deletedLikedIds.length }, [edit.deletedLikedIds])

  const { showToast: regenToast } = regen

  // Post-save landing (App.handleBoardSaved navigates with state.saved): toast once,
  // then drop the flag so back/forward doesn't replay it. Waits for ownership
  // because the toast host lives in the owner-only regeneration overlay.
  const savedRef = useRef(!!locationState?.saved)
  useEffect(() => {
    if (!savedRef.current || !isOwner) return
    savedRef.current = false
    regenToast(t('results.savedToast'))
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
      reloadBoard?.()
      return
    }
    genRef.current = false
    setGenError(false)
  }

  function handleOpenBuilding(card) {
    const id = cardId(card)
    if (!id) return
    navigate(`/buildings/${id}`)
  }

  // Back: the owner always lands on the profile (`replace` + profileRefresh mirror
  // TabBar's Profile tap, so Back from the profile does not bounce through the
  // board). A viewer goes back to wherever they came from.
  function handleBack() {
    if (isOwner) {
      navigate('/user/me', { replace: true, state: { profileRefresh: Date.now() } })
    } else if (location.key !== 'default') {
      navigate(-1)
    } else {
      navigate('/people')
    }
  }

  function handleShare() {
    shareBoardLink({
      title: (edit.localName || board?.name || t('board.defaultName')) + (localized?.persona_type ? ` · ${localized.persona_type}` : ''),
      text: localized?.one_liner || edit.localName || '',
      onCopied: () => showToast(t('board.linkCopied')),
      onCopyFailed: () => showToast(t('board.copyFailed')),
    })
  }

  let state = 'ready'
  if (!boardId) state = 'unavailable'
  else if (loading) state = 'fetching'
  else if (shouldAutoGenerate) state = 'making'
  else if (!board) state = loadFailed ? 'loadFail' : 'unavailable'
  else if (genError) state = 'genFail'
  else if (!report) state = isOwner ? 'noReport' : 'unavailable'

  // Liked row = the liked subset of the board's buildings (saved-only ones are not "liked").
  const buildings = edit.localBuildings ?? board?.buildings ?? []
  const likedIdSet = new Set((board?.liked_ids || []).map(item => String(item?.id ?? item)))
  const likedBuildings = board?.liked_ids ? buildings.filter(b => likedIdSet.has(String(cardId(b)))) : buildings
  const isPublic = edit.visibility === 'public'

  // Owner notice: deletions since the last regeneration, or a server-stale report
  // whose open-time regeneration did not succeed -> offer the manual regenerate.
  // Never while the user is mid-edit-save (busy) so the notice cannot flicker.
  const deletedCount = edit.deletedLikedIds.length
  const localStale = deletedCount > regenBaseline
  const serverStale = board?.report_stale === true && !localReport
  const needsRegen = isOwner && (localStale || serverStale)
  const legacy = isOwner && isLegacyAxisScores(axisScores)
  let noticeText = null
  if (needsRegen) {
    const reason = staleReason({
      likedCount: Array.isArray(board?.liked_ids) ? Math.max(0, countDistinctLiked(board) - deletedCount) : NaN,
      report,
    })
    noticeText = t(NOTICE_KEYS[reason])
  } else if (legacy) {
    noticeText = t('persona.noticeLegacy')
  }
  const topNotice = state === 'ready' && noticeText ? (
    <ReportNotice
      text={noticeText}
      busy={regen.reportProps.regenerating}
      failed={!!regen.reportProps.regenMessage}
      onRegenerate={regen.reportProps.onRegenerateReport}
    />
  ) : null

  const canSaveName = edit.isEditMode && isNameDirty(edit.nameDraft, edit.localName || fallbackTitle)

  const ownerSlots = isOwner ? {
    metaSlot: (
      <OwnerMeta
        isPublic={isPublic}
        buildingCount={buildings.length}
        reactionCount={reaction.reactionCount}
        onToggleVisibility={next => {
          edit.handleToggleVisibility(next)
          showToast(t(next === 'public' ? 'board.nowPublic' : 'board.nowPrivate'))
        }}
        disabled={!board}
      />
    ),
    titleSlot: edit.isEditMode ? (
      <TitleEdit
        value={edit.nameDraft}
        onChange={edit.setNameDraft}
        onCommit={() => edit.saveEdits({ deleting: false })}
        onCancel={edit.exitEditMode}
        canSave={canSaveName}
        busy={edit.busy}
      />
    ) : null,
    actionsSlot: (
      <OwnerTools
        onResume={onResume ? () => onResume(board?.board_id) : null}
        resumeDisabled={!board || edit.isEditMode}
        isEditMode={edit.isEditMode}
        editDisabled={!board || !!edit.busy}
        onToggleEdit={edit.isEditMode ? edit.exitEditMode : edit.enterEditMode}
        onShare={handleShare}
      />
    ),
    likedSlot: edit.isEditMode && likedBuildings.length > 0 ? (
      <EditGrid buildings={likedBuildings} selectedIds={edit.selectedIds} onToggleSelect={edit.handleToggleBuildingSelect} />
    ) : null,
    footerSlot: <DeleteFooter onDelete={edit.handleDeleteBoard} />,
  } : {
    metaSlot: (
      <ViewerMeta
        owner={board?.user}
        isPublic={isPublic}
        buildingCount={buildings.length}
        onOpenOwner={() => { if (board?.user?.user_id) navigate(`/user/${board.user.user_id}`) }}
      />
    ),
    actionsSlot: (
      <ViewerTools
        isReacted={reaction.isReacted}
        reactionCount={reaction.reactionCount}
        pending={reaction.isPending}
        error={reaction.error}
        onToggleReaction={reaction.toggle}
        onShare={handleShare}
      />
    ),
  }

  return (
    <>
    <PersonaReportPage
      state={state}
      onLogout={onLogout}
      onBack={handleBack}
      backLabel={isOwner ? t('board.profile') : t('board.back')}
      onRetry={handleRetry}
      onProfile={() => navigate(isOwner ? '/user/me' : '/people')}
      // Viewers never get a board id for the image job: Body's auto-start would POST.
      boardId={isOwner ? boardId : null}
      finalReport={report}
      axisScores={axisScores}
      reportImage={board?.report_image || null}
      reportImageMime={board?.report_image_mime || null}
      meta={{
        visibility: board?.visibility,
        buildingCount: buildings.length,
        reactionCount: reaction.reactionCount,
      }}
      likedBuildings={likedBuildings}
      recommendations={recommendations}
      architects={recommendedArchitects}
      onOpenArchitect={id => navigate(`/architects/${id}`)}
      onOpenBuilding={handleOpenBuilding}
      topNotice={topNotice}
      {...ownerSlots}
      {...regen.imageProps}
    />
    {regen.overlay}
    {!isOwner && <Toast message={viewerToast} />}
    {isOwner && edit.isEditMode && state === 'ready' && (
      <EditActionBar
        lastMsgOn={edit.lastMsgOn}
        regenNotice={edit.selectedIds.size > 0 ? t('board.deleteRegenNotice') : null}
        selectedCount={edit.selectedIds.size}
        busy={edit.busy}
        onCancel={edit.exitEditMode}
        onDelete={() => edit.saveEdits({ deleting: true })}
      />
    )}
    </>
  )
}
