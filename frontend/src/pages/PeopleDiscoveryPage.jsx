/**
 * PeopleDiscoveryPage.jsx
 * People discovery feed — personality-based user matching.
 * Route: /people (ProtectedRoute) — tab root for the "소셜" (Social) TabBar tab.
 * As a tab root, this page has no back button (see DiscoveryPage for the same
 * tab-root convention). DiscoveryTriggerCard's push-navigation into this page
 * (from Discovery, after 10 draft likes) still works unchanged.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getMyPersonality } from '../api/personality.js'
import { getPeopleDiscovery } from '../api/people.js'
import PersonCard from '../components/PersonCard.jsx'
import { TYPE_CODES } from '../constants/personalityTypes.js'
import PageTopControls from '../components/PageTopControls.jsx'
import styles from './PeopleDiscoveryPage.module.css'

const PRESET_FILTERS = [
  { id: 'all', label: '전체' },
  { id: 'inspired', label: '영감 주는 사람' },
  { id: 'opposite', label: '정반대 성향' },
]

// All filter chips: presets + 16 type codes
const ALL_FILTERS = [
  ...PRESET_FILTERS,
  ...TYPE_CODES.map(code => ({ id: code, label: code })),
]

function vectorFrom(p) {
  if (!p) return null
  return [p.axis_1, p.axis_2, p.axis_3, p.axis_4, p.axis_5]
}

// Simple inline toast
function Toast({ message, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 3000)
    return () => clearTimeout(t)
  }, [onDismiss])

  return (
    <div className={styles.toast} role="status" aria-live="polite">
      {message}
    </div>
  )
}

// Skeleton card placeholder — one image-shaped block, matching the card's
// report-image front face (FRONT-PEOPLE-CARD-1).
function PersonCardSkeleton() {
  return <div className={`${styles.skeleton} skeleton-shimmer`} aria-hidden="true" />
}

export default function PeopleDiscoveryPage({ onLogout }) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const axisParam = searchParams.get('axis')

  const [myPersonality, setMyPersonality] = useState(undefined) // undefined = loading
  const [people, setPeople] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeFilter, setActiveFilter] = useState('all')
  const [toast, setToast] = useState(null)
  const filterScrollRef = useRef(null)
  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true
    return () => { isMounted.current = false }
  }, [])

  // Fetch my personality on mount
  useEffect(() => {
    getMyPersonality()
      .then(data => { if (isMounted.current) setMyPersonality(data) })
      .catch(() => { if (isMounted.current) setMyPersonality(null) })
  }, [])

  const fetchPeople = useCallback(async ({ filter, axis } = {}) => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (filter && filter !== 'all') params.filter = filter
      if (axis !== undefined && axis !== null) params.axis = axis
      const data = await getPeopleDiscovery(params)
      if (isMounted.current) {
        setPeople(Array.isArray(data) ? data : (data?.results ?? []))
      }
    } catch (err) {
      if (!isMounted.current) return
      if (err.status === 403 && err.data?.detail === 'assessment_required') {
        setError('assessment_required')
      } else {
        setError(err.message || '피드를 불러오지 못했어요.')
      }
    } finally {
      if (isMounted.current) setLoading(false)
    }
  }, [])

  // Initial load — respect ?axis= param
  useEffect(() => {
    const axis = axisParam !== null ? Number(axisParam) : undefined
    fetchPeople({ filter: activeFilter, axis })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Refetch when filter changes (not on initial mount — covered above)
  const isFirstFilterChange = useRef(true)
  useEffect(() => {
    if (isFirstFilterChange.current) {
      isFirstFilterChange.current = false
      return
    }
    fetchPeople({ filter: activeFilter })
  }, [activeFilter, fetchPeople])

  function handleInterest(person) {
    setToast(`${person.display_name}에게 관심을 보냈어요.`)
  }

  function dismissToast() {
    setToast(null)
  }

  const myVector = myPersonality ? vectorFrom(myPersonality) : null

  return (
    <div className={styles.page}>
      <PageTopControls onLogout={onLogout} />

      {/* Header — tab root, no back button (see DiscoveryPage convention) */}
      <header className={styles.header}>
        <h1 className={styles.title}>사람 발견</h1>
      </header>

      {/* Assessment prompt (no personality yet) */}
      {myPersonality === null && (
        <div className={styles.assessmentBanner}>
          <p className={styles.assessmentText}>성향 진단 후 발견 피드를 볼 수 있어요</p>
          <button
            type="button"
            className={styles.assessmentCta}
            onClick={() => navigate('/assessment')}
          >
            진단 받기 →
          </button>
        </div>
      )}

      {/* Filter chips */}
      <div className={styles.filterBar} ref={filterScrollRef}>
        {ALL_FILTERS.map(f => (
          <button
            key={f.id}
            type="button"
            className={`${styles.filterChip} ${activeFilter === f.id ? styles.filterChipActive : ''}`}
            onClick={() => setActiveFilter(f.id)}
            aria-pressed={activeFilter === f.id}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className={styles.content}>

        {/* assessment_required error */}
        {error === 'assessment_required' && (
          <div className={styles.emptyState}>
            <p className={styles.emptyTitle}>성향 진단이 필요해요</p>
            <p className={styles.emptyDesc}>나의 건축 성향을 먼저 파악한 후 다른 사람들을 발견할 수 있어요.</p>
            <button
              type="button"
              className={styles.ctaBtn}
              onClick={() => navigate('/assessment')}
            >
              성향 진단 받기
            </button>
          </div>
        )}

        {/* Generic error */}
        {error && error !== 'assessment_required' && (
          <div className={styles.inlineError}>
            <p>{error}</p>
            <button
              type="button"
              className={styles.retryBtn}
              onClick={() => fetchPeople({ filter: activeFilter })}
            >
              다시 시도
            </button>
          </div>
        )}

        {/* Loading skeletons */}
        {loading && !error && (
          <div className={styles.feed}>
            {Array.from({ length: 8 }, (_, i) => <PersonCardSkeleton key={i} />)}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && people.length === 0 && (
          <div className={styles.emptyState}>
            <p className={styles.emptyTitle}>아직 발견할 사람이 없어요</p>
            <p className={styles.emptyDesc}>다른 필터를 선택해보거나 나중에 다시 확인해보세요.</p>
          </div>
        )}

        {/* Feed */}
        {!loading && !error && people.length > 0 && (
          <div className={styles.feed}>
            {people.map(person => (
              <PersonCard
                key={person.user_id}
                person={person}
                myVector={myVector}
                onInterest={handleInterest}
              />
            ))}
          </div>
        )}
      </div>

      {/* Toast */}
      {toast && <Toast message={toast} onDismiss={dismissToast} />}
    </div>
  )
}
