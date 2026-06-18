import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getUserProfile } from '../api/client.js'
import { updateProject, deleteProject } from '../api/projects.js'
import { purgeChatCache } from '../utils/appHelpers.js'
import { getUserSavedStudios } from '../api/architects.js'
import ShareCardModal from '../components/ShareCardModal.jsx'
import ProfileHeader from './userProfile/ProfileHeader'
import ProfileHero from './userProfile/ProfileHero'
import BoardGrid from './userProfile/BoardGrid'

/**
 * formatBoardDate — converts ISO 8601 timestamp to "Month YYYY" display string.
 * Handles null / undefined / invalid strings safely.
 */
function formatBoardDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    return d.toLocaleString('en-US', { month: 'long', year: 'numeric' })
  } catch {
    return ''
  }
}

export default function UserProfilePage({ onLogout, onResumeProject, onNewProjectSession }) {
  const { userId: routeUserId } = useParams()
  const navigate = useNavigate()

  const sessionUserId = sessionStorage.getItem('archithon_user')
  const rawUserId = routeUserId || sessionUserId
  // Defense-in-depth: only allow numeric user IDs in API path. Backend route
  // uses <int:user_id> so non-numeric values 404 anyway, but reject early to
  // avoid path-traversal-shaped values reaching fetch().
  const effectiveUserId = /^\d+$/.test(String(rawUserId || '')) ? rawUserId : null
  const isMe = !routeUserId || String(routeUserId) === String(sessionUserId)

  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Boards pagination state — separate from user profile so we can append incrementally
  const [boards, setBoards] = useState([])
  const [boardsTotalCount, setBoardsTotalCount] = useState(0)
  const [boardsPage, setBoardsPage] = useState(1)
  const [boardsHasMore, setBoardsHasMore] = useState(false)
  const [boardsLoading, setBoardsLoading] = useState(false)
  const sentinelRef = useRef(null)

  // Share card modal
  const [shareOpen, setShareOpen] = useState(false)
  // Tab state — 'boards' | 'studios'
  const [activeTab, setActiveTab] = useState('boards')
  const [savedStudios, setSavedStudios] = useState(null)  // null = not loaded yet
  const [studiosLoading, setStudiosLoading] = useState(false)

  // MINOR #1: inline error banner for failed board actions (optimistic revert feedback)
  const [boardActionError, setBoardActionError] = useState(null)
  // MINOR #3: per-board pending set — blocks rapid double-toggle
  const [pendingVisibility, setPendingVisibility] = useState(() => new Set())

  // P6 bulk edit mode state
  const [selectMode, setSelectMode] = useState(false)
  const [selectedBoards, setSelectedBoards] = useState(() => new Set())
  const [bulkPending, setBulkPending] = useState(false)
  const [confirmingBulkDelete, setConfirmingBulkDelete] = useState(false)
  const bulkDeleteBtnRef = useRef(null)
  const bulkConfirmTimerRef = useRef(null)

  // Helper: exit select mode and reset all selection state.
  // NOTE: does NOT clear bulkPending — bulk handlers clear it themselves after
  // Promise.allSettled resolves, so Cancel during a pending op cannot fire a
  // second op (MINOR #3).
  const exitSelectMode = useCallback(() => {
    setSelectMode(false)
    setSelectedBoards(new Set())
    setConfirmingBulkDelete(false)
    clearTimeout(bulkConfirmTimerRef.current)
  }, [])

  const handleStudiosTab = async () => {
    if (isMe) {
      navigate('/my/liked-offices')
      return
    }
    setActiveTab('studios')
    if (savedStudios !== null) return  // already loaded
    setStudiosLoading(true)
    try {
      const data = await getUserSavedStudios(effectiveUserId)
      setSavedStudios(data)
    } catch {
      setSavedStudios([])
    } finally {
      setStudiosLoading(false)
    }
  }

  // Adapter: map project_id -> board_id + format ISO date -> "Month YYYY"
  function adaptBoard(b) {
    return { ...b, board_id: b.project_id, date: formatBoardDate(b.date) }
  }

  useEffect(() => {
    if (!effectiveUserId) {
      setLoading(false)
      setError('No user ID found.')
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    // Reset boards state on user change
    setBoards([])
    setBoardsPage(1)
    setBoardsHasMore(false)
    getUserProfile(effectiveUserId, { boardsPage: 1, boardsPageSize: 12 })
      .then(data => {
        if (cancelled) return
        const boardsPayload = data.boards || {}
        const items = (boardsPayload.items || []).map(adaptBoard)
        setBoards(items)
        setBoardsTotalCount(boardsPayload.total_count ?? items.length)
        setBoardsHasMore(boardsPayload.has_more ?? false)
        setBoardsPage(boardsPayload.page ?? 1)
        // Store profile without boards — boards are in separate state
        setUser({ ...data, boards: undefined })
      })
      .catch(err => {
        if (cancelled) return
        setError(err.message || 'Failed to load profile.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [effectiveUserId])

  const loadMoreBoards = useCallback(async () => {
    if (boardsLoading || !boardsHasMore || !effectiveUserId) return
    setBoardsLoading(true)
    try {
      const nextPage = boardsPage + 1
      const data = await getUserProfile(effectiveUserId, { boardsPage: nextPage, boardsPageSize: 12 })
      const boardsPayload = data.boards || {}
      const items = (boardsPayload.items || []).map(adaptBoard)
      setBoards(prev => [...prev, ...items])
      setBoardsPage(boardsPayload.page ?? nextPage)
      setBoardsHasMore(boardsPayload.has_more ?? false)
    } catch (err) {
      console.error('[boards pagination]', err)
    } finally {
      setBoardsLoading(false)
    }
  }, [boardsLoading, boardsHasMore, boardsPage, effectiveUserId])

  // IntersectionObserver — trigger loadMoreBoards when sentinel is visible
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      entries => { if (entries[0].isIntersecting) loadMoreBoards() },
      { rootMargin: '200px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loadMoreBoards])

  // Auto-dismiss board action error after 4s
  useEffect(() => {
    if (!boardActionError) return
    const t = setTimeout(() => setBoardActionError(null), 4000)
    return () => clearTimeout(t)
  }, [boardActionError])

  // P6: clear bulk confirm timer on unmount
  useEffect(() => () => clearTimeout(bulkConfirmTimerRef.current), [])

  // P6: click-outside cancels bulk delete confirm (mirrors BoardCard pattern)
  useEffect(() => {
    if (!confirmingBulkDelete) return
    function handleOutside(e) {
      if (bulkDeleteBtnRef.current && !bulkDeleteBtnRef.current.contains(e.target)) {
        clearTimeout(bulkConfirmTimerRef.current)
        setConfirmingBulkDelete(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [confirmingBulkDelete])

  // Optimistic visibility toggle — reverts on API failure.
  // MINOR #3: per-board pending guard blocks rapid double-toggle stale-prev race.
  const handleVisibilityChange = useCallback(async (boardId, next) => {
    if (pendingVisibility.has(boardId)) return
    const prev = boards.find(b => b.board_id === boardId)?.visibility
    if (!prev) return
    setPendingVisibility(s => { const n = new Set(s); n.add(boardId); return n })
    setBoards(bs => bs.map(b => b.board_id === boardId ? { ...b, visibility: next } : b))
    try {
      await updateProject(boardId, { visibility: next })
    } catch (err) {
      setBoards(bs => bs.map(b => b.board_id === boardId ? { ...b, visibility: prev } : b))
      setBoardActionError({ type: 'patch', msg: 'Failed to update board visibility. Reverted.' })
      console.error('[UserProfilePage] visibility toggle failed, reverted', err)
    } finally {
      setPendingVisibility(s => { const n = new Set(s); n.delete(boardId); return n })
    }
  }, [boards, pendingVisibility])

  // Optimistic delete — reverts on API failure.
  // MINOR #2: id-based revert preserves concurrently-paginated boards that
  //           arrived after the snapshot was captured.
  const handleDelete = useCallback(async (boardId) => {
    const deletedBoard = boards.find(b => b.board_id === boardId)
    const deletedIndex = boards.findIndex(b => b.board_id === boardId)
    if (!deletedBoard) return
    setBoards(bs => bs.filter(b => b.board_id !== boardId))
    setBoardsTotalCount(t => Math.max(0, t - 1))
    // Purge this project's chat cache keys on delete.
    purgeChatCache(String(boardId))
    try {
      await deleteProject(boardId)
    } catch (err) {
      // Re-insert at original index; any boards paginated in during the flight are preserved.
      setBoards(bs => {
        const next = [...bs]
        const insertAt = Math.min(deletedIndex, next.length)
        next.splice(insertAt, 0, deletedBoard)
        return next
      })
      setBoardsTotalCount(t => t + 1)
      setBoardActionError({ type: 'delete', msg: 'Failed to delete board. Restored.' })
      console.error('[UserProfilePage] delete failed, restored', err)
    }
  }, [boards])

  // P6: derived — whether all currently-loaded boards are selected
  const allSelected = useMemo(
    () => boards.length > 0 && boards.every(b => selectedBoards.has(b.board_id)),
    [boards, selectedBoards],
  )

  // P6: toggle a single board in the selection set
  const handleSelectToggle = useCallback((boardId) => {
    setSelectedBoards(prev => {
      const next = new Set(prev)
      if (next.has(boardId)) next.delete(boardId)
      else next.add(boardId)
      return next
    })
  }, [])

  // P6: bulk visibility update (optimistic, partial revert on failure)
  const handleBulkVisibility = useCallback(async (next) => {
    if (bulkPending) return
    const ids = [...selectedBoards]
    if (ids.length === 0) return
    // Snapshot pre-state per id for revert
    const prevMap = Object.fromEntries(
      ids.map(id => [id, boards.find(b => b.board_id === id)?.visibility])
    )
    setBulkPending(true)
    // Optimistic update
    setBoards(bs => bs.map(b => selectedBoards.has(b.board_id) ? { ...b, visibility: next } : b))
    const results = await Promise.allSettled(ids.map(id => updateProject(id, { visibility: next })))
    const failedIds = results
      .map((r, i) => r.status === 'rejected' ? ids[i] : null)
      .filter(Boolean)
    if (failedIds.length > 0) {
      // Revert only the failed ones
      setBoards(bs => bs.map(b => failedIds.includes(b.board_id)
        ? { ...b, visibility: prevMap[b.board_id] ?? b.visibility }
        : b
      ))
      setBoardActionError({
        type: 'bulk-visibility',
        msg: `Failed to update ${failedIds.length} board(s). Reverted.`,
      })
    }
    // Clear pending BEFORE exitSelectMode so Cancel during in-flight op cannot
    // trigger a second bulk op (MINOR #3).
    setBulkPending(false)
    exitSelectMode()
  }, [bulkPending, selectedBoards, boards, exitSelectMode])

  // P6: bulk delete (optimistic, snapshot-based revert on failure)
  // MINOR #1: snapshot prevBoards BEFORE optimistic removal so re-insertion after
  // partial failure does not use stale indexes into the already-shrunk array.
  // MINOR #3: setBulkPending(false) runs AFTER allSettled, BEFORE exitSelectMode.
  const handleBulkDelete = useCallback(async () => {
    if (bulkPending) return
    const ids = [...selectedBoards]
    if (ids.length === 0) return
    const prevBoards = boards
    const prevTotal = boardsTotalCount
    setBulkPending(true)
    // Optimistic removal
    setBoards(bs => bs.filter(b => !selectedBoards.has(b.board_id)))
    setBoardsTotalCount(t => Math.max(0, t - ids.length))
    // Purge chat cache for all deleted projects.
    ids.forEach(id => purgeChatCache(String(id)))
    const results = await Promise.allSettled(ids.map(id => deleteProject(id)))
    const failedIds = results
      .map((r, i) => (r.status === 'rejected' ? ids[i] : null))
      .filter(Boolean)
    if (failedIds.length > 0) {
      const successfulIds = new Set(
        results.map((r, i) => (r.status === 'fulfilled' ? ids[i] : null)).filter(Boolean)
      )
      // Restore from snapshot, dropping only the actually-deleted IDs
      setBoards(prevBoards.filter(b => !successfulIds.has(b.board_id)))
      setBoardsTotalCount(prevTotal - successfulIds.size)
      setBoardActionError({
        type: 'bulk-delete',
        msg: `Failed to delete ${failedIds.length} board(s). Restored.`,
      })
    }
    // Clear pending BEFORE exitSelectMode so Cancel during in-flight op cannot
    // trigger a second bulk op (MINOR #3).
    setBulkPending(false)
    exitSelectMode()
  }, [bulkPending, selectedBoards, boards, boardsTotalCount, exitSelectMode])

  // MINOR #2: shared style helpers for Public / Private bulk action buttons.
  // Defined here (component-scoped consts) so they close over nothing and stay
  // stable across renders without needing useCallback/useMemo.
  function bulkActionButtonStyle(disabled) {
    return {
      flex: 1,
      minHeight: 44, padding: '0 12px',
      borderRadius: 10, border: '1px solid var(--color-border)',
      background: 'var(--color-surface)',
      color: 'var(--color-text-2)', fontSize: 13, fontWeight: 600,
      cursor: disabled ? 'not-allowed' : 'pointer',
      fontFamily: 'inherit',
      opacity: disabled ? 0.5 : 1,
      transition: 'border-color 0.18s, color 0.18s, opacity 0.18s',
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
    }
  }
  const bulkBtnHoverEnter = (disabled) => (e) => {
    if (!disabled) {
      e.currentTarget.style.borderColor = 'rgba(236,72,153,0.45)'
      e.currentTarget.style.color = '#ec4899'
    }
  }
  const bulkBtnHoverLeave = (e) => {
    e.currentTarget.style.borderColor = 'var(--color-border)'
    e.currentTarget.style.color = 'var(--color-text-2)'
  }

  if (loading) {
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 14,
      }}>
        Loading profile...
      </div>
    )
  }

  if (error || !user) {
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 14,
      }}>
        {error || 'Profile not found.'}
      </div>
    )
  }

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(100px + env(safe-area-inset-bottom))'
    }}>
      {/* Ambient brand-pink glow — on-brand */}
      <div style={{
        position: 'fixed', top: '-10%', left: '-10%', width: '120%', height: '50%',
        background: 'radial-gradient(circle at 50% 0%, rgba(236,72,153,0.10) 0%, transparent 70%)',
        pointerEvents: 'none', zIndex: 0,
      }} />

      <ProfileHeader
        isMe={isMe}
        handle={user?.handle}
        onLogout={onLogout}
        onShare={() => setShareOpen(true)}
      />

      {/* Unified responsive container (max-width 1100) */}
      <div style={{ position: 'relative', zIndex: 1, maxWidth: 1100, margin: '0 auto', padding: '32px 20px 40px' }}>

        <ProfileHero
          user={user}
          boardsTotalCount={boardsTotalCount}
          savedStudiosCount={user.saved_studios_count ?? 0}
          onSelectTab={(t) => t === 'studios' ? handleStudiosTab() : setActiveTab('boards')}
          isMe={isMe}
          onAvatarUpdated={(updatedUser) => setUser(prev => ({ ...prev, avatar_url: updatedUser.avatar_url }))}
        />

        {/* Tab bar — Boards | Studios */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--color-border-soft)',
          marginBottom: 0,
          marginTop: 8,
        }}>
          <button
            type="button"
            onClick={() => setActiveTab('boards')}
            style={{
              flex: 1,
              padding: '12px 0',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: activeTab === 'boards' ? 700 : 500,
              color: activeTab === 'boards' ? 'var(--color-text)' : 'var(--color-text-muted)',
              borderBottom: activeTab === 'boards' ? '2px solid var(--color-text)' : '2px solid transparent',
              marginBottom: -1,
              fontFamily: 'inherit',
              transition: 'color var(--motion-fast), border-color var(--motion-fast)',
            }}
          >
            Boards
          </button>
          <button
            type="button"
            onClick={handleStudiosTab}
            style={{
              flex: 1,
              padding: '12px 0',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: activeTab === 'studios' ? 700 : 500,
              color: activeTab === 'studios' ? 'var(--color-text)' : 'var(--color-text-muted)',
              borderBottom: activeTab === 'studios' ? '2px solid var(--color-text)' : '2px solid transparent',
              marginBottom: -1,
              fontFamily: 'inherit',
              transition: 'color var(--motion-fast), border-color var(--motion-fast)',
            }}
          >
            Studios
          </button>
        </div>

        {activeTab === 'boards' && (<>

        {/* MINOR #1: inline error banner for failed board actions */}
        {boardActionError && (
          <div aria-live="polite" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
            padding: '12px 16px', marginBottom: 12, borderRadius: 12,
            background: 'rgba(239,68,68,0.12)',
            borderLeft: '3px solid #ef4444',
            color: 'var(--color-text)', fontSize: 13, fontWeight: 500,
          }}>
            <span>{boardActionError.msg}</span>
            <button
              type="button"
              onClick={() => setBoardActionError(null)}
              aria-label="Dismiss"
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: 'var(--color-text-2)', padding: 4, lineHeight: 0,
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        )}

        {/* Boards section header — normal mode vs select mode */}
        {selectMode ? (
          // P6 select-mode header bar — Cancel / count / Select-all toggle
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 20, padding: '0 4px', minHeight: 44, gap: 8,
          }}>
            {/* Left: Cancel */}
            <button
              type="button"
              onClick={exitSelectMode}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: 'var(--color-text-2)', fontSize: 14, fontWeight: 600,
                minHeight: 44, padding: '0 4px',
                fontFamily: 'inherit',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-text)' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-2)' }}
            >
              Cancel
            </button>
            {/* Middle: selection count */}
            <span style={{
              color: 'var(--color-text)', fontSize: 15, fontWeight: 600,
              flex: 1, textAlign: 'center',
            }}>
              {selectedBoards.size} selected
            </span>
            {/* Right: Select all / Deselect all */}
            <button
              type="button"
              onClick={() => {
                if (allSelected) {
                  setSelectedBoards(new Set())
                } else {
                  setSelectedBoards(new Set(boards.map(b => b.board_id)))
                }
              }}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: '#ec4899', fontSize: 13, fontWeight: 600,
                minHeight: 44, padding: '0 4px',
                fontFamily: 'inherit',
                whiteSpace: 'nowrap',
              }}
            >
              {allSelected ? 'Deselect all' : 'Select all'}
            </button>
          </div>
        ) : (
          // Normal boards section header
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 20, padding: '0 4px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <h3 style={{
                color: 'var(--color-text)', fontSize: 20, fontWeight: 700,
                margin: 0, letterSpacing: '-0.01em',
              }}>
                Curated Boards
              </h3>
              <span style={{
                color: 'var(--color-text-dimmer)', fontSize: 13, fontWeight: 600,
              }}>
                {boardsTotalCount}
              </span>
              {isMe && (
                <button
                  type="button"
                  onClick={() => navigate('/liked-projects')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    background: 'transparent',
                    border: '1px solid var(--color-border)',
                    borderRadius: 10, cursor: 'pointer',
                    color: 'var(--color-text-2)', fontSize: 13, fontWeight: 600,
                    padding: '0 12px', minHeight: 36,
                    fontFamily: 'inherit',
                    transition: 'border-color 0.18s cubic-bezier(0.4,0,0.2,1), color 0.18s cubic-bezier(0.4,0,0.2,1)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(236,72,153,0.55)'
                    e.currentTarget.style.color = '#ec4899'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--color-border)'
                    e.currentTarget.style.color = 'var(--color-text-2)'
                  }}
                >
                  {/* Heart icon */}
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                  </svg>
                  Liked Projects
                </button>
              )}
            </div>
            {/* P6: Edit button — owner-only, only when boards exist */}
            {isMe && boards.length > 0 && (
              <button
                type="button"
                onClick={() => setSelectMode(true)}
                aria-label="Edit boards"
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  background: 'transparent',
                  border: '1px solid var(--color-border)',
                  borderRadius: 10, cursor: 'pointer',
                  color: 'var(--color-text-2)', fontSize: 13, fontWeight: 600,
                  padding: '0 12px', minHeight: 44,
                  fontFamily: 'inherit',
                  transition: 'border-color 0.18s cubic-bezier(0.4, 0, 0.2, 1), color 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(236,72,153,0.55)'
                  e.currentTarget.style.color = '#ec4899'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-border)'
                  e.currentTarget.style.color = 'var(--color-text-2)'
                }}
              >
                {/* Pencil icon */}
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
                Edit
              </button>
            )}
          </div>
        )}

        <BoardGrid
          boards={boards}
          isMe={isMe}
          selectMode={selectMode}
          selectedBoards={selectedBoards}
          onVisibilityChange={handleVisibilityChange}
          onDelete={handleDelete}
          onSelectToggle={handleSelectToggle}
          boardsHasMore={boardsHasMore}
          boardsLoading={boardsLoading}
          onResumeProject={onResumeProject}
          onNewProjectSession={onNewProjectSession}
        />

        {/* P6: sticky bulk action bar — visible when selectMode && selection > 0 */}
        {selectMode && selectedBoards.size > 0 && (
          <div style={{
            position: 'sticky', bottom: 12, zIndex: 5,
            margin: '16px 0 0',
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 12px',
            background: 'rgba(15,15,15,0.80)',
            backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
            borderRadius: 16,
            border: '1px solid var(--color-border-soft)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          }}>
            {/* Make public */}
            <button
              type="button"
              disabled={bulkPending}
              onClick={() => handleBulkVisibility('public')}
              style={bulkActionButtonStyle(bulkPending)}
              onMouseEnter={bulkBtnHoverEnter(bulkPending)}
              onMouseLeave={bulkBtnHoverLeave}
            >
              {/* Lock-open icon */}
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 9.9-1"></path>
              </svg>
              Public
            </button>
            {/* Make private */}
            <button
              type="button"
              disabled={bulkPending}
              onClick={() => handleBulkVisibility('private')}
              style={bulkActionButtonStyle(bulkPending)}
              onMouseEnter={bulkBtnHoverEnter(bulkPending)}
              onMouseLeave={bulkBtnHoverLeave}
            >
              {/* Lock-closed icon */}
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
              </svg>
              Private
            </button>
            {/* Delete with 2-step confirm */}
            <button
              ref={bulkDeleteBtnRef}
              type="button"
              disabled={bulkPending}
              onClick={() => {
                if (!confirmingBulkDelete) {
                  clearTimeout(bulkConfirmTimerRef.current)
                  setConfirmingBulkDelete(true)
                  bulkConfirmTimerRef.current = setTimeout(() => setConfirmingBulkDelete(false), 3000)
                } else {
                  clearTimeout(bulkConfirmTimerRef.current)
                  setConfirmingBulkDelete(false)
                  handleBulkDelete()
                }
              }}
              style={{
                minHeight: 44, padding: '0 14px',
                borderRadius: 10, border: 'none',
                background: confirmingBulkDelete ? '#ef4444' : 'rgba(239,68,68,0.12)',
                color: confirmingBulkDelete ? '#fff' : '#ef4444',
                fontSize: 13, fontWeight: 600,
                cursor: bulkPending ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
                opacity: bulkPending ? 0.5 : 1,
                transition: 'background 0.18s, color 0.18s, opacity 0.18s',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                whiteSpace: 'nowrap',
              }}
            >
              {/* Trash icon */}
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                <path d="M10 11v6"></path>
                <path d="M14 11v6"></path>
                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path>
              </svg>
              {confirmingBulkDelete
                ? `Confirm delete (${selectedBoards.size})?`
                : `Delete (${selectedBoards.size})`
              }
            </button>
          </div>
        )}

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} style={{ height: 1 }} />

        {/* Boards pagination loading spinner */}
        {boardsLoading && (
          <div style={{
            display: 'flex', justifyContent: 'center', padding: '24px 0',
          }}>
            <div style={{
              width: 24, height: 24, borderRadius: '50%',
              border: '2px solid var(--color-border)',
              borderTopColor: '#ec4899',
              animation: 'spin 0.8s linear infinite',
            }} />
          </div>
        )}

        </>)}

        {/* Studios tab content */}
        {activeTab === 'studios' && (
          <div style={{ padding: '16px 0' }}>
            {studiosLoading && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} style={{
                    height: 100, borderRadius: 12,
                    background: 'var(--color-surface-2)',
                  }} />
                ))}
              </div>
            )}
            {!studiosLoading && savedStudios && savedStudios.length === 0 && (
              <p style={{
                textAlign: 'center', color: 'var(--color-text-muted)',
                fontSize: 14, padding: '40px 0', margin: 0,
              }}>
                저장된 스튜디오가 없어요.
              </p>
            )}
            {!studiosLoading && savedStudios && savedStudios.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                {savedStudios.map(studio => (
                  <button
                    key={studio.architect_id}
                    type="button"
                    onClick={() => navigate('/architects/' + studio.architect_id)}
                    style={{
                      background: 'var(--color-surface)',
                      border: '1px solid var(--color-border-soft)',
                      borderRadius: 12,
                      padding: '12px 8px',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: 8,
                      fontFamily: 'inherit',
                      textAlign: 'center',
                    }}
                  >
                    {studio.logo_url ? (
                      <img
                        src={studio.logo_url}
                        alt={studio.name}
                        style={{
                          width: 48, height: 48, borderRadius: '50%',
                          objectFit: 'cover',
                          border: '1px solid var(--color-border-soft)',
                          background: 'var(--color-surface-2)',
                        }}
                      />
                    ) : (
                      <div style={{
                        width: 48, height: 48, borderRadius: '50%',
                        background: 'var(--color-surface-2)',
                        border: '1px solid var(--color-border-soft)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5">
                          <rect x="3" y="3" width="18" height="18" rx="2"/>
                          <path d="M9 9h6M9 12h6M9 15h6"/>
                        </svg>
                      </div>
                    )}
                    <p style={{
                      margin: 0,
                      fontSize: 11,
                      fontWeight: 600,
                      color: 'var(--color-text)',
                      lineHeight: 1.3,
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}>
                      {studio.name}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

      </div>

      {/* Share card modal */}
      {shareOpen && user && (
        <ShareCardModal user={user} onClose={() => setShareOpen(false)} />
      )}
    </div>
  )
}
