import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import { updateProject, getProjectReportImage } from '../api/projects.js'
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

  useEffect(() => {
    if (!board) return
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
  const personaImage = board?.report_image
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

  function handleToggleBuildingSelect(id) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function handleDeleteSelected() {
    if (!isOwner || selectedIds.size === 0 || deleteInProgress) return
    setDeleteInProgress(true)
    const ids = [...selectedIds]
    try {
      await updateProject(boardId, { remove_building_ids: ids })
      setLocalBuildings(prev => (prev || []).filter(b => {
        const bid = b.image_id || b.canonical_bld_id || b.building_id || b.id
        return !ids.includes(bid)
      }))
      setSelectedIds(new Set())
      setIsEditMode(false)
    } catch {
      // keep state on error
    } finally {
      setDeleteInProgress(false)
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
  const report = board?.final_report ? localizeReport(board.final_report, language) : null
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

      {/* Edit mode floating action bar — glass capsule, consistent with the TabBar. */}
      {isEditMode && (
        <div style={{
          position: 'fixed',
          left: 16, right: 16,
          bottom: 'var(--tabbar-clearance)',
          maxWidth: 420,
          margin: '0 auto',
          padding: 10,
          borderRadius: 'var(--radius-lg)',
          background: 'var(--tabbar-glass-bg)',
          border: '1px solid var(--tabbar-glass-border)',
          boxShadow: 'var(--tabbar-glass-shadow)',
          backdropFilter: 'blur(20px) saturate(160%)',
          WebkitBackdropFilter: 'blur(20px) saturate(160%)',
          display: 'flex',
          gap: 10,
          zIndex: 200,
        }}>
          <button
            onClick={() => { setIsEditMode(false); setSelectedIds(new Set()) }}
            className={s.ctaSecondary}
            style={{
              flex: 1, minHeight: 44,
              fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-semibold)',
              cursor: 'pointer',
            }}
          >
            {t('board.cancel')}
          </button>
          <button
            onClick={handleDeleteSelected}
            disabled={selectedIds.size === 0 || deleteInProgress}
            style={{
              flex: 2, minHeight: 44, borderRadius: 'var(--radius-md)',
              background: selectedIds.size > 0 ? 'var(--color-destructive)' : 'var(--color-surface-2)',
              color: selectedIds.size > 0 ? '#fff' : 'var(--color-text-dim)',
              border: 'none',
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
      )}
    </PageShell>
  )
}
