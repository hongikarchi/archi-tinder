/**
 * CompetitionDetailPage.jsx — 공모전 상세 (PROTOTYPE)
 * Route: /competitions/:competitionId
 *
 * 설계: docs/plans/2026-09-17-competition-team-design.md §7-2
 *
 * 이 설계의 핵심 화면. 찜 → 같은 의도를 가진 사람 발견 → 팀으로 이어지는
 * 전환이 이 한 화면에서 일어난다.
 *
 * 섹션 A(찜한 사람)는 teamFit 점수 순으로 정렬한다 — 발견 피드의 "가까운
 * 사람"과 달리 1·2축은 보완, 3·4축은 일치를 본다(§4).
 *
 * 백엔드 없음. 목 데이터 + localStorage 찜.
 */

import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import PentagonChart from '../components/PentagonChart.jsx'
import {
  competitionById,
  daysLeft,
  MOCK_INTERESTED,
  MOCK_TEAMS,
  MOCK_MY_VECTOR,
} from '../constants/mockCompetitions.js'
import { loadInterests, toggleInterest } from '../utils/competitionInterest.js'
import { sortByFit, fitReason } from '../utils/teamFit.js'
import styles from './CompetitionDetailPage.module.css'

export default function CompetitionDetailPage({ onLogout }) {
  const navigate = useNavigate()
  const { competitionId } = useParams()
  const competition = competitionById(competitionId)

  const [interests, setInterests] = useState(() => loadInterests())
  const [toast, setToast] = useState(null)

  if (!competition) {
    return (
      <div className={styles.page}>
        <PageBackButton onClick={() => navigate('/competitions')} />
        <PageTopControls onLogout={onLogout} />
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>공모전을 찾을 수 없어요</p>
        </div>
      </div>
    )
  }

  const saved = interests.has(competition.id)
  const d = daysLeft(competition)

  // 찜한 사람은 적합도 순. 발견 피드의 유클리드 정렬과 의도적으로 다르다(§4).
  const people = sortByFit(MOCK_INTERESTED[competition.id] || [], MOCK_MY_VECTOR)
  const teams = MOCK_TEAMS[competition.id] || []

  function handleToggleInterest() {
    setInterests(prev => toggleInterest(prev, competition.id))
  }

  function showToast(msg) {
    setToast(msg)
    setTimeout(() => setToast(null), 2200)
  }

  return (
    <div className={styles.page}>
      <PageBackButton onClick={() => navigate('/competitions')} />
      <PageTopControls onLogout={onLogout} />

      <div className={styles.content}>
        {/* ── 상단: 공모전 정보 ── */}
        <header className={styles.hero}>
          <span className={`${styles.dday} ${d <= 7 ? styles.ddayUrgent : ''}`}>D-{d}</span>
          <h1 className={styles.title}>{competition.title}</h1>
          <p className={styles.organizer}>{competition.organizer}</p>
          <p className={styles.theme}>{competition.theme}</p>
          <p className={styles.sizeHint}>
            권장 {competition.teamSizeMin}~{competition.teamSizeMax}인
          </p>

          <button
            type="button"
            className={`${styles.interestCta} ${saved ? styles.interestCtaOn : ''}`}
            onClick={handleToggleInterest}
            aria-pressed={saved}
          >
            {saved ? '관심 등록됨 ✓' : '관심 있어요'}
          </button>
          <p className={styles.interestCount}>
            {competition.interestCount + (saved ? 1 : 0)}명이 이 공모전을 보고 있어요
          </p>
        </header>

        {/* ── 섹션 A: 찜한 사람 ── */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>이 공모전에 관심 있는 사람</h2>
          {people.length === 0 ? (
            <p className={styles.sectionEmpty}>아직 관심을 표시한 사람이 없어요</p>
          ) : (
            <ul className={styles.personList}>
              {people.map(p => (
                <li key={p.user_id}>
                  <article className={styles.personCard}>
                    <div className={styles.personChart}>
                      <PentagonChart
                        myVector={MOCK_MY_VECTOR}
                        theirVector={p.vector}
                        mini
                        size={76}
                      />
                    </div>
                    <div className={styles.personBody}>
                      <div className={styles.personHead}>
                        <span className={styles.personName}>{p.display_name}</span>
                        <span className={styles.typeBadge}>{p.type_code}</span>
                      </div>
                      <p className={styles.personHandle}>@{p.handle}</p>
                      <p className={styles.fitReason}>{fitReason(MOCK_MY_VECTOR, p.vector)}</p>
                    </div>
                    <button
                      type="button"
                      className={styles.proposeBtn}
                      onClick={() => showToast(`${p.display_name}님에게 제안을 보냈어요`)}
                    >
                      제안
                    </button>
                  </article>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* ── 섹션 B: 모집 중인 팀 ── */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>모집 중인 팀</h2>
          {teams.length === 0 ? (
            <p className={styles.sectionEmpty}>아직 만들어진 팀이 없어요</p>
          ) : (
            <ul className={styles.teamList}>
              {teams.map(t => {
                // 빈 자리는 저장하지 않고 파생한다(설계 §6-3).
                const open = t.capacity - t.members.length
                return (
                  <li key={t.id}>
                    <article className={styles.teamCard}>
                      <div className={styles.teamHead}>
                        <span className={styles.teamName}>{t.name}</span>
                        {open > 0 ? (
                          <span className={styles.openSlot}>{open}자리 남음</span>
                        ) : (
                          <span className={styles.fullSlot}>마감</span>
                        )}
                      </div>
                      <p className={styles.teamMembers}>
                        {t.members.map(m => m.display_name).join(' · ')}
                      </p>
                      {open > 0 && (
                        <button
                          type="button"
                          className={styles.joinBtn}
                          onClick={() => showToast(`${t.name} 팀에 참여 요청을 보냈어요`)}
                        >
                          참여 요청
                        </button>
                      )}
                    </article>
                  </li>
                )
              })}
            </ul>
          )}

          <button
            type="button"
            className={styles.createTeamBtn}
            onClick={() => showToast('팀 만들기는 준비 중이에요')}
          >
            팀 만들기
          </button>
        </section>

        <p className={styles.protoNote}>
          프로토타입 — 공모전 정보와 참가자는 예시 데이터입니다
        </p>
      </div>

      {toast && <div className={styles.toast} role="status">{toast}</div>}
    </div>
  )
}
