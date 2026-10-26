/**
 * PeopleDiscoveryPage.jsx
 * Social board feed — public boards (with a report image) of other people,
 * filterable by taste relation / type code, with in-place expand + like.
 * Route: /people (ProtectedRoute) — tab root for the "소셜" (Social) TabBar tab.
 * As a tab root, this page has no back button (see DiscoveryPage for the same
 * tab-root convention). DiscoveryTriggerCard's push-navigation into this page
 * (from Discovery, after 10 draft likes) still works unchanged.
 *
 * Mock: social-board-like.html. Expand behaviour: the expanded card is moved to
 * the START of its grid row (left sibling drops below), every tile animates with
 * FLIP keyed by board_id (WAAPI), the toggled card rises from below, and the
 * scroll container scrolls so the card sits at the top.
 */

import { useState, useEffect, useCallback, useRef, useMemo, useLayoutEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMyPersonality } from '../api/personality.js'
import { getPeopleDiscovery } from '../api/people.js'
import { reactToProject, unreactToProject } from '../api/social.js'
import BoardSocialCard from '../components/BoardSocialCard.jsx'
import SocialSegment from '../components/SocialSegment.jsx'
import { TYPE_CODES } from '../constants/personalityTypes.js'
import PageTopControls from '../components/PageTopControls.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import { useTranslation } from '../i18n/index.js'
import { userHandle } from '../utils/userIdentity.js'
import {
  reorderForExpanded, mergePages, patchReaction, toggledReaction,
} from '../utils/socialFeed.js'
import styles from './PeopleDiscoveryPage.module.css'

const PAGE_SIZE = 20
const TOAST_MS = 3000 // DESIGN.md §8.11
// Mirrors --motion-flip (500ms) / --motion-ease; WAAPI needs a literal.
const FLIP_MS = 500
const FLIP_EASE = 'cubic-bezier(0.4, 0, 0.2, 1)'
const RISE_PX = 56

const PRESET_IDS = ['all', 'inspired', 'opposite']
const PRESET_LABEL_KEY = {
  all: 'socialBoard.filterAll',
  inspired: 'socialBoard.filterInspired',
  opposite: 'socialBoard.filterOpposite',
}
const FILTER_IDS = [...PRESET_IDS, ...TYPE_CODES]

function prefersReducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

function SkeletonTile() {
  return <div className={`${styles.skeleton} skeleton-shimmer`} aria-hidden="true" />
}

