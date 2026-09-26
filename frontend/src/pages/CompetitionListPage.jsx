/**
 * CompetitionListPage.jsx — 공모전 목록 (PROTOTYPE)
 * Route: /competitions — Social 탭의 두 번째 세그먼트
 *
 * 설계: docs/plans/2026-09-17-competition-team-design.md §7-1
 *
 * 저빈도 문제를 푸는 화면이므로 **팀을 짤 생각이 없어도 볼 만해야** 한다.
 * 마감 임박순이 기본 정렬인 이유 — 긴급함이 목록의 성격을 만든다.
 *
 * 백엔드 없음. 목 데이터 + localStorage 찜.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageTopControls from '../components/PageTopControls.jsx'
import SocialSegment from '../components/SocialSegment.jsx'
import { MOCK_COMPETITIONS, MOCK_TEAMS, daysLeft } from '../constants/mockCompetitions.js'
import { loadInterests, toggleInterest } from '../utils/competitionInterest.js'
import styles from './CompetitionListPage.module.css'

export default function CompetitionListPage({ onLogout }) {
  const navigate = useNavigate()
  const [interests, setInterests] = useState(() => loadInterests())

  // 마감 임박순. 목 데이터는 이미 그 순서지만 정렬을 명시해 의도를 남긴다.
  const items = [...MOCK_COMPETITIONS].sort((a, b) => daysLeft(a) - daysLeft(b))

  function handleToggle(e, id) {
    e.stopPropagation()   // 카드 클릭(상세 이동)과 분리
    setInterests(prev => toggleInterest(prev, id))
  }

  return (
    <div className={styles.page}>
      <PageTopControls onLogout={onLogout} />

      <header className={styles.header}>
        <h1 className={styles.title}>소셜</h1>
      </header>

      <SocialSegment active="competitions" />

      <div className={styles.content}>
        <ul className={styles.list}>
          {items.map(c => {
            const d = daysLeft(c)
            const saved = interests.has(c.id)
            const recruiting = (MOCK_TEAMS[c.id] || []).filter(
              t => t.members.length < t.capacity
            ).length
            return (
              <li key={c.id}>
                <article
                  className={styles.card}
                  onClick={() => navigate(`/competitions/${c.id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      navigate(`/competitions/${c.id}`)
                    }
                  }}
                >
                  <div className={styles.cardMain}>
                    <div className={styles.cardHead}>
                      <h2 className={styles.cardTitle}>{c.title}</h2>
                      <span className={`${styles.dday} ${d <= 7 ? styles.ddayUrgent : ''}`}>
                        D-{d}
                      </span>
                    </div>
                    <p className={styles.organizer}>{c.organizer}</p>
                    <p className={styles.theme}>{c.theme}</p>

                    <div className={styles.metaRow}>
                      <span className={styles.meta}>
                        {c.interestCount + (saved ? 1 : 0)}명 관심
                      </span>
                      {recruiting > 0 && (
                        <>
                          <span className={styles.dot} aria-hidden="true">·</span>
                          <span className={styles.metaAccent}>{recruiting}팀 모집중</span>
                        </>
                      )}
                    </div>
                  </div>

                  <button
                    type="button"
                    className={`${styles.interestBtn} ${saved ? styles.interestBtnOn : ''}`}
                    onClick={e => handleToggle(e, c.id)}
                    aria-pressed={saved}
                    aria-label={saved ? `${c.title} 관심 해제` : `${c.title} 관심 등록`}
                  >
                    {saved ? '관심 ✓' : '관심'}
                  </button>
                </article>
              </li>
            )
          })}
        </ul>

        <p className={styles.protoNote}>
          프로토타입 — 공모전 정보와 참가자는 예시 데이터입니다
        </p>
      </div>
    </div>
  )
}
