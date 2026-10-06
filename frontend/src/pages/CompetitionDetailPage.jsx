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
 *
 * UI-CONSISTENCY-B Phase 3b-3: onto the shared chrome system — PageShell
 * ('medium', 680, same precedent as BoardDetailPage) + PageBackButton +
 * PageTopControls + PageLogoHeader replace the hand-rolled 56px top-padding
 * spacer hack on .hero. h1 → PageTitle, section headers → SectionTitle,
 * not-found → EmptyState.
 */

import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from '../i18n/index.js'
import PageShell from '../components/PageShell.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTitle from '../components/PageTitle.jsx'
import SectionTitle from '../components/SectionTitle.jsx'
import EmptyState from '../components/EmptyState.jsx'
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
  const { t } = useTranslation()
  const { competitionId } = useParams()
  const competition = competitionById(competitionId)

  const [interests, setInterests] = useState(() => loadInterests())
  const [toast, setToast] = useState(null)

  const chrome = (
    <>
      <PageTopControls onLogout={onLogout} leading={<PageBackButton inline onClick={() => navigate('/competitions')} />} />
      <PageLogoHeader />
    </>
  )

  if (!competition) {
    return (
      <PageShell width="medium" chrome={chrome}>
        <EmptyState title={t('competitionB3.detail.notFound')} />
      </PageShell>
    )
  }

  const saved = interests.has(competition.id)
  const d = daysLeft(competition)

  // 찜한 사람은 적합도 순. 발견 피드의 유클리드 정렬과 의도적으로 다르다(§4).
  const ranked = sortByFit(MOCK_INTERESTED[competition.id] || [], MOCK_MY_VECTOR)
  // 상위 1명만 추천으로 올린다. 2~3명을 추천하면 "추천"이 희석되어 그냥
  // 정렬된 목록과 다를 게 없어진다.
  const recommended = ranked.length > 1 ? ranked[0] : null
  const rest = recommended ? ranked.slice(1) : ranked
  const teams = MOCK_TEAMS[competition.id] || []

  function handleToggleInterest() {
    setInterests(prev => toggleInterest(prev, competition.id))
  }

  function showToast(msg) {
    setToast(msg)
    setTimeout(() => setToast(null), 2200)
  }

  /**
   * 사람 카드. 추천/일반이 같은 카드를 쓰고 테두리만 달라진다 — 다른 레이아웃을
   * 쓰면 "추천"이 별개 기능처럼 보여 목록과의 연결이 끊긴다.
   *
   * 실명 대신 아이디만 보여준다. 판단용 프로토타입이라 사람을 특정할 필요가
   * 없고, 모르는 사람의 실명이 나열되면 발견보다 신상 목록처럼 읽힌다.
   */
  function renderPerson(p, isRecommended) {
    return (
      <article className={`${styles.personCard} ${isRecommended ? styles.personCardRec : ''}`}>
        <div className={styles.personChart}>
          <PentagonChart myVector={MOCK_MY_VECTOR} theirVector={p.vector} mini size={104} />
        </div>
        <div className={styles.personBody}>
          <div className={styles.personHead}>
            {/* 아이디를 누르면 그 사람의 Created 탭으로 — 작품을 보고
                판단할 수 있어야 "제안"에 근거가 생긴다. */}
            <button
              type="button"
              className={styles.handleBtn}
              onClick={() => navigate(`/user/${p.user_id}?tab=created`)}
              aria-label={t('competitionB3.detail.viewProfileAria', { handle: p.handle })}
            >
              @{p.handle}
            </button>
            <span className={styles.typeBadge}>{p.type_code}</span>
          </div>
          <p className={styles.fitReason}>{fitReason(MOCK_MY_VECTOR, p.vector)}</p>
        </div>
        <button
          type="button"
          className={styles.proposeBtn}
          onClick={() => showToast(t('competitionB3.detail.proposeSent', { handle: p.handle }))}
        >
          {t('competitionB3.detail.proposeBtn')}
        </button>
      </article>
    )
  }

  return (
    <PageShell width="medium" contentStyle={{ padding: '20px 20px 0' }} chrome={chrome}>
      {/* ── 상단: 공모전 정보 ── */}
      <header className={styles.hero}>
        <span className={`${styles.dday} ${d <= 7 ? styles.ddayUrgent : ''}`}>
          {t('competitionB3.dday', { d })}
        </span>
        <PageTitle style={{ margin: '0 0 6px' }}>{competition.title}</PageTitle>
        <p className={styles.organizer}>{competition.organizer}</p>
        <p className={styles.theme}>{competition.theme}</p>
        <p className={styles.sizeHint}>
          {t('competitionB3.detail.teamSizeHint', {
            min: competition.teamSizeMin,
            max: competition.teamSizeMax,
          })}
        </p>

        <button
          type="button"
          className={`${styles.interestCta} ${saved ? styles.interestCtaOn : ''}`}
          onClick={handleToggleInterest}
          aria-pressed={saved}
        >
          {t(saved ? 'competitionB3.detail.interestCtaOn' : 'competitionB3.detail.interestCtaOff')}
        </button>
        <p className={styles.interestCount}>
          {t('competitionB3.detail.interestCount', {
            count: competition.interestCount + (saved ? 1 : 0),
          })}
        </p>
      </header>

      {/* ── 섹션 A: 찜한 사람 — 추천 1명 + 전체 ── */}
      <section className={styles.section}>
        {recommended && (
          <>
            <SectionTitle>
              {t('competitionB3.detail.recommendedTitle')}{' '}
              <span className={styles.sectionHint}>{t('competitionB3.detail.recommendedHint')}</span>
            </SectionTitle>
            <div className={styles.recommendWrap}>
              {renderPerson(recommended, true)}
            </div>
          </>
        )}

        <SectionTitle
          className={recommended ? styles.sectionTitleGap : undefined}
          count={ranked.length > 0 ? t('competitionB3.detail.interestedCount', { count: ranked.length }) : null}
        >
          {t('competitionB3.detail.interestedTitle')}
        </SectionTitle>
        {rest.length === 0 ? (
          <p className={styles.sectionEmpty}>
            {ranked.length === 0
              ? t('competitionB3.detail.emptyAll')
              : t('competitionB3.detail.emptyRest')}
          </p>
        ) : (
          <ul className={styles.personList}>
            {rest.map(p => <li key={p.user_id}>{renderPerson(p, false)}</li>)}
          </ul>
        )}
      </section>

      {/* ── 섹션 B: 모집 중인 팀 ── */}
      <section className={styles.section}>
        <SectionTitle>{t('competitionB3.detail.teamsTitle')}</SectionTitle>
        {teams.length === 0 ? (
          <p className={styles.sectionEmpty}>{t('competitionB3.detail.noTeams')}</p>
        ) : (
          <ul className={styles.teamList}>
            {teams.map(team => {
              // 빈 자리는 저장하지 않고 파생한다(설계 §6-3).
              const open = team.capacity - team.members.length
              return (
                <li key={team.id}>
                  <article className={styles.teamCard}>
                    <div className={styles.teamHead}>
                      <span className={styles.teamName}>{team.name}</span>
                      {open > 0 ? (
                        <span className={styles.openSlot}>
                          {t('competitionB3.detail.openSlots', { count: open })}
                        </span>
                      ) : (
                        <span className={styles.fullSlot}>{t('competitionB3.detail.full')}</span>
                      )}
                    </div>
                    <p className={styles.teamMembers}>
                      {team.members.map(m => `@${m.handle}`).join(' · ')}
                    </p>
                    {open > 0 && (
                      <button
                        type="button"
                        className={styles.joinBtn}
                        onClick={() => showToast(t('competitionB3.detail.joinSent', { team: team.name }))}
                      >
                        {t('competitionB3.detail.joinBtn')}
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
          onClick={() => showToast(t('competitionB3.detail.createTeamComingSoon'))}
        >
          {t('competitionB3.detail.createTeamBtn')}
        </button>
      </section>

      <p className={styles.protoNote}>{t('competitionB3.protoNote')}</p>

      {toast && <div className={styles.toast} role="status">{toast}</div>}
    </PageShell>
  )
}
