/**
 * mockCompetitions.js — PROTOTYPE FIXTURE.
 *
 * 공모전 팀빌딩 기능을 "재미있는지" 판단하기 위한 화면 전용 가짜 데이터.
 * 설계: docs/plans/2026-09-17-competition-team-design.md
 *
 * 백엔드가 없다. Competition / CompetitionInterest / Team / TeamInvite 모델은
 * 아직 존재하지 않으며, 이 프로토타입은 의도적으로 그것들을 만들지 않는다 —
 * 커뮤니티 방향이 탈락하면 브랜치째 버릴 수 있어야 하고, 마이그레이션까지
 * 들어가면 되돌리기 어렵기 때문.
 *
 * 찜 상태만 localStorage 에 남는다(competitionInterest.js). 데모 도중
 * 새로고침해도 누른 게 유지되어야 "진짜처럼" 느껴지기 때문.
 */

/** 데모 당일 기준으로 D-day 가 항상 그럴듯하게 보이도록 상대 일수로 저장. */
function daysFromNow(n) {
  const d = new Date()
  d.setHours(23, 59, 0, 0)
  d.setDate(d.getDate() + n)
  return d
}

export const MOCK_COMPETITIONS = [
  {
    id: 'c1',
    title: '2026 대학생 건축대전',
    organizer: '대한건축사협회',
    theme: '도시의 빈 곳을 다시 쓰다',
    deadlineIn: 3,
    teamSizeMin: 2,
    teamSizeMax: 4,
    interestCount: 23,
    officialUrl: 'https://example.com/competition/1',
  },
  {
    id: 'c2',
    title: '공공건축 아이디어 공모',
    organizer: '서울특별시',
    theme: '작은 도서관, 동네의 거실',
    deadlineIn: 9,
    teamSizeMin: 1,
    teamSizeMax: 3,
    interestCount: 41,
    officialUrl: 'https://example.com/competition/2',
  },
  {
    id: 'c3',
    title: '제12회 신진건축사 대상',
    organizer: '국토교통부',
    theme: '기후위기 시대의 주거',
    deadlineIn: 21,
    teamSizeMin: 2,
    teamSizeMax: 4,
    interestCount: 12,
    officialUrl: 'https://example.com/competition/3',
  },
  {
    id: 'c4',
    title: '캠퍼스 리노베이션 설계공모',
    organizer: '한국건축가협회',
    theme: '비어가는 강의동의 다음',
    deadlineIn: 34,
    teamSizeMin: 2,
    teamSizeMax: 5,
    interestCount: 7,
    officialUrl: 'https://example.com/competition/4',
  },
]

/**
 * 공모전별 찜한 사람.
 *
 * vector 는 5축(-1..+1). PersonCard 가 그대로 받는 모양이라 발견 피드와 같은
 * 카드를 재사용할 수 있다.
 */
export const MOCK_INTERESTED = {
  c1: [
    { user_id: 9001, display_name: '김서연', handle: 'seoyeon_k', avatar_url: null, type_code: 'CLON', vector: [0.78, -0.12, 0.61, 0.83, 0.04] },
    { user_id: 9002, display_name: '박도현', handle: 'dohyun.arch', avatar_url: null, type_code: 'CSDN', vector: [-0.62, 0.55, 0.48, 0.71, -0.22] },
    { user_id: 9003, display_name: '이하늘', handle: 'haneul', avatar_url: null, type_code: 'RLOT', vector: [-0.55, -0.41, 0.72, 0.68, 0.31] },
    { user_id: 9004, display_name: '최민준', handle: 'minjun_c', avatar_url: null, type_code: 'CLDT', vector: [0.69, 0.33, -0.52, -0.15, 0.44] },
    { user_id: 9005, display_name: '정유진', handle: 'yujin.j', avatar_url: null, type_code: 'CLOT', vector: [0.58, -0.22, 0.49, 0.75, 0.42] },
  ],
  c2: [
    { user_id: 9006, display_name: '한지우', handle: 'jiwoo_h', avatar_url: null, type_code: 'RSON', vector: [-0.71, -0.33, 0.55, 0.62, -0.18] },
    { user_id: 9002, display_name: '박도현', handle: 'dohyun.arch', avatar_url: null, type_code: 'CSDN', vector: [-0.62, 0.55, 0.48, 0.71, -0.22] },
    { user_id: 9007, display_name: '오세림', handle: 'serim.o', avatar_url: null, type_code: 'CLDN', vector: [0.44, 0.61, -0.38, 0.29, 0.53] },
  ],
  c3: [
    { user_id: 9008, display_name: '윤태오', handle: 'taeo', avatar_url: null, type_code: 'CSOT', vector: [0.33, -0.68, 0.71, 0.58, -0.4] },
    { user_id: 9001, display_name: '김서연', handle: 'seoyeon_k', avatar_url: null, type_code: 'CLON', vector: [0.78, -0.12, 0.61, 0.83, 0.04] },
  ],
  c4: [
    { user_id: 9009, display_name: '배수린', handle: 'surin_b', avatar_url: null, type_code: 'RLDT', vector: [-0.48, 0.27, -0.61, -0.33, 0.19] },
  ],
}

/** 모집 중인 팀. capacity - members.length 가 빈 자리(설계 §6-3: 저장하지 않고 파생). */
export const MOCK_TEAMS = {
  c1: [
    {
      id: 't1',
      name: '빈틈',
      capacity: 4,
      members: [
        { user_id: 9010, display_name: '강예은', handle: 'yeeun', type_code: 'CLON', isOwner: true },
        { user_id: 9011, display_name: '노현수', handle: 'hyunsoo', type_code: 'RSDT' },
        { user_id: 9012, display_name: '심가율', handle: 'gayul', type_code: 'CSON' },
      ],
    },
    {
      id: 't2',
      name: '사이공간 연구소',
      capacity: 3,
      members: [
        { user_id: 9013, display_name: '문재하', handle: 'jaeha', type_code: 'CLDT', isOwner: true },
      ],
    },
  ],
  c2: [
    {
      id: 't3',
      name: '동네거실',
      capacity: 3,
      members: [
        { user_id: 9014, display_name: '조은결', handle: 'eungyeol', type_code: 'RLON', isOwner: true },
        { user_id: 9015, display_name: '백서진', handle: 'seojin', type_code: 'CSOT' },
      ],
    },
  ],
  c3: [],
  c4: [],
}

/** 뷰어 본인의 축 벡터 — 겹침 계산과 오버레이 그래프에 쓰인다. */
export const MOCK_MY_VECTOR = [0.62, -0.28, 0.45, 0.71, -0.15]

export function competitionById(id) {
  return MOCK_COMPETITIONS.find(c => c.id === id) || null
}

/** 마감까지 남은 일수 — 렌더 시점에 계산해 D-day 가 항상 살아 있게. */
export function daysLeft(competition) {
  const ms = daysFromNow(competition.deadlineIn) - new Date()
  return Math.max(0, Math.ceil(ms / 86400000))
}
