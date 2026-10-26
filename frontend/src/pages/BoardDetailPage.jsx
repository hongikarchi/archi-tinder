import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import { updateProject, deleteProject, getProjectReportImage } from '../api/projects.js'
import { useRegeneration } from '../hooks/useRegeneration.jsx'
import { useReportImageJob } from '../hooks/useReportImageJob.js'
import { canSelectForDelete, isLastLikedError } from '../utils/boardDeleteRules.js'
import { reactToProject, unreactToProject } from '../api/social.js'
import BuildingTile from './boardDetail/BuildingTile'
import tileStyles from './boardDetail/BuildingTile.module.css'
import RecommendedTile from './boardDetail/RecommendedTile'
import ArchitectSection from './boardDetail/ArchitectSection'
import BoardCover from './boardDetail/BoardCover'
import CoverIconButton from './boardDetail/CoverIconButton'
import { useTranslation } from '../i18n/index.js'
import { localizeReport } from '../utils/reportText.js'
import { resolveCoverTitle, isNameDirty } from '../utils/boardCoverTitle.js'
import { planEditSave } from '../utils/boardEditPlan.js'
import { purgeChatCache } from '../utils/appHelpers.js'
import { safeImageMime } from '../utils/imageMime.js'
import s from './BoardDetailPage.module.css'
import PageShell from '../components/PageShell.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import FloatingIconButton from '../components/FloatingIconButton.jsx'
import PageTitle from '../components/PageTitle.jsx'
import SectionTitle from '../components/SectionTitle.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Skeleton from '../components/Skeleton.jsx'
import { userHandle, atHandle } from '../utils/userIdentity.js'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export default function BoardDetailPage({ onResume, onLogout }) {
  const navigate = useNavigate()
  const { t, language } = useTranslation()
  const rawBoardId = useParams().boardId
  const boardId = UUID_RE.test(String(rawBoardId || '')) ? rawBoardId : null
  const { board, recommended: hookRecommended, recommendedArchitects, loading, resultLoading, error } = useBoard(boardId)

  const [isReacted, setIsReacted] = useState(false)
  const [reactionCount, setReactionCount] = useState(0)
  const [isReactionPending, setIsReactionPending] = useState(false)
  const [reactionError, setReactionError] = useState(null)
  const [localName, setLocalName] = useState('')
  const [nameDraft, setNameDraft] = useState('')
  const [isEditMode, setIsEditMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [localBuildings, setLocalBuildings] = useState(null)
  // True while a save/delete request is in flight (one lock for every edit action).
  const [busy, setBusy] = useState(null) // null | 'saving-name' | 'deleting'
  const [deletedLikedIds, setDeletedLikedIds] = useState([])
  const [lastMsgOn, setLastMsgOn] = useState(false)
  const [visibilityOverride, setVisibilityOverride] = useState(null)
  const lastMsgTimerRef = useRef(null)
  const aliveRef = useRef(true)
  const visPendingRef = useRef(false)
  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false; clearTimeout(lastMsgTimerRef.current) }
  }, [])

  useEffect(() => {
    if (!board) return
    setDeletedLikedIds([])
    setVisibilityOverride(null)
    setIsReacted(!!board.is_reacted)
    setReactionCount(board.reaction_count ?? 0)
    setReactionError(null)
    setLocalName(board.name || '')
    setNameDraft(board.name || '')
    setLocalBuildings(board.buildings || [])
  }, [board])

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

  async function handleToggleReaction() {
    if (!board || isReactionPending) return

    const wasReacted = isReacted
    const previousCount = reactionCount
    const nextReacted = !wasReacted
    setIsReactionPending(true)
    setReactionError(null)
    setIsReacted(nextReacted)
    setReactionCount(prev => Math.max(0, prev + (nextReacted ? 1 : -1)))

    try {
      const resp = nextReacted
        ? await reactToProject(board.project_id)
        : await unreactToProject(board.project_id)
      if (resp?.reaction_count !== undefined) setReactionCount(resp.reaction_count)
      if (resp?.reacted !== undefined) setIsReacted(!!resp.reacted)
    } catch (err) {
      setIsReacted(wasReacted)
      setReactionCount(previousCount)
      setReactionError(err.message || t('board.reactionFailed'))
    } finally {
      setIsReactionPending(false)
    }
  }

  async function handleShare() {
    const report = localizeReport(board?.final_report, language)
    const shareData = {
      title: (localName || board?.name || t('board.defaultName')) + (report?.persona_type ? ` · ${report.persona_type}` : ''),
      text: report?.one_liner || localName || '',
      url: window.location.href,
    }
    if (navigator.share && navigator.canShare?.(shareData)) {
      try { await navigator.share(shareData) } catch { /* user cancelled */ }
    } else {
      try {
        await navigator.clipboard.writeText(window.location.href)
        regen.showToast(t('board.linkCopied'))
      } catch {
        regen.showToast(t('board.copyFailed'))
      }
    }
  }

  // Edit mode = { isEditMode, selectedIds, nameDraft }; these two are the only
  // transitions (plus selection toggling and saveEdits below).
  function enterEditMode() {
    setIsEditMode(true)
    setSelectedIds(new Set())
    setNameDraft(localName || coverTitle)
  }

  function exitEditMode() {
    setIsEditMode(false)
    setSelectedIds(new Set())
    setNameDraft(localName || coverTitle)
  }

  // Save the title draft (if dirty) and, when `deleting`, delete the selected
  // buildings. Name first, then delete. Success of everything -> exit edit mode;
  // any failure keeps edit mode, selection and draft. A saved name becomes the
  // new baseline immediately so a retry never re-sends it.
  async function saveEdits({ deleting }) {
    if (!isOwner || busy) return
    const plan = planEditSave({
      draft: nameDraft, baseline: localName || coverTitle, selectedIds, deleting,
    })
    if (plan.blank && !deleting) return
    if (plan.noop) { if (!plan.blank) exitEditMode(); return }
    setBusy(deleting ? 'deleting' : 'saving-name')
    try {
      if (plan.name) {
        try {
          await updateProject(boardId, { name: plan.name })
        } catch {
          if (aliveRef.current) regen.showToast(t('board.nameSaveFailed'))
          return
        }
        setLocalName(plan.name)
        setNameDraft(plan.name)
        regen.showToast(t('board.nameSaved'))
      }
      if (plan.deleteIds.length > 0) {
        const ids = plan.deleteIds
        const likedSet = new Set(likedIdList)
        const deletedLiked = ids.filter(id => likedSet.has(String(id)))
        try {
          await updateProject(boardId, { remove_building_ids: ids })
        } catch (err) {
          if (aliveRef.current) {
            if (isLastLikedError(err)) flashLastMessage()
            else regen.showToast(t('board.deleteFailed'))
          }
          return
        }
        setLocalBuildings(prev => (prev || []).filter(b => {
          const bid = b.image_id || b.canonical_bld_id || b.building_id || b.id
          return !ids.includes(bid)
        }))
        if (deletedLiked.length > 0) setDeletedLikedIds(prev => [...prev, ...deletedLiked])
        // No regeneration here: the server flags the report stale and the owner's
        // next open of the report page regenerates it.
      }
      setIsEditMode(false)
      setSelectedIds(new Set())
    } finally {
      if (aliveRef.current) setBusy(null)
    }
  }

  // Only liked ids that are actually rendered count toward the "keep one liked
  // building" rule: ids the page cannot show (non-publishable / missing) can never
  // be selected, so counting them would let the owner delete every visible one.
  const renderedIdSet = new Set((localBuildings ?? board?.buildings ?? [])
    .map(b => String(b.image_id || b.canonical_bld_id || b.building_id || b.id)))
  const likedIdList = (board?.liked_ids || []).map(item => String(item?.id ?? item))
    .filter(id => renderedIdSet.has(id))

  function flashLastMessage() {
    setLastMsgOn(true)
    clearTimeout(lastMsgTimerRef.current)
    lastMsgTimerRef.current = setTimeout(() => setLastMsgOn(false), 2300)
  }

  function handleToggleBuildingSelect(id) {
    if (!selectedIds.has(id) && !canSelectForDelete({
      likedIds: likedIdList, deletedIds: deletedLikedIds, selectedIds, candidateId: id,
    })) {
      flashLastMessage()
      return
    }
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  // Owner chips on the cover: optimistic visibility toggle (revert on failure).
  // One PATCH at a time (taps during a pending request are ignored) so requests
  // cannot commit out of order; on success the server's value wins.
  async function handleToggleVisibility(next) {
    if (visPendingRef.current) return
    visPendingRef.current = true
    const prev = visibility
    setVisibilityOverride(next)
    try {
      const res = await updateProject(boardId, { visibility: next })
      if (aliveRef.current && (res?.visibility === 'public' || res?.visibility === 'private')) {
        setVisibilityOverride(res.visibility)
      }
    } catch {
      if (aliveRef.current) {
        setVisibilityOverride(prev ?? null)
        regen.showToast(t('board.visibilityFailed'))
      }
    } finally {
      visPendingRef.current = false
    }
  }

  async function handleDeleteBoard() {
    try {
      await deleteProject(boardId)
      purgeChatCache(String(boardId))
      navigate('/user/me', { replace: true })
    } catch {
      if (aliveRef.current) regen.showToast(t('board.deleteFailed'))
    }
  }

  function handleNavigateToOwner() {
    if (!board?.user?.user_id) return
    navigate(`/user/${board.user.user_id}`)
  }

  const visibility = visibilityOverride ?? board?.visibility
  const isPublic = !board || visibility === 'public'
  const buildings = localBuildings ?? board?.buildings ?? []
  const recommended = hookRecommended
  const viewerId = sessionStorage.getItem('archithon_user')
  const boardOwnerId = board?.user?.user_id ?? board?.owner?.user_id
  const isOwner = !!viewerId && String(boardOwnerId) === String(viewerId)
  // Toast host + owner gate (image/report regeneration is owner-only).
  const regen = useRegeneration({ projectId: boardId, enabled: isOwner, withReport: false })
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
  // Header (title / owner row / stats / action buttons) needs the real board
  // to decide owner vs non-owner — without this gate the non-owner branch
  // (e.g. the "Love this" button) and an empty/broken owner avatar flash
  // briefly before `board` arrives.
  const headerLoading = loading && !board
  const report = finalReport ? localizeReport(finalReport, language) : null
  const coverTitle = resolveCoverTitle({
    boardName,
    personaType: report?.persona_type,
    defaultName: t('board.defaultName'),
  })
  // Cover button: pencil / X / white-glass check (title draft dirty).
  const editBtnConfirm = isOwner && isEditMode && isNameDirty(nameDraft, localName || coverTitle)
  const countLabel = t(buildings.length === 1 ? 'board.buildingCountOne' : 'board.buildingCountMany', { n: buildings.length })
  const ownerHandle = atHandle(board?.user)
  const coverMeta = isOwner
    ? [isPublic ? t('board.public') : t('board.private'), countLabel, `♥ ${reactionCount}`].join(' · ')
    : [ownerHandle, countLabel, `♥ ${reactionCount}`].filter(Boolean).join(' · ')

  return (
    <PageShell
      width="medium"
      // Top padding so the cover card clears the fixed Share button
      // (top:50/left:12) instead of sitting flush under the logo header
      // (was the default `padding: '0 20px'` with no top gap at all —
      // profile-page-visual-parity gap, mirrors UserProfilePage's 32px
      // content-column top padding).
      contentStyle={{ padding: '20px 20px 0' }}
      chrome={
        <>
          <PageTopControls onLogout={onLogout} leading={<PageBackButton inline onClick={() => navigate(-1)} label={t('board.back')} />} />
          <PageLogoHeader />
          {/* Share — stacked under the back button (ArchitectProfilePage precedent:
              top:50/left:12, zIndex 299 — one below PageBackButton's 300), so its
              44px invisible hit area never collides with PageTopControls on the
              right at 390px width. */}
          {!isOwner && <FloatingIconButton
            onClick={handleShare}
            ariaLabel={t('board.share')}
            style={{ position: 'fixed', top: 50, left: 12, zIndex: 299 }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="18" cy="5" r="3" />
              <circle cx="6" cy="12" r="3" />
              <circle cx="18" cy="19" r="3" />
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
              <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
            </svg>
          </FloatingIconButton>}
        </>
      }
    >
      {/* Cover card (mock `boardDetail`) — persona image / building cover /
          gradient face, persona name + meta on a bottom scrim. */}
      {headerLoading ? (
        <Skeleton radius="var(--radius-lg)" style={{ height: 'auto', aspectRatio: '4 / 3' }} />
      ) : (
        <BoardCover
          imageUrl={personaImage || coverImage}
          alt={coverTitle || t('board.coverAlt')}
          title={coverTitle}
          titleEditable={isOwner && isEditMode}
          titleDraft={nameDraft}
          onTitleDraftChange={setNameDraft}
          onTitleCommit={() => saveEdits({ deleting: false })}
          onTitleCancel={exitEditMode}
          titleSaving={!!busy}
          titleLabel={t('board.nameLabel')}
          meta={coverMeta}
          ownerChips={isOwner ? {
            isPrivate: !isPublic,
            onToggleVisibility: handleToggleVisibility,
            onDelete: handleDeleteBoard,
            labels: {
              makePublic: t('board.makePublic'),
              makePrivate: t('board.makePrivate'),
              nowPublic: t('board.nowPublic'),
              nowPrivate: t('board.nowPrivate'),
              deleteBoard: t('board.deleteBoard'),
              deleteConfirm: t('board.deleteConfirm'),
              deleteConfirmAria: t('board.deleteConfirmAria'),
            },
          } : null}
          rightSlot={isOwner ? (
            <>
              <CoverIconButton
                onClick={editBtnConfirm ? () => saveEdits({ deleting: false }) : isEditMode ? exitEditMode : enterEditMode}
                disabled={busy || (!isEditMode && !board)}
                ariaLabel={editBtnConfirm ? t('board.save') : isEditMode ? t('board.cancel') : t('board.editBoard')}
                ariaPressed={isEditMode}
                confirm={editBtnConfirm}
                dimmed={!!busy || (!isEditMode && !board)}
              >
                {editBtnConfirm ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : isEditMode ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                )}
              </CoverIconButton>
              <CoverIconButton onClick={handleShare} ariaLabel={t('board.share')}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
                  <polyline points="16 6 12 2 8 6"/>
                  <line x1="12" y1="2" x2="12" y2="15"/>
                </svg>
              </CoverIconButton>
            </>
          ) : null}
        />
      )}

      {headerLoading ? (
        <div style={{ marginTop: 18 }}>
          <Skeleton width="80%" height={20} radius="var(--radius-sm)" />
          <div className={s.topActions}>
            <Skeleton height={44} radius="var(--radius-pill)" style={{ flex: 1 }} />
          </div>
        </div>
      ) : (
      <div>
        {/* Action row — owner: [report pill | continue exploring] (no report:
            continue only); viewer: [report pill | reaction pill]. Owner edit +
            share live on the cover. */}
        <div className={s.topActions}>
          {board?.final_report && (
            <button
              onClick={() => navigate(`/board/${board.board_id}/report`)}
              className={`${s.pill} ${s.pillPrimary}`}
              style={isOwner ? {
                flex: onResume ? '3 1 0' : '1 1 0', minWidth: 0, padding: '0 12px',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              } : undefined}
            >
              {t('board.viewReport')}
            </button>
          )}
          {isOwner ? (
            onResume && (
              <button
                onClick={() => onResume(board?.board_id)}
                disabled={!board}
                className={`${s.pill} ${s.pillSecondary}`}
                style={{
                  flex: board?.final_report ? '2 1 0' : '1 1 0', minWidth: 0, padding: '0 12px',
                  fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-semibold)',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}
              >
                {t('board.continueExploring')}
              </button>
            )
          ) : (
            <button
              onClick={handleToggleReaction}
              disabled={!board || isReactionPending}
              aria-label={isReacted ? t('board.loved', { r: reactionCount }) : t('board.loveThis')}
              aria-pressed={isReacted}
              className={`${s.pill} ${s.pillSecondary}${isReacted ? ` ${s.reacted}` : ''}`}
              style={board?.final_report ? undefined : { marginLeft: 'auto' }}
            >
              <svg
                width="16" height="16" viewBox="0 0 24 24"
                fill={isReacted ? 'currentColor' : 'none'}
                stroke="currentColor"
                strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
              </svg>
              <span>{reactionCount}</span>
            </button>
          )}
        </div>

        {!isOwner && reactionError && (
          <div style={{
            color: 'var(--color-text-muted)',
            fontSize: 'var(--fs-caption)',
            fontWeight: 'var(--fw-semibold)',
            margin: '8px 8px 0',
          }}>
            {reactionError}
          </div>
        )}

        {/* Viewer: link to the board owner's profile (kept from the old meta row). */}
        {!isOwner && board?.user?.user_id && (
          <button
            type="button"
            onClick={handleNavigateToOwner}
            className={s.ownerRow}
            style={{
              margin: '14px 8px 0',
              padding: 0,
              minHeight: 32,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontFamily: 'inherit',
              color: 'var(--color-text-dim)',
              fontSize: 'var(--fs-caption)',
              fontWeight: 'var(--fw-semibold)',
            }}
          >
            <img
              src={board.user.avatar_url || ''}
              alt=""
              style={{ width: 20, height: 20, borderRadius: '50%', objectFit: 'cover', background: 'var(--color-surface-2)' }}
            />
            <span className={s.ownerName}>{userHandle(board.user)}</span>
            <span aria-hidden="true">›</span>
          </button>
        )}

      </div>
      )}

      {/* Buildings section */}
      <div style={{ margin: '32px 0 16px' }}>
        <SectionTitle count={buildings.length > 0 ? buildings.length : null}>
          {t('board.buildingsTitle')}
        </SectionTitle>
      </div>

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
        <div className={tileStyles.grid} style={isEditMode ? { paddingBottom: 56 } : undefined}>
          {buildings.map((building) => {
            const bid = building.image_id || building.canonical_bld_id || building.building_id || building.id
            return (
            <BuildingTile
              key={bid}
              building={building}
              isEditMode={isEditMode}
              isSelected={selectedIds.has(bid)}
              onToggleSelect={handleToggleBuildingSelect}
            />
            )
          })}
        </div>
      )}

      {(recommended.length > 0 || resultLoading) && (
        <div style={{ marginTop: 8 }}>
          <div style={{ height: 1, background: 'var(--color-border)', margin: '0 0 32px' }} />
          <div style={{ margin: '0 0 4px' }}>
            <SectionTitle>{t('board.recommendedTitle')}</SectionTitle>
          </div>
          {resultLoading && recommended.length === 0 ? (
            <div style={{
              padding: '12px 0 24px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
              gap: 12,
            }}>
              {[1, 2, 3, 4].map(i => (
                <Skeleton key={i} radius="var(--radius-lg)" style={{ height: 'auto', aspectRatio: '3 / 4' }} />
              ))}
            </div>
          ) : (
            <>
              <p style={{
                color: 'var(--color-text-dimmer)',
                fontSize: 'var(--fs-caption)',
                fontWeight: 'var(--fw-medium)',
                margin: '8px 0 16px',
              }}>
                {t('board.basedOnPreferences')}
              </p>
              {(() => {
                const CHUNK_SIZE = 8
                const cappedRec = recommended.slice(0, 20)
                const chunks = []
                for (let i = 0; i < cappedRec.length; i += CHUNK_SIZE) {
                  chunks.push(cappedRec.slice(i, i + CHUNK_SIZE))
                }
                if (chunks.length === 0) return null
                return chunks.map((chunk, chunkIdx) => (
                  <div key={chunkIdx}>
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                      gap: 12,
                    }}>
                      {chunk.map(card => (
                        <RecommendedTile
                          key={card.image_id}
                          card={card}
                          onClick={() => navigate('/buildings/' + card.image_id)}
                        />
                      ))}
                    </div>
                    {recommendedArchitects[chunkIdx] && (
                      <div style={{ marginTop: 12 }}>
                        <ArchitectSection
                          architect={recommendedArchitects[chunkIdx]}
                          onBuildingClick={id => navigate('/buildings/' + id)}
                          onProfileClick={id => navigate('/architects/' + id)}
                        />
                      </div>
                    )}
                  </div>
                ))
              })()}
            </>
          )}
        </div>
      )}

      {regen.overlay}

      {/* Edit mode floating action bar (persona-report mock `editBar`): no
          container, two solid buttons + a solid notice pill above them. */}
      {isEditMode && (
        <div style={{
          position: 'fixed',
          left: 16, right: 16,
          bottom: 'var(--tabbar-clearance)',
          maxWidth: 420,
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 10,
          zIndex: 200,
        }}>
          <div role="status" aria-live="polite">
          {(lastMsgOn || showRegenNotice) && (
            <span style={{
              padding: '6px 12px',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border-soft)',
              boxShadow: '0 4px 12px rgba(0,0,0,.12)',
              fontSize: 'var(--fs-caption)',
              color: lastMsgOn ? 'var(--color-text)' : 'var(--color-text-dim)',
              fontWeight: lastMsgOn ? 'var(--fw-semibold)' : 'var(--fw-regular)',
              textAlign: 'center',
            }}>
              {lastMsgOn ? t('board.lastBuilding') : t('board.deleteRegenNotice')}
            </span>
          )}
          </div>
          <div style={{ display: 'flex', gap: 10, width: '100%' }}>
            <button
              onClick={exitEditMode}
              disabled={busy}
              style={{
                flex: 1, minHeight: 44, borderRadius: 'var(--radius-md)',
                background: 'var(--color-surface)', color: 'var(--color-text)',
                border: '1px solid var(--color-border)',
                boxShadow: '0 6px 18px rgba(0,0,0,.18)',
                fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-semibold)',
                fontFamily: 'inherit', cursor: 'pointer',
              }}
            >
              {t('board.cancel')}
            </button>
            <button
              onClick={() => saveEdits({ deleting: true })}
              disabled={selectedIds.size === 0 || busy}
              style={{
                flex: 2, minHeight: 44, borderRadius: 'var(--radius-md)',
                background: selectedIds.size > 0 ? 'var(--color-text)' : 'var(--color-surface-2)',
                color: selectedIds.size > 0 ? 'var(--color-bg)' : 'var(--color-text-dim)',
                border: 'none',
                boxShadow: selectedIds.size > 0 ? '0 6px 18px rgba(0,0,0,.25)' : 'none',
                fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-semibold)',
                cursor: selectedIds.size === 0 ? 'default' : 'pointer',
                fontFamily: 'inherit',
                opacity: busy ? 0.6 : 1,
                transition: 'background var(--motion-normal) var(--motion-ease), color var(--motion-normal) var(--motion-ease)',
              }}
            >
              {busy === 'deleting'
                ? t('board.deleting')
                : selectedIds.size > 0
                  ? t(selectedIds.size === 1 ? 'board.deleteCardOne' : 'board.deleteCardMany', { n: selectedIds.size })
                  : t('board.selectToDelete')}
            </button>
          </div>
        </div>
      )}
    </PageShell>
  )
}
