import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { updateProject, deleteProject } from '../api/projects.js'
import { canSelectForDelete, isLastLikedError } from '../utils/boardDeleteRules.js'
import { planEditSave } from '../utils/boardEditPlan.js'
import { purgeChatCache } from '../utils/appHelpers.js'
import { useTranslation } from '../i18n/index.js'

/**
 * useBoardEdit — owner edit state + handlers for a board, shared by
 * BoardDetailPage (no-report boards) and the merged report page.
 * Behaviour is the extracted BoardDetailPage logic, unchanged:
 *   - edit mode = { isEditMode, selectedIds, nameDraft }
 *   - saveEdits: name first (updateProject name), then delete selected buildings
 *     (remove_building_ids); any failure keeps edit mode + selection + draft
 *   - the last liked building can neither be selected nor deleted
 *     (UI flash + server 400 `last_liked_building`)
 *   - optimistic public/private toggle (one PATCH at a time, rollback on failure)
 *   - deleteBoard: delete + purge chat cache + navigate /user/me (replace)
 *
 * Options
 *   boardId, board       project id + useBoard payload (state re-initialises per board object)
 *   isOwner              all writes are no-ops for non-owners
 *   getFallbackTitle     () => string  baseline title when the board has no name; called lazily
 *   showToast            (text) => void  lazily called from handlers
 */
export function useBoardEdit({ boardId, board, isOwner, getFallbackTitle, showToast }) {
  const { t } = useTranslation()
  const navigate = useNavigate()

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
    setLocalName(board.name || '')
    setNameDraft(board.name || '')
    setLocalBuildings(board.buildings || [])
  }, [board])

  const fallbackTitle = () => getFallbackTitle?.() ?? ''
  const toast = text => showToast?.(text)

  // Edit mode = { isEditMode, selectedIds, nameDraft }; these two are the only
  // transitions (plus selection toggling and saveEdits below).
  function enterEditMode() {
    setIsEditMode(true)
    setSelectedIds(new Set())
    setNameDraft(localName || fallbackTitle())
  }

  function exitEditMode() {
    setIsEditMode(false)
    setSelectedIds(new Set())
    setNameDraft(localName || fallbackTitle())
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

  // Save the title draft (if dirty) and, when `deleting`, delete the selected
  // buildings. Name first, then delete. Success of everything -> exit edit mode;
  // any failure keeps edit mode, selection and draft. A saved name becomes the
  // new baseline immediately so a retry never re-sends it.
  async function saveEdits({ deleting }) {
    if (!isOwner || busy) return
    const plan = planEditSave({
      draft: nameDraft, baseline: localName || fallbackTitle(), selectedIds, deleting,
    })
    if (plan.blank && !deleting) return
    if (plan.noop) { if (!plan.blank) exitEditMode(); return }
    setBusy(deleting ? 'deleting' : 'saving-name')
    try {
      if (plan.name) {
        try {
          await updateProject(boardId, { name: plan.name })
        } catch {
          if (aliveRef.current) toast(t('board.nameSaveFailed'))
          return
        }
        setLocalName(plan.name)
        setNameDraft(plan.name)
        toast(t('board.nameSaved'))
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
            else toast(t('board.deleteFailed'))
          }
          return
        }
        setLocalBuildings(prev => (prev || []).filter(b => {
          const bid = b.image_id || b.canonical_bld_id || b.building_id || b.id
          return !ids.includes(bid)
        }))
        if (deletedLiked.length > 0) setDeletedLikedIds(prev => [...prev, ...deletedLiked])
        // No regeneration here: the server flags the report stale and the owner's
        // next open of the report page regenerates it (or the owner taps the
        // report page's regenerate notice).
      }
      setIsEditMode(false)
      setSelectedIds(new Set())
    } finally {
      if (aliveRef.current) setBusy(null)
    }
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

  const visibility = visibilityOverride ?? board?.visibility

  // Optimistic visibility toggle (revert on failure). One PATCH at a time (taps
  // during a pending request are ignored) so requests cannot commit out of
  // order; on success the server's value wins.
  async function handleToggleVisibility(next) {
    if (!isOwner || visPendingRef.current) return
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
        toast(t('board.visibilityFailed'))
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
      if (aliveRef.current) toast(t('board.deleteFailed'))
    }
  }

  return {
    localName, nameDraft, setNameDraft, isEditMode, selectedIds, busy,
    deletedLikedIds, lastMsgOn, likedIdList,
    localBuildings, visibility,
    enterEditMode, exitEditMode, saveEdits,
    handleToggleBuildingSelect, handleToggleVisibility, handleDeleteBoard,
  }
}
