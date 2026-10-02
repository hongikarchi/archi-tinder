# 관심 있어요 → 연결 → 앱 내 메시지 설계

**작성** 2026-10-02 · **상태** 설계 확정, 구현 미착수 · **선행** `2026-08-20-personality-discovery-design.md` §8 (컨택 플로우 B안), §9 (차단/신고 MVP 최소)

---

## 1. 문제

사람 발견(`/people`) 기능의 종착점인 다른 유저 프로필의 **"관심 있어요"** 버튼이
`onClick={() => {}}`로 비어 있다 (`UserProfilePage.jsx`). 발견 → 프로필 → 연결로 이어져야 할
P2(Person→Person, 최우선 페르소나) 흐름이 여기서 끊긴다. 2026-10-02 미결사항 점검에서
체감 완성도에 가장 큰 영향을 주는 항목으로 꼽혔다.

§8은 "관심 표현 → 수락 → DM 개방"을 확정했지만 채팅 인프라·스레드 구조·UI 위치가 미결이었다.
이 문서가 그 미결을 닫는다.

## 2. 확정된 결정

| # | 결정 | 근거 |
|---|---|---|
| D1 | 수락 후 연결 = **앱 내 1:1 메시지** (연락처 공개 단계 없이 처음부터) | 대화가 앱 안에서 이어져야 완성도가 오른다 |
| D2 | 실시간 = **폴링**, WebSocket 아님 | 신규 인프라(Channels) 없이 Django + Postgres + Redis 캐시로 충분. 원칙 5 (외부 의존 절제). 데이터 구조는 WebSocket 전환 시 그대로 재사용 |
| D3 | 요청 시 **선택적 인사말** (최대 100자). 수락되면 대화방 첫 메시지가 됨 | 수락 판단 근거 제공 + 보내는 부담 최소 |
| D4 | 메시지 버튼은 **내 프로필(`/user/me`)에만**, 콘텐츠 영역 우측 상단 | 탭바 옆 플로팅 안(A안)은 375px 폭 공간 부족·토스트/입력창 충돌로 취소 |
| D5 | 메시지 버튼은 헤더 아이콘보다 크게 (≥44px 알약: 💬 + "메시지" + 배지) | DEPLOY-BLOCKER-1 ④ (헤더 버튼 28px) 반복 금지 |
| D6 | 다른 화면에서도 알 수 있게 **탭바 프로필 아이콘에 안 읽음 점** | 버튼이 프로필에만 있으므로 |
| D7 | 메시지함·대화 모두 **바텀시트 안에서** 진행 (페이지 이동 없음) | Discovery 이탈 경고 모달(`discoveryNavigationGuard`)과 충돌 회피 |
| D8 | 실시간 말풍선 없음. **NOTIF-INAPP-1 정책 유지** — 진입/탭 복귀/라우트 이동 시에만 카운트 갱신. **대화방이 열려 있을 때만** 3~5초 폴링 | 백그라운드 폴링 금지 정책(§3)과 충돌 회피 |
| D9 | 요청·메시지는 **알림 화면에서 완전히 제외**, 메시지함에만 존재. `Notification` row 생성 안 함 | 배지 중복 카운트 원천 차단 |
| D10 | 무시된 요청: **30일간 재요청 불가**. 보낸 사람에게는 계속 **"보냄"**으로만 표시 (무시 사실 비공개) | 거절 통보로 인한 부담 제거 + 반복 요청 방지 |
| D11 | 요청 수신 가능 대상 = **성향 진단 완료(`PersonalityProfile` 존재) AND `discovery_opt_in = true`** | 발견 피드 노출에 동의한 사람만 연락 받음 |

## 3. 사용자 흐름

