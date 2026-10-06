import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import styles from './UserProfilePage.module.css'
import { useTranslation } from '../i18n/index.js'
import { getUserProfile, getLikedBuildings, getArchitectProfile } from '../api/client.js'
import { updateProject, deleteProject } from '../api/projects.js'
import { getMyWorks, getUserWorks } from '../api/works.js'
import { purgeChatCache } from '../utils/appHelpers.js'
import { getUserSavedStudios } from '../api/architects.js'
import { getMyPersonality } from '../api/personality.js'
import WorkDetailModal from '../components/WorkDetailModal.jsx'
import ProfileHero from './userProfile/ProfileHero'
import BoardGrid from './userProfile/BoardGrid'
import PentagonChart from '../components/PentagonChart.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import Tabs from '../components/Tabs.jsx'
import EmptyState from '../components/EmptyState.jsx'
import PhotoTile from '../components/PhotoTile.jsx'
import SectionTitle from '../components/SectionTitle.jsx'
import FloatingIconButton from '../components/FloatingIconButton.jsx'
import Skeleton from '../components/Skeleton.jsx'
import { useUnreadNotifications } from '../hooks/useUnreadNotifications.js'
import { useMessagingEnabled } from '../hooks/useMessagingFeature.js'
import MessagesEntry from '../components/messaging/MessagesEntry.jsx'
import ContactCta from '../components/messaging/ContactCta.jsx'
import UserActionsMenu from '../components/messaging/UserActionsMenu.jsx'
import { useBlockedUser } from '../components/messaging/blockedUsers.js'
import { StudioCard, SkeletonCard, BuildingIconEmpty } from '../components/StudioCard.jsx'

