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
 * user_id / handle / type_code / vector 는 **로컬 DB의 실제 행과 일치**시켰다
 * (seed_people_local.py 로 심은 36~40, 그리고 실계정 3). 아이디를 누르면
 * /user/:id?tab=created 로 가서 그 사람의 작품이 실제로 뜬다.
 *
 * 주의: 이 id 들은 로컬 개발 DB에만 있다. 다른 환경(배포 서버 등)에서는
 * 프로필이 "찾을 수 없음"으로 뜬다 — 그 환경에서 쓰려면 seed_discovery
 * 관리 커맨드로 유저를 심고 여기 id 를 맞춰야 한다.
 *
 * vector 는 5축(-1..+1).
 */
export const MOCK_INTERESTED = {
  c1: [
    { user_id: 36, display_name: 'seoyeon', handle: 'seoyeon', avatar_url: null, type_code: 'CLON', vector: [0.78, -0.12, 0.61, 0.83, 0.04] },
    { user_id: 37, display_name: 'dohyun', handle: 'dohyun', avatar_url: null, type_code: 'CSDN', vector: [0.41, 0.55, -0.38, 0.29, -0.62] },
    { user_id: 38, display_name: 'haneul', handle: 'haneul', avatar_url: null, type_code: 'RLOT', vector: [-0.55, -0.41, 0.72, -0.18, 0.66] },
    { user_id: 39, display_name: 'minjun', handle: 'minjun', avatar_url: null, type_code: 'CLDT', vector: [0.69, -0.33, -0.52, 0.75, 0.31] },
    { user_id: 40, display_name: 'yujin', handle: 'yujin', avatar_url: null, type_code: 'CLOT', vector: [0.58, -0.22, 0.49, 0.68, 0.42] },
  ],
  c2: [
    { user_id: 3, display_name: '예원', handle: '예원', avatar_url: null, type_code: 'CSDT', vector: [0.12, -0.12, -0.12, -0.12, 0.25] },
    { user_id: 37, display_name: 'dohyun', handle: 'dohyun', avatar_url: null, type_code: 'CSDN', vector: [0.41, 0.55, -0.38, 0.29, -0.62] },
  ],
  c3: [
    { user_id: 36, display_name: 'seoyeon', handle: 'seoyeon', avatar_url: null, type_code: 'CLON', vector: [0.78, -0.12, 0.61, 0.83, 0.04] },
  ],
  c4: [],
}

/** 모집 중인 팀. capacity - members.length 가 빈 자리(설계 §6-3: 저장하지 않고 파생).
 *  팀 멤버는 DB에 없는 가공 인물이다 — 이름만 나열될 뿐 프로필로 가는 링크가
 *  없어서 깨질 곳이 없다. */
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

/**
 * 뷰어 본인의 축 벡터 — 겹침 계산과 오버레이 그래프에 쓰인다.
 *
 * 시드 유저들과의 관계를 보고 고른 값이다. 임의로 두면 "보완과 일치를 동시에
 * 갖춘 사람"이 하나도 없어, 일치만 만점인 복제형이 추천 1위가 된다(w=0.4 라
 * 일치가 무겁기 때문). 그러면 데모가 "보완되는 사람을 추천한다"는 기능 자체를
 * 보여주지 못한다.
 *
 * 이 값에서는 @dohyun 이 1·2축 반대 + 3·4축 일치로 뚜렷한 1위가 된다.
 */
export const MOCK_MY_VECTOR = [-0.6, -0.7, -0.4, 0.3, 0.1]

export function competitionById(id) {
  return MOCK_COMPETITIONS.find(c => c.id === id) || null
}

/** 마감까지 남은 일수 — 렌더 시점에 계산해 D-day 가 항상 살아 있게. */
export function daysLeft(competition) {
  const ms = daysFromNow(competition.deadlineIn) - new Date()
  return Math.max(0, Math.ceil(ms / 86400000))
}