1. A가 B의 프로필에서 **"관심 있어요"** → 작은 시트에 인사말(선택) 입력 → 보내기 → 버튼이 "보냄" 상태로 바뀜
2. B는 내 프로필의 **메시지 버튼 배지** 또는 **탭바 프로필 점**으로 인지 → 메시지함 시트 상단의 **받은 요청 카드**에서 수락/무시
3. 수락 → 대화방 생성, 인사말이 첫 메시지. A의 메시지함에도 대화방이 나타남 (별도 알림 없음, D9)
4. 무시 → B의 목록에서 사라짐. A에게는 "보냄" 유지, 30일 뒤 재요청 가능 (D10)
5. 대화방: 시트 안에서 말풍선 UI, 열려 있는 동안 3~5초마다 증분 조회. 뒤로 → 목록
6. ⋯ 메뉴(대화 화면, 다른 유저 프로필): 차단 / 신고

## 4. 백엔드 (PR 1)

### 모델 (`apps.social` 또는 신규 `apps.messaging` — 구현 단계에서 기존 앱 구조에 맞춰 결정)

- **`ContactRequest`** — `sender`, `recipient` (FK `accounts.UserProfile`), `greeting` (≤100, blank), `status` (`pending` / `accepted` / `ignored`), `created_at`, `responded_at`
  - 같은 (sender, recipient) 쌍에 `pending`은 하나만 (partial unique constraint)
  - 재요청 가드: 같은 쌍의 최근 `ignored`가 30일 이내면 거부 (D10). 응답은 일반 성공과 구분되지 않게 — 보낸 사람 UI는 "보냄" 유지
  - 역방향 요청이 이미 pending이면: 새 요청 대신 **기존 요청을 수락 처리**하고 대화방 개설 (서로 관심 = 연결)
- **`Conversation`** — 두 참여자 (`user_a`, `user_b`, 정규화: `user_a_id < user_b_id`, unique), `last_message_at` (db_index), 참여자별 `a_last_read_at` / `b_last_read_at`, `closed_at` (차단 시)
- **`Message`** — `conversation` FK, `sender` FK, `body` (≤1000), `created_at`. 인덱스 `(conversation, id)`
- **`Block`** — `blocker`, `blocked`, unique 쌍
- **`Report`** — `reporter`, `target_type` (`user` / `message` / `profile`), `target_id`, `reason`, `created_at`. 처리 UI는 범위 밖 (관리자 조회만)

### API (모두 trailing slash, 인증 필수)

| 메서드 | 경로 | 동작 |
|---|---|---|
| POST | `contact-requests/` | `{recipient_id, greeting?}` 요청 보내기. 가드: 자기 자신 ✗, 차단 관계 ✗, D11 미충족 ✗, 30일 쿨다운(조용히 성공처럼) |
| GET | `contact-requests/received/` | 받은 pending 목록 (보낸 사람 요약 + 인사말) |
| GET | `contact-requests/status/?user_id=` | 다른 유저 프로필의 버튼 상태 (`none` / `sent` / `connected`) — ignored도 `sent`로 반환 |
| POST | `contact-requests/<id>/accept/` | 수락 → Conversation 생성 + 인사말을 첫 Message로 |
| POST | `contact-requests/<id>/ignore/` | 무시 |
| GET | `conversations/` | 목록 (상대 요약, 마지막 메시지, 안 읽은 수), `last_message_at` 내림차순 |
| GET | `conversations/<id>/messages/?after=<msg_id>` | 증분 조회 (폴링용, 응답 가볍게) |
| POST | `conversations/<id>/messages/` | 보내기. 참여자 아님 / closed / 차단 → 거부 |
| POST | `conversations/<id>/read/` | 내 `last_read_at` 갱신 |
| GET | `messages/unread-count/` | `pending 받은 요청 수 + 안 읽은 메시지 수` 단일 숫자 — 버튼 배지와 탭바 점 공용 |
| POST / DELETE | `users/<id>/block/` | 차단 / 해제 |
| POST | `reports/` | 신고 |

### 규칙