// Hidden 2026-09-26 per user (design noise); functionality kept, delete
// entirely if no issue surfaces.
const SHOW_BOARD_EDIT_BUTTON = false

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
  const [searchParams] = useSearchParams()
  const { t } = useTranslation()

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

  // Tab state — 'boards' | 'studios' | 'liked'
  const [activeTab, setActiveTab] = useState('boards')
  const [savedStudios, setSavedStudios] = useState(null)  // null = not loaded yet
  const [studiosLoading, setStudiosLoading] = useState(false)
  const [buildingsMap, setBuildingsMap] = useState({}) // architect_id → buildings[]
  const [likedBuildings, setLikedBuildings] = useState(null) // null = not yet fetched
  const [likedLoading, setLikedLoading] = useState(false)
  const [likedCount, setLikedCount] = useState(0)
  const [works, setWorks] = useState(null)  // null = not loaded yet
  const [worksLoading, setWorksLoading] = useState(false)
  const [selectedWorkId, setSelectedWorkId] = useState(null)

  // Personality profile state (isMe: my personality; !isMe: for overlay comparison)
  const [myPersonality, setMyPersonality] = useState(null)

  // Own-profile only — bell + unread badge (NOTIF-INAPP-1). Count fetch is
  // mount + visibilitychange only (no polling) per the hook's own contract.
  // enabled=isMe so viewing someone else's profile never fires the request.
  // Relocated from the retired ProfileHeader (Rules of Hooks — before the
  // loading/error early returns below).
  const { count: unreadCount } = useUnreadNotifications(isMe)
  const unreadBadgeLabel = unreadCount > 9 ? '9+' : String(unreadCount)

  // FULL-MESSAGING-1: flag-gated messaging surfaces. `blockedPeer` hides the
  // contact CTA after the viewer blocks this user from the profile menu.
  const messagingEnabled = useMessagingEnabled()
  const blockedPeer = useBlockedUser(effectiveUserId)

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

  // Fetch likedCount on mount for ProfileHero stat display — own list when
  // isMe, otherwise the viewed user's liked list (design-parity, FRONT-*).
  useEffect(() => {
    if (!effectiveUserId) return
    getLikedBuildings(isMe ? undefined : effectiveUserId)
      .then(data => setLikedCount(data?.total ?? 0))
      .catch(() => {})
  }, [isMe, effectiveUserId])

  // Fetch my personality for overlay comparison (both isMe and !isMe paths)
  // Empty deps intentional: runs once on mount to load the caller's own personality.
  useEffect(() => {
    getMyPersonality()
      .then(data => setMyPersonality(data))
      .catch(() => setMyPersonality(null))
  }, [])

  // Fetch architect profiles for buildingsMap whenever savedStudios changes
  useEffect(() => {
    if (!savedStudios?.length) return
    savedStudios.forEach(office => {
      if (buildingsMap[office.architect_id] !== undefined) return
      getArchitectProfile(office.architect_id)
        .then(profile => {
          setBuildingsMap(prev => ({
            ...prev,
            [office.architect_id]: profile?.buildings || [],
          }))
        })
        .catch(() => {
          setBuildingsMap(prev => ({ ...prev, [office.architect_id]: [] }))
        })
    })
  }, [savedStudios]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleLikedTab() {
    setActiveTab('liked')
    if (likedBuildings !== null) return
    setLikedLoading(true)
    try {
      const data = await getLikedBuildings(isMe ? undefined : effectiveUserId)
      setLikedBuildings(data?.buildings || [])
      setLikedCount(data?.total ?? 0)
    } catch {
      setLikedBuildings([])
    } finally {
      setLikedLoading(false)
    }
  }

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

  const handleCreatedTab = async () => {
    setActiveTab('created')
    if (works !== null) return  // already loaded
    setWorksLoading(true)
    try {
      const data = isMe ? await getMyWorks() : await getUserWorks(effectiveUserId)
      setWorks(data?.works || [])
    } catch {
      setWorks([])
    } finally {
      setWorksLoading(false)
    }
  }

  // handleCreatedTab is redefined every render (not useCallback) — stash the
  // latest reference in a ref so the deep-link effect below can call it
  // without depending on it directly (which would re-fire on every render).
  const handleCreatedTabRef = useRef(handleCreatedTab)
  handleCreatedTabRef.current = handleCreatedTab

  // Deep-link support: ?tab=created lands directly on the Created tab.
  // Originally isMe-only (upload success-modal confirm). The isMe guard is
  // gone because handleCreatedTab already handles both sides — it calls
  // getUserWorks() for other people — and the competition prototype links
  // straight to another user's works from the interested-people list.
  const deepLinkAppliedRef = useRef(false)
  useEffect(() => {
    if (deepLinkAppliedRef.current) return
    if (!user || loading) return
    if (searchParams.get('tab') === 'created') {
      deepLinkAppliedRef.current = true
      handleCreatedTabRef.current()
    }
  }, [user, loading, searchParams])

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
    // Reset Liked/Created tab caches on user change — both are now reachable
    // for !isMe (design-parity), so navigating between two profiles without
    // an unmount must not leak the previous user's likes/works/count.
    setLikedBuildings(null)
    setLikedCount(0)
    setWorks(null)
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

  if (loading) {
    return (
      <div style={{
        height: 'var(--page-height)',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 'var(--fs-body)',
        paddingBottom: 'var(--tabbar-clearance)',
      }}>
        {t('profileB3.loadingProfile')}
      </div>
    )
  }

  if (error || !user) {
    return (
      <div style={{
        height: 'var(--page-height)',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 'var(--fs-body)',
        paddingBottom: 'var(--tabbar-clearance)',
      }}>
        {error || t('profileB3.profileNotFound')}
      </div>
    )
  }

  return (
    <div style={{
      height: 'var(--page-height)',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'var(--tabbar-clearance)'
    }}>
      {/* Top rail: theme pill left, 한/EN + logout right (same as other tab pages).
          isMe: settings circle (with unread-notification badge) AFTER the theme
          pill via `trailing`. !isMe: single back circle in `leading`. */}
      <PageTopControls
        onLogout={onLogout}
        leading={isMe ? undefined : <PageBackButton inline onClick={() => navigate(-1)} />}
        trailing={isMe ? (
          <FloatingIconButton
            onClick={() => navigate('/settings')}
            ariaLabel={t('profile.settings')}
            title={t('profile.settings')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h0a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h0a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v0a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"></path>
            </svg>
            {unreadCount > 0 && (
              <span
                aria-hidden="true"
                style={{
                  position: 'absolute', top: -3, right: -3,
                  minWidth: 15, height: 15, padding: '0 4px',
                  borderRadius: 999, background: 'var(--accent-1)', color: '#fff',
                  fontSize: 9, fontWeight: 700, lineHeight: '15px', textAlign: 'center',
                }}
              >
                {unreadBadgeLabel}
              </span>
            )}
          </FloatingIconButton>
        ) : undefined}
      />

      <PageLogoHeader padding="20px 16px 0" />

      {/* Unified responsive container (max-width 1100) */}
      <div style={{ position: 'relative', zIndex: 1, maxWidth: 1100, margin: '0 auto', padding: '32px 20px 40px' }}>

        {/* FULL-MESSAGING-1: in-flow (NOT fixed) so it can never overlap the
            fixed PageTopControls / isMe cluster; both render nothing while the
            messaging flag is OFF. isMe -> message pill (>=44px, unread badge);
            !isMe -> block/report "..." menu. */}
        {isMe && <MessagesEntry />}
        {!isMe && messagingEnabled && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '-12px 0 12px', minHeight: 44, alignItems: 'center' }}>
            <UserActionsMenu
              userId={effectiveUserId}
              name={user.display_name || t('messaging.unknownUser')}
            />
          </div>
        )}

        <ProfileHero
          user={user}
          boardsTotalCount={boardsTotalCount}
          savedStudiosCount={user.saved_studios_count ?? 0}
          likedCount={likedCount}
          onSelectTab={(t) => {
            if (t === 'studios') handleStudiosTab()
            else if (t === 'liked') handleLikedTab()
            else if (t === 'created') handleCreatedTab()
            else setActiveTab('boards')
          }}
          isMe={isMe}
          onAvatarUpdated={(updatedUser) => setUser(prev => ({ ...prev, avatar_url: updatedUser.avatar_url }))}
        />

        {/* ── Personality section ────────────────────────────────────────── */}
        {(() => {
          function vectorFrom(p) {
            if (!p) return null
            return [p.axis_1, p.axis_2, p.axis_3, p.axis_4, p.axis_5]
          }

          // isMe + no personality → CTA to assessment
          if (isMe && !user.personality) {
            return (
              <div style={{ padding: '16px 20px 0', display: 'flex', justifyContent: 'center' }}>
                <button
                  type="button"
                  onClick={() => navigate('/assessment')}
                  className={styles.personalityCtaSecondary}
                >
                  {t('profilePersonality.takeAssessment')}
                </button>
              </div>
            )
          }

          // isMe + has personality → interactive pentagon (myVector only, no overlay)
          if (isMe && user.personality) {
            return (
              <div style={{ padding: '16px 20px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <PentagonChart
                  myVector={vectorFrom(user.personality)}
                  interactive={true}
                  onAxisClick={(i) => navigate(`/people?axis=${i}`)}
                  size={180}
                />
                <p style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-muted)', margin: 0 }}>
                  {t('profilePersonality.typeSuffix', { type: user.personality.type_code })}
                </p>
                {/* Retest. The backend already upserts (PersonalityProfile
                    .update_or_create + profile-cache eviction), so this needs no
                    API of its own — the only thing missing was a way back into
                    the assessment once a profile existed.

                    No confirm step on purpose: nothing is overwritten until the
                    new run is submitted, so abandoning midway leaves the current
                    result intact and there is nothing to protect against.

                    Same styling as the `성향 진단 받기` CTA in the sibling branch
                    above (isMe + no personality) so the two states read as one
                    pair; placed under the type label to keep the chart primary. */}
                <button
                  type="button"
                  onClick={() => navigate('/assessment')}
                  style={{ marginTop: 4 }}
                  className={styles.personalityCtaSecondary}
                >
                  {t('profilePersonality.retake')}
                </button>
              </div>
            )
          }

          // !isMe + both have personality → overlay comparison
          if (!isMe && user?.personality && myPersonality) {
            return (
              <div style={{ padding: '16px 20px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <PentagonChart
                  myVector={vectorFrom(myPersonality)}
                  theirVector={vectorFrom(user.personality)}
                  size={180}
                />
                <p style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-muted)', margin: 0, fontStyle: 'italic' }}>
                  {t('profilePersonality.legend')}
                </p>
                {/* Contact CTA — reflects contact-requests/status/ (none ->
                    greeting sheet, sent -> disabled, connected -> open
                    conversation); hidden entirely while the flag is OFF. */}
                <ContactCta
                  userId={effectiveUserId}
                  buttonClassName={styles.personalityCtaPrimary}
                  hidden={blockedPeer}
                />
              </div>
            )
          }

          // !isMe + they have personality, I don't → single graph + CTA
          if (!isMe && user?.personality && !myPersonality) {
            return (
              <div style={{ padding: '16px 20px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <PentagonChart
                  theirVector={vectorFrom(user.personality)}
                  size={180}
                />
                <button
                  type="button"
                  onClick={() => navigate('/assessment')}
                  className={styles.personalityCtaPrimary}
                >
                  {t('profilePersonality.checkMine')}
                </button>
              </div>
            )
          }

          return null
        })()}
        {/* ── End personality section ────────────────────────────────────── */}

        {/* Tab bar — Boards | Studios | Liked | Created (all 4 visible to any
            viewer, design-parity user-other.html; edit affordances inside
            each panel stay isMe-gated) */}
        <Tabs
          style={{ marginTop: 8 }}
          tabs={[
            { id: 'boards', label: t('profileB3.tabBoards') },
            { id: 'studios', label: t('profileB3.tabStudios') },
            { id: 'liked', label: t('profileB3.tabLiked') },
            { id: 'created', label: t('profileB3.tabCreated') },
          ]}
          value={activeTab}
          onChange={(id) => {
            if (id === 'studios') handleStudiosTab()
            else if (id === 'liked') handleLikedTab()
            else if (id === 'created') handleCreatedTab()
            else setActiveTab('boards')
          }}
        />

        {activeTab === 'boards' && (<>

        {/* MINOR #1: inline error banner for failed board actions */}
        {boardActionError && (
          <div aria-live="polite" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
            padding: '12px 16px', marginBottom: 12, borderRadius: 'var(--radius-md)',
            background: 'color-mix(in srgb, var(--color-destructive) 12%, transparent)',
            borderLeft: '3px solid var(--color-destructive)',
            color: 'var(--color-text)', fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-medium)',
          }}>
            <span>{boardActionError.msg}</span>
            <button
              type="button"
              onClick={() => setBoardActionError(null)}
              aria-label={t('profileB3.dismiss')}
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
              className={styles.cancelBtn}
            >
              {t('profileB3.cancel')}
            </button>
            {/* Middle: selection count */}
            <span style={{
              color: 'var(--color-text)', fontSize: 'var(--fs-emphasis)', fontWeight: 'var(--fw-semibold)',
              flex: 1, textAlign: 'center',
            }}>
              {t('profileB3.selectedCount', { n: selectedBoards.size })}
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
              className={styles.selectAllBtn}
            >
              {allSelected ? t('profileB3.deselectAll') : t('profileB3.selectAll')}
            </button>
          </div>
        ) : null}

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
            position: 'sticky', bottom: 'calc(var(--tabbar-clearance) + 12px)', zIndex: 5,
            margin: '16px 0 0',
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 12px',
            background: 'color-mix(in srgb, var(--color-bg) 80%, transparent)',
            backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-soft)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          }}>
            {/* Make public */}
            <button
              type="button"
              disabled={bulkPending}
              onClick={() => handleBulkVisibility('public')}
              className={styles.bulkActionBtn}
            >
              {/* Lock-open icon */}
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 9.9-1"></path>
              </svg>
              {t('profileB3.makePublic')}
            </button>
            {/* Make private */}
            <button
              type="button"
              disabled={bulkPending}
              onClick={() => handleBulkVisibility('private')}
              className={styles.bulkActionBtn}
            >
              {/* Lock-closed icon */}
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
              </svg>
              {t('profileB3.makePrivate')}
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
              className={`${styles.bulkDeleteBtn} ${confirmingBulkDelete ? styles.bulkDeleteBtnConfirming : ''}`}
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
                ? t('profileB3.confirmDelete', { n: selectedBoards.size })
                : t('profileB3.deleteCount', { n: selectedBoards.size })
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
              borderTopColor: 'var(--accent-1)',
              animation: 'spin 0.8s linear infinite',
            }} />
          </div>
        )}

        </>)}

        {/* Studios tab content */}
        {activeTab === 'studios' && (
          <div style={{ padding: '16px 0' }}>
            {studiosLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>
                {[0, 1, 2].map(i => <SkeletonCard key={i} />)}
              </div>
            ) : !savedStudios || savedStudios.length === 0 ? (
              <EmptyState
                icon={<BuildingIconEmpty />}
                title={t('profile.noSavedOfficesInline')}
                body={t('profile.followToShowInline')}
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>
                {savedStudios.map((office, i) => (
                  <StudioCard
                    key={office.architect_id || i}
                    office={office}
                    buildings={buildingsMap[office.architect_id] ?? null}
                    onClick={() => navigate('/architects/' + office.architect_id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Liked tab content */}
        {activeTab === 'liked' && (
          <div style={{ padding: '16px 0' }}>
            <div style={{ marginBottom: 20 }}>
              <SectionTitle as="h3">{t('profileB3.likedProjects')}</SectionTitle>
            </div>
            {likedLoading ? (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: 20,
              }}>
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} style={{ aspectRatio: '4 / 5', borderRadius: 'var(--radius-lg)', background: 'var(--color-surface-2)' }} />
                ))}
              </div>
            ) : !likedBuildings || likedBuildings.length === 0 ? (
              <EmptyState
                title={t('profile.noLikedProjectsInline')}
                body={t('profile.swipeToSaveInline')}
              />
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: 20,
              }}>
                {likedBuildings.map((bld, i) => (
                  <PhotoTile
                    key={bld.canonical_bld_id || i}
                    imageUrl={bld.image_url || bld.display_cover_url}
                    title={bld.name || bld.canonical_bld_id}
                    subtitle={bld.architect_names?.length > 0 ? bld.architect_names.join(', ') : 'Building'}
                    placeholder={<BuildingIconEmpty />}
                    onClick={() => navigate('/buildings/' + bld.canonical_bld_id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Created tab content — isMe: full owner voice (upload CTA, review
            badges). !isMe: publishable-only works from ?user_id=, cards are
            NOT clickable into detail (GET /works/<id>/ is owner-only, 403s
            for other viewers) — rendered as plain non-interactive cards
            rather than linking anywhere else. */}
        {activeTab === 'created' && (
          <div style={{ padding: '16px 0' }}>
            <div style={{ marginBottom: 20 }}>
              <SectionTitle
                as="h3"
                right={isMe && (
                  <button
                    type="button"
                    onClick={() => navigate('/upload')}
                    className={styles.uploadBtn}
                  >
                    {t('profile.uploadButton')}
                  </button>
                )}
              >
                {isMe ? t('profile.myWorksTitle') : t('profile.worksTitle')}
              </SectionTitle>
            </div>
            {worksLoading ? (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: 20,
              }}>
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} radius="var(--radius-lg)" style={{ height: 'auto', aspectRatio: '4 / 5' }} />
                ))}
              </div>
            ) : !works || works.length === 0 ? (
              <EmptyState
                title={t('profile.noWorksTitle')}
                body={isMe ? t('profile.noWorksBody') : undefined}
                actionLabel={isMe ? t('profile.uploadWorkAction') : undefined}
                onAction={isMe ? () => navigate('/upload') : undefined}
              />
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: 20,
              }}>
                {works.map(work => (
                  <PhotoTile
                    key={work.upload_id}
                    imageUrl={work.cover_url}
                    title={work.title}
                    subtitle={work.program}
                    placeholder={!work.cover_url && (
                      <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--fs-caption)' }}>
                        {t('profile.workProcessing')}
                      </span>
                    )}
                    onClick={isMe ? () => setSelectedWorkId(work.upload_id) : undefined}
                    topRight={isMe && !work.is_publishable && (
                      <span style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'color-mix(in srgb, var(--color-destructive) 12%, transparent)',
                        color: 'var(--color-destructive)',
                        fontSize: 'var(--fs-caption)',
                        fontWeight: 'var(--fw-semibold)',
                      }}>
                        {work.gate_reason ? t('workDetail.status.rejected') : t('workDetail.status.processing')}
                      </span>
                    )}
                  />
                ))}
              </div>
            )}
          </div>
        )}

      </div>

      {/* Work detail modal */}
      {selectedWorkId && (
        <WorkDetailModal
          uploadId={selectedWorkId}
          onClose={() => setSelectedWorkId(null)}
        />
      )}
    </div>
  )
}
