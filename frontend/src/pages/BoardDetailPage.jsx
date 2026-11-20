import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useBoard, useBoardSessionResult } from '../hooks/useBoard.js'
import { getProjectReportImage } from '../api/projects.js'
import { useRegeneration } from '../hooks/useRegeneration.jsx'
import { useReportImageJob } from '../hooks/useReportImageJob.js'
import { useBoardEdit } from '../hooks/useBoardEdit.js'
import { useBoardReaction } from '../hooks/useBoardReaction.js'
import BuildingTile from './boardDetail/BuildingTile'
import tileStyles from './boardDetail/BuildingTile.module.css'
import BoardCover from './boardDetail/BoardCover'
import EditActionBar from './boardDetail/EditActionBar'
import { useTranslation } from '../i18n/index.js'
import { localizeReport } from '../utils/reportText.js'
import { resolveCoverTitle, isNameDirty } from '../utils/boardCoverTitle.js'
import { safeImageMime } from '../utils/imageMime.js'
import s from './BoardDetailPage.module.css'
import {
  OwnerMeta, ViewerMeta, OwnerTools, ViewerTools, TitleEdit, EditGrid, DeleteFooter,
} from './boardReport/BoardReportParts.jsx'
import {
  ReportScope, ReportSection, ReportHero, ReportHeading, RecommendationsSection, ArchitectsSection,
} from '../components/PersonaReportPage.jsx'
import Toast from '../components/Toast.jsx'
import { shareBoardLink } from '../utils/shareBoard.js'
import PageShell from '../components/PageShell.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Skeleton from '../components/Skeleton.jsx'

