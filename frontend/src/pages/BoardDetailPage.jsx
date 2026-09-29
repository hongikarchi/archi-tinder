import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import { updateProject } from '../api/projects.js'
import { reactToProject, unreactToProject } from '../api/social.js'
import BuildingTile from './boardDetail/BuildingTile'
import RecommendedTile from './boardDetail/RecommendedTile'
import ArchitectSection from './boardDetail/ArchitectSection'
import BoardCover from './boardDetail/BoardCover'
import { useTranslation } from '../i18n/index.js'
import { localizeReport } from '../utils/reportText.js'
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

// UI-CONSISTENCY-B Phase 3a, decision 7 (.claude/plans/ui-consistency-b.md):
// option (a) shipped — cover photo as a contained card below the chrome, no
// full-bleed hero. Flip this to `false` to switch to option (b) (drop the
// cover entirely, text-only header) — the only line that needs to change.
const SHOW_COVER = true

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
          <PageBackButton onClick={() => navigate(-1)} label={t('board.back')} />
          <PageTopControls onLogout={onLogout} />
          <PageLogoHeader />
          {/* Share — stacked under the back button (ArchitectProfilePage precedent:
              top:50/left:12, zIndex 299 — one below PageBackButton's 300), so its
              44px invisible hit area never collides with PageTopControls on the
              right at 390px width. */}
          <FloatingIconButton
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
          </FloatingIconButton>
        </>
      }
    >
      {/* Cover card — option (a). See SHOW_COVER above for the option (b) switch. */}
      {SHOW_COVER && (
        <BoardCover imageUrl={coverImage} alt={boardName || t('board.coverAlt')} />
      )}

      {/* Info block — title / meta line / action row, one left-aligned column.
          A single ternary on `headerLoading` so the 16 / 8 / 20 vertical
          rhythm lives in exactly one place per branch (real vs skeleton) and
          the owner-vs-non-owner action row is never guessed before `board`
          arrives. */}
      {headerLoading ? (
        <div style={{ marginTop: 16 }}>
          <Skeleton width="70%" height={28} radius="var(--radius-sm)" />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
            <Skeleton circle height={24} />
            <Skeleton width={100} height={16} />
            <Skeleton width={60} height={16} />
          </div>
          <div className={s.actionRow} style={{ marginTop: 20 }}>
            <Skeleton height={44} radius="var(--radius-md)" style={{ flex: 1 }} />
            <Skeleton height={44} radius="var(--radius-md)" style={{ flex: 1 }} />
          </div>
        </div>
      ) : (
      <div style={{ marginTop: 16 }}>
        {/* Title row — board name, editable inline by the owner. The rename
            pencil sits inline right after the title text (8px gap) instead of
            being pushed to the far edge; title may wrap, pencil stays
            vertically centered on the line. */}
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
                fontSize: 'var(--fs-title)',
                fontWeight: 'var(--fw-bold)',
                lineHeight: 1.2,
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
            {/* DESIGN.md §4: 2-line clamp is reserved for card titles — the
                board title here wraps naturally, no line-clamp. `flex: '0 1
                auto'` (not `flex: 1`) so the pencil sits right after the text
                instead of being pushed to the far edge by a stretched title. */}
            <PageTitle style={{ margin: 0, flex: '0 1 auto', minWidth: 0 }}>
              {boardName}
            </PageTitle>
            {isOwner && (
              <FloatingIconButton onClick={startEditingName} ariaLabel={t('board.editName')}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </FloatingIconButton>
            )}
          </div>
        )}

        {/* Meta line — owner link · private (owner-only visibility) · building
            count · reaction count, all vertically centered on one wrapping
            row, dot-separated. */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          columnGap: 6,
          rowGap: 4,
          marginTop: 8,
          fontSize: 'var(--fs-caption)',
          fontWeight: 'var(--fw-medium)',
          color: 'var(--color-text-dim)',
        }}>
          {/* Owner link. `padding`/negative `margin` expand the tap target to
              the DESIGN.md §3.2 desktop tier (32px) without affecting the
              24px visual row height — same "invisible expanded hit area"
              idea FloatingIconButton uses. Capped at 4px (not the full 10px
              needed for the 44px mobile tier) so the expansion stays inside
              the 8px gap above this line and never overlaps the rename
              pencil's own 44px hit area on the title row. */}
          <div
            onClick={handleNavigateToOwner}
            className={s.ownerRow}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                handleNavigateToOwner()
              }
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              cursor: 'pointer',
              padding: '4px 0',
              margin: '-4px 0',
              userSelect: 'none',
            }}
          >
            <img
              src={board?.user?.avatar_url || ''}
              alt={board?.user?.display_name || t('board.ownerAlt')}
              style={{
                width: 24,
                height: 24,
                borderRadius: '50%',
                objectFit: 'cover',
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface)',
              }}
            />
            <span className={s.ownerName} style={{
              color: 'var(--color-text)',
              fontSize: 'var(--fs-caption)',
              fontWeight: 'var(--fw-semibold)',
              textUnderlineOffset: 3,
            }}>
              {board?.user?.display_name || ''}
            </span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-dim)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </div>

          {/* PRIVATE-only — plain inline icon + text, no bordered chip. */}
          {!isPublic && (
            <>
              <span aria-hidden="true">·</span>
              <span aria-label={t('board.privateBoardAria')} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
                {t('board.private')}
              </span>
            </>
          )}

          <span aria-hidden="true">·</span>
          <span>{t(buildings.length === 1 ? 'board.buildingCountOne' : 'board.buildingCountMany', { n: buildings.length })}</span>

          <span aria-hidden="true">·</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden="true">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
            </svg>
            {reactionCount}
          </span>
        </div>

        {/* Action row — owner sees edit controls, others see Love This;
            report button joins the same row when final_report exists. Each
            button is flex:1 so the row spans the full column width, left
            edge aligned with the title. */}
        <div className={s.actionRow} style={{ marginTop: 20 }}>
          {isOwner ? (
            <>
              <button
                onClick={() => {
                  if (isEditMode) { setIsEditMode(false); setSelectedIds(new Set()) }
                  else { setIsEditMode(true); setSelectedIds(new Set()) }
                }}
                disabled={!isEditMode && (!board || buildings.length === 0)}
                className={`${s.ctaSecondary}${isEditMode ? ` ${s.editModeActive}` : ''}`}
                style={{
                  flex: '1 1 0',
                  minWidth: 0,
                  minHeight: 44,
                  padding: '14px 16px',
                  fontSize: 'var(--fs-body)',
                  fontWeight: 'var(--fw-semibold)',
                  cursor: (!isEditMode && buildings.length === 0) ? 'default' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  opacity: (!isEditMode && buildings.length === 0) ? 0.4 : 1,
                }}
              >
                {isEditMode ? (
                  <>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                    <span>{t('board.cancel')}</span>
                  </>
                ) : (
                  <>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                    <span>{t('board.editBoard')}</span>
                  </>
                )}
              </button>
              {onResume && (
                <button
                  onClick={() => onResume(board?.board_id)}
                  disabled={!board}
                  className={s.ctaPrimary}
                  style={{
                    flex: '1 1 0',
                    minWidth: 0,
                    minHeight: 44,
                    padding: '14px 16px',
                    fontSize: 'var(--fs-body)',
                    fontWeight: 'var(--fw-semibold)',
                    cursor: !board ? 'default' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    opacity: !board ? 0.4 : 1,
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                  </svg>
                  <span>{t('board.continueExploring')}</span>
                </button>
              )}
            </>
          ) : (
            <button
              onClick={handleToggleReaction}
              disabled={!board || isReactionPending}
              className={isReacted ? `${s.ctaSecondary} ${s.reacted}` : s.ctaPrimary}
              style={{
                flex: '1 1 0',
                minWidth: 0,
                minHeight: 44,
                padding: '14px 16px',
                fontSize: 'var(--fs-body)',
                fontWeight: 'var(--fw-semibold)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              <svg
                width="18" height="18" viewBox="0 0 24 24"
                fill={isReacted ? 'currentColor' : 'none'}
                stroke="currentColor"
                strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
              >
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
              </svg>
              <span>{isReacted ? t('board.loved', { r: reactionCount }) : t('board.loveThis')}</span>
            </button>
          )}
          {board?.final_report && (
            <button
              onClick={() => navigate(`/board/${board.board_id}/report`)}
              className={s.ctaSecondary}
              style={{
                flex: '1 1 0',
                minWidth: 0,
                minHeight: 44,
                padding: '14px 16px',
                background: 'color-mix(in srgb, var(--accent-1) 8%, var(--color-surface))',
                color: 'var(--accent-1)',
                border: '1px solid color-mix(in srgb, var(--accent-1) 30%, transparent)',
                fontSize: 'var(--fs-body)',
                fontWeight: 'var(--fw-semibold)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
              <span>{t('board.viewReport')}</span>
            </button>
          )}
        </div>
        {!isOwner && reactionError && (
          <div style={{
            color: 'var(--color-text-muted)',
            fontSize: 'var(--fs-caption)',
            fontWeight: 'var(--fw-semibold)',
            margin: '8px 0 0',
          }}>
            {reactionError}
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