export default function PeopleDiscoveryPage({ onLogout }) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [myPersonality, setMyPersonality] = useState(undefined) // undefined = loading
  const [boards, setBoards] = useState([])
  const [nextCursor, setNextCursor] = useState(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null) // 'assessment_required' | message
  const [moreError, setMoreError] = useState(false)
  const [activeFilter, setActiveFilter] = useState('all')
  const [expanded, setExpanded] = useState(null) // { id, cols } | null
  const [toast, setToast] = useState(null) // { text, key }

  const isMounted = useRef(true)
  const reqRef = useRef(0)            // stale-response guard across filter changes
  const contentRef = useRef(null)
  const gridRef = useRef(null)
  const sentinelRef = useRef(null)
  const tileRefs = useRef(new Map())  // board_id -> element (FLIP)
  const flipRef = useRef(null)        // { before, risenId, scrollToId }
  const pendingLikes = useRef(new Set())
  const toastTimer = useRef(null)
  const animsRef = useRef([])         // in-flight WAAPI animations
  const expandedRef = useRef(null)
  expandedRef.current = expanded

  useEffect(() => {
    isMounted.current = true
    const tiles = tileRefs.current
    return () => {
      isMounted.current = false
      clearTimeout(toastTimer.current)
      tiles.clear()
    }
  }, [])

  useEffect(() => {
    getMyPersonality()
      .then(data => { if (isMounted.current) setMyPersonality(data) })
      .catch(() => { if (isMounted.current) setMyPersonality(null) })
  }, [])

  // ── Feed loading ──────────────────────────────────────────────────────────
  const loadPage = useCallback(async (filter, cursor) => {
    const req = cursor ? reqRef.current : ++reqRef.current
    if (cursor) { setLoadingMore(true); setMoreError(false) } else { setLoading(true); setError(null) }
    try {
      const data = await getPeopleDiscovery({ filter, cursor, pageSize: PAGE_SIZE })
      if (!isMounted.current || req !== reqRef.current) return
      const results = Array.isArray(data) ? data : (data?.results ?? [])
      setBoards(prev => (cursor ? mergePages(prev, results) : mergePages([], results)))
      setNextCursor(data?.next_cursor ?? null)
      setHasMore(!!data?.has_more && !!data?.next_cursor)
    } catch (err) {
      if (!isMounted.current || req !== reqRef.current) return
      if (cursor) {
        setMoreError(true)
      } else if (err.status === 403 && err.data?.detail === 'assessment_required') {
        setError('assessment_required')
      } else if (err.status === 429) {
        setError(t('socialBoard.throttled'))
      } else {
        setError(err.message || t('socialBoard.feedError'))
      }
    } finally {
      if (isMounted.current && req === reqRef.current) {
        if (cursor) setLoadingMore(false); else setLoading(false)
      }
    }
    // t is a fresh function every render; only used for a fallback string.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { loadPage('all', null) }, [loadPage])

  function selectFilter(id) {
    if (id === activeFilter) return
    setActiveFilter(id)
    setExpanded(null)
    setBoards([])
    setNextCursor(null)
    setHasMore(false)
    setMoreError(false)
    setLoadingMore(false)
    loadPage(id, null)
  }

  // Infinite scroll — sentinel at the end of the feed.
  useEffect(() => {
    const el = sentinelRef.current
    if (!el || !hasMore || loading || loadingMore || moreError || error) return
    const io = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting) loadPage(activeFilter, nextCursor)
    }, { root: contentRef.current, rootMargin: '300px' })
    io.observe(el)
    return () => io.disconnect()
  }, [hasMore, loading, loadingMore, moreError, error, nextCursor, activeFilter, loadPage])

  // ── Toast ─────────────────────────────────────────────────────────────────
  const showToast = useCallback(text => {
    clearTimeout(toastTimer.current)
    setToast({ text, key: Date.now() })
    toastTimer.current = setTimeout(() => setToast(null), TOAST_MS)
  }, [])

  // ── Like ──────────────────────────────────────────────────────────────────
  const handleLike = useCallback(async board => {
    const id = board.board_id
    if (board.is_me || pendingLikes.current.has(id)) return
    pendingLikes.current.add(id)
    const wasReacted = !!board.is_reacted
    const prev = { is_reacted: wasReacted, reaction_count: board.reaction_count ?? 0 }
    setBoards(list => patchReaction(list, id, toggledReaction(board)))
    showToast(wasReacted
      ? t('socialBoard.unlikedToast')
      : t('socialBoard.likedToast', { name: userHandle(board) }))
    try {
      if (wasReacted) {
        await unreactToProject(id)
      } else {
        const res = await reactToProject(id)
        if (isMounted.current && typeof res?.reaction_count === 'number') {
          setBoards(list => patchReaction(list, id, { reaction_count: res.reaction_count }))
        }
      }
    } catch {
      if (isMounted.current) {
        setBoards(list => patchReaction(list, id, prev))
        showToast(t('socialBoard.likeFailed'))
      }
    } finally {
      pendingLikes.current.delete(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showToast])

  // ── Expand / collapse with FLIP ───────────────────────────────────────────
  const registerRef = useCallback((id, el) => {
    if (el) tileRefs.current.set(id, el)
    else tileRefs.current.delete(id)
  }, [])

  const toggleExpand = useCallback(id => {
    // Cancel in-flight animations first so the "before" rects are the settled
    // layout positions, not mid-transform ones.
    animsRef.current.forEach(a => { try { a.cancel() } catch { /* already gone */ } })
    animsRef.current = []
    const cur = expandedRef.current
    const opening = !cur || cur.id !== id
    const before = new Map()
    tileRefs.current.forEach((el, key) => before.set(key, el.getBoundingClientRect()))
    flipRef.current = { before, risenId: opening ? id : cur.id, scrollToId: opening ? id : null }
    let cols = 2
    if (gridRef.current) {
      const n = getComputedStyle(gridRef.current).gridTemplateColumns.split(' ').filter(Boolean).length
      if (n > 0) cols = n
    }
    setExpanded(opening ? { id, cols } : null)
  }, [])

  useLayoutEffect(() => {
    const flip = flipRef.current
    if (!flip) return
    flipRef.current = null
    const reduce = prefersReducedMotion()
    // `before` rects were taken at click time (possibly mid-animation), so any
    // previous animation is cancelled now to avoid overlapping transforms.
    animsRef.current.forEach(a => { try { a.cancel() } catch { /* already gone */ } })
    animsRef.current = []
    // Measure the scroll target NOW: animations are cancelled and none has been
    // started yet, so rects are settled layout positions (no in-flight transform).
    let scrollTarget = null
    if (flip.scrollToId != null) {
      const el = tileRefs.current.get(flip.scrollToId)
      const sc = contentRef.current
      if (el && sc) {
        const raw = sc.scrollTop + (el.getBoundingClientRect().top - sc.getBoundingClientRect().top) - 20
        const max = Math.max(0, sc.scrollHeight - sc.clientHeight)
        scrollTarget = Math.min(max, Math.max(0, raw))
      }
    }
    if (!reduce) {
      const run = (el, frames) => {
        const anim = el.animate(frames, { duration: FLIP_MS, easing: FLIP_EASE })
        animsRef.current.push(anim)
        anim.onfinish = () => { animsRef.current = animsRef.current.filter(x => x !== anim) }
      }
      tileRefs.current.forEach((el, key) => {
        if (!el.animate) return
        if (key === flip.risenId) {
          // The toggled card never slides sideways: it rises from below.
          run(el, [{ transform: `translateY(${RISE_PX}px)`, opacity: 0.55 }, { transform: 'none', opacity: 1 }])
          return
        }
        const a = flip.before.get(key)
        if (!a) return
        const b = el.getBoundingClientRect()
        const dx = a.left - b.left
        const dy = a.top - b.top
        if (!dx && !dy) return
        run(el, [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }])
      })
    }
    if (scrollTarget != null && contentRef.current) {
      contentRef.current.scrollTo({ top: scrollTarget, behavior: reduce ? 'auto' : 'smooth' })
    }
  }, [expanded])

  // Column count is captured at open; collapse on resize so row-start can't go stale.
  const isExpanded = expanded != null
  useEffect(() => {
    if (!isExpanded) return undefined
    let timer = null
    function onResize() {
      clearTimeout(timer)
      timer = setTimeout(() => {
        animsRef.current.forEach(a => { try { a.cancel() } catch { /* already gone */ } })
        animsRef.current = []
        flipRef.current = null
        setExpanded(null)
      }, 150)
    }
    window.addEventListener('resize', onResize)
    return () => { clearTimeout(timer); window.removeEventListener('resize', onResize) }
  }, [isExpanded])

  // Escape closes the expanded card.
  useEffect(() => {
    if (!expanded) return
    function onKey(e) {
      if (e.key === 'Escape') toggleExpand(expanded.id)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [expanded, toggleExpand])

  const displayed = useMemo(
    () => reorderForExpanded(boards, expanded?.id ?? null, expanded?.cols ?? 2),
    [boards, expanded],
  )

  return (
    <div className={styles.page}>
      <PageTopControls onLogout={onLogout} />

      {/* Header — tab root, no back button (see DiscoveryPage convention) */}
      <header className={styles.header}>
        <PageLogoHeader />
      </header>

      {/* FRONT-COMP-PROTO-1 — [사람] / [공모전] 전환 */}
      <SocialSegment active="people" />

      {/* Assessment prompt (no personality yet) */}
      {myPersonality === null && (
        <div className={styles.assessmentBanner}>
          <p className={styles.assessmentText}>{t('socialBoard.needAssessmentBanner')}</p>
          <button
            type="button"
            className={styles.assessmentCta}
            onClick={() => navigate('/assessment')}
          >
            {t('socialBoard.needAssessmentBannerCta')}
          </button>
        </div>
      )}

      {/* Filter chips */}
      <div className={styles.filterBar}>
        {FILTER_IDS.map(id => (
          <button
            key={id}
            type="button"
            className={`${styles.filterChip} ${activeFilter === id ? styles.filterChipActive : ''}`}
            onClick={() => selectFilter(id)}
            aria-pressed={activeFilter === id}
          >
            {PRESET_LABEL_KEY[id] ? t(PRESET_LABEL_KEY[id]) : id}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className={styles.content} ref={contentRef}>

        {error === 'assessment_required' && (
          <div className={styles.emptyState}>
            <p className={styles.emptyTitle}>{t('socialBoard.needAssessmentTitle')}</p>
            <p className={styles.emptyDesc}>{t('socialBoard.needAssessmentDesc')}</p>
            <button type="button" className={styles.ctaBtn} onClick={() => navigate('/assessment')}>
              {t('socialBoard.needAssessmentCta')}
            </button>
          </div>
        )}

        {error && error !== 'assessment_required' && (
          <div className={styles.inlineError}>
            <p>{error}</p>
            <button type="button" className={styles.retryBtn} onClick={() => loadPage(activeFilter, null)}>
              {t('socialBoard.retry')}
            </button>
          </div>
        )}

        {loading && !error && (
          <div className={styles.feed}>
            {Array.from({ length: 8 }, (_, i) => <SkeletonTile key={i} />)}
          </div>
        )}

        {!loading && !error && boards.length === 0 && (
          <div className={styles.emptyState}>
            <p className={styles.emptyTitle}>
              {t(activeFilter === 'all' ? 'socialBoard.emptyAllTitle' : 'socialBoard.emptyFilterTitle')}
            </p>
            <p className={styles.emptyDesc}>
              {t(activeFilter === 'all' ? 'socialBoard.emptyAllDesc' : 'socialBoard.emptyFilterDesc')}
            </p>
          </div>
        )}

        {!loading && !error && boards.length > 0 && (
          <>
            <div className={styles.feed} ref={gridRef}>
              {displayed.map(board => (
                <BoardSocialCard
                  key={board.board_id}
                  board={board}
                  expanded={expanded?.id === board.board_id}
                  onToggle={toggleExpand}
                  onLike={handleLike}
                  registerRef={registerRef}
                />
              ))}
              {loadingMore && Array.from({ length: 4 }, (_, i) => <SkeletonTile key={`more-${i}`} />)}
            </div>
            {moreError && (
              <div className={styles.inlineError}>
                <p>{t('socialBoard.feedError')}</p>
                <button type="button" className={styles.retryBtn} onClick={() => loadPage(activeFilter, nextCursor)}>
                  {t('socialBoard.retry')}
                </button>
              </div>
            )}
            <div ref={sentinelRef} style={{ height: 1 }} aria-hidden="true" />
          </>
        )}
      </div>

      {toast && (
        <div key={toast.key} className={styles.toast} role="status" aria-live="polite">
          {toast.text}
        </div>
      )}
    </div>
  )
}
