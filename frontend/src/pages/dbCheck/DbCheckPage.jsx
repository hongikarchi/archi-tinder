/**
 * DbCheckPage.jsx — ADMIN-DBCHECK-1 internal DB-quality inspection page.
 *
 * Dev-build only, URL-only route (/db-check, no TabBar/nav link). Lets us
 * visually audit canonical_v2_buildings quality:
 *   - Browse mode: infinite-scroll grid of every publishable building
 *     (keyset pagination via GET /inspect/buildings/).
 *   - Search mode: natural-language query through the real service search
 *     (POST /inspect/search/) — shows parsed structured_filters as chips,
 *     filter_priority order, and an is_fallback warning badge.
 *   - Click a tile -> full DB row detail modal.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { getInspectBuildings, inspectSearch } from '../../api/inspect.js'
import DbCheckTile from './DbCheckTile.jsx'
import DbCheckDetailModal from './DbCheckDetailModal.jsx'
import styles from './DbCheck.module.css'

const PAGE_SIZE = 60

export default function DbCheckPage() {
  // Browse mode state
  const [browseResults, setBrowseResults] = useState([])
  const [nextAfter, setNextAfter] = useState(null)
  const [total, setTotal] = useState(null)
  const [browseLoading, setBrowseLoading] = useState(false)
  const [browseInitialized, setBrowseInitialized] = useState(false)

  // Search mode state
  const [query, setQuery] = useState('')
  const [searchActive, setSearchActive] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchResults, setSearchResults] = useState([])
  const [searchMeta, setSearchMeta] = useState(null) // { structured_filters, filter_priority, is_fallback }
  const [searchError, setSearchError] = useState(null)

  const [selectedId, setSelectedId] = useState(null)

  const fetchInFlight = useRef(false)
  const sentinelRef = useRef(null)

  // -- Browse: initial load --------------------------------------------
  useEffect(() => {
    if (browseInitialized) return
    setBrowseInitialized(true)
    setBrowseLoading(true)
    fetchInFlight.current = true
    getInspectBuildings({ pageSize: PAGE_SIZE })
      .then(data => {
        setBrowseResults(data.results || [])
        setNextAfter(data.next_after ?? null)
        setTotal(data.total ?? null)
      })
      .catch(() => {})
      .finally(() => {
        setBrowseLoading(false)
        fetchInFlight.current = false
      })
  }, [browseInitialized])

  // -- Browse: load next page (guarded against duplicate in-flight fetches)
  const loadMoreBrowse = useCallback(() => {
    if (fetchInFlight.current) return
    if (searchActive) return
    if (nextAfter === null) return
    fetchInFlight.current = true
    setBrowseLoading(true)
    getInspectBuildings({ after: nextAfter, pageSize: PAGE_SIZE })
      .then(data => {
        setBrowseResults(prev => [...prev, ...(data.results || [])])
        setNextAfter(data.next_after ?? null)
        if (data.total != null) setTotal(data.total)
      })
      .catch(() => {})
      .finally(() => {
        setBrowseLoading(false)
        fetchInFlight.current = false
      })
  }, [nextAfter, searchActive])

  // -- IntersectionObserver sentinel — browse mode only
  useEffect(() => {
    if (searchActive) return
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      entries => { if (entries[0].isIntersecting) loadMoreBrowse() },
      { rootMargin: '300px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loadMoreBrowse, searchActive])

  // -- Search submit -----------------------------------------------------
  const runSearch = useCallback((q) => {
    const trimmed = q.trim()
    if (!trimmed) return
    setSearchActive(true)
    setSearchLoading(true)
    setSearchError(null)
    inspectSearch(trimmed)
      .then(data => {
        setSearchResults(data.results || [])
        setSearchMeta({
          structured_filters: data.structured_filters || {},
          filter_priority: data.filter_priority || [],
          is_fallback: !!data.is_fallback,
        })
      })
      .catch(err => {
        setSearchError(err?.message || 'Search failed')
        setSearchResults([])
        setSearchMeta(null)
      })
      .finally(() => setSearchLoading(false))
  }, [])

  function handleSearchKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      runSearch(query)
    }
  }

  function handleClear() {
    setQuery('')
    setSearchActive(false)
    setSearchResults([])
    setSearchMeta(null)
    setSearchError(null)
  }

  const displayedResults = searchActive ? searchResults : browseResults

  const filterChips = searchMeta
    ? Object.entries(searchMeta.structured_filters || {}).filter(([, v]) => v != null && v !== '' && !(Array.isArray(v) && v.length === 0))
    : []

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.searchRow}>
          <div className={styles.searchInputWrap}>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="벽돌 재질로 만든 건물..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleSearchKeyDown}
              aria-label="Natural-language building search"
            />
            {searchLoading && <div className={styles.spinner} aria-hidden="true" />}
          </div>
          {searchActive && (
            <button type="button" className={styles.clearBtn} onClick={handleClear} aria-label="Clear search, return to browse">
              ✕
            </button>
          )}
        </div>

        {/* Status line */}
        <div className={styles.statusLine}>
          {searchActive ? (
            searchError ? (
              <span style={{ color: 'var(--color-destructive)' }}>{searchError}</span>
            ) : searchLoading ? (
              'Searching…'
            ) : (
              `${searchResults.length} result${searchResults.length === 1 ? '' : 's'}`
            )
          ) : (
            `All publishable buildings — loaded ${browseResults.length} / ${total ?? '…'}`
          )}
        </div>

        {/* Structured filter chips + fallback badge (search mode only) */}
        {searchActive && searchMeta && !searchLoading && (
          <div className={styles.chipRow}>
            {filterChips.map(([axis, value]) => (
              <span key={axis} className={styles.chip}>
                <span className={styles.chipAxis}>{axis}:</span>
                {Array.isArray(value) ? value.join(', ') : String(value)}
              </span>
            ))}
            {searchMeta.filter_priority?.length > 0 && (
              <span className={styles.chip}>
                <span className={styles.chipAxis}>priority:</span>
                {searchMeta.filter_priority.join(' > ')}
              </span>
            )}
            {searchMeta.is_fallback && (
              <span className={styles.fallbackBadge}>no signal — showing random sample</span>
            )}
          </div>
        )}
      </div>

      {/* Grid */}
      {displayedResults.length === 0 && !browseLoading && !searchLoading ? (
        <div className={styles.emptyState}>No buildings to show.</div>
      ) : (
        <div className={styles.grid}>
          {displayedResults.map((card, i) => (
            <DbCheckTile
              key={card.image_id || card.canonical_bld_id || i}
              card={card}
              onClick={setSelectedId}
            />
          ))}
        </div>
      )}

      {/* Infinite-scroll sentinel — browse mode only */}
      {!searchActive && nextAfter !== null && (
        <div ref={sentinelRef} className={styles.sentinel} />
      )}

      {selectedId && (
        <DbCheckDetailModal id={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
