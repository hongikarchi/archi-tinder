/**
 * CompetitionListPage.jsx — 공모전 목록
 * Route: /competitions — Social 탭의 두 번째 세그먼트
 *
 * 설계: docs/decisions/2026-10-09-contest-real-data.md (FRONT-CONTEST-1)
 *
 * 실제 API(GET contests/)를 읽는다. D-n 은 남은 마감 중 가장 가까운 것(D9) —
 * 어떤 마감인지 라벨을 함께 보여준다. 마감 임박순.
 *
 * 상단 구조는 형제 화면 PeopleDiscoveryPage 와 같다
 * (PageTopControls + PageLogoHeader + SocialSegment).
 */

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from '../i18n/index.ts'
import { listContests } from '../api/contests.ts'
import { useNow } from '../hooks/useNow.ts'
import { nextDeadline } from '../utils/contestDeadline.ts'
import PageTopControls from '../components/PageTopControls.tsx'
import PageLogoHeader from '../components/PageLogoHeader.tsx'
import SocialSegment from '../components/SocialSegment.tsx'
import EmptyState from '../components/EmptyState.tsx'
import Skeleton from '../components/Skeleton.tsx'
import DeadlineBadge from '../components/contests/DeadlineBadge.tsx'
import styles from './CompetitionListPage.module.css'

export default function CompetitionListPage({ onLogout }) {
  const { t } = useTranslation()
  const now = useNow()
  const [status, setStatus] = useState('loading')   // 'loading' | 'error' | 'ready'
  const [contests, setContests] = useState([])
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    listContests()
      .then(data => {
        if (cancelled) return
        setContests(Array.isArray(data?.results) ? data.results : [])
        setStatus('ready')
      })
      .catch(() => { if (!cancelled) setStatus('error') })
    return () => { cancelled = true }
  }, [reloadKey])

  function retry() {
    setStatus('loading')
    setReloadKey(k => k + 1)
  }

  // 마감 임박순 — 카드에 보이는 D-n(가장 가까운 남은 마감)과 같은 기준으로 정렬한다.
  const items = useMemo(() => {
    const key = c => nextDeadline(c, now)?.at.getTime() ?? Infinity
    return [...contests].sort((a, b) => key(a) - key(b))
  }, [contests, now])

  return (
    <div className={styles.page}>
      <PageTopControls onLogout={onLogout} />

      {/* Header — tab root, no back button (matches PeopleDiscoveryPage) */}
      <header className={styles.header}>
        <PageLogoHeader />
      </header>

      <SocialSegment active="competitions" />

      <div className={styles.content}>
        {status === 'loading' && (
          <ul className={styles.list} aria-hidden="true">
            {[0, 1, 2].map(i => (
              <li key={i}>
                <Skeleton height={108} radius="var(--radius-md)" />
              </li>
            ))}
          </ul>
        )}

        {status === 'error' && (
          <div className={styles.inlineError} role="alert">
            <p>{t('contest.list.loadError')}</p>
            <button type="button" className={styles.retryBtn} onClick={retry}>
              {t('contest.list.retry')}
            </button>
          </div>
        )}

        {status === 'ready' && items.length === 0 && (
          <EmptyState
            title={t('contest.list.emptyTitle')}
            body={t('contest.list.emptyBody')}
          />
        )}

        {status === 'ready' && items.length > 0 && (
          <ul className={styles.list}>
            {items.map(c => (
              <li key={c.id}>
                <Link to={`/competitions/${encodeURIComponent(c.id)}`} className={styles.card}>
                  <DeadlineBadge contest={c} now={now} />
                  <h2 className={styles.cardTitle}>{c.title}</h2>
                  <p className={styles.organizer}>{c.organizer}</p>
                  {c.theme && <p className={styles.theme}>{c.theme}</p>}
                  {c.interest_count > 0 && (
                    <p className={styles.meta}>
                      {t('contest.list.interestCount', { count: c.interest_count })}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
