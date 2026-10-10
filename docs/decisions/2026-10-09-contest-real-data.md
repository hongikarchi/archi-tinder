# 공모전 — 목 데이터에서 실제 공모전으로

**작성** 2026-10-09 · **상태** accepted (Phase 1 구현 예정 — #414 #415 #416 #417, Phase 2 설계만 — #418) · **선행** `2026-09-17-competition-team-design.md` (찜 기반 팀빌딩 프로토타입, PR #333) · **관련** #363 DEPLOY-BLOCKER-1 ①②

---

## 1. 배경

공모전 화면(`/competitions`)은 프론트에 박아 둔 목 데이터(`constants/mockCompetitions.js`)다.
실제 기관명이 붙은 가짜 공모전, 가짜 관심 수, 존재하지 않는 유저(@dohyun 등)가 모든 사용자에게 보인다(#363).
백엔드 모델·API는 없고, 관심 등록은 계정 구분 없는 localStorage다. 공고 링크와 포스터도 없다.

이 문서는 화면을 **실제 공모전 데이터**로 바꾸는 결정을 기록한다. 선행 문서 §6-1의 `Competition`
(운영자 등록, 필드 9개)은 이 문서의 `Contest`로 대체된다. §6-3 `Team` / §6-4 `TeamInvite`는 범위 밖(미구현 유지).

## 2. 검토한 운영 방식

| 안 | 내용 | 판단 |
|---|---|---|
| A. 운영자 등록 + 입력 보조 | 관리자 화면에서 공고 URL을 붙여 넣고 사람이 확인 | **기각** (사용자 결정) — 관리자 페이지를 만들지 않고, 사람이 매번 검수하는 구조를 피한다 |
| B. 공공 API(나라장터) 자동 수집 | 설계공모 입찰공고 API | 보류 — 포스터 없음, 소규모 지역 공고 위주(연 700~800건 추정), "포스터 보고 → 관심 유저 구경" 흐름과 맞지 않음 |
| **C′. 모음 사이트 후보 수집 + 공식 페이지 LLM 추출 + 자동 검증** | 위비티 목록에서 후보만 모으고, 값은 주최처 공식 페이지에서 읽어 교차검증. 검증 실패는 노출하지 않음 | **채택** (Phase 2). 단 약관 확인이 선행 게이트(§6-0) |

조사(2026-10-09): 건축HUB 설계공모는 API·RSS 없음. 위비티·씽굿·링커리어는 공식 API 미확인, `robots.txt`는 `*` 허용이나 **이용약관은 미확인**.
판례 참고(요약 수준): 공개 데이터 접근 자체는 침입 아님(대법원 2021도1533), 경쟁 서비스의 DB를 통째로 긁어 재게시하는 패턴은 위법 인정(잡코리아 대 사람인). 포스터는 주최 측 저작물.

## 3. 확정된 결정

| # | 결정 | 근거 |
|---|---|---|
| D1 | **범위**: 건축 + 도시·공간·경관·조경·인테리어·건설(공공디자인 포함). `AGENTS.md` Product Constitution의 "건축 외 업종" 경계에 대해 **사용자가 2026-10-09 이 범위를 명시 승인** | 실내건축대전·도로경관디자인 대전 등 포함. 로고·패키지·영상 등은 제외 |
| D2 | Phase 2 수집은 카테고리를 통째로 받지 않고 **키워드(건축, 도시, 공간, 경관, 조경, 인테리어, 건설) 통과분만** | D1 |
| D3 | **관리자 페이지 없음.** 사람 손이 필요한 지점(pending 해제, 포스터 allowed 전환, 포스터 복구)은 **관리 커맨드** | 저장소 선례(`seed_discovery`, `sync_offices`) |
| D4 | **포스터는 hotlink만.** 서버·R2에 저장/재호스팅 금지. `poster_status = allowed`일 때만 노출, 그 외·로딩 실패는 폴백 카드 | 저작권 위험 최소화 |
| D5 | **포스터 신고 접수 즉시 자동 숨김**(`poster_status → none`). 복구는 커맨드로만 | 숨겨도 폴백 카드일 뿐이라 손해가 작고, 내려달라는 포스터를 며칠 보여주는 쪽이 훨씬 위험 |
| D6 | 포스터 `allowed` 전환은 자동 금지. 공공누리 표시 확인 또는 주최처 서면 허락이 있을 때만, 근거를 남김 | D4 |
| D7 | **마감일을 못 읽으면 임의 값으로 채우지 않는다.** 교차검증 실패 → `hidden` | 틀린 마감일은 사용자 피해 |
| D8 | 주최처 유형이 협회/지자체/공공기관이면 자동 `published`, 임의단체·미확인은 `pending`(사람이 풀기 전 비노출) | 신뢰도 |
| D9 | **D-day 기준 = 남은 마감 중 가장 가까운 것**(신청 마감이 미래면 신청 마감, 아니면 제출 마감) + 어떤 마감인지 라벨. 목록 제외 기준은 `submission_deadline` 경과 | 신청을 놓치면 제출도 못 하는 공모전이 많음 |
| D10 | 상세 화면의 **가짜 유저 제거.** 추천 섹션은 그 공모전에 실제 관심 등록한 사람(본인 제외), 0명이면 섹션 숨김. "모집 중인 팀"은 팀 모델이 생길 때까지 숨김 | 존재하지 않는 유저를 보여주는 것은 사용자를 속이는 것 |
| D11 | 화면 색상은 `DESIGN.md` 테마 토큰에 대응. 포스터 확대 오버레이의 어두운 배경만 고정값 | 다크·타 테마에서 깨지지 않게 |
| D12 | 배치 실행 = **Railway cron** (Phase 2). 수집기는 1회 실행 후 종료하는 관리 커맨드 | DB·LLM 키가 이미 Railway에 있음. UTC, 최소 5분 간격, 이전 실행 중이면 skip (Railway docs). 플랜별 가용 여부는 미확인 — Phase 2 착수 시 확인 |
| D13 | 이름: 모델·API는 `Contest` / `contests/`, 화면 경로는 `/competitions` 유지 | 기존 링크 보존 |

## 4. Phase 1 — 모델 + API + 화면

### 4-1. 모델 (새 앱 `backend/apps/contests/`, `'default'` DB만)

**`Contest`**

| 필드 | 설명 |
|---|---|
| `title`, `organizer` | |
| `organizer_type` | `public_agency` / `association` / `local_gov` / `private_group` / `unknown` |
| `submission_deadline` | 필수, aware datetime(KST 입력), `db_index`. 최종 작품 제출 마감 |
| `apply_deadline` | nullable. 참가신청 마감이 제출 마감과 다를 때만 |
| `notice_date` | nullable date. 없어도 화면이 깨지지 않아야 함 |
| `theme`, `summary`(≤300), `eligibility`, `team_size`(nullable 문자열) | |
| `source_url` | 공식 공고 원문 |
| `listing_source`, `listing_url` | 예: `'wevity'` |
| `poster_url`(nullable), `poster_credit`, `poster_status` | `allowed` / `unverified`(기본) / `none` |
| `status` | `published` / `hidden` / `pending` |
| `interest_count` | `Reaction`과 같은 signal 기반 denormalize |
| `created_at`, `updated_at`, `last_verified_at` | |

**`ContestInterest`** — `social.Reaction`과 동형(user FK + contest FK, 쌍 unique, `created_at` index).

**`ContestPosterReport`** — contest FK, `reporter_email`(선택), `reason`, `created_at`.

마이그레이션은 신규 테이블 추가만. 기존 데이터 삭제·변경 없음.

### 4-2. API (`/api/v1/`)

| 경로 | 동작 |
|---|---|
| `GET contests/` | `status=published` AND `submission_deadline` 미경과, 마감 임박순 |
| `GET contests/<id>/` | 상세. 마감이 지나도 열림. `hidden`/`pending`은 404 |
| `POST` / `DELETE contests/<id>/interest/` | 관심 등록·해제(인증, 스로틀) |
| `POST contests/<id>/poster-report/` | 접수 + 즉시 `poster_status = none` (D5), 스로틀 |
| `GET contests/<id>/interested/` | (PR 4) 진단 완료 + `discovery_opt_in` 관심 등록자, 본인·차단 관계 제외, 성향 벡터 포함 |

### 4-3. 관리 커맨드

- `seed_contests` — 개발용 시드(§4-5). `DEBUG`에서만 실행.
- `contest_status <id> published|hidden|pending`
- `contest_poster <id> allow --basis "<공공누리 유형/메일 날짜>"` · `contest_poster <id> restore|none`

운영용 "검증된 JSON 임포트" 커맨드는 Phase 1 종료 시점에 다시 논의한다(사용자 결정 2026-10-10).

### 4-4. 상세 화면 (시안 B)

위에서 아래: ① 상단바(기존 `PageTopControls` + `PageBackButton` + `PageLogoHeader`) ② D-n 배지(D9, 마감 종류 라벨) · 제목 · "주최처 · 권장 인원"
③ 카드(왼쪽 포스터 썸네일 112×158 + "포스터 © {poster_credit}", 오른쪽 주제 · 제출 마감 · `apply_deadline`이 미래면 "신청 마감" 행 · `notice_date`가 있을 때만 "공고일" · summary 4줄 말줄임)
④ 출처 줄 + "원문 보기 ↗"(≥44px) ⑤ 관심 등록 버튼 + "N명이 이 공모전을 보고 있어요" ⑥ 추천 섹션(PR 4, D10).

포스터 썸네일은 `<button>` → 확대 오버레이(같은 원본 URL, 별도 저장 없음; X·바깥 클릭·Esc로 닫힘, 포커스 이동, aria-label; "포스터 © 주최처" + "원문 보기" 노출).
`poster_status != allowed` 또는 이미지 로딩 실패 → 폴백 카드("제출 마감" 칩, 주제, summary; 출처 줄 "포스터 없음 · 출처 …"). 색은 D11.

### 4-5. 개발용 시드 7건

**실서비스 전 전부 재검증 필요.** 2026-10-09 조사에서 공식 사이트 직접 확인은 대부분 실패(ggkia.or.kr 인증서 오류/IP 차단, kosid.or.kr 403) — 정림(junglimaward.com) 외에는 모음 사이트·기사 기준이다. 포스터 URL·공공누리는 7건 모두 미확인 → 전부 `poster_status = unverified`.

| 공모전 | status | 제출 마감 (KST) | 신청 마감 | 비고 |
|---|---|---|---|---|
| 대한건축사협회 모듈러건축 공모 | published | 2026-12-02 15:00 | 2026-10-19 15:00 | 신청 마감은 이전 조사값, 재확인 필요 |
| 제14회 한옥디자인 국제공모 | published | 2026-12-28 18:00 | — | |
| 제38회 대한민국 실내건축대전 | published | 2026-10-14 17:00 | — | 신청+1차 작품 접수 마감. 2차 접수 11/11은 summary |
| 제15회 도로경관디자인 대전 | published | 2026-10-29 18:00 | — | 18시는 이전 조사값, 재확인 필요. 누구나 |
| 제62회 경기건축대전 | published | 2026-10-28 18:00 | — | 1차 = 온라인 작품 제출. 입선 발표 11/2, 2차(패널·모형) 11/21은 summary. 주최 "한국건축가협회 경기지회"(모음 사이트 기준) |
| 정림학생건축상 2027 | published | 2027-01-11 23:59 | 2027-01-04 23:59 | 날짜는 공식 사이트 확인, **시각 미확인**(23:59는 자리표시) |
| 에어-비트 시티 건축디자인 | pending | 2026-11-19 23:59 | — | 주최가 임의단체. 11/20은 위비티 D-n 환산값이라 오차 가능 → 출처 있는 11/19 사용. 시각 미확인 |

## 5. PR 분할 (Phase 1)

| PR | 내용 |
|---|---|
| 0 | 이 문서 + 이슈 등록 |
| 1 | 백엔드: `Contest` + 마이그레이션, 목록·상세 API, `seed_contests`, 테스트 |
| 2 | 백엔드: `ContestInterest` · `ContestPosterReport`, 관심·포스터 신고 API, 스로틀, 관리 커맨드, 테스트 |
| 3 | 프론트: `api/contests.js`, 목록·상세 화면(시안 B), 포스터 확대, 폴백, D-day 유틸, i18n, 목 데이터·localStorage 관심 제거. 추천·팀 섹션 숨김 |
| 4 | 관심 등록자 API + 추천 섹션 재개(`utils/teamFit.js` 재사용) |

## 6. Phase 2 — 수집기 (설계만, Phase 1 머지 후 별도 진행)

0. **게이트**: 위비티 이용약관과 `robots.txt`를 읽고 결과를 사용자에게 보고. 허용 범위가 불분명하면 구현하지 않고 멈춘다.
1. 후보 수집: 위비티 목록 건축/건설/인테리어(cidx=24), 디자인(cidx=19), 기획/아이디어(cidx=1) → D2 키워드 통과분만. 요청 간격, User-Agent 명시.
2. 위비티의 "D-n"은 캐시/오프셋으로 하루씩 틀어질 수 있다 → 날짜 환산 시 **수집 시각(기준일)을 함께 저장**, 공식 페이지 날짜와 하루 이상 어긋나면 공식 페이지 우선.
3. 주최처 공식 페이지를 따라가 LLM(`recommendation/services/_gemini.py` 재사용)으로 제출 마감·신청 마감·주제·참가 자격·요약을 구조화 추출. 스키마 검증(신규 의존성 없이 수기 검증기) + **원문 근거 문장 저장**.
4. 교차검증: 공식 페이지에서 제출 마감을 못 읽었거나 위비티 값과 충돌 → `hidden` (D7).
5. 주최처 필터 (D8).
6. 포스터 기본 `unverified`; 허락 근거 필드(공공누리 유형 / 메일 날짜)를 `Contest`에 nullable 추가 (D6).
7. 하루 1~2회 Railway cron (D12). 실패해도 기존 `published` 유지.
8. 수집 로그 테이블(실행 단위 + 후보 단위: 성공/실패/hidden 사유, 원본 D-n, 수집 시각, 근거 문장).

## 7. 하지 않는 것

포스터·위비티 이미지 다운로드/재호스팅 · 마감일 임의 채우기 · 관리자 페이지 · Make-DB(`canonical_v2_buildings`) 쓰기 · 팀/초대 모델.

## 8. 미결

- Railway 플랜의 cron 가용 여부·최대 실행 시간 (Phase 2 착수 시)
- 위비티 약관 (Phase 2 게이트)
- 운영용 검증된 JSON 임포트 커맨드 (Phase 1 종료 시 논의)
- 시드 7건의 공식 페이지 재검증, 포스터 허락
