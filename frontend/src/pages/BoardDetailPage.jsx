import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import { updateProject } from '../api/projects.js'
import { reactToProject, unreactToProject } from '../api/social.js'
import BuildingTile from './boardDetail/BuildingTile'
import RecommendedTile from './boardDetail/RecommendedTile'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// TODO(claude): Replace MOCK_BOARD with API call to GET /api/v1/boards/${boardId}/
// Returns: { board_id, name, visibility, owner{user_id, display_name, avatar_url},
// buildings[], reaction_count, is_reacted }
// TODO(claude): Backend should add `cover_image_url` to Board Detail response (or
// derive on the frontend from buildings[0].image_url as fallback). Currently this
// mockup shows it as a top-level field.
const MOCK_BOARD = {
  board_id: "proj_123",
  name: "Museum References",
  visibility: "public",
  cover_image_url: "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1600&q=80",
  owner: {
    user_id: 1,
    display_name: "Kim Minseo",
    avatar_url: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&q=80",
  },
  buildings: [
    {
      building_id: "B00042",
      name_en: "Seattle Central Library",
      image_url: "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&q=80",
      architect: "OMA / Rem Koolhaas",
      year: 2004,
      program: "Public",
      city: "Seattle",
    },
    {
      building_id: "B00109",
      name_en: "Casa da Musica",
      image_url: "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800&q=80",
      architect: "OMA / Rem Koolhaas",
      year: 2005,
      program: "Cultural",
      city: "Porto",
    },
    {
      building_id: "B00231",
      name_en: "Heydar Aliyev Center",
      image_url: "https://images.unsplash.com/photo-1511818966892-d7d671e672a2?w=800&q=80",
      architect: "Zaha Hadid",
      year: 2012,
      program: "Cultural",
      city: "Baku",
    },
    {
      building_id: "B00358",
      name_en: "Therme Vals",
      image_url: "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=800&q=80",
      architect: "Peter Zumthor",
      year: 1996,
      program: "Sports",
      city: "Vals",
    },
    {
      building_id: "B00413",
      name_en: "Centre Pompidou",
      image_url: "https://images.unsplash.com/photo-1524815340653-53d719ce3660?w=800&q=80",
      architect: "Renzo Piano",
      year: 1977,
      program: "Museum",
      city: "Paris",
    },
    {
      building_id: "B00504",
      name_en: "Vitra Fire Station",
      image_url: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80",
      architect: "Zaha Hadid",
      year: 1993,
      program: "Public",
      city: "Weil am Rhein",
    },
    {
      building_id: "B00612",
      name_en: "Fondazione Prada",
      image_url: "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=800&q=80",
      architect: "OMA / Rem Koolhaas",
      year: 2015,
      program: "Museum",
      city: "Milan",
    },
    {
      building_id: "B00718",
      name_en: "Bruder Klaus Field Chapel",
      image_url: "https://images.unsplash.com/photo-1506146332389-18140dc7b2fb?w=800&q=80",
      architect: "Peter Zumthor",
      year: 2007,
      program: "Religion",
      city: "Mechernich",
    },
    {
      building_id: "B00802",
      name_en: "Milstein Hall",
      image_url: "https://images.unsplash.com/photo-1486718448742-163732cd1544?w=800&q=80",
      architect: "OMA / Rem Koolhaas",
      year: 2011,
      program: "Public",
      city: "Ithaca",
    },
    {
      building_id: "B00917",
      name_en: "Maxxi Museum",
      image_url: "https://images.unsplash.com/photo-1496564203457-11bb12075d90?w=800&q=80",
      architect: "Zaha Hadid",
      year: 2010,
      program: "Museum",
      city: "Rome",
    },
    {
      building_id: "B01024",
      name_en: "Kolumba Museum",
      image_url: "https://images.unsplash.com/photo-1481026469463-66327c86e544?w=800&q=80",
      architect: "Peter Zumthor",
      year: 2007,
      program: "Museum",
      city: "Cologne",
    },
    {
      building_id: "B01138",
      name_en: "Whitney Museum",
      image_url: "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=800&q=80",
      architect: "Renzo Piano",
      year: 2015,
      program: "Museum",
      city: "New York",
    },
  ],
  reaction_count: 7,
  is_reacted: false,
}

