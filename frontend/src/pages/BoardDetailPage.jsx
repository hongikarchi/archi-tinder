import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import { updateProject, getProjectReportImage, generateReport } from '../api/projects.js'
import { useRegeneration } from '../hooks/useRegeneration.jsx'
import { useReportImageJob, reportImageJobs } from '../hooks/useReportImageJob.js'
import { canSelectForDelete, isLastLikedError } from '../utils/boardDeleteRules.js'
import { reactToProject, unreactToProject } from '../api/social.js'
import BuildingTile from './boardDetail/BuildingTile'
import RecommendedTile from './boardDetail/RecommendedTile'
import ArchitectSection from './boardDetail/ArchitectSection'
import BoardCover from './boardDetail/BoardCover'
import { useTranslation } from '../i18n/index.js'
import { localizeReport } from '../utils/reportText.js'
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

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export default function BoardDetailPage({ onResume, onLogout }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { t, language } = useTranslation()
  const rawBoardId = useParams().boardId
  const boardId = UUID_RE.test(String(rawBoardId || '')) ? rawBoardId : null
  const { board, recommended: hookRecommended, recommendedArchitects, loading, resultLoading, error } = useBoard(boardId)

  const [isReacted, setIsReacted] = useState(false)
  const [reactionCount, setReactionCount] = useState(0)
  const [isReactionPending, setIsReactionPending] = useState(false)
  const [reactionError, setReactionError] = useState(null)
  const [localSavedIds, setLocalSavedIds] = useState([])
  const [localName, setLocalName] = useState('')
  const [isEditingName, setIsEditingName] = useState(false)
  const [editName, setEditName] = useState('')
  const [nameSaving, setNameSaving] = useState(false)
  const [shareCopied, setShareCopied] = useState(false)
  const nameInputRef = useRef(null)
  const [isEditMode, setIsEditMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [localBuildings, setLocalBuildings] = useState(null)
  const [deleteInProgress, setDeleteInProgress] = useState(false)
  // Capture bookmark signal once at mount so board-load effect can apply it
  const bookmarkSignalRef = useRef(location.state?.bookmarkChanged || null)
  // Report regenerated after deleting liked buildings (null -> use board.final_report)
  const [localFinalReport, setLocalFinalReport] = useState(null)
  const [deletedLikedIds, setDeletedLikedIds] = useState([])
  const [lastMsgOn, setLastMsgOn] = useState(false)
  const lastMsgTimerRef = useRef(null)
  const aliveRef = useRef(true)
  const regenBusyRef = useRef(false)
  const regenAgainRef = useRef(false)
  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false; clearTimeout(lastMsgTimerRef.current) }
  }, [])

  useEffect(() => {
    if (!board) return
    setLocalFinalReport(null)
    setDeletedLikedIds([])
    setIsReacted(!!board.is_reacted)
    setReactionCount(board.reaction_count ?? 0)
    setReactionError(null)
    setLocalName(board.name || '')
    setLocalBuildings(board.buildings || [])
    // Seed from board data, then apply any pending bookmark signal
    const base = (board.saved_ids || []).map(item => item?.id || item).filter(Boolean)
    const signal = bookmarkSignalRef.current
    if (signal?.buildingId && signal?.action) {
      bookmarkSignalRef.current = null
      const { buildingId: changedId, action } = signal
      if (action === 'save') {
        setLocalSavedIds([...new Set([...base, changedId])])
      } else {
        setLocalSavedIds(base.filter(id => id !== changedId))
      }
    } else {
      setLocalSavedIds(base)
    }
  }, [board])

  // Clear bookmark signal from history on mount so forward/back doesn't re-apply it
  useEffect(() => {
    if (!location.state?.bookmarkChanged) return
    navigate(location.pathname, { replace: true, state: null })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
        setShareCopied(true)
        setTimeout(() => setShareCopied(false), 2000)
      } catch { /* silent */ }
    }
  }

  function startEditingName() {
    setEditName(localName)
    setIsEditingName(true)
    setTimeout(() => nameInputRef.current?.select(), 0)
  }

  async function commitNameEdit() {
    const trimmed = editName.trim()
    if (!trimmed || trimmed === localName) {
      setIsEditingName(false)
      return
    }
    setNameSaving(true)
    try {
      await updateProject(boardId, { name: trimmed })
      setLocalName(trimmed)
    } catch {
      // revert on error — keep original name
    } finally {
      setNameSaving(false)
      setIsEditingName(false)
    }
  }

  function handleNameKeyDown(e) {
    if (e.key === 'Enter') { e.preventDefault(); commitNameEdit() }
    if (e.key === 'Escape') { setIsEditingName(false) }
  }

  const likedIdList = (board?.liked_ids || []).map(item => String(item?.id ?? item))

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

  // Sequential, fire-and-forget after a successful delete: report first, then
  // the image through the shared store (previous image kept on failure).
  // Serialized: a delete during a running regeneration queues exactly one
  // follow-up run so the final run reflects the final board state.
  async function regenerateAfterDelete() {
    if (regenBusyRef.current) { regenAgainRef.current = true; return }
    regenBusyRef.current = true
    try {
      regen.showToast(t('board.regeneratingToast'))
      const data = await generateReport(boardId, { regenerate: true })
      if (!data?.final_report) throw new Error('empty report')
      if (aliveRef.current) setLocalFinalReport(data.final_report)
      const img = await reportImageJobs.regenerate(boardId)
      if (!img && aliveRef.current) regen.showToast(t('persona.regenFail'))
    } catch (err) {
      console.error('[BoardDetailPage] regenerate after delete failed:', err?.status, err?.message)
      if (aliveRef.current) regen.showToast(t('persona.regenFail'))
    } finally {
      regenBusyRef.current = false
      if (regenAgainRef.current) {
        regenAgainRef.current = false
        if (aliveRef.current) regenerateAfterDelete()
      }
    }
  }

  async function handleDeleteSelected() {
    if (!isOwner || selectedIds.size === 0 || deleteInProgress) return
    setDeleteInProgress(true)
    const ids = [...selectedIds]
    const likedSet = new Set(likedIdList)
    const deletedLiked = ids.filter(id => likedSet.has(String(id)))
    const hadReport = !!board?.final_report
    try {
      await updateProject(boardId, { remove_building_ids: ids })
      setLocalBuildings(prev => (prev || []).filter(b => {
        const bid = b.image_id || b.canonical_bld_id || b.building_id || b.id
        return !ids.includes(bid)
      }))
      if (deletedLiked.length > 0) setDeletedLikedIds(prev => [...prev, ...deletedLiked])
      setSelectedIds(new Set())
      setIsEditMode(false)
      // Policy (2026-10-23): every board building is treated as liked, so any
      // successful deletion regenerates the persona report and image.
      // Skip when the board has no liked ids at all (saved-only board): nothing
      // to regenerate from and the server would 400.
      if (ids.length > 0 && hadReport && likedIdList.length > 0) regenerateAfterDelete()
    } catch (err) {
      // keep edit mode + selection on error
      if (aliveRef.current) {
        if (isLastLikedError(err)) flashLastMessage()
        else regen.showToast(t('board.deleteFailed'))
      }
    } finally {
      if (aliveRef.current) setDeleteInProgress(false)
    }
  }

  function handleNavigateToOwner() {
    if (!board?.user?.user_id) return
    navigate(`/user/${board.user.user_id}`)
  }

  const isPublic = !board || board.visibility === 'public'
  const buildings = localBuildings ?? board?.buildings ?? []
  const recommended = hookRecommended
  const viewerId = sessionStorage.getItem('archithon_user')
  const boardOwnerId = board?.user?.user_id ?? board?.owner?.user_id
  const isOwner = !!viewerId && String(boardOwnerId) === String(viewerId)
  // Toast host + owner gate (image/report regeneration is owner-only).
  const regen = useRegeneration({ projectId: boardId, enabled: isOwner, withReport: false })
  const finalReport = localFinalReport || board?.final_report || null
  // All board buildings are treated as liked: any selection triggers regeneration.
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
  const coverTitle = report?.persona_type || boardName
  const countLabel = t(buildings.length === 1 ? 'board.buildingCountOne' : 'board.buildingCountMany', { n: buildings.length })
  const ownerHandle = board?.user?.username
    ? `@${board.user.username}`
    : (board?.user?.display_name || '')
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
            style={{
              position: 'fixed', top: 50, left: 12, zIndex: 299,
              color: shareCopied ? 'var(--accent-2)' : undefined,
              borderColor: shareCopied ? 'var(--accent-2)' : undefined,
            }}
          >
            {shareCopied ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="18" cy="5" r="3" />
                <circle cx="6" cy="12" r="3" />
                <circle cx="18" cy="19" r="3" />
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
              </svg>
            )}
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
          meta={coverMeta}
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
      <div style={{ marginTop: 18 }}>
        {/* One-liner — only when a report exists. */}
        {report?.one_liner && (
          <p style={{
            margin: '0 8px',
            color: 'var(--color-text)',
            fontSize: 'var(--fs-body)',
            fontWeight: 'var(--fw-semibold)',
            lineHeight: 1.6,
            wordBreak: 'keep-all',
          }}>
            {report.one_liner}
          </p>
        )}

        {/* Action row — primary pill (report only), owner: edit + share
            circles, viewer: reaction pill. */}
        <div className={s.topActions}>
          {board?.final_report && (
            <button
              onClick={() => navigate(`/board/${board.board_id}/report`)}
              className={`${s.pill} ${s.pillPrimary}`}
            >
              {t('board.viewReport')}
            </button>
          )}
          {isOwner ? (
            <>
              <button
                onClick={() => {
                  if (isEditMode) { setIsEditMode(false); setSelectedIds(new Set()) }
                  else { setIsEditMode(true); setSelectedIds(new Set()) }
                }}
                disabled={!isEditMode && (!board || buildings.length === 0)}
                aria-label={isEditMode ? t('board.cancel') : t('board.editBoard')}
                aria-pressed={isEditMode}
                className={`${s.circ}${isEditMode ? ` ${s.active}` : ''}`}
                style={board?.final_report ? undefined : { marginLeft: 'auto' }}
              >
                {isEditMode ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                )}
              </button>
              <button
                onClick={handleShare}
                aria-label={t('board.share')}
                className={s.circ}
                style={shareCopied ? { color: 'var(--accent-2)', borderColor: 'var(--accent-2)' } : undefined}
              >
                {shareCopied ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
                    <polyline points="16 6 12 2 8 6"/>
                    <line x1="12" y1="2" x2="12" y2="15"/>
                  </svg>
                )}
              </button>
            </>
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
            <span className={s.ownerName}>{board.user.display_name || ''}</span>
            <span aria-hidden="true">›</span>
          </button>
        )}

        {/* Owner-only secondary controls kept from the previous layout: board
            rename (the cover now shows the persona name) and resume. */}
        {isOwner && (
          <div style={{ margin: '16px 8px 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {isEditingName ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  ref={nameInputRef}
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  onKeyDown={handleNameKeyDown}
                  onBlur={commitNameEdit}
                  disabled={nameSaving}
                  maxLength={100}
                  style={{
                    flex: 1,
                    fontSize: 'var(--fs-body)',
                    fontWeight: 'var(--fw-semibold)',
                    color: 'var(--color-text)',
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '6px 12px',
                    fontFamily: 'inherit',
                    outline: 'none',
                  }}
                />
                <FloatingIconButton
                  onMouseDown={e => { e.preventDefault(); commitNameEdit() }}
                  ariaLabel={t('board.save')}
                  disabled={nameSaving}
                  style={{ background: 'var(--accent-1)', borderColor: 'var(--accent-1)', color: '#fff' }}
                >
                  <span style={{ fontSize: 'var(--fs-caption)', fontWeight: 'var(--fw-bold)', lineHeight: 1 }}>{nameSaving ? '…' : '✓'}</span>
                </FloatingIconButton>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  minWidth: 0,
                  color: 'var(--color-text-dim)',
                  fontSize: 'var(--fs-caption)',
                  fontWeight: 'var(--fw-medium)',
                  wordBreak: 'keep-all',
                }}>
                  {boardName}
                </span>
                <FloatingIconButton onClick={startEditingName} ariaLabel={t('board.editName')}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </FloatingIconButton>
              </div>
            )}
            {onResume && (
              <button
                onClick={() => onResume(board?.board_id)}
                disabled={!board}
                className={s.ctaSecondary}
                style={{
                  minHeight: 44,
                  padding: '0 16px',
                  fontSize: 'var(--fs-body)',
                  fontWeight: 'var(--fw-semibold)',
                  cursor: !board ? 'default' : 'pointer',
                  opacity: !board ? 0.4 : 1,
                }}
              >
                {t('board.continueExploring')}
              </button>
            )}
          </div>
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
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 20,
        }}>
          {[1, 2, 3, 4].map(i => (
            <Skeleton key={i} radius="var(--radius-lg)" style={{ height: 'auto', aspectRatio: '4 / 5' }} />
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
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 20,
          ...(isEditMode ? { paddingBottom: 56 } : null),
        }}>
          {buildings.map((building, index) => {
            const bid = building.image_id || building.canonical_bld_id || building.building_id || building.id
            return (
            <BuildingTile
              key={bid}
              building={building}
              fromProjectId={isOwner ? boardId : null}
              rank={index + 1}
              savedIds={localSavedIds}
              referrer={location.pathname}
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
              onClick={() => { setIsEditMode(false); setSelectedIds(new Set()) }}
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
              onClick={handleDeleteSelected}
              disabled={selectedIds.size === 0 || deleteInProgress}
              style={{
                flex: 2, minHeight: 44, borderRadius: 'var(--radius-md)',
                background: selectedIds.size > 0 ? 'var(--color-text)' : 'var(--color-surface-2)',
                color: selectedIds.size > 0 ? 'var(--color-bg)' : 'var(--color-text-dim)',
                border: 'none',
                boxShadow: selectedIds.size > 0 ? '0 6px 18px rgba(0,0,0,.25)' : 'none',
                fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-semibold)',
                cursor: selectedIds.size === 0 ? 'default' : 'pointer',
                fontFamily: 'inherit',
                opacity: deleteInProgress ? 0.6 : 1,
                transition: 'background var(--motion-normal) var(--motion-ease), color var(--motion-normal) var(--motion-ease)',
              }}
            >
              {deleteInProgress
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