- 참여자가 아닌 대화방은 404 (존재 여부 비노출)
- 차단: 양방향 요청·메시지 차단, 대화방 `closed_at` 설정, **발견 피드에서 서로 미노출** (people feed 쿼리에 Block 제외 조건 추가)
- 보내는 사람 조건: 로그인 + 비게스트. (보내는 쪽 진단 여부는 강제하지 않음 — 필요해지면 추가)
- 수신자가 나중에 opt-out해도 기존 대화방은 유지, 신규 요청만 차단
- 스로틀 (code-pinned rate): `contact_request` 20/day 수준, `message_send` 30/min 수준 — 구현 시 기존 `DEFAULT_THROTTLE_RATES` 컨벤션 따름
- `unread-count`는 진입마다 호출되므로 인덱스 기반 COUNT로 가볍게

### 테스트

권한(비참여자 접근 404), 상태 전이(pending→accepted/ignored), 30일 쿨다운 + "보냄" 비노출, 역방향 상호 요청 자동 수락, D11 가드, 차단 시 요청/메시지/피드 차단, 증분 조회 `after`, unread-count 정확성, 스로틀.

## 5. 프론트엔드 (PR 2, `DESIGN.md` 준수)

1. **다른 유저 프로필 "관심 있어요"** — 기존 빈 `onClick` 교체. 상태 `none` → 인사말 시트, `sent` → 비활성 "보냄", `connected` → "메시지 보내기"(메시지함 시트의 해당 대화로). 수신 불가(D11 미충족) 유저에게는 버튼 숨김. 하드코딩 한국어(`실선 = 나…`, `다시 진단받기` 등 인접 문구 포함) i18n 키로 이동
2. **내 프로필 메시지 버튼** — 콘텐츠 컨테이너(max-width 1100) 우측 상단, ≥44px 알약, 숫자 배지. 상단 고정 컨트롤(`PageTopControls`, top-left 클러스터)과 겹치지 않게 콘텐츠 흐름 안에 배치
3. **탭바 프로필 점** — 앱 공용 `useUnreadMessages` hook (NOTIF-INAPP-1과 같은 계약: mount + `visibilitychange` + 라우트 변경 시 갱신, `setInterval` 없음). `TabBar`의 profile 아이콘에 점
4. **메시지함 시트** — 기존 `Modal` sheet 모드 재사용. 상단 받은 요청 카드(인사말 + 수락/무시), 아래 대화방 목록. 빈 상태·로딩·에러 상태 포함
5. **대화 화면 (시트 내부)** — 말풍선, 하단 입력창. 열려 있는 동안만 3~5초 `after=` 폴링, 시트 닫힘/탭 숨김 시 중지. 진입 시 read 호출. 모바일 키보드: `visualViewport` 기준으로 시트 높이 조정 (body는 viewport-lock)
6. **⋯ 메뉴** — 차단 / 신고 (대화 화면, 다른 유저 프로필)
7. **i18n** — 신규 문구 전부 ko/en 키

## 6. 범위 밖 (YAGNI)

- 실시간 말풍선/토스트, WebSocket
- 이메일·푸시 알림 (NOTIF-CHANNELS-1, 신규 외부 의존 승인 필요)
- 이미지·파일 첨부, 메시지 수정/삭제, 그룹 대화
- 신고 처리 관리자 UI (DB 조회로 대응)
- 공모전 팀 초대와의 연동 (DEPLOY-BLOCKER-1에서 별도 처리)

## 7. 연관 항목

- **FULL-LEGAL-1**: 개인정보처리방침에 메시지 보관·신고 데이터 처리 명시 필요 (이 기능 출시 전후로 함께)
- **DEPLOY-BLOCKER-1 ④**: D5로 반복 방지
- **NOTIF-INAPP-1 §3**: D8로 정책 유지

## 8. 검증과 배포

- `app-test` FEATURE-SCOPED: 계정 2개로 요청 → 수락 → 대화 → 무시(쿨다운) → 차단 체크리스트
- 마이그레이션 포함 → 배포 후 `make migrate-prod` 필수
- 브랜치 `feature/sns-contact-messaging`, PR 1(백엔드) → PR 2(프론트) 순서