export default function BoardDetailPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const rawBoardId = useParams().boardId
  const boardId = UUID_RE.test(String(rawBoardId || '')) ? rawBoardId : null
  const { board, recommended: hookRecommended, loading, resultLoading, error } = useBoard(boardId)

  const [isReacted, setIsReacted] = useState(false)
  const [reactionCount, setReactionCount] = useState(0)
  const [isReactionPending, setIsReactionPending] = useState(false)
  const [reactionError, setReactionError] = useState(null)
  const [isReactHovered, setIsReactHovered] = useState(false)
  const [isReactPressed, setIsReactPressed] = useState(false)
  const [isOwnerRowHovered, setIsOwnerRowHovered] = useState(false)
  const [isBackHovered, setIsBackHovered] = useState(false)
  const [isShareHovered, setIsShareHovered] = useState(false)
  const [localSavedIds, setLocalSavedIds] = useState([])
  const [localName, setLocalName] = useState('')
  const [isEditingName, setIsEditingName] = useState(false)
  const [editName, setEditName] = useState('')
  const [nameSaving, setNameSaving] = useState(false)
  const [shareCopied, setShareCopied] = useState(false)
  const reportRef = useRef(null)
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
      setReactionError(err.message || 'Failed to update reaction.')
    } finally {
      setIsReactionPending(false)
    }
  }

  async function handleShare() {
    const report = board?.final_report
    const shareData = {
      title: (localName || board?.name || 'Board') + (report?.persona_type ? ` · ${report.persona_type}` : ''),
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
  const statusMessage = error?.message || (loading ? 'Loading board...' : 'This board is empty')

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(80px + env(safe-area-inset-bottom))',
    }}>
      {/* Hero cover */}
      <div style={{
        position: 'relative',
        width: '100%',
        height: 'clamp(280px, 42vw, 360px)',
        overflow: 'hidden',
        background: 'var(--color-surface)',
      }}>
        {coverImage && (
          <img
            src={coverImage}
            alt={board?.name || 'Board cover'}
            fetchpriority="high"
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
        )}

        {/* Bottom gradient overlay (specified in brief) */}
        <div style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(to top, var(--color-bg) 0%, rgba(15,15,15,0.85) 30%, rgba(15,15,15,0.4) 60%, transparent 100%)',
          pointerEvents: 'none',
        }} />

        {/* Sticky header bar overlaid on top of cover */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          padding: '12px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          zIndex: 5,
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, transparent 100%)',
        }}>
          <button
            onClick={() => navigate(-1)}
            onMouseEnter={() => setIsBackHovered(true)}
            onMouseLeave={() => setIsBackHovered(false)}
            aria-label="Back"
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              background: 'rgba(0,0,0,0.4)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: isBackHovered ? '#ec4899' : '#fff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 0,
              transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: isBackHovered ? 'scale(1.05)' : 'scale(1)',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"></line>
              <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
          </button>

          <button
            onClick={handleShare}
            onMouseEnter={() => setIsShareHovered(true)}
            onMouseLeave={() => setIsShareHovered(false)}
            aria-label="Share"
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              background: 'rgba(0,0,0,0.4)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: shareCopied ? '#34d399' : (isShareHovered ? '#ec4899' : '#fff'),
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 0,
              transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: isShareHovered ? 'scale(1.05)' : 'scale(1)',
            }}
          >
            {shareCopied ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="18" cy="5" r="3" />
                <circle cx="6" cy="12" r="3" />
                <circle cx="18" cy="19" r="3" />
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
              </svg>
            )}
          </button>
        </div>

        {/* §3.5.3 PRIVATE-only icon-lock chip — small dark blur circle, white-ish lock SVG.
            PUBLIC renders nothing (public is the default; only flag the exception).
            Anchored to hero top-right, sits alongside the back/share row at z-index 5. */}
        {!isPublic && (
          <div style={{
            position: 'absolute',
            top: 68,
            right: 20,
            zIndex: 5,
            background: 'rgba(0,0,0,0.4)',
            backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
            padding: 6, borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          aria-label="Private board"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="rgba(255,255,255,0.85)" strokeWidth="2"
                 strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
          </div>
        )}

        {/* Hero content overlapping cover bottom */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '24px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          {/* Board name — editable by owner */}
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
                  fontSize: 'clamp(20px, 5vw, 26px)',
                  fontWeight: 700,
                  lineHeight: 1.2,
                  color: '#fff',
                  background: 'rgba(255,255,255,0.12)',
                  border: '1px solid rgba(255,255,255,0.35)',
                  borderRadius: 10,
                  padding: '6px 12px',
                  fontFamily: 'inherit',
                  outline: 'none',
                  backdropFilter: 'blur(8px)',
                }}
              />
              <button
                onMouseDown={e => { e.preventDefault(); commitNameEdit() }}
                disabled={nameSaving}
                style={{
                  width: 36, height: 36, borderRadius: '50%',
                  background: '#ec4899', border: 'none',
                  color: '#fff', fontSize: 16, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {nameSaving ? '…' : '✓'}
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <h1 style={{
                color: '#fff',
                fontSize: 'clamp(24px, 5vw, 28px)',
                fontWeight: 700,
                margin: 0,
                lineHeight: 1.2,
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                textShadow: '0 2px 12px rgba(0,0,0,0.4)',
              }}>
                {localName || board?.name || ''}
              </h1>
              {isOwner && (
                <button
                  onClick={startEditingName}
                  aria-label="Edit board name"
                  style={{
                    flexShrink: 0,
                    marginTop: 4,
                    width: 32, height: 32, borderRadius: '50%',
                    background: 'rgba(0,0,0,0.35)',
                    backdropFilter: 'blur(8px)',
                    border: '1px solid rgba(255,255,255,0.18)',
                    color: 'rgba(255,255,255,0.8)',
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: 0,
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
              )}
            </div>
          )}

          {/* Owner row */}
          <div
            onClick={handleNavigateToOwner}
            onMouseEnter={() => setIsOwnerRowHovered(true)}
            onMouseLeave={() => setIsOwnerRowHovered(false)}
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
              gap: 10,
              cursor: 'pointer',
              padding: '6px 4px',
              minHeight: 44,
              userSelect: 'none',
              alignSelf: 'flex-start',
            }}
          >
            <img
              src={board?.user?.avatar_url || ''}
              alt={board?.user?.display_name || 'Board owner'}
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                objectFit: 'cover',
                border: '1px solid rgba(255,255,255,0.25)',
                background: 'var(--color-surface)',
              }}
            />
            <span style={{
              color: '#fff',
              fontSize: 14,
              fontWeight: 600,
              textDecoration: isOwnerRowHovered ? 'underline' : 'none',
              textUnderlineOffset: 3,
            }}>
              {board?.user?.display_name || ''}
            </span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.65)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </div>

          {/* Meta strip */}
          <p style={{
            color: 'rgba(255,255,255,0.7)',
            fontSize: 12,
            fontWeight: 600,
            margin: 0,
            letterSpacing: '0.02em',
          }}>
            {buildings.length} {buildings.length === 1 ? 'building' : 'buildings'} · {reactionCount} {String.fromCharCode(0x2764)}
          </p>
        </div>
      </div>

      {/* Action row — owner sees edit controls, others see Love This; report button when final_report exists */}
      <div style={{
        padding: '24px 20px 8px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 10,
      }}>
        {isOwner ? (
          <button
            onClick={() => { setIsEditMode(true); setSelectedIds(new Set()) }}
            disabled={!board || buildings.length === 0}
            style={{
              width: '100%',
              maxWidth: 320,
              minHeight: 44,
              padding: '14px 24px',
              borderRadius: 999,
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border)',
              fontSize: 15,
              fontWeight: 700,
              cursor: buildings.length === 0 ? 'default' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              fontFamily: 'inherit',
              opacity: buildings.length === 0 ? 0.4 : 1,
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
            <span>Edit Board</span>
          </button>
        ) : (
          <button
            onClick={handleToggleReaction}
            disabled={!board || isReactionPending}
            onMouseEnter={() => setIsReactHovered(true)}
            onMouseLeave={() => { setIsReactHovered(false); setIsReactPressed(false) }}
            onMouseDown={() => setIsReactPressed(true)}
            onMouseUp={() => setIsReactPressed(false)}
            style={{
              width: '100%',
              maxWidth: 320,
              minHeight: 44,
              padding: '14px 24px',
              borderRadius: 999,
              background: isReacted
                ? 'var(--color-surface)'
                : 'linear-gradient(135deg, #ec4899, #f43f5e)',
              color: isReacted ? '#ec4899' : '#fff',
              border: isReacted ? '1px solid #ec4899' : 'none',
              fontSize: 15,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), filter 0.2s cubic-bezier(0.4, 0, 0.2, 1), background 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: isReactPressed ? 'scale(0.98)' : (isReactHovered ? 'scale(1.02)' : 'scale(1)'),
              filter: isReactHovered && !isReacted ? 'brightness(1.08)' : 'none',
              boxShadow: isReacted ? 'none' : '0 8px 22px rgba(236,72,153,0.32)',
              fontFamily: 'inherit',
            }}
          >
            <svg
              width="18" height="18" viewBox="0 0 24 24"
              fill={isReacted ? '#ec4899' : 'none'}
              stroke={isReacted ? '#ec4899' : 'currentColor'}
              strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
            >
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
            </svg>
            <span>{isReacted ? `Loved · ${reactionCount}` : 'Love this'}</span>
          </button>
        )}
        {board?.final_report && (
          <button
            onClick={() => reportRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            style={{
              width: '100%',
              maxWidth: 320,
              minHeight: 44,
              padding: '12px 24px',
              borderRadius: 999,
              background: 'linear-gradient(135deg, rgba(236,72,153,0.12), rgba(244,63,94,0.12))',
              color: '#ec4899',
              border: '1px solid rgba(236,72,153,0.3)',
              fontSize: 14,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              fontFamily: 'inherit',
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
            <span>페르소나 리포트 보기</span>
          </button>
        )}
      </div>
      {!isOwner && reactionError && (
        <div style={{
          color: 'var(--color-text-muted, #999)',
          fontSize: 12,
          fontWeight: 600,
          padding: '0 20px 4px',
          textAlign: 'center',
        }}>
          {reactionError}
        </div>
      )}

      {/* Persona Report section — only when final_report exists */}
      {board?.final_report && (
        <div ref={reportRef} style={{ maxWidth: 1100, margin: '0 auto', padding: '0 20px 28px' }}>
          <div style={{
            borderRadius: 16,
            border: '1px solid var(--color-border-soft)',
            background: 'var(--color-surface)',
            padding: '20px',
            position: 'relative',
            overflow: 'hidden',
          }}>
            <div style={{
              position: 'absolute', inset: 0,
              background: 'radial-gradient(circle at 0% 0%, rgba(236,72,153,0.07), transparent 60%)',
              pointerEvents: 'none',
            }} />
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  color: 'var(--color-text-muted)',
                  fontSize: 11, fontWeight: 800,
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  margin: '0 0 6px',
                }}>
                  Persona Report
                </p>
                <h3 style={{
                  color: 'var(--color-text)',
                  fontSize: 20, fontWeight: 800,
                  margin: '0 0 6px', lineHeight: 1.1,
                }}>
                  {board.final_report.persona_type}
                </h3>
                <p style={{
                  color: '#ec4899',
                  fontSize: 13, fontWeight: 600,
                  margin: '0 0 10px', lineHeight: 1.45,
                }}>
                  {board.final_report.one_liner}
                </p>
                {board.final_report.description && (
                  <p style={{
                    color: 'var(--color-text-dim)',
                    fontSize: 13, lineHeight: 1.6,
                    margin: '0 0 14px',
                  }}>
                    {board.final_report.description}
                  </p>
                )}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {(board.final_report.dominant_programs || []).map(tag => (
                    <span key={tag} style={{
                      padding: '4px 10px', borderRadius: 999,
                      background: 'rgba(236,72,153,0.1)',
                      border: '1px solid rgba(236,72,153,0.22)',
                      color: '#ec4899',
                      fontSize: 11, fontWeight: 700,
                    }}>{tag}</span>
                  ))}
                  {(board.final_report.dominant_styles || []).map(tag => (
                    <span key={tag} style={{
                      padding: '4px 10px', borderRadius: 999,
                      background: 'rgba(99,102,241,0.1)',
                      border: '1px solid rgba(99,102,241,0.22)',
                      color: 'var(--color-text-dim)',
                      fontSize: 11, fontWeight: 700,
                    }}>{tag}</span>
                  ))}
                  {(board.final_report.dominant_materials || []).map(tag => (
                    <span key={tag} style={{
                      padding: '4px 10px', borderRadius: 999,
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid var(--color-border-soft)',
                      color: 'var(--color-text-dim)',
                      fontSize: 11, fontWeight: 700,
                    }}>{tag}</span>
                  ))}
                </div>
              </div>
              {board.report_image && (
                <img
                  src={`data:image/png;base64,${board.report_image}`}
                  alt="Persona"
                  style={{ width: 80, height: 80, borderRadius: 12, objectFit: 'cover', flexShrink: 0 }}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Buildings section */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0' }}>
        <h3 style={{
          color: 'var(--color-text)',
          fontSize: 20,
          fontWeight: 700,
          margin: '32px 0 16px',
          padding: '0 20px',
          letterSpacing: '-0.01em',
        }}>
          Buildings
        </h3>

        {buildings.length === 0 ? (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '60px 20px',
            color: 'var(--color-text-muted, #9ca3af)',
            textAlign: 'center',
            gap: 16,
          }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5 }}>
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <circle cx="8.5" cy="8.5" r="1.5"></circle>
              <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
            <p style={{
              color: 'var(--color-text-muted, #9ca3af)',
              fontSize: 14,
              fontWeight: 600,
              margin: 0,
            }}>
              {statusMessage}
            </p>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 20,
            padding: '0 20px',
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
      </div>

      {(recommended.length > 0 || resultLoading) && (
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0' }}>
          <div style={{ height: 1, background: 'var(--color-border)', margin: '0 20px' }} />
          <h3 style={{
            color: 'var(--color-text)',
            fontSize: 20,
            fontWeight: 700,
            margin: '32px 0 16px',
            padding: '0 20px',
            letterSpacing: '-0.01em',
          }}>
            Recommended
          </h3>
          {resultLoading && recommended.length === 0 ? (
            <div style={{
              padding: '8px 20px 24px',
              color: 'var(--color-text-muted)',
              fontSize: 13,
              fontWeight: 500,
            }}>
              Loading recommendations...
            </div>
          ) : (
            <>
              <p style={{
                color: 'var(--color-text-dimmer)',
                fontSize: 13,
                fontWeight: 500,
                margin: '0 0 16px',
                padding: '0 20px',
              }}>
                Based on your preferences
              </p>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                gap: 12,
                padding: '0 20px',
              }}>
                {recommended.slice(0, 10).map(card => (
                  <RecommendedTile
                    key={card.image_id}
                    card={card}
                    onClick={() => navigate('/buildings/' + card.image_id)}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Edit mode sticky bottom bar */}
      {isEditMode && (
        <div style={{
          position: 'fixed',
          bottom: 'calc(64px + env(safe-area-inset-bottom, 0px))',
          left: 0, right: 0,
          padding: '12px 20px',
          background: 'var(--color-surface)',
          borderTop: '1px solid var(--color-border)',
          backdropFilter: 'blur(20px)',
          display: 'flex',
          gap: 10,
          zIndex: 50,
        }}>
          <button
            onClick={() => { setIsEditMode(false); setSelectedIds(new Set()) }}
            style={{
              flex: 1, minHeight: 44, borderRadius: 14,
              background: 'var(--color-surface-2)',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border)',
              fontSize: 14, fontWeight: 700,
              cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleDeleteSelected}
            disabled={selectedIds.size === 0 || deleteInProgress}
            style={{
              flex: 2, minHeight: 44, borderRadius: 14,
              background: selectedIds.size > 0 ? 'var(--color-destructive, #ef4444)' : 'var(--color-surface-2)',
              color: selectedIds.size > 0 ? '#fff' : 'var(--color-text-dim)',
              border: 'none',
              fontSize: 14, fontWeight: 700,
              cursor: selectedIds.size === 0 ? 'default' : 'pointer',
              fontFamily: 'inherit',
              opacity: deleteInProgress ? 0.6 : 1,
              transition: 'background 0.2s, color 0.2s',
            }}
          >
            {deleteInProgress
              ? 'Deleting...'
              : selectedIds.size > 0
                ? `Delete ${selectedIds.size} card${selectedIds.size > 1 ? 's' : ''}`
                : 'Select cards to delete'}
          </button>
        </div>
      )}
    </div>
  )
}