const TOAST_MS = 2000
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// `boardData` (optional): the useBoard() result already loaded by BoardRoute
// (with fetchResult:false); when given, this page skips its own board fetch and
// loads only the owner-only session result. Standalone use still works.
export default function BoardDetailPage({ boardData, onResume, onLogout }) {
  const navigate = useNavigate()
  const { t, language } = useTranslation()
  const rawBoardId = useParams().boardId
  const boardId = UUID_RE.test(String(rawBoardId || '')) ? rawBoardId : null
  const own = useBoard(boardId, { enabled: !boardData })
  const injected = useBoardSessionResult(boardData?.board, !!boardData)
  const { board, recommendedArchitects, loading, error } = boardData || own
  const hookRecommended = boardData ? injected.recommended : own.recommended
  const resultLoading = boardData ? injected.resultLoading : own.resultLoading

  const viewerId = sessionStorage.getItem('archithon_user')
  const boardOwnerId = board?.user?.user_id ?? board?.owner?.user_id
  const isOwner = !!viewerId && String(boardOwnerId) === String(viewerId)
  // Toast host + owner gate (image/report regeneration is owner-only).
  const regen = useRegeneration({ projectId: boardId, enabled: isOwner, withReport: false })
  // Viewers have no regeneration overlay (toast host), so they get a tiny toast of their own.
  const [viewerToast, setViewerToast] = useState(null)
  const viewerToastTimer = useRef(null)
  useEffect(() => () => clearTimeout(viewerToastTimer.current), [])
  const { showToast: regenToast } = regen
  const showToast = useCallback(text => {
    if (isOwner) { regenToast(text); return }
    setViewerToast({ text, key: Date.now() })
    clearTimeout(viewerToastTimer.current)
    viewerToastTimer.current = setTimeout(() => setViewerToast(null), TOAST_MS)
  }, [isOwner, regenToast])

  const {
    isReacted, reactionCount, isPending: isReactionPending, error: reactionError, toggle: handleToggleReaction,
  } = useBoardReaction(board)
  // Owner edit state + handlers (shared with the merged report page).
  const {
    localName, nameDraft, setNameDraft, isEditMode, selectedIds, busy, lastMsgOn,
    localBuildings, visibility,
    enterEditMode, exitEditMode, saveEdits,
    handleToggleBuildingSelect, handleToggleVisibility, handleDeleteBoard,
  } = useBoardEdit({
    boardId, board, isOwner,
    getFallbackTitle: () => coverTitle,
    showToast,
  })

  // Persona report image: inline on the project payload when present, else
  // lazily fetched (same chain as BoardCard). null -> building cover fallback.
  const [fetchedPersonaImage, setFetchedPersonaImage] = useState(null)
  useEffect(() => {
    setFetchedPersonaImage(null)
    if (!board || board.report_image || !(board.has_report_image ?? board.final_report)) return
    let cancelled = false
    getProjectReportImage(board.project_id || board.board_id).then(data => {
      if (cancelled || !data?.image_data) return
      setFetchedPersonaImage(`data:${safeImageMime(data.mime_type)};base64,${data.image_data}`)
    })
    return () => { cancelled = true }
  }, [board])
  // The shared image-job store wins once it holds an image (regeneration after a
  // delete lands here), so the cover follows the newest generated image.
  const imageJob = useReportImageJob(boardId)
  const personaImage = imageJob.image
    ? `data:${safeImageMime(imageJob.mime)};base64,${imageJob.image}`
    : board?.report_image
      ? `data:${safeImageMime(board.report_image_mime)};base64,${board.report_image}`
      : fetchedPersonaImage

  function handleNavigateToOwner() {
    if (!board?.user?.user_id) return
    navigate(`/user/${board.user.user_id}`)
  }

  function handleShare() {
    const report = localizeReport(board?.final_report, language)
    shareBoardLink({
      title: (localName || board?.name || t('board.defaultName')) + (report?.persona_type ? ` · ${report.persona_type}` : ''),
      text: report?.one_liner || localName || '',
      onCopied: () => showToast(t('board.linkCopied')),
      onCopyFailed: () => showToast(t('board.copyFailed')),
    })
  }

  const isPublic = !board || visibility === 'public'
  const buildings = localBuildings ?? board?.buildings ?? []
  // Recommendations: predicted likes, capped at 20 (owner only; viewers get none).
  const recommended = isOwner ? hookRecommended.slice(0, 20) : []
  const finalReport = board?.final_report || null
  // Notice: deleting buildings makes the persona report need regeneration.
  const showRegenNotice = selectedIds.size > 0 && !!board?.final_report
  // Recompute cover from local state first so deleting the first card doesn't
  // leave a stale cover. Fall back to board.cover_image_url only when buildings
  // are present but buildings[0] lacks an image_url; null when board is empty.
  const coverImage = buildings.length > 0
    ? (buildings[0]?.image_url || board?.cover_image_url || null)
    : null
  const showBuildingsSkeleton = loading && buildings.length === 0
  const boardName = localName || board?.name || ''
  // Header needs the real board to decide owner vs viewer — without this gate
  // the viewer rows flash briefly before `board` arrives.
  const headerLoading = loading && !board
  const report = finalReport ? localizeReport(finalReport, language) : null
  const coverTitle = resolveCoverTitle({
    boardName,
    personaType: report?.persona_type,
    defaultName: t('board.defaultName'),
  })
  const canSaveName = isOwner && isEditMode && isNameDirty(nameDraft, localName || coverTitle)

  return (
    <PageShell
      width="medium"
      className={s.scroll}
      // The report column owns its gutter (28px) via --rp-gutter inside ReportScope.
      contentStyle={{ padding: 0 }}
      chrome={
        <>
          <PageTopControls onLogout={onLogout} leading={<PageBackButton inline onClick={() => navigate(-1)} label={t('board.back')} />} />
          <PageLogoHeader />
        </>
      }
    >
      <ReportScope>
        {/* Cover card: image + title only (meta / owner controls live in the rows below). */}
        <div style={{ padding: '20px var(--rp-gutter) 0' }}>
          {headerLoading ? (
            <Skeleton radius="var(--radius-lg)" style={{ height: 'auto', aspectRatio: '4 / 3' }} />
          ) : (
            <BoardCover
              imageUrl={personaImage || coverImage}
              alt={coverTitle || t('board.coverAlt')}
              title={coverTitle}
            />
          )}
        </div>

        <ReportHero afterCover>
          {headerLoading ? (
            <Skeleton width="80%" height={20} radius="var(--radius-sm)" />
          ) : isOwner ? (
            <>
              <OwnerMeta
                isPublic={isPublic}
                buildingCount={buildings.length}
                reactionCount={reactionCount}
                onToggleVisibility={next => {
                  handleToggleVisibility(next)
                  showToast(t(next === 'public' ? 'board.nowPublic' : 'board.nowPrivate'))
                }}
                disabled={!board}
              />
              {isEditMode && (
                <TitleEdit
                  value={nameDraft}
                  onChange={setNameDraft}
                  onCommit={() => saveEdits({ deleting: false })}
                  onCancel={exitEditMode}
                  canSave={canSaveName}
                  busy={busy}
                />
              )}
              <OwnerTools
                onResume={onResume ? () => onResume(board?.board_id) : null}
                resumeDisabled={!board || isEditMode}
                isEditMode={isEditMode}
                editDisabled={!board || !!busy}
                onToggleEdit={isEditMode ? exitEditMode : enterEditMode}
                onShare={handleShare}
              />
            </>
          ) : (
            <>
              <ViewerMeta
                owner={board?.user}
                isPublic={isPublic}
                buildingCount={buildings.length}
                onOpenOwner={handleNavigateToOwner}
              />
              <ViewerTools
                isReacted={isReacted}
                reactionCount={reactionCount}
                pending={isReactionPending || !board}
                error={reactionError}
                onToggleReaction={handleToggleReaction}
                onShare={handleShare}
              />
            </>
          )}
        </ReportHero>

        {/* Liked buildings — existing BuildingTile grid. */}
        {isOwner && isEditMode && buildings.length > 0 ? (
          <EditGrid buildings={buildings} selectedIds={selectedIds} onToggleSelect={handleToggleBuildingSelect} />
        ) : (
          <ReportSection>
            <ReportHeading count={buildings.length > 0 ? buildings.length : null}>{t('board.buildingsTitle')}</ReportHeading>
            {showBuildingsSkeleton ? (
              <div className={tileStyles.grid}>
                {[1, 2, 3, 4].map(i => (
                  <Skeleton key={i} radius="var(--radius-lg)" style={{ height: 'auto', aspectRatio: '3 / 4' }} />
                ))}
              </div>
            ) : buildings.length === 0 ? (
              <EmptyState
                icon={
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5, color: 'var(--color-text-muted)' }}>
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                    <circle cx="8.5" cy="8.5" r="1.5"></circle>
                    <polyline points="21 15 16 10 5 21"></polyline>
                  </svg>
                }
                title={error?.message || t('board.emptyBoard')}
              />
            ) : (
              <div className={tileStyles.grid}>
                {buildings.map(building => {
                  const bid = building.image_id || building.canonical_bld_id || building.building_id || building.id
                  return (
                    <BuildingTile
                      key={bid}
                      building={building}
                      isEditMode={false}
                      isSelected={false}
                      onToggleSelect={handleToggleBuildingSelect}
                    />
                  )
                })}
              </div>
            )}
          </ReportSection>
        )}

        {/* Recommendations + recommended architects: owner only, same sections as the persona report. */}
        {isOwner && resultLoading && recommended.length === 0 && (
          <ReportSection>
            <ReportHeading>{t('results.recTitle')}</ReportHeading>
            <div className={tileStyles.grid}>
              {[1, 2].map(i => (
                <Skeleton key={i} radius="var(--radius-lg)" style={{ height: 'auto', aspectRatio: '3 / 4' }} />
              ))}
            </div>
          </ReportSection>
        )}
        <RecommendationsSection
          recommendations={recommended}
          onOpenBuilding={card => navigate('/buildings/' + card.image_id)}
        />
        {isOwner && (
          <ArchitectsSection
            architects={recommendedArchitects || []}
            onOpenArchitect={id => navigate('/architects/' + id)}
          />
        )}

        {isOwner && board && <DeleteFooter onDelete={handleDeleteBoard} />}
      </ReportScope>

      {regen.overlay}
      {!isOwner && <Toast message={viewerToast} />}

      {/* Edit mode floating action bar (persona-report mock `editBar`). */}
      {isEditMode && (
        <EditActionBar
          lastMsgOn={lastMsgOn}
          regenNotice={showRegenNotice ? t('board.deleteRegenNotice') : null}
          selectedCount={selectedIds.size}
          busy={busy}
          onCancel={exitEditMode}
          onDelete={() => saveEdits({ deleting: true })}
        />
      )}
    </PageShell>
  )
}
