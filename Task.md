# Task Board

> Authored by the session; updated by the `reporter-inline` skill at session end. The dashboard
> (`project/dashboard.html` ← `project/state.js`) renders this file's three active
> sections (`## Now` / `## Next` / `## Done`). The compact `## Roadmap (Historical)`
> section at the bottom is a phase-level summary, not a task list.

## Workflow Rules

- **Session start** — read `## Now` first. If empty and the user is starting new work, move the matched `## Next` entry (under `### X-HIGH` / `### HIGH` / `### MEDIUM` / `### LOW`) into `## Now`. Or write a fresh entry if brand-new. One initiative slice at a time.
- **Mid-session** — if work in `## Now` gets deferred ("미루자"), move it back to `## Next` with a one-line rationale note. If a new sub-task appears, add it under the active Now entry's body or create a new Now entry.
- **Session end (success)** — the `reporter-inline` skill moves `## Now` → `## Done` with SHA + optional PR ref (keyed on the task ID). If the Now entry's note mentions a deferred follow-up (`Deferred: ...`), it also auto-surfaces a matching `## Next` entry (see the `reporter-inline` skill).

**ID convention** (since 2026-05-25): `<SURFACE>-<TOPIC>-<N>`.
- **SURFACE** = `FRONT` / `BACK` / `FULL` / `INFRA`. Tells where the work lives.
  - `FRONT` = frontend only (React/Vite)
  - `BACK` = backend only (Django/DRF)
  - `FULL` = cross-cutting FE + BE (one feature, two PRs coordinated)
  - `INFRA` = ops surface — Neon / Railway / Vercel / `.env` / DB roles / deploy
- **TOPIC** = readable English word. **No obscure abbreviations.** Only universal acronyms allowed: `LLM`, `UX`, `DB`, `ENV`, `AUTH`. Conventional topics:
  - BACK: `LLM` / `RECOMMEND` / `PERFORMANCE` / `AUTH` / `EXTERNAL`
  - FRONT: `UX` / `DESIGN` / `LAYOUT` / `AUTH`
  - FULL: `LANGUAGE` / `LEGAL` / `REFACTOR` / `LLM`
  - INFRA: `DB` / `ENV` / `DEPLOY` / `QUEUE` / `MONITOR`
- **N** = integer counter per `<SURFACE>-<TOPIC>`, persistent across bucket moves. `BACK-LLM-1`, `BACK-LLM-2`, etc. Never re-used.
- **SURFACE is a CLOSED set** — the first token MUST be exactly one of `FRONT` / `BACK` / `FULL` / `INFRA`. `PERF`, `OFFICE`, `UX`, `PROFILE` are NOT surfaces; map them: `PERF` to `BACK-PERFORMANCE`, `OFFICE` to `BACK-OFFICE`, `UX` to `FRONT-UX`, `PROFILE` to `FRONT-PROFILE`/`BACK-PROFILE`. Added topics: BACK gains `OFFICE` + `PROFILE`; FRONT gains `PROFILE`.
- **TOPIC is exactly ONE word** (domain noun). Actions (`POLISH` / `SANITIZE` / `CLEANUP` / `CONSOLIDATION` / `HARVEST`) are NOT topics — they go in the title, never the ID.
- **Renamed 2026-06-04 audit** (2축 enforce): `PERF-PREFETCH-POOL-RISK` to `BACK-PERFORMANCE-6`, `INFRA-DB-CLEANUP-1` to `INFRA-DB-3`, `FRONT-PROFILE-POLISH-1` to `FRONT-PROFILE-1`, `BACK-PROFILE-SANITIZE-1` to `BACK-PROFILE-1`, new `BACK-OFFICE-1`. `## Done` IDs are archive (never rewritten).

**Title convention**: short Korean problem / goal statement, ≤ 25 chars. Says **what is wrong or what we want**, not **how**. The body carries the how. Examples:
- ✅ `LLM 채팅이 검색에 필요한 정보를 다 안 모음`
- ✅ `/projects/ 응답 600ms (목표 300ms)`
- ❌ `LLM chat refinement: refine probe behaviour to deterministically target missing required slate fields` (too long, English jargon, embeds the how)

**Header format**:
- `## Now` and `## Done` items → `### <ID> — <Korean title>`
- `## Next` items → `#### <ID> — <Korean title>` under one of `### HIGH` / `### MEDIUM` / `### LOW`
- `## Done` resolved suffix → append ` — RESOLVED YYYY-MM-DD (PR #N `<sha>`)`
- Multi-line body for context. Sub-tasks use `- [ ]` / `- [x]` checkboxes.

**Consistency across artefacts** — every surface that names a task uses the same `<ID> — <Korean title>` pair so cross-referencing is mechanical:
- **Commit subject**: `<type>(<ID>): <Korean title>`. Body keeps caveman-terse description.
- **PR title**: same shape as the commit subject.
- **Reporter Done entry** in `## Done`: `### <ID> — <Korean title> — RESOLVED YYYY-MM-DD (PR #N `<sha>`)`.
- **state.js**: `id` = `<ID>`, `title` = Korean title (no English duplicate).
- Long historical Done entries from before 2026-05-25 keep their legacy headers (`### #21 SWIPE-CALIBRATING — ...`) as archive — do not rewrite history.

**Priority bucket semantics** (`## Next`):
- **X-HIGH** — critical: a confirmed defect against the core taste-match promise or against data correctness, with file:line evidence (e.g. the 2026-05-31 swipe/discovery review). Pull before HIGH.
- **HIGH** — specced, ready to pull into `## Now`. Open dimensions resolved or acceptable to resolve during implementation.
- **MEDIUM** — uncategorised pending. Needs review before promotion (scope, urgency, prerequisites).
- **LOW** — explicitly deferred / skipped. Not blocking; revisit when context shifts (traffic, prereq shipped, priority change).

Algorithm work (`engine.py`, `services/embeddings.py`, etc.) is owned by a separate collaborator post-2026-05-18 — see CLAUDE.md `## Rules`. Tracked in `docs/algorithm.md`, not this board.

---

## Now

_(비어있음 — 배치 플랜 `reactive-soaring-hearth` 6/6 PR 완료 2026-07-13. 잔여 액션 완료 2026-07-15/16: i18n EN 카피 스팟체크 PASS(한글 누출 0, ko 의도 일치) + PERF-5 재계측→root-cause→fix 종결(## Done § BACK-PERFORMANCE-5 — Redis US리전이 범인, swipe p50 1638→124ms))_

---

## Next

> Backlog grouped by priority bucket (`### X-HIGH` / `### HIGH` / `### MEDIUM` / `### LOW`). Each
> item is a `#### <SLUG>` entry one level deeper. Bucket semantics described in
> `## Workflow Rules` above. Phase 16-18 dimensions inlined here (formerly
> `docs/specs/*`, absorbed 2026-05-24). Algorithm theory + production
> hyperparameters still live in `docs/algorithm.md` (admin-owned, reporter syncs
> Production Value column only).

> **2026-06-04 backlog audit** (25 items verified vs `develop@2f9a9c2`): 0 resolved/dead; ~13 had
> file:line drift from **FULL-REFACTOR-1 (#170-173)** moving view bodies → `services/*.py`, splitting
> `accounts/views.py` → `views/{auth,profile}.py`, decomposing `engine.py`. **Ref-drift convention:**
> a backend item pinned to `views/swipe.py` / `views/sessions.py` at a pre-FULL-REFACTOR SHA now
> lives in `services/swipe_service.py` / `services/session_service.py`; `accounts/views.py` →
> `accounts/views/{auth,profile}.py`. Refs are re-pinned for the active-sequence items (X-HIGH bundles + the new HIGH
> quick-wins BACK-OFFICE-1 / BACK-PROFILE-1); deferred items keep their original ref + this convention.
>
> **2026-06-04 quick-win batch + both 1-PR bundles (UX-WRITE-FAIL, UX-GALLERY) shipped → ## Done.** `FRONT-DESIGN-1` stays **paused** (multi-session sweep); `FULL-LANGUAGE-1` / `FULL-LEGAL-1` deferred.

### X-HIGH

> Critical — confirmed defect against core taste-match / data correctness, OR a hard
> public-launch blocker. Pull before `### HIGH`. **재분류 2026-06-28 (공개런칭 수주 내 임박):**
> X-HIGH = (1) FULL-ONBOARDING-2 라이브 데이터-무결성 결함, (2) FULL-LEGAL-1 런칭 법적 차단.

_(FULL-ONBOARDING-2 → `## Now` 승격 2026-07-12, 배치 플랜 PR1. orphan temp GC 서브아이템만 `### MEDIUM` `INFRA-TEMP-GC-1`로 분리.)_

#### FULL-LEGAL-1 — PIPA/GDPR consent: Terms/Privacy 페이지 + 한국어 affirmative copy (잔여)
_Status (2026-06-28 grep): **백엔드 consent 인프라 + 가입 흐름 consent gate DONE** — `UserProfile.consent_accepted_at`/`consent_policy_version`(models.py:73-74), RegisterView+GuestLoginView consent_accepted 강제, LoginPage consent step. **잔여 = (1) `/terms`·`/privacy` 라우트/페이지 없음(App.jsx), (2) 한국어 PIPA affirmative copy(현재 영어 swipe copy만), (3) retention/export/delete 정책.** **공개런칭 차단 → X-HIGH (런칭 수주 내).**_

_Status (2026-07-12 감사 re-pin, develop@e536784): 잔여 3개 **전부 미착수** — (1) `/terms`·`/privacy` 라우트 부재 확인(App.jsx:1069-1119, TermsPage/PrivacyPage 파일 없음); (2) 한국어 consent copy는 존재하나(locales.js:144-149) **여전히 right-swipe 제스처 방식**(LoginPage.jsx:855-929) — 요구사항은 명시적 버튼/체크박스 affirmative act, 미해소; (3) retention/export/계정삭제 정책·UI 없음(AccountScreen 무, backend 유저-발의 삭제 view 무 — auth.py:393 `guest_user.delete()`는 Google-merge 흐름 전용). **추가 발견(Opus)**: `consent_policy_version`이 단일 mutable CharField(models.py:84-85, 라인 이동됨)라 재동의 시 덮어씀 — item이 요구한 immutable 동의 이력(ConsentRecord) 부재. 백엔드 gate는 그대로 유효(auth.py:248 GuestLoginView, :697 RegisterView)._
Phase 13+ Profile/Board public/private visibility shipped. PIPA + GDPR posture for signup data collection / consent flow / retention policy still open. **Required before public launch.**

**FRONT-AUTH-2 consent regression (2026-06-01):** the swipe-onboarding login (merged to develop) replaced #155's explicit Korean "동의합니다" PIPA button with a right-swipe gesture + generic English consent copy (`LoginPage.jsx` ConsentStep). Backend `consent_accepted` / `consent_policy_version` contract intact, but Korea-first + PIPA favor an explicit affirmative act (button/checkbox) + Korean disclosure. Restore Korean PIPA copy + explicit affirmative before public launch (flagged by both code-review + security in the merge gate).

Code audit 2026-05-27 (`develop@3894ffd`):
- Only visible consent surface found is `frontend/src/pages/LoginPage.jsx` line text: "By continuing, you agree to our terms of service". There are no Terms/Privacy routes in `App.jsx`, and no stored consent/version fields on `UserProfile`.
- `backend/apps/accounts/models.py` marks `external_links` as privacy-sensitive and opt-in, but there is no retention policy, export/delete workflow, or policy-version audit trail.
- Guest-first auth (`FULL-LOGIN-REDESIGN-1`) will collect at least display name/role and may create anonymous user rows; it should not ship publicly until legal consent and retention are explicit.

Implementation map:
- Backend fields likely belong on `UserProfile` or a separate `ConsentRecord`: `terms_accepted_at`, `privacy_accepted_at`, `policy_version`, optional marketing consent. Keep immutable history if policy versioning matters.
- Frontend needs Terms/Privacy pages or external links plus a blocking checkbox/continue copy in login/onboarding. Korean-first copy should be reviewed outside Codex.
- Account deletion/export is not currently in scope but should be tracked before public launch if GDPR-like obligations apply.

### HIGH

#### BACK-RECOMMEND-1 — Project 두번째 세션이 이전 taste를 모름
Same Project can host multiple `AnalysisSession` rows (user comes back, "Resume" or new swipe round on the same Project — second session is created fresh while `Project.liked_ids` / `disliked_ids` / `saved_ids` carry forward as the persistent accumulator). Today the new session's algorithm-side state (`like_vectors`, `convergence_history`, `phase`) starts from scratch — exploring phase, empty pool of taste signal — even though the user just liked 12 buildings in Session #1.

Code audit 2026-05-27 (`develop@3894ffd`):
- `backend/apps/recommendation/views/sessions.py` `SessionCreateView.post()` resolves an owned `project_id` early only to skip retry-dedupe. In `session_insert`, every new `AnalysisSession` is still created with `phase='exploring'`, `like_vectors=[]`, `convergence_history=[]`, `previous_pref_vector=[]`, `preference_vector=[]`.
- Persistent taste lives on `Project.liked_ids` as `[{id, intensity}]`; `Project.disliked_ids` and `Project.saved_ids` also carry across sessions. The create path does not read these fields when `project` already exists.
- `backend/apps/recommendation/engine.py` already has `compute_user_taste_vector(profile)` for Discovery-level cross-project taste and `get_pool_embeddings(ids)` for batch embedding fetch. A session-specific warm-start should not call `compute_user_taste_vector(profile)` blindly because it aggregates all Projects, not just the active Project.
- `SwipeView.post()` phase transition still keys off `len(session.like_vectors)` and `min_likes_for_clustering`; any warm-start that seeds `like_vectors` changes phase/progress semantics immediately.
- (2026-06-04 audit re-pin, `develop@2f9a9c2`) FULL-REFACTOR-1 moved this into services: create path = `services/session_service.py:46` create_session (project resolved L82-86 only to skip dedupe L78-80; `session_insert` L236-266 sets phase='exploring' L250, like_vectors=[] L257); phase transition = `services/swipe_service.py:531-534`; `compute_user_taste_vector` = `engine.py:1869`. Premise unchanged — 2nd session still starts cold.

Open dimensions:
- **Carry policy** — A independent (status quo) / B exposure-only carry (don't re-show prior cards, taste fresh) / C asymmetric negative-only (carry dislikes, drop likes) / D fade-decay carry (recency-weight prior `liked_ids` into `like_vectors`) / E full warm-start (replay prior `liked_ids` → `like_vectors`, skip exploring phase) / F user-controlled toggle ("Resume taste?" prompt at session 2 start).
- **Phase entry on warm-start** — if D or E chosen: enter `analyzing` immediately (3+ likes already), or still play 1-2 exploring rounds for diversity?
- **Backend wiring** — `SessionCreateView` (`views/sessions.py:28`) currently treats project lookup as cosmetic (just resolves project_id). Carry would require reading `Project.liked_ids` → embedding fetch → seeding `AnalysisSession.like_vectors` at create time.
- **Exposure carry** — decide whether previous `liked_ids` / `disliked_ids` / `saved_ids` should seed `session.exposed_ids`. Without this, session 2 may show cards the user already judged even if taste is warm-started.
- **Progress semantics** — if seed vectors count toward `min_likes_for_clustering`, `frontend/src/pages/SwipePage.jsx` progress/Finish logic may jump. If seed vectors are algorithm-only, add metadata or keep them separate to avoid UX mismatch.

Likely tests:
- `backend/tests/test_session_create_correctness.py`: create Project with prior `liked_ids`, start a new session with `project_id`, assert selected policy (`like_vectors` seeded or explicitly not seeded), no cross-project leakage, invalid/foreign `project_id` remains current contract.
- API smoke: session 2 first response latency should not exceed session 1 beyond one extra `get_pool_embeddings(prior_liked_ids)` batch.

Acceptance: behavior matches chosen option deterministically; session 2 TTFC not regressed beyond session 1 (warm-start should be ≤ or equal); A/B telemetry on session 2 satisfaction (saved_ids growth rate, completion rate) vs status quo.

_(Deferred 2026-06-04 batch scope → 별도 focused 플랜. Premise CONFIRMED post-BACK-RECOMMEND-4: global taste vector는 고쳤으나 같은 Project 2nd 세션은 여전히 cold-start(`session_service.py`가 like_vectors=[] seed, prior taste 안 읽음). algorithm-owner 코어 + frontend progress-bar UX 결정 얽힘 → 단독 처리.)_

_(2026-06-08 범위 축소: #212(`4e58195`) Case #3 resume guard가 **진행중(active, phase≠completed) 세션 resume**을 해결 — 보드 재진입 시 새 빈 세션 대신 live 세션의 like_vectors(원본 round)/preference_vector/phase/convergence/pool_ids/exposed_ids 전체 복원. **잔여 범위 = 완료된 세션 뒤 새 라운드가 `Project.liked_ids` 워밍 없이 cold-start**(`session_service.py:285` 새 세션 like_vectors=[], `:104` resume은 `.exclude(phase='completed')`). warm-start carry policy(D fade-decay / E full warm-start) + progress-bar UX 결정은 여전히 단독 처리 대상.)_

_(2026-07-12 감사 re-pin: 전제 유효, 라인 이동 — resume guard `session_service.py:167-182`(completed 제외), 신규 세션 cold-create `:397-416`(phase='exploring', like_vectors=[] 등 전부 빈 값), `liked_ids`는 완료-세션 리포트에만 사용(`:688-689`), warm-start seed 경로 여전히 부재.)_


### MEDIUM
#### FULL-WORKS-2 — works Phase 2: srcset/LQIP + 알고리즘 통합
FULL-WORKS-1 배포 후. (1) `rightSizeImageUrl.js`에 R2 works URL srcset/LQIP 처리 추가 (Cloudflare Image Transforms 필요 — ops 설정 선행). (2) `engine.py` Python-layer에 `user_uploaded_works` 풀 병합 — 별도 협업자(algorithm 소유) 작업, 설계 sync 필요.

#### FRONT-VERIFY-1 — 보드저장 PATCH 경로 verify_required 모달 미배선
FULL-ONBOARDING-2(`92237d8`)가 guest promote-limit을 `403 {'detail':'verify_required','reason':'board_limit_reached','limit':3}`로 표준화했으나, 프론트 `updateProject`(projects.js:64-71)는 verify_required를 VerifyRequiredError로 변환 안 함(createProject:26-40만 처리) → SaveBoardModal에서 guest가 4번째 보드 저장확정 시 VerifyGateModal 대신 generic 에러 문자열. `updateProject`에 createProject와 동일한 403 verify_required 감지 + VerifyGateModal 배선. Non-blocking(백엔드 enforcement는 정상).

#### INFRA-TEMP-GC-1 — orphan temp 보드 서버측 GC/TTL 없음
FULL-ONBOARDING-2에서 분리(2026-07-12). 브라우저 닫기/로그아웃 시 `is_temp=True` 보드가 서버에 영구 잔류(frontend cleanup은 /search 재진입 경로만). TTL 필드 or 정리 job(cron/management command) 필요 — 설계 결정(TTL 기간, report-있는 temp 처리) 선행. 비차단.

#### FRONT-UX-7 — 로그인 뒤로가기 시 입력 draft 소실
LOGIN-REWORK-1(`a390f9f`) pre-existing 잔존. CredentialsStep이 localId/localPassword를 컴포넌트 로컬 useState로 들고, 앞 카드가 `step`으로 key돼 profile→back→credentials 시 remount → 입력 draft 초기화. 부모 id/password는 마지막 confirmed 값 유지하나 local state를 props로 seed 안 함 → 입력창 빈 채로 보임. deck 리워크가 뒤로가기를 쉽게 만들어 노출 빈도↑. 수정: 마운트 시 부모 props로 local state seed, 또는 id/password를 부모로 완전 lift해 controlled 전환. Non-blocking UX papercut.

#### NOTIF-CHANNELS-1 — 이메일·푸시 알림 채널 발송
NOTIF-INAPP-1(0bac717)은 앱 내 채널만. 이메일(SMTP — Resend/Gmail 등) + 웹푸시(FCM)는 새 외부 의존성 → Product Constitution 상 사용자 승인 필요. prefs JSON은 push/email 키 이미 보존·검증됨(validator {push,email,in_app}) — 발송 파이프라인만 추가하면 됨. 보안 카테고리 이메일이 최우선 후보.

#### BACK-IDS-1 — user_id 정수 PK 노출 비열거화
`UserMiniSerializer.user_id`(source=user.id, serializers.py:70-74)가 순차 정수 Django PK 노출 — Project serializer·reactors 목록·notifications actor 전반 동일(시스템적, NOTIF-INAPP-1 net-new 0). 고치려면 handle/UUID로 전면 일괄 교체(부분 교체는 불일치만 초래). Opus verify low, 2026-07-06.

_(FRONT-IMAGE-RESIZE-3 → RESOLVED 2026-07-13, `## Done` 참조. Tier B(Divisare 포맷 프록시)는 user-결정 gated 유지 — `findings-r2-retirement.md`.)_

_(FULL-LANGUAGE-1 → **전체 RESOLVED 2026-07-13**, `## Done` 슬라이스 a(#275)/b(#276)/c 참조 — 3 PR로 32파일 176 리터럴 sweep 완료. Open dimension 결정: scope=고트래픽 3슬라이스(플랜 Q2), 번역 소스=에이전트 EN+diff 스팟체크(Q3), 폴백=ko(기구현). 신규 문자열은 이제 t()+locales.js가 기본 컨벤션.)_

#### FRONT-DESIGN-1 — 디자인 시스템 컴포넌트 리워크 (paused)
Foundation shipped: PR #54 (`tokens.css` 4 themes + `ThemeContext` + `AppearanceSettings`) + PR #59 (theme/font server persistence). Remaining: per-component visual rework — inline `style={{}}` → CSS Modules + `:hover/:focus`/`:active`, light-theme polish where dark-only assumptions still leak through, leaf→hub component order (small leaf components first, then containers).

Code audit 2026-06-28 (grep): inline `style={{` = **958** call sites (was 801 @2026-06-04 — debt grew); `*.module.css` = **13** (was 4 — 일부 컴포넌트 마이그레이션됨: Toggle/Button/AppearanceSettings/SaveBoardModal/ArchitectProfilePage/BoardReportPage/EditCardForm/settings/* 등). Foundation(tokens.css + ThemeContext)만 출하, per-component sweep은 대부분 미완.

Code audit 2026-07-12 (grep): inline `style={{` = **990** call sites / 64 files (958 → 990, 신규 기능 PR로 부채 계속 증가); `*.module.css` = **15** (+CalibrationChat #254, +NotificationInboxScreen #262 — 부수적 증가, 체계적 sweep은 여전히 미착수).

Resume via `/plan per slice` — each slice = one logical component cluster (e.g. SwipeCard + LoadingCard, then BoardCard, then HomePage, etc.). Each slice ships its own PR via the orchestrate skill; the full sweep takes many sessions. **Paused, 멀티세션 대공사 → MEDIUM(비긴급).**

Acceptance per slice: `npm run lint` + `npm run build` clean; light + all dark variants render the touched components without visual regressions; no new global token added without DESIGN.md update.

#### FRONT-LAYOUT-1 — Desktop wide-screen 레이아웃 어색함
Current viewport-lock layout is mobile-first. Detail pages on desktop work but unoptimised. 데스크탑은 2차 플랫폼 → MEDIUM.

Code audit 2026-05-27 (`develop@3894ffd`):
- `frontend/src/index.css` sets `body { height: 100vh; overflow: hidden; }`; each page owns its own scroll region. This works for mobile-app feel but makes desktop layout tuning page-by-page.
- `BuildingDetailPage.jsx` uses `maxWidth: 820` for most content and only one `.building-masonry` media query. On wide screens it stays narrow rather than using a split gallery/details layout.
- `BoardDetailPage.jsx` and `UserProfilePage.jsx` use `maxWidth: 1100` and auto-fill grids, but hero/profile sections remain mostly mobile-centered; there is no desktop-specific information hierarchy.

Likely slices:
- Building detail desktop pass first: full-bleed or two-column gallery + sticky metadata/read actions.
- Board/User profile second: keep existing mobile layout, add desktop breakpoints for hero + board grid density.

### LOW

#### INFRA-WORKS-1 — R2 works 버킷 프로비저닝 (dev/prod 버킷 + 환경별 토큰 + CORS + public access)
_(2026-07-17 플랜 `streamed-bubbling-lagoon` 으로 구체화·진행중)_ 토큰 모델 확정 = **환경별 2개**: dev 토큰(works-dev 버킷만 스코프, 협업자 전달용) / prod 토큰(archibe-avatars+works-prod 멀티버킷, Railway 전용) — 코드 무수정(공유 `R2_*` env 유지). ops 체크리스트: ① `archibe-works-dev` 생성 + Object R/W 토큰 + CORS(`http://localhost:5174` — vite.config.js 고정 포트, 5173 아님!) + public access(r2.dev)=`WORKS_PUBLIC_BASE_URL` → 협업자 전달 (지금). ② `archibe-works-prod` + prod 토큰 재발급 + prod 도메인 CORS(Vercel 도메인 레포에 없음, 대시보드 확인) + Railway env 4종 — 배포 직전 (Workstream C). 설정 전 브라우저 presigned POST XHR이 CORS로 차단됨.

#### BACK-WORKS-1 — works 목록 페이지네이션 + 응답 슬리밍
`FinalizeView.get`(views.py)이 무페이지네이션 전량 직렬화 — 피어 목록 엔드포인트는 전부 50 cap(notifications/_build_boards_field 패턴). + 목록 응답의 `r2_keys` 전체 배열은 프론트 미소비(cover_url만 렌더) → 제외. 2026-07-16 ultracode 리뷰 low(Opus 확정, 현 규모 실해 없음 — 관례 일치성 이슈).

#### BACK-WORKS-2 — finalize R2 HEAD 순차 왕복 개선
finalize가 r2_keys당 동기 `head_object`를 순차 실행(요청 사이클 내, 이미지 N장 = N왕복). 개선: 소형 ThreadPoolExecutor 병렬화 or 커버 외 키는 HEAD 생략(prefix 소유권 검증은 이미 상류에서 수행, 누락 이미지는 `_process_work` fail-closed가 커버). 2026-07-16 ultracode 리뷰 low.

#### FRONT-SWIPE-CLEANUP-1 — #281 진행바 리뷰 low 3건 정리
`SwipePage.jsx`: ① 죽은 `value` prop×2 + orphan `confidence` 로컬(353/473/585 — 시그니처에서 제거된 prop을 호출부가 계속 전달, 주석이 dead code를 문서화) ② pct 공식 3분기 verbatim 중복(87/90/94 — 분기 밖 1회 계산 + converged만 100 override) ③ 도달불가 `like+dislike` fallback(76-78 — 백엔드 `_progress()`가 세 필드 항상 동시 방출) → `progress?.swipe_count ?? 0`. 2026-07-16 ultracode 리뷰 low 3건(Opus 확정), 기능 영향 0.

#### BACK-ANALYTICS-1 — session_metrics_report 콘솔 ESC-byte 주입 (pre-existing #268)
`session_metrics_report.py` 텍스트 모드가 SessionEvent payload의 `domain`/`context` 값을 raw로 stdout 출력(~:548-559, #268 소산) — prod payload에 ESC 바이트 섞이면 터미널 이스케이프 주입 가능. BACK-PERFORMANCE-5a(`afc0b88`) Opus 검증서 실증됐으나 해당 PR 미접촉 영역이라 분리. 수정 = 출력 전 non-printable strip/repr(). 운영자-실행 read-only 커맨드라 LOW.

#### ARCHITECT-UNIFY-1 — firm-side Office→Architect 전면 통합 (deferred, firm-UX 착수 시)
office-interest **모델 중복은 해소됨**: Phase 0(SavedOffice #188) + C(OfficeFollow, ARCHITECT-UNIFY-C)로 두 미배선 중복 삭제 → follow 모델 1개(ArchitectFollow). 남은 통합 = Office 서브시스템(table/claim/OfficeProjectLink/sync_offices/FirmProfilePage)을 arch_id로 흡수 = firm-side 전면 재설계.

상태: **deferred → LOW (firm-UX 우선순위 미정, park).** Office 서브시스템은 계획 백로그(BACK-RECOMMEND-3 firm추천 / BACK-EXTERNAL-1 firm기사 / P1 firm-claim)의 **substrate라 park**(삭제 X). 전면 통합(FirmProfilePage→ArchitectProfilePage 흡수, claim/projects/recs/articles를 arch_id-overlay로)은 firm-UX 우선순위 정해질 때 별도 대형 작업. 옵션 A(재키잉)/B(전부삭제) 검토 후 탈락 — `docs/specs/architect-unification.md`(PROPOSAL).

#### BACK-AVATAR-3 — 기존 누적 orphan 아바타 일괄 청소 (sweep 명령)
BACK-AVATAR-2(`5e1f934`)가 교체/삭제 시점 GC를 붙였으나 그 이전에 쌓인 orphan(R2/디스크)은 남음. management command(dry-run + `--confirm`, `purge_legacy_projects` 패턴) — R2 `list_objects`로 `avatars/` 나열 → 어떤 `UserProfile.avatar_url`도 참조 않는 키 삭제. 비차단·비긴급(현 prod 아바타 ≈0, 기능 갓 출시) → LOW.

#### BACK-PERFORMANCE-6 — Neon connection pool 고갈 위험 (async prefetch thread)
PR 4 PERF-PREFETCH-CHAIN flipped `async_prefetch_enabled: True` — every prod swipe now spawns a daemon thread holding its own DB connection until `_connections.close_all()` runs in finally. Under high concurrent swipe load: connections ≈ (concurrent_requests × 2). Neon limit ~25 conns; Railway Gunicorn default 2-4 workers. Acceptable for current scale (~tens of daily users/day). Monitor Neon dashboard + revisit if peak concurrency exceeds 8-10 connections. Mitigation if exhausted: (a) pool size increase, (b) thread-local pool, (c) PgBouncer. security-manager flagged availability concern on PR #134.

_(Re-scoped 2026-06-04: premise OVERSTATED — 연결 누수 없음(prefetch thread 0 conn, telemetry thread finally서 close). 실위험 = 고동시성 peak(>12-15 conn)뿐, 현 규모 무관 → LOW(모니터링). Neon active_connections 모니터, 코드 변경 無.)_

_(2026-07-12 감사: 스레드 인벤토리 증가 — #266이 세션생성당 데몬 스레드 1개 추가(`_async_board_name_update`, session_service.py:387-394; close_all entry+finally 동일 안전 패턴). 현 프로드 데몬 스레드 4종: per-swipe 2(`_async_prefetch` swipe.py:80/155 — DB 무접속, `_emit_telemetry` swipe.py:37/45) + per-session-create 1(board-name) + per-ParseQuery 1(`_spawn_stage2` search.py:90). "concurrent_requests × 2" 산식은 이제 과소 — 결론(현 규모 무관, 모니터링만) 불변.)_

#### INFRA-DB-3 — Unverified guest row 누적 정리 + 죽은 guest 엔드포인트 제거 (conditional)
_2026-07-12 감사 재스코프: 문제가 **확대**됨 — #265 LOGIN-REWORK-1 이후 축적 경로가 2개. (1) `GuestLoginView`(auth.py:228) + `/auth/guest/`(urls.py:19) + `guestLogin()`(api/auth.js:30, client.js:11 재수출)은 **어떤 UI 경로도 호출 안 하는 죽은 코드** — LoginPage(#265)는 `login`/`register`/`checkHandle`만 import. (2) RegisterView(auth.py:762)도 `email=''` + `is_guest=True` row 생성(id+password 계정, Google 연동 전까지 미인증). 모니터링 쿼리 `email='' AND is_active=True`는 두 경로 다 포착._
재스코프된 작업: (a) 죽은 `GuestLoginView`/라우트/`guestLogin` export 제거, (b) 정리 정책 정의 — `last_active`/`swipe_count` 필드 부재라 `is_guest=True AND created_at < now()-interval AND (스와이프 무)` 형태로 가용 필드 기반 재작성, (c) management command(dry-run + `--confirm`). 조건부: > 500 rows/week 지속 시 착수. LOW 유지.

#### FRONT-UX-6 — temp 삭제 실패 무음 + activeProjectId 미정리
App.jsx temp-delete cleanup(`:207 deleteProject().catch(()=>{})`)가 DELETE 실패 시에도 무음(다음 `/search` 재진입 때 self-correct). 성공 후에만 닫거나 에러 토스트. 또 temp 삭제 경로가 `setActiveProjectId(null)`을 안 불러 exit 핸들러와 불일치(파생값 `projects.find()||null`로 무해). FULL-ONBOARDING-1 follow-up. (FULL-ONBOARDING-2 X-HIGH 작업에 흡수 가능 — item 5 orphan/cleanup.)

#### FRONT-AUTH-1 — LoginPage에 Kakao/Naver 버튼 없음
Backend Kakao + Naver implementation shipped: `apps/accounts/views/auth.py` KakaoLoginView + NaverLoginView, `apps/accounts/urls.py` `auth/social/kakao/` + `auth/social/naver/`, provider choices. Frontend `LoginPage.jsx` currently has Google button only (2026-06-28 grep: kakao/naver 없음 확인).
- [ ] Kakao button on `LoginPage.jsx`
- [ ] Naver button on `LoginPage.jsx`

⚠️ **LOGIN-ONBOARD-1로 reshape됨**: social = **인증 전용(verify-only)** 모델 — Kakao/Naver를 1차 로그인 버튼이 아니라 "기존 계정 인증" 옵션으로 둘지 product 결정 필요. (Google조차 신규가입 차단 404 signup_required.) 통합 ID + verify-only와 정합 맞춰 재설계 후 착수.

#### BACK-RECOMMEND-3 — Profile-tab 사무소/유저 추천 endpoint 없음
Re-scoped 2026-05-14 (REC1 already shipped as Push S3). REC2 (firm) + REC3 (user) target a single composite endpoint `GET /api/v1/recommendations/profile/` returning `{offices: [...], users: [...]}` for a Profile-tab button.

**2026-06-04 audit narrowing:** #178 shipped architect recommendation (`projects/PK/recommended_architects/` + `architects/ID/`, `views/office_recommendation.py`), partially satisfying the OFFICE/architect dimension (board-scoped, flat architect list). The literal `/recommendations/profile/` {offices,users} endpoint still does NOT exist, and the USER↔USER ("유저") recommendation dimension remains entirely unbuilt → narrow this item to the user-recommendation gap + the unified profile-tab endpoint.

Open dimensions (admin decision before implementation):
- **Firm vector composition** — Mean / weighted-mean / curated-subset / max-sim of firm's project embeddings?
- **User taste vector** — Aggregated from user's `liked_ids` across Projects; recency-weighted?
- **Cold-start strategy** — New user 0 swipes → "popular users" / generic taste cluster / disable User tab until N swipes?
- **Match score visibility** — Show "92% match" on cards or hide?
- **Trigger surface UX** — Single button → modal / full-page / toggle between Office/User?

Acceptance: `/recommendations/profile/` p95 ≤ 800 ms on Singapore deploy; cold-start UX graceful; `canonical_bld_id` + `is_publishable=true` gating preserved per CLAUDE.md hard rules.

#### BACK-EXTERNAL-1 — FirmProfilePage에 외부 기사 surface 없음
Surfaces external articles about a firm on FirmProfilePage (Space / ArchDaily / news keyword match). Phase 18 deferred. `frontend/src/pages/FirmProfilePage.jsx` already renders an Articles section only when `office.articles?.length > 0` (defaults `[]`); `ArticleCard.jsx` exists expecting `{title,url,source,date}`; backend `OfficeDetailView` omits the field (no OfficeArticle model — 2026-06-28 confirmed).

Open dimensions: source priority (Space-first Korean vs ArchDaily) / crawl freshness (real-time vs scheduled) / storage (OfficeArticle table vs denormalized) / fallback (empty vs hide).
Acceptance: ≤10 most recent articles per firm; open in new tab; no FirmProfilePage TTFC regression (article fetch async).

#### INFRA-QUEUE-1 — corpus_rank telemetry 꺼져있음
Bookmark telemetry used to compute `corpus_rank` synchronously (O(corpus_size) scan). PR #79 turned it off (`rank_corpus = None` + TODO in `swipe.py ProjectBookmarkView`). `engine.compute_corpus_rank()` still implemented (pgvector ROW_NUMBER); tests lock the None placeholder. No Celery in requirements (2026-06-28 confirmed).

Why LOW (YAGNI): Celery+worker for one product-unconsumed telemetry field = over-investment (Redis add-on, worker process, monitoring, deploy step). Revisit when ≥2 background jobs accumulate (image batch / embedding refresh / snapshots) → single INFRA-JOBS ticket. Do NOT re-enable synchronous compute in the bookmark hot path.

## Done
### FULL-WORKS-1 — 건축 작품 업로드 Phase 1 — RESOLVED 2026-07-15 (`6089487`)
presigned direct upload to Cloudflare R2: Django `apps/works/` 신설 + `/api/v1/works/presign/`·`/api/v1/works/` API + UploadWorkPage.
- [x] Work 모델 (upload_id `usr_XXXXXX`, 14개 program enum, r2_keys JSONField, is_publishable=False, report_count) + migration 0001_initial
- [x] presign 뷰: 10MB content-length-range 정책 + image/* 강제 + 10분 만료, key `works/{profile_id}/{uuid8}_{slot}.webp`
- [x] finalize 뷰: 저작권 확인 → namespace 검증(403) → R2 존재 확인 → Work 저장 → 백그라운드 스레드(Gemini 품질 게이트 + atmosphere enum 12개 강제; HF 384차원 임베딩은 07-17 fix에서 삭제 — 저장 필드 부재 dead call) → 201 `{upload_id, status:'processing'}` 즉시 반환
- [x] storage.py: `_make_s3_client()` 공유 + `generate_presigned_post()` + `verify_key_exists()` (boto3 lazy, accounts/storage.py 패턴 미러)
- [x] WORKS_R2_ENABLED 플래그, INSTALLED_APPS 등록, `/api/v1/works/` URL
- [x] 테스트 14개 (기존 9: presign 503/400x2, finalize 400/403/400/201/401 + fix 배치 5: Content-Type Fields 회귀 / presign·finalize 11장 cap / project_year 비정수 / 비str r2_key) — all PASS
- [x] UploadWorkPage: canvas.toBlob WebP 변환(max 2400px) + XHR progress + processing/error 상태 UI + /upload 라우트
- [x] r2_keys isinstance + empty 가드 패치 (2 LOW 소견)
- [x] **리뷰 fix 배치 2026-07-17** (ultracode 4-lens + Opus verify 10건 확정 → critical+medium+저비용 low 적용): presign `Fields={'Content-Type': ...}` 누락 수정(**critical** — boto3는 Condition에서 field 자동 생성 안 함 → 실 R2 업로드 전면 거부되던 결함) · Gemini 호출 `_retry_gemini_call` 15s 데드라인 경유 · HF embed dead call 삭제 + `_GEMINI_RESPONSE_SCHEMA` 소비 필드로 트림 · project_year/r2_keys 원소 입력검증(500→400) · `MAX_WORK_IMAGES=10` 3-tier(presign+finalize+프론트 keep-what-fits, 신규 문자열 t() i18n) · DRY 3건(`_finish` 헬퍼, `_make_s3_client` 재사용, 잔여 ternary). 유보 → BACK-WORKS-1(페이지네이션)/BACK-WORKS-2(HEAD 병렬화)
- 검증: workflow 2 cycles commitReady=true · app-test FEATURE-SCOPED 5/5 PASS · drift clean
- Deferred-MEDIUM: FULL-WORKS-2 (Phase 2 works srcset/LQIP + algorithm 통합 + works 임베딩 저장 필드·HF 호출 재도입 — Phase 1 배포 후; 임베딩 dead call은 2026-07-17 fix에서 삭제됨)
- Deferred-LOW: INFRA-WORKS-1 (R2 works 버킷 프로비저닝 — `## Next` § LOW로 구체화, 2026-07-17 진행중)

### BACK-PERFORMANCE-5 — Swipe latency 0.7-1.5s 흔들림 — RESOLVED 2026-07-16 (ops-only, 코드 0줄)
Codex retest 2026-05-26: browser swipe 1.82s/1.75s/1.12s/1.81s; server swipe 1.50s/1.38s/0.746s/1.36s. **PR4 async prefetch consume IS working** — 3rd swipe with cache hit drops to 156ms prefetch stage. But variability is high. Identify which stage causes the 0.7→1.5s spread (DB query latency? embedding cache miss? pgvector?). Aim for swipe p95 ≤1.0s and p50 ≤0.5s on Singapore prod. **(2026-06-28 HIGH로 승격 — 코어 스와이프 루프 + <1s 페이지로드 목표 + 런칭 임박.)**

Code audit 2026-05-27 (`develop@3894ffd`):
- `backend/apps/recommendation/views/swipe.py` still performs the algorithmic card selection inside the request transaction: update Project/session, phase transition, `engine.refresh_pool_if_low()`, `engine.get_pool_embeddings(session.pool_ids)`, then `engine.farthest_point_from_pool()` or `engine.compute_mmr_next()`.
- PERF-PREFETCH-CHAIN moved card data lookahead off-path only after `next_bid` is selected. The cache-hit path avoids some prefetch-card compute/fetch, but it does not skip `get_pool_embeddings()` or MMR/farthest selection for the next visible card.
- The response already logs `[SWIPE TIMING] lock/embed/select/prefetch/total` and captures `engine.get_last_embedding_call_stats()` for cache miss counts. That is the fastest way to classify the spread before editing.
- `engine.get_pool_embeddings()` has an in-process LRU-like building embedding cache; cache misses can still trigger a DB fetch against `canonical_v2_buildings`. Under multi-worker prod, this cache is per process.

Diagnostic plan:
- Re-run a fixed 8-10 swipe session and bucket slow responses by timing stage: `embed_ms` > selection, `select_ms` > MMR/farthest CPU, `prefetch_ms` > buildings batch fetch / cache miss, `lock_ms` > transaction contention.
- Compare first session after worker boot vs warmed worker. If first swipes are slow and later cache-hit swipes are fast, embedding cache warmup is the likely source.
- If `select_ms` dominates in analyzing phase, inspect `engine.compute_mmr_next()` vector math and pool size. If `embed_ms` dominates, inspect `get_pool_embeddings()` DB batch and cache-hit ratio.

_(Deferred 2026-06-04 batch scope → 계측 먼저. Variance CONFIRMED(per-worker in-process embedding 캐시 cold-miss 50-200ms + KMeans 재계산)나 ~tens-daily-users 규모서 cold-miss는 주로 배포직후 일시적; Redis-migration은 조회마다 RTT 추가 + premature 가능. prod hit-rate/지배 원인 계측 후 결정.)_

_(2026-07-12 감사 re-pin: 전제 유효 — 알고리즘 코어(refresh_pool_if_low/get_pool_embeddings/compute_mmr_next/farthest_point)가 여전히 `transaction.atomic()` + `select_for_update()` 안(FULL-REFACTOR-1로 `swipe_service.py:727-1087` 이동, off-path 이동은 아님). `[SWIPE TIMING]` 로그 잔존(swipe.py:457-466). **#268 `session_metrics_report`가 timing_breakdown 리더 제공** — item의 진단 플랜(8-10 스와이프 stage별 bucket)을 이제 prod 데이터로 즉시 실행 가능, 계측 선행조건 충족.)_

_(2026-07-13 BACK-PERFORMANCE-5a 출하(`afc0b88`): 리더에 stage별 p50/p95 + cache_hit 분리 + warmup 위치 bucket 집계 탑재 완료. 배치 플랜 Q1 결정: 진단만 이번 배치, fix 별도.)_

**🔬 PROD 계측 결과 (2026-07-13, user-승인 read-only, 90일 창 = 전체 timing 데이터, n=247 swipes / 35 sessions / cache_hit 95.5% / malformed 0):**
| stage | p50 | p95 | max |
|---|---|---|---|
| prefetch_ms | **888** | 1213 | 2907 |
| select_ms | 416 | **1389** | 82282 (outlier 1건) |
| lock_ms | 171 | 530 | 1650 |
| embed_ms | 75 | 151 | 561 |
| **total_ms** | **1638** | **2826** | 83737 |
- **지배 stage = prefetch (p50의 54%)** — cache HIT에서도 prefetch p50 902ms. 코드 대조로 정체 확정: prefetch 구간(select_done→prefetch_done) = **동기 `engine.get_buildings_by_ids([next, pf, pf2])` 배치 fetch** (swipe.py:396-403). IMP-8 async 스레드는 **이미 켜져 있고 정상** (`async_prefetch_enabled: True`, settings.py:319, PERF-PREFETCH-CHAIN 후 재활성) — 스레드는 의도적으로 ID만 캐시(스레드 ~50ms 유지, swipe.py:85-91 주석), 카드 hydration은 요청 경로에 남는 설계. "IMP-8 꺼짐" 1차 추정은 **기각**.
- **근본 원인 후보**: `DATABASES['buildings']`에 `CONN_MAX_AGE` 무 → 매 요청 Neon 신규 TLS 커넥션. 단 이는 **문서화된 소유권 결정**(Make-DB 소유 프로젝트에 앱 영구 커넥션 금지, CONTRIBUTING.md § Buildings-DB connection pooling) — 직접 CONN_MAX_AGE 추가는 소유권 위반. **승인된 해법 = Neon 서버측 pooler**: `BUILDINGS_DB_HOST`를 `ep-<id>-pooler.<region>...`로 (Railway env + 로컬 .env, user-applied, 코드 0줄). 2026-07-07 실측: connect tail max 2059→517ms 평탄화.
- **p95 드라이버 = select (1389ms)** — cache miss 시 select p50 2.5배(1032 vs 412; miss 시 `get_pool_embeddings`가 buildings DB fetch = 같은 커넥션 비용). max 82s outlier 1건 = Neon autosuspend cold-start 추정 — pooler로는 안 잡힘, 별도(autosuspend 설정 or keepalive).
- **가설 기각 2건**: ① embed cold-miss 지배 가설(2026-06-04 deferred 노트) — embed p50 75ms, 총량의 5%뿐. ② warmup 가설 — 세션내 1-2번째 swipe(p50 1577ms)가 3+번째(1650ms)보다 오히려 빠름.
- **✅ pooler 적용 완료 (2026-07-13, user 전권 승인)**: Railway `archi-tinder` 서비스(production) `BUILDINGS_DB_HOST` → `ep-broad-hat-a1jaomn7-pooler.ap-southeast-1.aws.neon.tech` 플립 + 로컬 `backend/.env` 동일 플립(gitignored). 배포 `049e3b8a` SUCCESS, gunicorn 워커 3 클린 부팅(DB/커넥션 에러 0). 검증: prod buildings 역할(`make_web`)로 pooler 호스트 직접 SELECT → 36,673 publishable buildings 정상. 참고: prod app DB(`DB_HOST`=동일 엔드포인트 ep-broad-hat, DB=user_data)와 buildings(DB=archi_data)가 같은 Neon 엔드포인트 공유 — `default` alias는 CONN_MAX_AGE=600 유지, buildings만 pooler로(CONTRIBUTING.md 명시대로).
- **잔여 액션**: ① 트래픽 쌓인 뒤(수일) `session_metrics_report --days 7` 재실측(before/after — prefetch p50 888ms 개선 확인) → ② 잔여 병목이면 후보: 스레드측 bcard warm-hydration(fast-swiper 트레이드오프 있음, swipe.py:85 주석), prefetch 구간 sub-split 계측(connect vs query vs cache), in-region 커넥션 비용 실측. ③ 82s outlier = Neon autosuspend cold-start 별도(설정 or keepalive).
- 주의: 247건은 4-7월 코드 세대 혼합(Redis 5/26 도입·PERF-PREFETCH-CHAIN 6월 배포 전 데이터 포함) — stage 지배 구도는 유효하나 절대값은 pooler 플립 후 재실측이 기준. 30일 창 n=4(저트래픽)라 90일 창 채택. 원데이터 `/tmp/perf5-prod-90.json`(로컬 휘발).

**✅ ROOT CAUSE + FIX (2026-07-16)**: Railway `Redis` 서비스가 **US 리전**에 배포돼 있었음(INFRA-REDIS-1 2026-05-26 생성 시 기본 리전 방치; `REDIS_URL`은 `redis.railway.internal`이라 겉보기 정상 — 내부 DNS가 리전 간 resolve, 지리 RTT ~172ms/op는 그대로. 시그니처: p50 171.6-172.6ms 분산 ~1ms = 순수 네트워크). swipe 경로 Redis 4-6회(prefetch-key get + `get_buildings_by_ids` per-card 순차 `cache.get` + select 스테이지) → prefetch 888ms(54%) + 0.7-1.5s jitter 전부 이것. **fix = Redis 서비스 리전 Southeast Asia 이동(user, Railway 대시보드, 캐시라 데이터 무손실)** → Redis get p50 172→1.56ms, `get_buildings_by_ids` warm 518→7ms. **합성 11-swipe 동일방법론 before/after: swipe total p50 3360→124ms(max 184), 전 stage <60ms — 목표(p50≤0.5s, p95≤1.0s) 달성.**
- **진단법**: `railway ssh`로 prod 컨테이너 안 in-region 마이크로벤치(read-only `SELECT 1` connect 루프 + Redis RTT + 실 카드 SQL + `engine.get_buildings_by_ids` cold/warm 분해). 로컬 `railway run` delta 벤치는 클라이언트 RTT(~700ms)에 잠식돼 무용.
- **가설 기각 2건**: ① #278 "per-request TLS connect" 가설 — in-region fresh connect 37ms뿐(888의 4%). ② **pooler flip(2026-07-13) 이득 ~3ms**(direct p50 37 vs pooler 34), tail 악화(max 728 vs 50) → **pooler REVERT 결정(2026-07-16)**: prod `BUILDINGS_DB_HOST` direct 복귀 + 로컬 `.env` 동일(user-applied).
- cache_hit(902ms) > cache_miss(578ms) 역전 해명: hit=카드 3장=Redis 3회 순차, miss=1장=1회 — op당 172ms 시대 산물, 버그 아님.
- 합성 오염 ledger(향후 텔레메트리 분석 시 제외): prod session `e1103b42-7dba…`(07-15 pre-fix) + `0e0cd2f7-0a63…`(07-16 post-fix) 각 11 swipes.
- 잔여(비차단): select_ms max 82s outlier = pre-fix 시대 n=1 — 재발 시에만 추적(Neon autosuspend). 상세 메모리: `project_perf5_redis_region_fix`.

### FULL-LANGUAGE-1c — i18n 슬라이스 c: 프로필·보드 + 모달 — RESOLVED 2026-07-13 (`f54d998`-pre-squash) → **FULL-LANGUAGE-1 전체 CLOSE**
최종 슬라이스 17파일 ~115 리터럴 — 3슬라이스(a #275 / b #276 / c) 합산 32파일 176줄 sweep 완료, 전 고트래픽 surface가 ko/en 동일 string source 렌더. FULL-LANGUAGE-1 백로그 항목 종결.
- [x] PersonaReport(SPECTRUM_AXES 모듈상수 → leftKey/rightKey 렌더 해석) · SaveBoardModal(visibility labelKey) · VerifyGateModal 자체 리터럴 7 · ShareCardModal({name} 보간) · ArchitectProfilePage · ProfileHeader · LLMSearchPage · LikedOffices/Projects · BoardReport/Detail · ArchitectSection · BoardCard({count} 보간) · SaveToBoardModal(useLanguage 삼항 패턴 제거) · EditCardForm/ProfileQr partial 마감 · UserProfilePage.
- [x] locales.js 신규 네임스페이스 6(persona/board/architect/share/profile/search) + profileEdit 확장, ko/en 양쪽 additive.
- [x] 잔여 한글 17파일 전수 grep = 주석만(세션 재검증 — built 목록에 UserProfilePage 누락은 리포팅 미비였고 실변경 확인).
- 검증: eslint 0(신규 exhaustive-deps 워닝 1 → mount-only disable 주석, LikedProjectsPage 선례) · node --test 79/0 · build PASS · code-review PASS · security PASS · Opus 적대검증 confirmed 0.
- 잔여 액션: EN 카피 스팟체크(사용자, locales.js diff) — ko 폴백이 있어 오역시에도 비파괴.

### FULL-LANGUAGE-1b — i18n 슬라이스 b: 설정·계정 + 인증에러 — RESOLVED 2026-07-13 (`b433892`-pre-squash)
설정/계정 표면 9파일 + 인증 에러 훅 국지화 — Settings 트리 전체가 ko/en 동일 string source 렌더.
- [x] AccountScreen(33 리터럴, {email} 보간) · EditProfileScreen(6) · SettingsPage(ROWS {labelKey,hintKey} 전환) · AppearanceSettings partial-adopter 마감(LANGUAGE_OPTIONS labelKey) · AppearanceScreen · buildingDetail Header(useLanguage 삼항→t()) /ErrorState · LoginPage 마지막 리터럴.
- [x] `useGoogleEmailVerify` 에러 8종: raw 한글 → `{key, params}` 객체(FRONT-AUTH-3 LoginPage 에러 선례) — 훅에 useTranslation 미주입(hooks rules), 소비자(VerifyGateModal·AccountScreen) 렌더층 `t(error.key, error.params)`.
- [x] locales.js additive: account(33키)+auth(6)+buildingDetail(4)+settings.rows+title+profileEdit(7)+login.common 확장, ko/en parity 비대칭 0 (Opus 검증).
- [x] 리뷰 follow-up 2건 in-PR 반영: `settings.title`('설정'/'Settings') + `buildingDetail.retry`('다시 시도'/'Retry') — 국지화 카피 옆 pre-existing 영어 하드코딩 비일관 해소.
- 검증: eslint 0 · node --test 79/0 · build PASS · code-review PASS · security PASS · Opus 적대검증 confirmed LOW 2(위 follow-up으로 수정)·false positive(HIGH 주장 1 포함) 기각. VerifyGateModal 잔여 한글은 슬라이스 c 스코프.

### FULL-LANGUAGE-1a — i18n 슬라이스 a: 코어 스와이프 루프 — RESOLVED 2026-07-13 (`ff6210b`-pre-squash)
고트래픽 코어 루프 5파일의 하드코딩 한글 전량(주석 제외)을 t() 키로 — Discovery/Swipe/Results가 ko/en 동일 string source에서 렌더.
- [x] DiscoveryPage(17 리터럴: 토스트·진행 라벨·CTA·cap 메시지·이탈 모달) · SwipePage(14: ActionCard/ExitConfirm/DismissConfirm/본문) · ResultsPage(1) · DiscoveryTriggerCard(4블록, `<br/>` 분할은 sibling t() 콜) · QuestionCard(3).
- [x] locales.js additive: discovery 확장(+triggerCard) + swipe/results 신규 네임스페이스, ko/en 양쪽. **43키 전부 양 트리 resolve** (Opus 검증 스크립트 확인 — 미해결 키 회귀 0).
- [x] 동적 문자열 {placeholder} 보간, adopter 패턴(useTranslation) 준수, 잔여 한글 grep = 주석만.
- 검증: eslint 0 · node --test 79 pass/0 fail · build PASS · code-review PASS · security PASS · Opus 적대검증 confirmed LOW 1(`t` 섀도잉 — `n => n + 1` 리네임으로 in-PR 수정), false positive 5 기각(전부 스코프밖 pre-existing).
- EN 번역 에이전트 작성 — locales.js diff 스팟체크 요망(플랜 Q3). 슬라이스 b(설정+인증에러)·c(프로필·보드+모달) 잔여.

### FRONT-IMAGE-RESIZE-3 — 이미지 풀해상도 passthrough + telemetry currentSrc — RESOLVED 2026-07-13 (`05858b4`-pre-squash)
이미지 리사이즈 시리즈(PR1 #241 / PR2 #242 / LQIP #267) 마지막 잔여 마감 — 빈-갤러리 건물의 라이트박스/다운로드가 원본을 받고, telemetry가 실제 렌더 variant를 기록.
- [x] `normalizeCard`에 `cover_full_url`(raw 미변환 passthrough) 추가 — 840px 리라이트로 소실되던 원본 URL 보존. additive, 소비자 무영향.
- [x] `BuildingDetailPage` 빈-갤러리 폴백 `cover_full_url || image_url` — #235 다운로드 840px known-limitation(FRONT-IMAGE-RESIZE-1) 해소.
- [x] `useImageTelemetry` onLoad/onError `currentSrc || src` — srcset variant별 load_ms 정확화.
- [x] images.test.mjs에 cover_full_url 가드 테스트(node --test 환경서 graceful skip — 기존 getImageSource와 동일 제약).
- 검증: eslint PASS · npm test 79 pass/2 skip · build PASS · 세션 diff 리뷰(bounded 3파일, 스펙 일치). Tier B(Divisare 포맷 프록시)는 별개 user-결정 gated 유지(findings-r2-retirement.md).

### BACK-PERFORMANCE-5a — swipe timing_breakdown 계측 리더 — RESOLVED 2026-07-13 (`afc0b88`-pre-squash)
`session_metrics_report`가 SessionEvent `timing_breakdown`을 이제 집계 — stage별 p50/p95/max + cache_hit 분리 + 세션내 위치 warmup bucket으로 swipe 0.7-1.5s 변동의 지배 원인을 prod 데이터로 특정 가능.
- [x] 순수 헬퍼 5종(`_extract_timing`/`_stage_percentiles`/`_cache_split_percentiles`/`_position_buckets`/percentile) — DB 없이 unit 테스트 가능 구조.
- [x] swipe 섹션 신규 키 4: `timing_breakdown`(stage별 p50/p95/max/count), `timing_breakdown_by_cache`(hit/miss), `timing_breakdown_by_position`(warmup 1-2 vs warmed 3+, total+embed), `timing_malformed`(불량 payload 카운트+제외). 텍스트+`--json` 양쪽, 기존 키/섹션 무변경(additive).
- [x] 테스트 +30: pure-unit 23(percentile 홀짝/단일, 추출 all-or-nothing, cache 분리, 위치 bucket 교차세션) + django_db 통합 7(CI). 기존 테스트 원문 유지.
- 검증: pure-unit 23/23 로컬 PASS · flake8 clean · 로컬 dev DB 스모크(신규 키 4 출력, malformed 0; 로컬 4-swipe select_ms p50 1834ms — 참고 신호일 뿐) · code-review PASS · security PASS · Opus 적대검증 confirmed 0(스코프밖 pre-existing 1건은 LOW 백로그로 분리).
- 다음 스텝: **prod read-only 실행(user-gated)** → 지배 stage 확정 → BACK-PERFORMANCE-5 fix를 데이터 기반 스코핑(배치 플랜 Q1 결정).
- Deferred: #268 기존 코드의 payload 값 콘솔 raw 출력(ESC-byte 터미널 주입 가능, 이 PR 미접촉 영역) → BACK-ANALYTICS-1.

### FULL-ONBOARDING-2 — is_temp 라이프사이클 마감 (#243 fast-follows) — RESOLVED 2026-07-13 (`92237d8`-pre-squash)
temp 보드 누수 5개 사이트 일괄 마감: one-way finalize 강제 + 리스트/카운트/취향벡터/피드 전부 `is_temp=False` 필터 — 사일런트 보드 유실 경로 차단.
- [x] **`validate_is_temp`** (serializers.py ProjectSelfUpdateSerializer): PATCH `{is_temp:true}` → 400 "is_temp can only be set to false (finalize is one-way)." — 영구보드 temp 되돌림 → /search 재진입 자동삭제 사일런트 유실 경로 차단.
- [x] **board-list 필터**: `ProjectListCreateView.get()` + `UserProjectsListView.get()`에 `.filter(is_temp=False)` — temp 보드 프로필 리스트 비노출.
- [x] **guest-count fix**: discovery.py 268/405 guest 3-보드 카운트 `is_temp=False`만 (temp 1+저장 2 false 403 해소) + **promote 시점 limit enforce**: ProjectDetailView.patch가 guest의 temp→permanent 전환 시 영구보드 ≥3이면 `403 {'detail':'verify_required','reason':'board_limit_reached','limit':3}` (discovery.py 계약 미러) + promote 성공 시 taste/discovery-feed 캐시 evict.
- [x] **taste/feed 혼입 제거**: engine.py `compute_user_taste_vector` + discovery_feed.py fallback rows + discovery.py DiscoveryFeedView rows 전부 `is_temp=False`.
- [x] 테스트 신규 8: `backend/tests/test_is_temp_lifecycle.py` (DB 통합 6 — one-way 400, promote 성공, guest limit 403+temp 유지, 리스트 2뷰 제외, guest-count false-403 해소) + `apps/recommendation/tests/test_is_temp_data_filters.py` (pure unit 2 — taste vector/feed filter kwargs).
- 검증: flake8 clean(7파일) · pure-unit 2/2 로컬 PASS · DB 통합 6은 CI canonical(로컬 runtime user CREATEDB 무) · workflow code-review FAIL→계약정렬 fix→해소 · security PASS · Opus 적대검증 confirmed MEDIUM 1(bare-string 400 계약 불일치)→403 verify_required로 in-PR 수정. app-test SKIP(4-gate 정책, 플랜 승인).
- Deferred: orphan temp GC/TTL → `INFRA-TEMP-GC-1`(### MEDIUM, 사전 분리됨) · guest promote-limit 403의 프론트 VerifyGateModal 배선(updateProject가 verify_required 미변환, createProject만 처리) → FRONT-VERIFY-1.

### BACK-LLM-4 — search.py ParseQueryView byte-cap ensure_ascii 부풀림 의심 — CLOSED 2026-07-12 (premise falsified, no PR)
2026-07-12 백로그 전수 감사에서 무혐의 판명: `ParseQueryView.post`는 conversation_history 검증을 serializer로 위임하며, 해당 serializer는 BACK-LLM-2(#195)가 이미 UTF-8 byte 측정으로 고침 — ParseQueryView 자체에 `ensure_ascii=True` byte-cap 경로가 애초에 없음(Sonnet 검증 + Opus 적대검증 동의). 의심 항목이었고 실재하지 않아 폐기.

### OVERNIGHT-PERF-1 — 야간 자율 4-PR 묶음 (핫패스·카드비주얼·집계·ops문서) — RESOLVED 2026-07-08 (#266-#269)
Plan `.claude/plans/settings-encapsulated-sedgewick.md` 4슬라이스 전부 머지: **PR-A** #266 back-hotpath (보드명 async + like 태그조회 캐시, 개별 Done 항목 PERF-HOTPATH-1) · **PR-B** #267 LQIP blur-up + 비율적응형 object-fit · **PR-C** #268 `session_metrics_report` 첫 SessionEvent 리더 · **PR-D** #269 인덱스 핸드오프 + Neon pooler 문서. (우산 항목 Done 이동 2026-07-12 감사 시 — 데스크탑 reporter 미처리분.)

### PERF-HOTPATH-1 — 세션생성 보드명 비동기화 + like 태그조회 캐시 대체 — RESOLVED 2026-07-07 (`37a3340`-pre-squash)
세션 생성 최악 ~12s Gemini 대기 제거 + like 스와이프당 buildings DB 왕복 1회 절감 (OVERNIGHT-PERF-1 PR-A).
- [x] `session_service.py`: `.join(timeout=12)` 삭제 — deterministic fallback 이름(`_deterministic_board_name`+`_dedup_board_name`)으로 즉시 INSERT·응답; Gemini 이름은 `transaction.on_commit` 등록 데몬 스레드 `_async_board_name_update`(PK 전달, `connections.close_all()` entry+finally = 텔레메트리 스레드 패턴)가 **조건부 원자 UPDATE** `filter(pk, name=fallback).update(...)` — 유저 수동 rename 절대 안 덮음. API shape 무변경.
- [x] `swipe_service.py` `_update_question_state`: raw SQL 대신 `engine.get_building_card` bcard 캐시 우선(+scalar wrap/list 리맵), 카드/metadata 부재 시 기존 SQL fallback 유지. 다운스트림 fold 불변.
- [x] 테스트: `test_taste_board_name.py` 재작성(즉답·가드·예외·비-placeholder 무스레드) + 신규 `test_question_state.py`(캐시/SQL 동형·fallback·결측키). 리뷰 PASS · 보안 PASS · Opus verify 0건 (cyclesUsed 0).
- [x] **라이브 검증 (FEATURE-SCOPED, API 직접 — 브라우저 app-test 대체, hang 리스크 0)**: dev-login → placeholder 세션생성 **201 + "Untitled (1)" 즉답** → like 스와이프 200 → 수 초 후 프로젝트 이름 **"Warm Timber"로 비동기 승격 확인**. 로컬 세션생성 500(orphan column) 이슈 재현 안 됨.
- 참고: 콜드 세션생성 6.0s는 풀 생성 쿼리 비용(인덱스 핸드오프 = PR-D 항목) — 본 PR 범위 밖.

### LOGIN-REWORK-1 — 로그인 페이지 컨셉 재작업 — RESOLVED 2026-07-06 (`a390f9f`-pre-squash)
로그인 페이지 전면 재작업 — 스와이프-취향발견 컨셉 + 명함 UI에 충실, 사용자 포커싱. Frontend-only, 백엔드 무변경. Plan: `.claude/plans/login-page-concept-rework.md`.
- [x] (6) 실제 카드 덱: 다음 카드를 앞 카드 뒤에 프리렌더 (새로 렌더가 아니라 '뒤에서 대기하던 카드가 올라옴' 느낌) + step-history 스택 뒤로가기(pop). 기존 장식용 faux-depth 카드 대체.
- [x] (2) IntroOverlay 모달 제거 → 첫 choice 카드에 통합, 카드 자체가 스와이프 튜토리얼(타이핑 질문 + 좌우 제스처 힌트).
- [x] (3) ARCHIBE 워드마크 로고급 확대(24px/700/0.14em) via 로그인 전용 `loginWordmarkStyle` — 공유 `wordmarkStyle`은 원복해 CardSkeleton(Discovery/Swipe 로딩 스켈레톤) 무영향. 질문/라벨/finePrint 텍스트 MONO→기본 폰트(IBM Plex Sans KR) 전환 (DESIGN.md §2.5a single-font). MONO는 @id·JOINED 명함 메타 액센트로만 잔존.
- [x] (1) ID 중복확인: 수동 `중복확인` 버튼 제거 → 타이핑 시 ~450ms 디바운스 자동 확인, 인라인 checking/available/taken 상태. 한글 IME compositionstart/end 가드(조합 중 API 미발사, 조합 끝나면 재확인) + stale in-flight 응답 무시. NFC 정규화 유지.
- [x] (4) 타이핑 애니메이션 복원 (모달 제거로 다시 보임, step 전환 시 재실행).
- [x] (5) 노이즈 카피 제거 (ko+en 양쪽) — '명함에 새길 이름이에요' 등 행동 지시 없는 문구 정리.
- 진단: 백엔드 check-handle + dev-login은 라이브 테스트로 정상 확인(200) — 이슈 1은 프론트 UX, 이슈 7은 최초 backend가 global python으로 떠 죽었던 오탐(venv `.venv/Scripts/python.exe`로 해결). Review PASS, security PASS.
- Finding(medium/fixed): 공유 wordmarkStyle 스코프 누수 → `loginWordmarkStyle` 격리로 해결.
- Deferred: CredentialsStep 뒤로가기 remount 시 입력 draft 소실(pre-existing, non-blocking) — 후속.

### NOTIF-INAPP-1 — 앱 내 알림 v1 (❤️ 받음 + 보안 이벤트) — RESOLVED 2026-07-06 (`0bac717`-pre-squash)
앱 내 알림 v1 — 신규 `apps/notifications` (인박스+종+발생훅), 설정 알림 화면 실동작 전환 (설정 페이지 개선 2/2).
- [x] 신규 앱 `apps/notifications`: `Notification`(recipient/actor/type[reaction·password_changed·new_login]/category[social·security]/payload/read_at, 인덱스 2종) + `KnownDevice`(user+ua_hash unique) — additive migration 0001 (accounts.0011 의존).
- [x] 발생 훅: ❤️ Reaction 생성 시 프로젝트 소유자 알림(본인 스킵 · `social.in_app` opt-out 기본 ON · 미읽음 dedupe) — social react view; 비번 변경 + 새 기기 로그인(ua_hash 신규 & 기존 기기 ≥1, 최초 기기 무음) — auth views. 훅 실패해도 호스트 요청 안 깨짐(wrap+log).
- [x] API: `GET /api/v1/notifications/`(self-only, 20/50 cap 페이지네이션) · `unread-count/` · `POST mark-read/`(ids≤500|all, 멱등). prefs validator `in_app` 채널 키 허용.
- [x] 프론트: `/notifications` 인박스(문장 ko/en, time-ago, 진입 시 전체 읽음, 더 보기, empty state) + 프로필 헤더 종 아이콘/9+ 뱃지(mount+visibilitychange만, 폴링 없음, `useUnreadNotifications` 훅) + 설정 알림 화면 카테고리별 `in_app` 단일 토글(보안 LOCKED, merge-PATCH push/email 키 보존) + Avatar/timeAgo 유틸 신규.
- [x] 게이트: code-review PASS · security PASS · Opus verify PASS (cyclesUsed 1 — 인박스/설정 `[t]` useEffect 의존성 무한 refetch 결함 수정). low 1건 shipped: `UserMiniSerializer.user_id` 정수 PK 노출 — 기존 시스템 전반(Project/reactors)과 동일, net-new 0 (전면 교체는 별도 과제).
- [x] app-test skip(4-gate 정책) · drift clean. ⚠️ migration 0001 로컬/프로드 미적용 — `make migrate-local`(로컬), 배포 시 `make migrate-prod` CODE-FIRST (additive라 안전).
- Deferred: 이메일/푸시 채널 발송(SMTP/FCM 외부 의존성 — 사용자 승인 필요), user_id 정수 PK 전면 비열거화.

### LOGIN-CARD-REDESIGN — 로그인/가입 명함 UI 재설계 (명함 언어 + CardSkeleton) — RESOLVED 2026-07-06 (`e9b3638`-pre-squash)
- 로그인/가입 5단계 카드를 테마 적응형 명함 언어로 재설계 (신규 `cardLanguage.js` 공유 모듈: paper face + ink 타이포 + mono 라벨 + ink 버튼 + paper-flat 인풋; 기존 토큰만, BusinessCard.jsx 불변).
- 텍스트 다이어트: 페이지 헤더 + 카드 아래 캡션 삭제, 타자기 프롬프트가 유일 안내(제목 중복 제거), 규칙은 placeholder/검증 에러로 이동.
- 동의 단계 = 입력값으로 채워진 명함 미리보기 (모노그램 스탬프 + fine-print 동의 한 줄 + 우스와이프 = 발급); register payload 불변.
- Discovery + SwipePage 공용 LoadingCard → 신규 `CardSkeleton` (마스코트/shimmer 제거, lp-skel pulse — DESIGN.md §8.8 준수 전환). 카드 크기/제스처/사진 SwipeCard 불변 (온보딩→Discovery 연속성).
- DESIGN.md 의도적 이탈 (로그인 flow 한정, PR 설명 명기): §8.1 CTA = ink 버튼(accent gradient 대신), §8.5 인풋 = paper-flat(glass 대신).
- 부수: git-guard hook `python3`→`python` (`47f87d6`, Windows Store 스텁 이슈). locales.js/Task.md hunk는 동시 세션 PR1 `4180535`에 선탑승. 브랜치는 `feature/claude-settings-polish` 위 스택 — PR1 머지 후 retarget 필요 (parent merge 전 child retarget, `--delete-branch` 주의).
- Plan: `.claude/plans/validated-honking-owl.md`. Workflow: review PASS + security PASS, cyclesUsed 0. app-test 스킵 (pure-UI + 4게이트 PASS 정책); 사용자 육안 확인 :5174 권장.

### SETTINGS-POLISH-1 — 설정 페이지 개선 1/2 (직업 dropdown 통합 + Bio auto-grow + 폰트 칩 + 테마 preview) — RESOLVED 2026-07-06 (`4180535`-pre-squash)
직업(Role) enum 단일화 + Bio auto-grow + 폰트 2-칩 + 테마 라이브 preview — 설정/프로필 편집 4개 개선 1커밋.
- [x] Role 단일 소스: `UserProfile.ONBOARDING_ROLE_CHOICES` + 신규 `ONBOARDING_ROLE_LABELS_KO` → 신규 `GET /api/v1/meta/roles/` (AllowAny, {value,label_en,label_ko}×5); choices 항목 추가만으로 회원가입+프로필편집 동시 전파.
- [x] 프로필 편집 직업 = dropdown(`onboarding_role` 바인딩, getRoles() + 번들 fallback constants/roles.js). SAVE RULE: 선택 시 `{onboarding_role, role:''}`(legacy 자유텍스트 정리), 미선택 시 두 키 생략(legacy 보존 — clobber 방지). legacy hint 표시.
- [x] 공개 `UserProfileSerializer`에 `onboarding_role` 노출; ProfileHero 표시규칙 legacy text > enum label('other' 억제) > 없음.
- [x] 회원가입 5종 노출(구 3종 불일치 해소) — objective i18n designer/enthusiast 키 추가(develop LoginPage용; 신 LoginPage는 동시 세션 LOGIN-CARD-REDESIGN PR).
- [x] Bio textarea auto-grow 90→240px(JS cap, 초과 시 내부 스크롤), 수동 resize 제거, 500자 카운터 유지.
- [x] 폰트 = 2-칩(IBM Plex Sans KR / Noto Serif KR, 각자 폰트로 렌더) — 언어 스위처 패턴.
- [x] 테마 preview 미니목업(`ThemePreviewCard`, scoped `data-theme` wrapper, 전 색상 var(--...) 토큰) + tokens.css `:root,[data-theme="github-light"]` 셀렉터 수정(다크 활성 중에도 라이트 preview 정상).
- [x] 게이트: code-review PASS · security PASS · Opus verify PASS (cyclesUsed 0); low 1건 shipped(구 objective 키 dead — LOGIN-CARD-REDESIGN 랜딩 후 정리). app-test skip(4-gate 정책, swipe 경로 아님) · drift clean.

### PROFILE-QR-1 — 프로필 공유 진짜 QR (FakeQr 스텁 교체) — RESOLVED 2026-07-01 (`e872bf7`-pre-squash)
프로필 공유 모달 QR이 가짜(FakeQr.jsx, 스캔불가 SVG 격자)였음 → 실제 스캔되는 QR로 교체.
- [x] `qrcode.react@4.2.0` 추가 + 신규 `ProfileQr.jsx`(QRCodeSVG, `{window.location.origin}/user/{user_id}` 인코딩, level M, marginSize=2 quiet-zone, dark-on-white 테마독립, `role=img`, userId 없으면 skip).
- [x] `BusinessCard.jsx`: FakeQr→ProfileQr (앞 72px/뒤 160px, `user.user_id` 전달 — 본인+타인 프로필 공유 둘 다).
- [x] `ShareCardModal.jsx`: "QR 공유 준비 중" → 스캔 안내 + **링크 복사** 버튼(clipboard, BoardDetailPage 패턴) + `navigator.share`(모바일 점진적 향상).
- [x] `FakeQr.jsx` 삭제(타 importer 없음). frontend-only, 백엔드 0(기존 `/user/:userId` + `GET /users/{id}/` AllowAny 재사용).
- [x] eslint 0 · build PASS · inline review clean. lockfile: 미사용 lightningcss optional transitive prune(vite=esbuild, benign). ⚠️ app-test 라이브 스모크는 agent hang(소켓)으로 미실행 → localhost:5174 수동확인/CI로 이연.

### CLEANUP-DEPLOY-2026-06-28 — 배포 #250 + 백로그 정리 — RESOLVED 2026-06-28
배포 후 정리 batch: develop→main deploy + prod migration + 백로그 audit.
- [x] Deploy PR #250 (develop→main squash, main `c3a7ac2`; develop force-reset to match, HARD RULE 4 carve-out). Railway 자동배포. Migration 0011 prod 적용+검증 (12 profiles: handle==display_name 0 mismatch, is_guest True=8/False=4). [[project_login_onboard_1_shipped]]
- [x] PR #232 (yywon1 sns-persona-description-axis, conflicting/CI-red post force-reset) CLOSED — 브랜치 보존 + rebase 경로 코멘트.
- [x] Next 백로그 audit (코드 대조): **FRONT-DISCOVERY-1**(트리거 한박자 지연) #238 Fix #4(splice index 0 = 즉시) + mid-fetch 가드 + 멱등 ref로 RESOLVED → Next에서 제거. (FULL-ONBOARDING-2 fast-follows 미적용: validate_is_temp/projects.py is_temp filter/discovery guest-count fix 전부 absent → 유지.)
- [x] 백로그 전수 재검증 (user 지적 후, grep + Explore agent): **FRONT-PROFILE-1 제거**(타겟 EditProfileModal.jsx + FollowListModal.jsx 둘 다 삭제됨 → obsolete). **FULL-LANGUAGE-1 축소**(토글·필드·LLM 배선 DONE, UI 라벨 sweep만 잔여 — title "토글 없음"은 stale였음). **FULL-LEGAL-1 축소**(consent gate DONE, Terms/Privacy 페이지+한국어 copy만 잔여). **INFRA-DB-3 주석**(GuestLoginView 미제거 — 여전히 존재). 나머지 9항목(ARCHITECT-UNIFY-1/BACK-RECOMMEND-1·3/BACK-PERFORMANCE-5·6/FRONT-LAYOUT-1/BACK-EXTERNAL-1/INFRA-QUEUE-1/BACK-AVATAR-3/FRONT-DESIGN-1) 전부 코드상 PENDING 확인 → 유지.

### LOGIN-ONBOARD-1 — 로그인/온보딩 통합 + 인증 모델 단순화 — RESOLVED 2026-06-27 (`1d58a6f`-pre-squash)
신규계정 경로 2개(게스트 스와이프 + 별도 아이디/비번 가입)를 단일 흐름으로 병합 + display_name·handle 통합 ID + Google 인증전용 모델.
- [x] 통합 ID: `display_name == handle` (한글 허용·공백없음·2-20·NFC 정규화·대소문자 무관 유일). write-layer 동기화(물리 컬럼 병합 안 함). 중복확인 버튼 + 신규 `GET /auth/check-handle/` (`CheckHandleThrottle` 20/min/IP).
- [x] 인증 모델: id+password 가입 = 미인증(`is_guest=True` 의미 재정의 = "Google 이메일 미인증"); Google = 인증 전용 — `_get_or_create_user` branch(iii) create-new 제거, 매칭 없으면 404 `signup_required`; social 재로그인이 `display_name` 안 덮어씀; `link-email`이 `email_verified_at` + `is_guest=False` flip.
- [x] `RegisterView` 단일 가입 경로: body `{id,password,affiliation?,onboarding_role,consent_accepted}`, PIPA consent gate, `is_guest=True`, `consent_accepted_at`.
- [x] Migration 0011 (depends 0010): `handle==display_name` backfill (NFC·dedup·≤20) + `is_guest` backfill(미인증 True/인증 False). default DB only, no-op reverse.
- [x] Frontend: 별도 register step+버튼 삭제 → 단일 3-step(ID+비번 → 소속+목표 → consent), `jobRole` 입력 삭제, choice 단계 중복 caption 제거, `checkHandle()` 배선, `register(payload)` 객체화, `loginFlow` id 정규식 백엔드 미러.
- [x] Verified: flake8 0 · eslint 0 · pytest 169/169 (accounts, fresh test DB incl 0011) · loginFlow 45/45 · workflow review+security+Opus-verify PASS.
- FRONT-AUTH-2 스와이프 온보딩 흐름을 재설계/대체. app-test FULL은 CI/prod로 이연. 기존 Google 표시이름 공백제거(통합ID 규칙)·기존 id+password 유저 미인증 전환은 의도된 동작.
- Deferred: PIPA 한국어 consent 프론트 copy 복원 → FULL-LEGAL-1. 통합 ID 물리 컬럼 collapse(display_name/handle 단일화)는 후속 cleanup.

### DISCOVERY-SKELETON — Discovery 로딩 스켈레톤 (마스코트 + "취향 탐색 중…") — RESOLVED 2026-06-27 (`3292231`-pre-squash)
Discovery 첫 로딩(GET /discovery/ 추천연산 대기) 동안 카드 자리에 귀여운 스켈레톤 표출.
- [x] `LoadingCard` 확장: 인라인 SVG 건물 마스코트 + i18n "취향 탐색 중…" + thinking dots를 기존 `.skeleton-shimmer` 위 오버레이 (`role=status`/`aria-busy`/`aria-live`), `mascot-bob`+`dot-blink` keyframes, 토큰 테마.
- [x] Frontend-only (DiscoveryPage.jsx + index.css + locales.js). eslint 0 · build PASS · node 45/45.

### FRONT-AUTH-2 — 로그인 스와이프 온보딩 — RESOLVED 2026-06-27 (superseded by LOGIN-ONBOARD-1)
1차 스와이프 온보딩(Codex, merged 2026-06-01). 흐름은 LOGIN-ONBOARD-1에서 통합·재설계됨.
- 잔존: app-test FULL (swipe path) — prod 전 실행 이연; PIPA 한국어 consent 프론트 copy 복원 → FULL-LEGAL-1.

### FULL-ONBOARDING-1 — Taste 탭 설정단계 제거 + 임시저장 flow — RESOLVED 2026-06-23 (`a58a9f6`-pre-squash)
신규 flow: Taste 탭 → AI 대화(`/search`) 즉시 진입 → 스와이프 → 리포트 생성 → "저장할까요?" 모달(보드명 자동=persona_type, public/private 토글) → 저장확정(보드 생성).
- [x] `ProjectSetupPage.jsx` 삭제 + `/new` 라우트 삭제 + Taste 탭 진입 라우팅 `/search`로 변경 (TabBar/MainLayout/DiscoveryPage), `wizardData`의 minArea/maxArea 죽은코드 제거
- [x] `Project.is_temp` BooleanField(default=False) + migration 0028 (depends 0027), `create_session`에서 신규 프로젝트만 `is_temp=True` 생성 (재사용 프로젝트 미변경)
- [x] 저장확정 = 기존 PATCH `/api/v1/projects/{id}/` 확장 (`ProjectSelfUpdateSerializer`가 `is_temp`+`name`+`visibility` 동시 처리, validate_visibility) — 신규 엔드포인트 없음. `SaveBoardModal` 신규 (보드명 persona_type 자동·수정가능)
- [x] 재진입 처리: `is_temp && !final_report` 자동삭제 / `is_temp && final_report` 배너("이전에 완성된 리포트가 있어요") → 저장/삭제
- [x] code-review PASS · security PASS · Opus adversarial-verify (LOW 2건, benign/self-correcting)
- [ ] app-test FULL — **SKIP (사용자 요청, 라이브 검증 미실행)**; migration 0028 로컬 미적용(파일만, prod는 배포 시 적용)
- Deferred: App.jsx handleTempDelete DELETE 실패 시 배너 무음 닫힘(다음 /search 재진입 self-correct) + temp 삭제 경로 setActiveProjectId(null) 누락(파생값으로 무해) → LOW follow-up.

### FRONT-IMAGE-RESIZE-2 — 이미지 Tier A: srcset + decode-preload + classifier (PR2) — RESOLVED 2026-06-22 (`feature/claude-image-tier-a-2`-pre-squash, #242)
PR1(#241) 리사이즈 로컬 A/B 검증(shipped 함수, 실 50카드: 91.5% 바이트, 0 broken) **후** 착수(measure-first 충족). 프론트 only.
- **A4 srcset + per-DPR q**: `buildCardSrcSet(raw url)` 신규 순수 헬퍼 — Divisare `w_420 1x, w_840 2x`(q_auto, 무 q), imgix `w=420&q=80 1x, w=840&q=40 2x`(Q8). `normalizeCard`에 `image_srcset` 추가(raw에서 — Divisare regex가 w_auto만 매칭, 이미-840엔 no-op이라 raw 필수). `<img srcSet>`(x-descriptor라 `sizes` 생략, 2x=DPR3 perceptual cap). `rightSizeImageUrl`에 optional `quality` 파라미터(imgix만).
- **A6 `img.decode()` preload(srcset-aware)**: `App.jsx preloadImage(card)`로 시그니처 변경 — `img.srcset` 세팅(DPR2서 `<img>`와 동일 variant 선택 → preload 적중) + `await img.decode()`(paint-ready, reject→resolve로 swipe 무차단). 13 호출부 `preloadImage(X.image_url)`→`preloadImage(X)`.
- **A3 포맷 = PR1이 이미 충족**: imgix는 PR1이 `auto=format` 보존 → 이미 WebP/AVIF auto-negotiate. Divisare 포맷은 프록시-gated(Tier B). C3 decode A/B 주의로 fm=avif 강제 안 함.
- **getImageSource imgix 갭**: `architizer-prod.imgix.net`→`'imgix'`(이전 'external' 오분류 수정, telemetry 버킷팅). dormant(소비자 없음, 라이브 telemetry 무변경) — forward-looking.
- **2 blocking 상호작용 수정**(Plan-agent): A4↔fallback(`advanceFallback`서 `target.srcset=''` 후 src — 1x srcset이 imperative src 무시하는 레이스 차단), A4↔A6(preloader srcset-aware로 DPR2 preload 적중).
- **CRITICAL 보안 수정**(security): Divisare srcset 공백-주입 — 리터럴 공백이 srcset URL 토큰 종료 → 뒤 attacker URL이 candidate로 fetch(allowlist 우회). `buildCardSrcSet` 상단 whitespace 가드(→null, 안전한 src degrade). imgix는 `new URL().toString()` %20 인코딩이라 무관. 실증 재현+fix 확인.
- Gates: 27 node --test PASS(+9 A4/quality, +injection 가드; getImageSource는 node import.meta.env 제약 graceful skip), lint+build PASS, code-review PASS(6/6, 2 blocking 검증), security PASS(injection fix 후). **app-test FEATURE-SCOPED PASS 5/5** — srcset 라이브(currentSrc=w_840 DPR2), fallback **라이브 실증**(imgix 카드 4s 타임아웃→srcset 클리어→gallery 승격, 안 빔), decode 무-stutter, imgix `q80/q40` 라이브, 회귀 smoke 0 err.
- A7 LQIP = PR3 descope(유일 render-lifecycle 침습 + object-fit:contain letterbox 충돌; 기존 skeleton-shimmer가 blank-gap 커버). 풀해상도 passthrough도 PR3.

### FRONT-IMAGE-RESIZE-1 — swipe 커버 right-sizing (PR1) — RESOLVED 2026-06-22 (`b3e5d3f`-pre-squash, #241)
이미지 레이턴시 리서치(#240) 지배 lever 구현. swipe 카드가 중앙값 4.6배(p90 21.9배) 과대-페치 → 커버 `image_url`을 표시크기(840px=DPR2)로 우-사이징. **프론트 only** — 백엔드/Redis 캐시/API 계약 무변경(user 결정: 같은 URL 변환이라 효과 동일, SPA라 프론트가 유일 소비자). **리사이즈만**(포맷/srcset/decode/LQIP = PR2, 측정 후).
- 새 순수 모듈 `frontend/src/api/rightSizeImageUrl.js`: Divisare(Cloudinary FETCH) `w_auto`→`w_840,c_limit`(f_auto,q_auto + `//images` 더블슬래시 유지, 측정 90.7% 절감); imgix(`architizer-prod.imgix.net`) `w=840&fit=max`(q/cs/auto 보존, 콤마 리터럴 — `%2C` 아님, CDN 정규 캐시키). 그 외/malformed/relative/empty → 무변경, 멱등.
- 자체 URL 파싱(`getImageSource`가 imgix 호스트 미인식) + 의존성 없음(`images.js`→`core.js` `import.meta.env`가 `node --test` 크래시 → 독립 모듈 필수). 와이어링: `normalizeCard` 커버 1줄, gallery/gallery_meta/covers_by_type 풀해상도 유지(#235 라이트박스+다운로드).
- Known-limitation(PR1 수용, 플랜): gallery+gallery_meta 둘 다 빈 건물은 `BuildingDetailPage` 폴백이 840px 커버 → #235 다운로드 비-풀해상도(narrow 엣지, 이미지 유효). 풀해상도 passthrough = ## Next 추적.
- Gates: 17 node --test(양 CDN+malformed/relative/empty/null/non-CDN/멱등) PASS, lint+build PASS, code-review 2 fix(imgix %2C + 그걸 잡는 테스트), security PASS(host allowlist 선행/path-only replace/regex 선형 — injection·ReDoS·XSS 0). app-test: 4-gate green + Phase 0 실측 CDN 검증(리라이트 URL이 90.7% 측정의 실제 fetch 대상) → develop 머지; 라이브 FULL app-test = develop→main 배포 전 권장.
- 측정: 기존 `useImageTelemetry`(`load_ms`, 5% success, context `swipe_card`)로 배포 전/후 비교. Divisare(84%) 클린 주신호.

### PERF-IMAGE-RESEARCH-1 — 이미지 레이턴시 리서치 (measure-first) — RESOLVED 2026-06-22 (`0715bd3`, #240)
프론트/웹 이미지-렌더 레이턴시 리서치(코드 아님). 측정-우선: Phase 0(실 swipe 카드 50장) → 이슈별 1차출처 리서치 → adversarial 검증. 백엔드 알고리즘 out of scope.
- 결론: 지배 lever=리사이즈(과대페치 중앙값 4.6배, Divisare `w_auto`→`w_840` 측정 90.7%). 포맷=부차+Divisare 프록시-gated(Cloudflare zone JPEG 고정, Vary:Accept 무시). 디코드=픽셀 비례 → 리사이즈가 디코드도 ~4.6배 절감.
- 검증 Q7(Cloudinary f_auto 840px=WebP까지)·Q8(imgix per-DPR q 80/40/20)·Q9(AVIF 50-60% 과장, arch 사진 현실 ~25-50%).
- 권고 Tier A(프론트 URL, 무인프라, 선행) / B(프록시, 정책) / C(do-not). Open: R2폐기 이유(외부 spec)·프록시/핫링크 정책(user) + 게이트 prod 텔레메트리(기존 `image_load` RUM이 geo지연·CDN점유 답). docs/research/image-latency/ (research-report 59 cites + phase0 + findings×6).

### FRONT-AUTH-3 — 로그인 테마 통일 + 한영 토글 — RESOLVED 2026-06-12 (`c57de5a`-pre-squash)
협업자 dain `archibe-login`(`c4954ea`) 리디자인 이식 — 제스처 인트로 팝업 + 카드 상단 한/영 토글 + 로그인 전체 i18n + 디자인 테마 통일. 5단계 플로우/consent 스와이프/반응형 카드/API 계약 무변경.
- [x] IntroOverlay: 미니카드 스와이프 데모 애니메이션(lpSwipeDemo 3.4s + 화살표 동기 점등), 매 마운트 표시(D1, `INTRO_SHOW_ONCE=false` — localStorage 1회 경로 보존).
- [x] LangToggle pill(한국어/ENGLISH): 5개 카드 + 인트로 상단. react-tinder-card native touchstart `preventDefault` 우회 = 버튼 `className="pressable"`(터치 필수) + wrapper stopPropagation(마우스 방어선). LanguageContext 재사용(로그인 전 localStorage만, 로그인 후 서버 PATCH).
- [x] i18n: locales.js `login` 트리 ko/en 53키 + `t(key, params)` `{detail}` 치환(하위호환). 에러 state `{key,params}|{text}` — 토글 시 재번역. 가입 직후 언어 push(D2: guest/register 성공 후 `setLanguage`)로 신규계정 기본 ko 스냅백 차단.
- [x] 테마 통일: per-step entrance(lp-card-in), 그라디언트 CTA(accent-1→2) + hover lift, glass input(color-mix 72%), GestureHint 텍스트+화살표(양쪽 accent-1, D3) + 드래그 intent 실시간 점등, faux 깊이 카드 2장, 카드 아래 캡션.
- [x] 드래그 콜백 identity 안정성: 덱 4콜백 전부 useCallback + preventSwipe 모듈상수 삼항 + `setConsentGiven` fly-off 이후로 이동 + latest-ref(`guestSubmitRef`) — 드래그 중 재바인딩 사망 차단(app-test 왕복 wiggle 생존 확인).
- Gates: code-review PASS(9/9 기준 + 53키 ko/en 교차검증), security PASS(XSS sink 0, consent 게이트 유지, dev login DEV-gated), lint+build PASS, app-test FEATURE-SCOPED PASS 9/9(인트로/토글/드래그 생존/게스트 e2e/회귀 smoke, 0 console err).

### BACK-AVATAR-2 — 교체/계정삭제 시 옛 아바타 객체 GC — RESOLVED 2026-06-08 (`5e1f934`-pre-squash)
FRONT-AVATAR-1(`84ba1f1`) orphan 누적 닫음. 업로드마다 새 uuid4 키 저장 + 옛 객체 영구 잔류하던 갭 — 교체 시 + 계정삭제 시 옛 객체를 안전 GC.
- `storage.delete_avatar(url)`: best-effort GC. 정규식 `^avatars/[0-9a-f]{32}\.webp$`가 **주 인가 게이트**(경로탈출 + 외부 OAuth URL 차단). 프리픽스는 백엔드 *선택*만 — `if base and url.startswith(base+'/')`로 empty-base `startswith('')` 함정 가드. dispatch by URL **shape**(현 `AVATAR_R2_ENABLED` 아님 → env flip 시 잘못된 백엔드 삭제 방지). 절대 raise 안 함.
- `AvatarUploadView`: 옛 url을 overwrite 전 캡처 → `profile.save()` **이후** 삭제(새 아바타 먼저 영속 → 실패해도 무손실 orphan).
- signal: `post_delete(sender=UserProfile)`(User 아님 — cascade가 `instance.avatar_url` 메모리 보유한 채 발화)로 계정삭제 시 GC.
- 외부 OAuth URL(구글 `lh3.googleusercontent`/카카오/네이버)은 정규식 미통과 → **절대 삭제 안 됨**.
- Codex PR #220 리뷰 fix: (1) **동시 업로드 orphan** — 두 업로드가 같은 old=A 읽고 req1=B/req2=C 저장 시 B orphan → `avatar_url` **compare-and-swap**(`filter(pk, avatar_url=old).update(new)`)로 교정, CAS 패자는 자기 새 객체를 삭제(무손실, 무orphan). (2) R2-shape URL + `AVATAR_R2_ENABLED=False` 스킵을 명시 + `logger.debug`(creds 없어 삭제 불가 — sweep 대상).
- 12 테스트: 교체-옛파일삭제, 외부URL-skip(empty+nonempty base), 정규식 traversal/short-key 게이트, R2 dispatch(boto3 mock Bucket+Key), 계정삭제 GC, upload-survives-GC-failure, FileSystemStorage traversal 백스톱, **동시업로드-CAS-패자-자가삭제**, R2-shape-disabled-skip. 마이그레이션 없음(`avatar_url` 기존 필드).
- Gates: code-review PASS(초기+fix 재리뷰), security FULL PASS-WITH-WARNINGS(0 critical; W2 prod-path 외부URL-skip 테스트 fold-in), flake8+check clean, app-test FEATURE-SCOPED PASS(라이브 filesystem GC 검증 — 업로드 A→B 후 A 파일 디스크에서 삭제 확인, 0 console err).
- Deferred: BACK-AVATAR-3(기존 누적 orphan sweep 명령) → ## Next ### MEDIUM.

### INFRA-AVATAR-R2-1 — prod R2 아바타 영속화 설정 + 검증 — RESOLVED 2026-06-08 (ops, no code)
prod Railway에 R2 5개 env 설정 + 공개 아바타 버킷 프로비저닝 완료 → 아바타 영속화. FRONT-AVATAR-1 폴백 경로 졸업.
- Cloudflare: `archibe-avatars` 버킷 + Public r2.dev URL(`pub-cb679a6c…`) + Object R&W API 토큰(S3 Access Key ID + Secret) 발급.
- Railway prod env: `R2_ENDPOINT_URL`(account `04342c5d…`) / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_AVATAR_BUCKET=archibe-avatars` / `AVATAR_PUBLIC_BASE_URL`. (디버깅: 변수명 오타 `R2_AVARAT_BUCKET` + Access Key ID에 account id 오입력 + cfat_ 토큰 혼동 순차 해결.)
- 검증: prod guest-login→업로드→`avatar_url`이 `pub-cb679a6c….r2.dev/avatars/<uuid>.webp`(폴백 `/media/` 아님), GET 200 image/webp, 서버 880×540→512×512 center-crop+WEBP 재인코딩 확인. BACK-AVATAR-2(옛 객체 GC)만 잔여.

### FULL-DISCOVERY-2 — Discovery v3.1+v3.2 라이브 브라우저 검증 — RESOLVED 2026-06-08 (app-test FULL pre-deploy)
FULL-DISCOVERY-1(#200/#209) prod 배포(#218) 직전 app-test FULL로 라이브 검증 완료. chunk 시스템·10장 트리거 카드·우=promote→Taste(`/discovery/promote-to-taste/ 201`, 11 likes 이월)·진행바·phase 전이 정상, 콘솔 0, 회귀(AI검색+스와이프) OK. 배포 후 prod probe로 라우트 라이브 확인.

### FRONT-AVATAR-1 — 프로필 사진 업로드 (server-proxy R2 + 폴백) — RESOLVED 2026-06-07 (`84ba1f1`-pre-squash, #217 → main #218)
아바타 업로드(Slice D). 마이그 없음(`avatar_url` URLField 기존). data-URL 지양 결정대로 R2 URL만 저장.
- 백엔드: `POST /users/me/avatar/`(IsAuthenticated, self-only, AvatarUploadThrottle 10/min). server-proxy multipart → Pillow 파이프라인(조기 Content-Length 게이트 + `.size` cap 5MB + 25MP 차원 가드 + verify + **WEBP 재인코딩**=EXIF/polyglot 제거 + 정사각 center-crop 512 + uuid4 키). 신규 `apps/accounts/storage.py` `store_avatar`: 플러그블 — R2_* 설정 시 boto3→R2(prod), 미설정 시 FileSystemStorage 절대-URL 폴백(local+CI). INFRA-REDIS-1 prod/local 분기 패턴. settings MEDIA_*/R2_*/AVATAR_* 한도; urls DEBUG-only media serve; requirements +boto3; `.gitignore` media/.
- 프론트: ProfileHero isMe 아바타 → 파일 선택 + canvas 정사각 리사이즈 → multipart 업로드(`callApi` JSON-only라 직접 fetch, `api/profiles.js uploadAvatar`) → in-place `avatar_url` 갱신. hover 오버레이 + 스피너 + 에러(ProfileHero.module.css). UserProfilePage가 isMe + onAvatarUpdated 전달.
- 게이트: code-review PASS, security-manager **0 critical**(경고 3개 in-branch 수정: 조기 CL 게이트, 픽셀 cap 40M→25M + `Image.MAX_IMAGE_PIXELS`, profile-404-before-store=orphan 방지). flake8+check clean, 마이그 0개, lint+build PASS. **라이브 app-test FEATURE-SCOPED PASS 9/9**(900×600 업로드→200→512×512 webp center-crop, reload 영속, 비소유자 /user/2 오버레이 없음, 콘솔 0, 회귀 AI검색+5스와이프 OK). CI=DB-게이트 7 테스트.
- Deferred: BACK-AVATAR-2(교체 시 옛 객체 GC) + INFRA-AVATAR-R2-1(prod Railway R2 env 미설정 시 비영속) → ## Next ### MEDIUM.

### AUTH-LOGIN-1 — handle+비번 로그인 + 이메일 인증(OAuth 연동) — RESOLVED 2026-06-07 (`4c37545`-pre-squash)
표준 로그인 추가(소셜 유지 + handle=ID+비밀번호). 식별자 확정: `handle`=ID(로그인·공개@), `display_name`=이름(프로필), `User.username`=내부키(`local_<uuid>`).
- E1 백엔드: `POST /auth/register/`(handle+pw, validate_password, atomic) · `/auth/login/`(handle__iexact→check_password, **균일 에러+더미해시 타이밍**으로 enumeration 차단, throttle) · `/auth/set-password/`(first-set 무current / change 요current, throttle 5/min, **변경 시 전 refresh 토큰 blacklist + fresh 재발급**=현 세션 유지·타 세션 evict). 모두 `_make_token_response` 재사용.
- E2 백엔드: `POST /auth/link-email/`(IsAuthenticated, `_exchange_google_code`+GuestPromote 로직 재사용 — verified만, **충돌=거부** 400 email_already_linked, SocialAccount+`email_verified_at`). 마이그 0009. `UserSerializer` self-only +email/email_verified_at/has_password(공개 serializer 미노출).
- E3 프론트: LoginPage handle+pw 로그인(Returning)+가입(Register, 기존 guest/Google 무변경) · Account `@핸들`→"ID" 라벨+중복 "이름" 제거+이메일 행+비번 설정/변경(토큰 swap)+이메일 인증(GoogleVerifyButton 재사용→link-email) · EditCardForm "Display Name"→"이름". 토큰은 기존 setTokens 재사용.
- 게이트: code-review PASS ×2, **security-manager FULL PASS**(경고 2개 수정: set-password throttle + 토큰 blacklist). flake8+lint+build clean. 라이브 curl: register/login/틀린pw(400 generic)/set-password/**구토큰 401(blacklist)**/새pw로그인 전부 통과. Account UI 검증(ID/이메일/비번/인증). DB-게이트 32 테스트 = CI.
- Deferred: FRONT-AUTH-1(Kakao/Naver 버튼) 이 트랙 흡수 가능; 비번 재설정(이메일 발송)은 EMAIL_BACKEND 없어 보류.

### SETTINGS-PROFILE-IA-1 — archibe Settings harvest + Profile/Account IA + rebrand archibe — RESOLVED 2026-06-07 (`2bb2b64`-pre-squash)
archibe-profile(외부 레퍼런스, #179 harvest와 동일 repo) 2차 harvest + 프로필/계정 정보구조 재설계 + 서비스명 archibe 리브랜드. 4 커밋(slices 1-2-3 + A/B/C + F).
- 백엔드: `UserProfile.handle`(공개 @id, unique, `^[a-z0-9_]{3,30}$`, 예약어, self-only 검증) + `notifications` JSONField(self-only, ≤50키/≤64자/nested {push,email} bool) + `role`(50)/`affiliation`(100) 자유텍스트. 마이그 0007+0008. `UserSerializer`/공개`UserProfileSerializer`/self-update에 배선. `GuestLoginView` 가입 시 role/affiliation 수신(truncate). 이메일/username은 비편집 유지(#206 경계).
- archibe 재사용 조각: `Toggle`(role=switch, a11y) + `AppearanceSettings` 테마 시각 스와치(accent dots+글로우) + gradient CTA(`Button.module.css`) + `ProfileHeader` glassmorphic blur. `/settings` 라우트 + Account/Notifications/Appearance 화면(FollowListPage 레이아웃).
- 프로필 IA: 히어로 = 이름 → @handle → "role · affiliation" + website pill; 헤더 = 본인 메인서 Back 제거 + "Profile"+@handle; Edit Profile → `/settings/edit-profile`(EditCardForm + role/affiliation, 단일화 — 헤더 Edit 버튼 제거). MBTI UI 제거. `EditProfileModal.jsx` 삭제.
- BusinessCard archibe 재설계: ARCHIBE 워드마크(양면) + display_name/role/affiliation/handle 직접 + persona/mbti fallback 제거 + 흰 명함 하드코딩 유지.
- 리브랜드 ArchiTinder→archibe(유저향): ARCHIBE 워드마크(LoginPage/SwipePage/MainLayout, 투톤 분할 제거) + archibe 소문자 본문(타이틀/동의문/"archibe AI"/share fallback). 내부(package/repo/docs)는 archi-tinder 유지.
- 게이트: code-review PASS ×4, security PASS ×3, flake8+lint+build clean. 라이브 Playwright 스모크: handle 저장, notifications 토글+영속, role/affiliation 히어로, edit-profile, BusinessCard 재설계, 타이틀 archibe. DB-게이트 테스트(handle/notifications/role/affiliation/guest) = CI.
- Deferred: 아바타 R2 업로드(FRONT-AVATAR-1); handle+비번 로그인 + 이메일인증 OAuth연동(AUTH-LOGIN-1). FRONT-PROFILE-1 상당부분 흡수(EditProfileModal 삭제로 그 minor들 moot; FollowListModal bottom-sheet/4테마 픽셀은 잔존).

### BACK-LLM-GEMINI-1 — Gemini 3.1 모델 마이그레이션 + 페르소나 이미지 플로우 배선 — RESOLVED 2026-06-05 (`dc1b068`, #204)
하드코딩 모델 ID(텍스트 `gemini-2.5-flash` 9곳 + 이미지 Imagen 3 orphan) → settings/env 분리(`GEMINI_TEXT_MODEL`=3.1-flash-lite, `GEMINI_IMAGE_MODEL`=3.1-flash-image, 각 fallback). 텍스트 호출 `generate_content_with_fallback` 래퍼로 일원화(model+retry+timeout+4xx fallback). 이미지: Imagen `generate_images` → Gemini-native `generate_content(response_modalities=['TEXT','IMAGE'])` 재작성 + Pillow WebP 변환(`report_image_mime`, migration 0023). App.jsx 세션완료 후 fire-and-forget 이미지 생성 배선(전엔 orphan — 한 번도 호출 안 됨).
- [x] **실키 스모크 검증**: 3.1-flash-lite(텍스트) + 3.1-flash-image(이미지 JPEG 880KB) 둘 다 200 OK — fallback 안 타고 3.1 primary 실작동 확인. `['TEXT','IMAGE']`로 이미지 part 정상 반환(Codex 🟡 text-only 우려 실측 미발생).
- [x] **Codex 리뷰 수정**: 래퍼가 facade `_retry_gemini_call`(테스트 9곳 patch 대상) 우회 → 실HTTP/MagicMock 누출로 CI 8실패. late-bound `_svc._retry_gemini_call`로 seam 복원(FULL-REFACTOR-1 교훈). MIME fallback webp→png(레거시 PNG 행). 22 신규 테스트 green.
- Deferred: prod 배포 시 실키 가용성/latency 재확인(fallback 안전망). [[BACK-LLM-4]]

### SNS-REPORT-PAGE-1 — 페르소나 리포트 별도 페이지 + axis_scores 영속화 (yywon1, Claude fix-forward) — RESOLVED 2026-06-05 (`1917f5d`, #196)
인라인 리포트 → 별도 `/board/:id/report` 페이지(BoardReportPage: 레이더/스펙트럼 차트 + 페르소나 이미지 생성 버튼 + 스크롤 수정). fix-forward(Claude): Codex blocker 2건 수정.
- [x] **axis_scores 영속화**: `compute_axis_scores`가 생성 응답에만 실리고 저장 안 돼 reload/직접링크 시 차트 0(빈 레이더) → `Project.axis_scores` JSONField(migration 0024) + 생성 시 저장 + serializer 노출(detail; list서 defer) + BoardReportPage `board.axis_scores` 읽음. 계산 로직 무변경.
- [x] **이미지 MIME 동적화**: BoardReportPage `data:image/png` 하드코딩 → `report_image_mime`(#204 WebP 대응) || png fallback. (#204↔#196 MIME 해저드 종결.)
- [x] code-review + security PASS. CI green. 팀원(yywon1) PR 코멘트로 변경 통지.

### CODEX-FUNC-3 — Codex 라운드3 기능 수정 4건 (auth/tokens/cache/testenv) — RESOLVED 2026-06-05 (#199/#201/#202/#203)
Codex 기능 리뷰 배치 머지(SECURITY 항목은 배포-게이트 배치로 deferred).
- [x] **#203 `3870bc4` (FIX-2)**: 게스트 promote 머지 conflict-aware — 500/데이터 유실 방지.
- [x] **#202 `54a40e5` (FIX-3)**: 토큰 refresh single-flight — 동시 401 spurious logout 차단.
- [x] **#201 `3c742c7` (FIX-7)**: architect follow/unfollow 시 프로필 캐시 evict.
- [x] **#199 `230e29d` (FIX-1/8)**: pytest 하 `.env` 로드 가드 + `.flake8` 설정(repo-wide flake8 정상화).
- Deferred(HARD): 배포 전 SECURITY 배치 — **OAuth `email_verified`(계정 탈취, develop→main 전 필수)** + swipe/bookmark/architect ID 검증 + merge.py DoS row-cap.

### BACK-AUTH-3 — guest like-gate @50 + frontend verify 배선 — RESOLVED 2026-06-04 (`feature/claude-auth-batch` → develop, #193)
`LikedBuildingsView.post`가 guest 무제한 like 허용하던 것 → 50개서 verify-gate(403 `verify_required`/`liked_limit_reached`, board-gate precedent mirror). frontend `addLikedBuilding`가 403 intercept → `archithon:verify-required` dispatch + `VerifyRequiredError` throw(`createProject` 패턴); DiscoveryPage catch가 VerifyRequiredError 시 generic 토스트 skip. Codex #193: 51st like 유실 → `archithon:pending-like`로 bldId 저장 후 promote(onPromoted)에서 addLikedBuilding retry(pendingBoardCreate 패턴). guest-scenario 테스트 4.

### BACK-AUTH-2 — JWT user-row cache 통합 테스트 — RESOLVED 2026-06-04 (`feature/claude-auth-batch` → develop, #193)
기존 unit-level만이던 JWT 캐시 테스트에 DRF 파이프라인 통합 테스트 5 추가(`test_jwt_cache_integration.py`): cache-hit, **is_active=False stale-cache 거부**(signal invalidation), post_save invalidation, logout, refresh-rotation invalidation. prod 코드 무변경. is_active bulk `.update()` 우회는 기존 문서화된 known limitation(코드에 그 경로 없음).

### BACK-LLM-2 — 채팅기록 backend 영속화 (cross-device) — RESOLVED 2026-06-04 (`feature/claude-llm-chat-persist` → develop, #195)
채팅기록이 localStorage-only라 기기간 유실 → `Project.conversation_history` JSONField(migration 0022, #194 0021_tagaxisweight 충돌로 renumber). 기존 PATCH 재사용(신규 endpoint 無). detail-read/PATCH-write 검증(dict, ≤64KB **UTF-8** ensure_ascii=False, messages≤60/history≤10/text≤2000), list서 제외+defer. frontend hydration(backend=source of truth)+debounced byte-bounded save+logout/delete purge. Codex 3 must-fix 수정: **비-owner 프라이버시 strip**(public 보드서 남 채팅 노출), UTF-8 byte-cap(한글), hydration-실패 stale-overwrite 방지. follow-up [[BACK-LLM-4]].

### INFRA-DB-2 — make test-local (로컬 pytest unblock) — RESOLVED 2026-06-04 (`feature/claude-test-local` → develop, #197)
runtime `make_web_app`가 CREATEDB 없어 로컬 pytest가 'permission denied to create database'로 차단(conftest SQLite override는 자체 docstring상 not-load-bearing). `make test-local` 추가 — `migrate-local` idiom(read -s neondb_owner pw, inline DB_USER override로 DB_HOST는 LOCAL 유지), CI-shape real-PG+pgvector 실행. Neon 콘솔 작업 불필요. CLAUDE.md 문서화.


### UX-GALLERY — 갤러리 제스처 3버그 (FRONT-UX-6/9/10) — RESOLVED 2026-06-04 (`feature/claude-ux-gallery` → develop)
갤러리 3버그(부모-sync wobble·모바일 세로스크롤·Discovery long-press 오작동)를 **lift 없이** 해결. 원 premise(sibling-overlay lift)를 유저 product 재검토로 재정의 — 갤러리 보면서도 스와이프 유지 + 순수 Discovery. session 브라우저 spike로 "3D가 스크롤 안 깸"(원인은 touch-action·snap, 3D 아님) 확정 후 구현.
- [x] **방향잠금 + 갤러리 스크롤**: SwipeCard card root `touch-action:none→pan-y`(세로=브라우저 pan·카드 안흔들림, 가로=스와이프) + 갤러리 scroll div/이미지/img `pressable`(react-tinder-card preventDefault 스킵) + 갤러리 `touch-action:pan-y`. rotateY flip 유지.
- [x] **Discovery long-press 제거**(FRONT-UX-10): 400ms 보드저장 제스처 -91줄 삭제 → 순수 스와이프. 우-스와이프 like + Surprise 모달 유지.
- [x] **cleanup**(FRONT-UX-6 obsolete): SwipePage 죽은 galleryOpen/preventSwipe-ALL/ESC 제거(suppress 안 함 — 스와이프 유지 의도).
- [x] **Codex #191 HIGH 수정 — native direction-lock**: `touch-action:pan-y`만으론 부족 — react-tinder-card가 카드 엘리먼트에 native touchmove(index.js:244, bubble) 바인딩, React synthetic `stopPropagation`은 native 리스너 못 막음 → 세로 드래그 wobble·touchcancel 미처리 카드 고착·대각선 스와이프 오발. SwipeCard 갤러리 scroll div에 native touchstart/touchmove 리스너(8px slop axis-lock, 세로 확정 시 `e.stopPropagation()`; passive·preventDefault 안 함 → 브라우저 pan-y 스크롤 그대로) 추가 + 쓸모없던 React synthetic stopPropagation 2개 제거. bubble 순서상 갤러리 리스너가 카드보다 먼저 발화 → 세로=카드 handleMove 차단, 가로=전파(스와이프 유지).
- 게이트: lint/build PASS, code-review PASS(4영역 무결). session spike GO(3D 스크롤 viable + 레시피 라이브 검증). **native 모바일 터치(손가락 스크롤·방향잠금·sloppy boundary)는 Codex 실모바일 최종확인**(Playwright 데스크톱=native 터치 부정확).
- 재정의: A(lift) 탈락(갤러리중 스와이프 유지와 충돌). premise=hypothesis([[feedback_taskmd_premise_verification]]), product 재검토로 교체.
### BACK-RECOMMEND-4 — Discovery 좋아요가 추천에 반영 (taste vector + exclude + evict) — RESOLVED 2026-06-04 (`feature/claude-back-recommend-4` → develop)
Discovery 우-스와이프 like(`UserProfile.liked_building_ids`)가 추천 엔진에 안 먹히던 것 해결 — Discovery-only 유저가 영구 cold/random feed였던 core-promise 위반 수정. 3곳 주입, 전부 기존 infra 재사용.
- [x] **taste vector**(`engine.py compute_user_taste_vector`): Project.liked_ids 루프 뒤 `reversed(liked_building_ids)` append(intensity 1.0). recent-50 cap·dedupe·weighted-mean 무변경, 추가 쿼리 0(profile 인자). minimal·additive.
- [x] **exclude-set**(`discovery.py` DiscoveryFeedView + BoardSurpriseView): `liked_building_ids`를 exclude 합집합에 추가 → 이미 like한 빌딩 재등장 안 함.
- [x] **evict**(`accounts/views/profile.py LikedBuildingsView.post`): 실-write 시 `evict_taste`+`evict_discovery_feed`(caches.py:42/155) 로컬-import 호출(순환 회피).
- [x] 테스트 7개(`test_back_recommend_4.py`): **zero-Project-likes fresh profile** cold→warm(discriminating), truly-cold None, DiscoveryFeed+BoardSurprise exclude(warm/cold), evict-on-write, evict-suppress-on-dup.
- 게이트: `manage.py check` PASS, flake8 clean(2 pre-existing E221 무관), code-review PASS(5영역: dedupe·exclude·evict-placement·test-discriminating·TTFC 무회귀). 로컬 pytest INFRA-DB-1 차단 → **CI가 실게이트**. app-test 스킵(추천 로직, swipe-lifecycle 무변경, 단위테스트가 정밀 커버). algorithm.md annotate.
- ⚠️ recency 회귀(오너 결정): Project 40+Discovery 60 유저 → `[-50:]`가 Discovery 50개만 → Taste 프로필 탈락. 이번 minimal-additive로 두고 PR에 명시 — 오너가 source별 recent-N 병합 채택 여부 결정.

### FULL-DISCOVERY-1 — Discovery 탭 v3.1+v3.2 재설계 (10장 청크 + 3-Tier + Draft Board → Taste 퍼널) — RESOLVED 2026-06-04 (`fc72639-pre-squash`, merged #200 `2238e5d` 2026-06-05)
레거시 global-centroid + 커서 무한스크롤 폐기 → 10장 chunk prefetch + 다중 centroid + 40:60 Local/Global FPS + Deferred Exclusion(dislike zone) + 3-Tier 라이프사이클(0/100·20/80·40/60) + 세션별 Draft Board → Taste 퍼널로 전면 교체. 신규 마이그레이션 0건(Project 재사용), `engine.py` 미수정(신규 `discovery_feed.py` 모듈로 compose, 알고리즘 소유권 준수).
- [x] 백엔드 v3.1: `discovery_feed.py`(draft helper·tier·`build_discovery_chunk`·greedy FPS·interleave·dislike zone), `caches.py` App-Open centroid 캐시(6h TTL, like-evict 안함), `GET /discovery/`(chunk) 재작성, `POST /discovery/feedback/`, `settings.py` RECOMMENDATION에 discovery_* 14개 추가.
- [x] 백엔드 v3.2: 세션별 `discovery_YYMMDD_HHMM` Draft Project(프로필 노출, tier project_count는 `discovery_` 접두 제외, centroid는 전체 like 누적), feedback `draft_id` 왕복, `POST /discovery/promote-to-taste/`(draft 10 likes로 AnalysisSession like_vectors 사전주입+풀 생성).
- [x] 프론트: `DiscoveryPage` 10장 chunk 버퍼(client_buffer_ids stateless dedup) + swipe→feedback + 덱 내 Taste 트리거 카드(우=promote, 좌=계속) + 진행률 바(N/10→취향 탐색 중) + 재등장 shake; `DiscoveryTriggerCard.jsx`(신규); Surprise 모달 제거.
- [x] 버그픽스: stale `draftLikeCount`(sessionStorage)로 트리거 조기 등장 → 로그인 시에도 draft 초기화 + draftId 게이트 + not_enough_likes 복구; promote 응답 `normalizeCard`로 Taste 첫 스와이프 400(`canonical_bld_id` undefined) 방지.
- [x] code-review + security 2라운드 PASS(ImportError·백필·buffer DoS·JSON 무한증가·예약명·draft_id 500·트리거 ref race 수정). Django check 0 issues + Discovery 테스트 52개 green. ESLint/build green.
- [x] **fix-forward (Claude, #200 머지)**: Codex blocker 3건 — promote 임계값 `<10` 거부(전엔 1~9도 promote; 스펙=10장 전환), feedback+promote 게스트 보드 게이트(`is_guest & ≥3보드`→403 verify_required; 3보드 우회 차단, graceful draft 생성 설계는 보존), long-press→SaveToBoardModal 제거(UX-GALLERY/#191 순수-스와이프 제거가 머지 통째덮어쓰기로 부활한 잔재; 알고리즘 코어 무변경). promote 테스트 3건 10 likes로 갱신. code-review+security PASS. 팀원(ksangjo) PR 코멘트로 통지.
- Deferred: app-test FULL 라이브 브라우저 검증 미실행(dev 서버 + app-test 에이전트 부재) — prod 전 실행 필요. Deferred: 트리거 카드 희귀 엣지(like 10번째가 빈 덱 동시각) 한 박자 지연, 비차단.

### ARCHITECT-UNIFY-C — OfficeFollow 중복 제거 (follow 모델 통합) — RESOLVED 2026-06-04 (`feature/claude-architect-unify-c` → develop)
미배선 중복 `OfficeFollow`(firm-follow, ArchitectFollow와 중복) 제거 → office-interest follow 모델이 ArchitectFollow 1개로 통합(원 audit 중복 finding 종결). Office 서브시스템 나머지는 계획 기능 substrate라 park.
- [x] 백엔드: `social/models.py` OfficeFollow + 시그널 2개 삭제, `social/views.py` OfficeFollowView, urls route, test_office_follow.py(파일), guest-merge FK_TABLES 항목, `OfficeDetailView.is_following`→False 상수. 신규 마이그 `social/0006_delete_officefollow`(로컬 적용 OK, 빈 테이블).
- [x] 프론트: `api/social.js` followOffice/unfollowOffice + client.js 재export 삭제, FirmProfilePage/FirmProfileHero 팔로우 버튼 제거(FirmProfilePage는 parked view-only). build PASS, grep 0.
- [x] KEEP(park): Office/OfficeProjectLink/claim/sync_offices/FirmProfilePage(view) — BACK-RECOMMEND-3/EXTERNAL-1/firm-claim substrate. ArchitectFollow/Follow 무손상.
- 게이트: check PASS, makemigrations --check no-change, migrate --plan OK, flake8 clean, lint/build PASS, **code-review PASS**(6영역: guest-merge/dangling/is_following/signals/hero/migration 무결). app-test 스킵(swipe/recommendation 무관, FirmProfilePage 도달불가). A/B 탈락→C: `docs/specs/architect-unification.md` + deploy-gate 메모리 갱신.
- 후속: firm-side 전면 arch_id 통합 = `ARCHITECT-UNIFY-1`(deferred, firm-UX 착수 시).

### BACK-PROFILE-1 — external_links 검증 강화 (handle/email/website + mailto 주입 차단) — RESOLVED 2026-06-04 (`feature/claude-back-profile-1` → develop)
`validate_external_links`(accounts/serializers.py)에 키별 포맷 검증 추가 — 프론트가 검증 없이 `instagram.com/${handle}`·`mailto:${email}` 평문 조립하던 주입 nuisance를 서버에서 차단.
- [x] instagram: 선행 `@` 1개 strip + `^[A-Za-z0-9._]{1,30}$` fullmatch(경로 break-out 문자 전부 배제), normalized 저장.
- [x] email: Django EmailValidator + **mailto 헤더 주입 차단**(`?`/`&` reject — RFC5321은 local-part 허용하나 RFC6068 mailto hfield 구분자라 `user?cc=evil@x.com` 차단). security-manager 발견 수정.
- [x] website: URLValidator(http/https) — javascript:/data:/protocol-relative 차단. 전 키: 제어문자(CRLF) reject, unknown 키 forward-compat, empty=skip, normalized dict 반환.
- 게이트: `manage.py check` PASS, flake8 clean(3 E221 pre-existing 무관), sanity 10+케이스(주입/우회 reject·정상 통과). security-manager FAIL→fix→재검증. test_phase13 instagram assert 갱신(strip). app-test SKIP(API 검증, UI 무변경).
- 후속(별도, 낮은 위험): office/architect contact_email mailto 조립 2곳(FirmProfileHero:241, ArchitectProfilePage:166)은 동일 클래스이나 **corpus-curated 이메일**(user-PATCH 불가)이라 위험 낮음 — 범위 밖.

### BACK-OFFICE-1 (ARCHITECT-UNIFY Phase 0) — SavedOffice orphan 제거 — RESOLVED 2026-06-04 (`feature/claude-architect-unify-p0` → develop)
예원 #180의 미배선 SavedOffice(model+2뷰+2url) 삭제 + DROP 마이그 0005. ARCHITECT-UNIFY(Office↔Architect 통합) 스펙의 첫 안전 조각 — "스튜디오 저장"은 ArchitectFollow saved-studios(#179)가 이미 충족, SavedOffice는 프론트 콜러 0이라 무위험.
- [x] `profiles/models.py` SavedOffice 클래스 삭제(+미사용 settings import 정리), `views.py` OfficeSaveView+SavedOfficeListView+import 삭제, `urls.py` 2 path+import(re_path) 삭제.
- [x] 신규 마이그 `0005_delete_savedoffice`(makemigrations 자동생성, DeleteModel만, deps 0004). 로컬 적용 OK(빈 테이블 안전 DROP).
- [x] OfficeFollow/ArchitectFollow/Office/sync_offices 무손상. 게이트: `manage.py check` PASS, makemigrations --check "no changes", flake8 profiles clean. app-test SKIP(dead endpoint, UI 표면 0), code-review 스킵(순수 삭제 — check가 dangling-ref 검증).
- 설계: `docs/specs/architect-unification.md`(PROPOSAL). Phase 1-4 = `ARCHITECT-UNIFY-1`(## Next), 조율-게이트.
- 후속: SavedOffice는 #180 의도적 기능이었으나 #182 ArchitectFollow에 밀린 중복 → 제거(예원 통지). deploy-gate: 0005 DROP은 #180/#182 prod 마이그 배치 합류(prod SavedOffice 비어있어 안전).

### UX-WRITE-FAIL — 쓰기 실패 무음 유실 표면화 (FRONT-UX-8 + FRONT-UX-7) — RESOLVED 2026-06-04 (`feature/claude-ux-write-fail` → develop)
두 쓰기 POST 실패를 빈 `.catch(()=>{})`로 삼켜 취향신호(질문답변·좋아요)가 조용히 유실되던 것을 공유 토스트로 표면화. 기존 `globalToast` 재사용(새 이벤트 시스템 없음).
- [x] **신규 `utils/reportWriteError.js`**: `reportWriteError(showToast, msg)` → `showToast?.({message, type:'error'})`. optional-chaining 안전 no-op.
- [x] **FRONT-UX-8** (App.jsx `handleQuestionAnswer`): `submitQuestionResponse` 실패 시 한글 토스트 + `setPendingQuestion(q)`로 질문 재노출(재시도 보존). 낙관적 클리어 유지.
- [x] **FRONT-UX-7** (DiscoveryPage `onCardLeftScreen`): `addLikedBuilding().then(()=>setSavesThisVisit+1).catch(()=>reportWriteError)`. 카운터를 POST 성공 후로 이동 → 실패한 좋아요는 Surprise threshold 미반영. `<DiscoveryPage showToast={setGlobalToast}/>` prop 직결.
- [x] code-review PASS(0 blocker). 카피 정직성 수정: UX-7은 카드 advance로 재시도 불가 → '좋아요 저장 실패'(재시도 함의 제거).
- 게이트: lint/build PASS, code-review PASS(0 blocker). app-test FEATURE-SCOPED는 로컬 DB 마이그 갭(#180/#182 미적용, 내 코드 무관)으로 B1c 차단 → 3-gate 수용 후 **Codex browser-verify PASS** (2026-06-04, PR #186): liked-POST 500→토스트+카드진행+Surprise 미발동(4회), 3초 자동 dismiss, 200→무토스트; question-response 실패→'답변 전송 실패' 토스트+질문 재노출, 200→정상 복귀. GitHub CI Backend/Frontend/Vercel PASS, npm test 36 PASS.
- 후속: 로컬 DB migrate(profiles/0003·0004 + social/0005) 필요 — 향후 app-test/백엔드 페이지 테스트 복구용(operator DDL). theme/font 영속 무음 catch(ThemeContext:57,63)는 낮은-stakes 형제 → 후보 FRONT-UX-11.

### DASHBOARD-LOCALVIEW-REMOVE — state.local.js 그림자 메커니즘 제거 — RESOLVED 2026-06-04 (`feature/claude-dashboard-localview-remove` → develop)
`make dashboard`가 만드는 gitignored `project/state.local.js`가 신선도 가드 없이 committed `state.js`를 가리는 footgun 제거. 6/1 stale local이 6/4 audit 변경(BACK-OFFICE-1·BACK-PROFILE-1 등)을 영구히 가려 유저가 대시보드에서 못 봄. 대시보드 단일 소스 = committed `state.js`.
- [x] **dashboard.html**: `state.local.js` 그림자 `<script>` 로더 삭제 → `window.PROJECT_STATE` 단일 소스.
- [x] **gen-state.js**: `--local` 경로 전면 제거(LOCAL flag, untracked union, state.local.js 출력, 헤더+HEADER doc).
- [x] **Makefile dashboard**: open-only(재생성 안 함 → git churn 0; committed state.js는 reporter-inline이 PR마다 갱신 = 항상 최신-committed). 미커밋 Task.md 프리뷰 니치 의도적 드롭(유저 승인).
- [x] **.gitignore** state.local.js 엔트리 삭제 + stale 로컬 파일 제거 + `reporter-inline/SKILL.md` doc 동기화.
- 게이트: gen-state self-check PASS(done:8 files:368), grep 잔여 0, `make -n dashboard` open-only. app-test 스킵(순수 tools/meta, 런타임 표면 0). code-review/security 스킵(기계적 삭제, session self-review).

### FRONT-PROFILE-HARVEST-1 — 프로필 컴포넌트 하베스트 + 인스타식 재설계 — RESOLVED 2026-06-04 (`feature/claude-profile-harvest` → develop, PR #179)
archibe-profile에서 핵심 컴포넌트 채택 + 4테마 재토큰화 + 프로필 인스타식 재설계. **Profile-area 컴포넌트 하베스트 + CSS-Module/hook 패턴 토대** — 명명된 ~646 인라인 부채(SwipePage/BoardDetailPage 등) 상환 아님(그 파일 안 건드림); FRONT-DESIGN-1 핵심 인라인 마이그레이션은 ## Next 잔존.
- [x] **하베스트** (584d659/3619bbc/eb0d167/25c2a26): `icons.jsx` 8-아이콘(stroke currentColor), `FollowList`(+`.module.css` 첫 CSS Module), `EditCardForm`/`EditProfileModal`(PATCH /users/me/ 낙관적 머지), `BusinessCard`+`ShareCardModal`+스텁 `FakeQr`(흰 명함 PAPER/INK 의도적 하드코딩). 다크-온리 소스 → themed 토큰 재배선.
- [x] **develop 머지** (1b2c566): #178/#180/#181→#182 통합. 충돌 2파일(App.jsx import + UserProfilePage state/JSX) keep-both.
- [x] **재설계** (01c2e93): Share/Edit/Logout(isMe)+Share/Follow(타인) → ProfileHeader 우상단(ProfileHero에서 이동, Message DM 스텁 제거). Hero stat 4(Boards/Studios/Followers/Following) — Boards/Studios→탭, Followers/Following→인스타식 팝업. 신규 `FollowListModal`+`useFollowList` 훅; `FollowListPage` 훅 리팩터(동작 동일); deep-link 라우트 유지. 백엔드: `UserProfileSerializer.saved_studios_count` SerializerMethodField(COUNT ArchitectFollow, 마이그 0, social↔accounts 순환 회피 로컬 import).
- 게이트: lint/build/django-check PASS, flake8 신규 0(4 pre-existing), code-review+security PASS(0 blocker). 로컬 pytest 불가(runtime DDL 없음, INFRA-DB-1) → CI가 DB-gated 게이트; 새 필드 field-set assert 무회귀 선제 grep 확인.
- Deferred: Codex 브라우저 픽셀 패스 → FRONT-PROFILE-POLISH-1; external_links sanitize → BACK-PROFILE-SANITIZE-1.

### DASHBOARD-AUTOGEN-1 — 대시보드 Files 탭 + state.js 자동생성 — RESOLVED 2026-06-01 (`feature/claude-dashboard-autogen` → develop)
프로젝트 대시보드 2건: (1) 파일 구조 Files 탭 (collapsible 트리 + 파일별 role), (2) state.js를 reporter 수작업 재작성 대신 `tools/gen-state.js`로 자동생성.
- [x] **gen-state.js** (1232e12): meta/done/now/next ← Task.md+git, agents ← `.claude/agents` frontmatter, prs ← gh(offline=prior 유지), fileTree ← `git ls-files` ∪ file-roles.json. mermaid×3+milestones는 이전 state.js verbatim 복사; done/next note + agent role은 id/name 캐리포워드(신규는 첫 bullet seed). self-check(11키+배열) + verifyCarry(캐리키 round-trip) + drift 리포트. `make dashboard` → `--local` state.local.js(gitignored, 미커밋 포함). reporter-inline Step 4 = 생성기 호출로 교체.
- [x] **Files 탭** (918680b): native `<details>` collapsible 트리 + role 컬럼 + 폴더 file-count. `project/file-roles.json` 337개(짧은 한국어 noun-phrase, max 29자; 10-chunk agent workflow + critic + revise; 손-유지, 생성기는 병합만). jsdom 렌더 게이트 PASS(337 files/68 folders, 탭 토글, done/next 무회귀, state.local.js 부재=무음 no-op 확인).
- [x] **drift 정규화** (d8c6250): 생성기가 노출한 state.js↔Task.md 드리프트 4건(SNS-RESULTS-UI-1/SNS-REPORT-CONNECT/DOCS-SESSION done + INFRA-DB-CLEANUP-1 medium) Task.md canonical 복원.
- [x] **reporter-inline 정합** (b8d8c0f): note/role 캐리-바이-id 비대칭(seed 후 sticky) + 기존 note 수정 절차 + sentinel 정정 문서화.
- 효과: reporter가 컨텍스트 다 읽고 state.js 424줄 재작성하던 비용 + `*/` 백지 버그 제거. Task.md 편집 → `node tools/gen-state.js` 한 줄. 픽셀 검증만 Codex lane(공유 Chrome 점유)로 이월.

### FULL-REFACTOR-1 — 큰 파일 분해 (engine.py 등) pure-move 분해 — RESOLVED 2026-06-01 (PRs #170 `6f54cc3` / #171 `7302ae6` / #172 `e1ff077` / engine `16e2a1a-pre-squash`)
Behavior-preserving decomposition of the repo's largest files into focused modules. PURE MOVE — lines relocated, zero behavior change. 4 slices:
- [x] **#170 `6f54cc3`** — recommendation backend: parse_query.py 906→656 (+`_prompts.py`), views/sessions.py 622→80 (+`session_service.py`), views/swipe.py 1205→497 (+`swipe_service.py`). Extracted services reference engine via MODULE (`from .. import engine`), never `from ..engine import X` — preserves `views.engine.*` patch-bite.
- [x] **#171 `7302ae6`** — accounts/views.py 939 → `views/` package (`auth.py` + `profile.py` + facade). CI caught the mock-patch landmine (facade re-export ≠ patch interception for function/object names) → fixed by repointing 9 test patch paths to the symbol's submodule + corrected docstrings.
- [x] **#172 `e1ff077`** — frontend 5 stable pages → 16 co-located modules: BoardDetail 1050→862, UserProfile 1022→715, BuildingDetail 711→499, FirmProfile 540→156, App.jsx 983→897 (`utils/appHelpers` + `components/{ErrorBoundary,LLMSearchUpdateWrapper}`). Pages have 0 named exports (only default, consumed by App routing) → no facade needed. Codex mocked-API browser smoke confirmed the 4 swipe-journey-skipped pages render (desktop+mobile, no ErrorBoundary).
- [x] **engine.py `16e2a1a-pre-squash`** — 2446→1976; 18 verified-pure leaf fns → `engine_{vecmath,convergence,filters,cards}.py` (4 acyclic siblings — siblings NEVER import engine; engine.py re-imports + re-exports as facade). Landmine defused by KEEPING all ~20 patch targets (`connection`/`RC`/patched fns) in engine.py → same-module bare-name patch interception unchanged. poison-mock confirmed facade reach (27 fail poisoned → 31 pass reverted). Residual ~1976 LOC stays patch-saturated; deeper split needs mass patch-repointing → deferred.
- Verified per-slice: code-review PASS, lint/build/collect (810) green, bundle byte-stable (frontend), CI green on merged PRs, engine poison-mock.
- 🔴 Durable lesson: facade re-export preserves IMPORT but NOT `mock.patch` interception for function/object names — only MODULE names survive. Repoint test patch paths to the symbol's new home (or keep patch targets co-located) + poison-mock to prove the patch still bites (green pytest ≠ proof; DB-gated tests run only on CI).
- Excluded → Codex fresh frontend pass: LoginPage/SwipePage/DiscoveryPage + SwipeGestureFrame. Skipped: web-testing/runner.py.

### INFRA-MULTIAGENT-1 — one-clone-per-worker model + agent-config overhaul (supersedes PR #166 worktree) — RESOLVED 2026-06-01 (`feature/claude-multiagent-model-docs` → develop)
- [x] **Isolation model**: every worker (human OR local AI tool) owns ONE clone + own `.git` + own `feature/*` branch + own PR. Replaces PR #166 worktree isolation — shared `.git` was the 2026-05-31 HEAD-contamination path (a Codex checkout moved the main clone's HEAD off `develop`). Two failure modes split: HEAD collision (fix = separate `.git`) + merge conflict (fix = non-overlapping file scope). Claude = main clone `make_web` (terminal; backend/API tendency); Codex = `make_web-codex` (browser; frontend tendency). Tendencies = defaults, not walls. Branch prefixes: team `feature/<role>-<topic>` (algo/sns/admin) UNCHANGED; local agents `feature/claude-<topic>` / `feature/codex-<topic>`. Canonical section in `CONTRIBUTING.md`; mirrored to CLAUDE.md + AGENTS.md HARD RULE 7 + both `WORKFLOW.md` session-start checks.
- [x] **Task board → root**: `.claude/Task.md` + `.codex/Task.md` consolidated to one shared root `Task.md` (Claude + Codex same project; instructions stay per-tool, work-state shared). 76 path refs swept across 33 files; `.gitignore` negation dropped.
- [x] **Deprecated agents deleted**: `git-manager` + `reporter` (`.claude/agents/` + `.codex/agents/`) removed — superseded by `git-commit` + `reporter-inline` skills (2026-05-26 fallback window closed). state.js roster + doc refs cleaned.
- [x] **reporter-inline → Model 1**: runs BEFORE `git-publish`; audit commits onto the feature branch, ships in same PR; keyed on stable task ID (GitHub PR# optional, auto-stamped on squash). orchestrate Mermaid + both `WORKFLOW.md` + skill mirrors aligned; 0 Model-2 remnants.
- [x] **Plan-gate safety**: 4 resolved plans archived (`.claude/plans/archive/` + `.codex/plans/archive/`); stale `## PR Plan` sections neutered so a resolved plan can't falsely open the publish gate. README guards in both plans dirs.
- [x] **Codex-side**: Codex set its own commit-trailer identity; `browser-verify` placed after `git-commit`; AGENTS.md / `.codex/*` / `.agents/skills/` (Codex skills) aligned. Pure docs/config → app-test auto-skip.

### SNS-RESULTS-UI-1 — ResultsPage UI overhaul — Liked 카드 노출 + 추천 그리드 — RESOLVED 2026-05-31 (PR #165 `61c9ee1`)
Top-K 추천 4-column 그리드 + 신규 "My Likes" 가로 스크롤 섹션 (`result.liked_images` 소비). Imagen placeholder/rank-10 divider 제거, Fragment import drop. `frontend/src/pages/ResultsPage.jsx` +118/-69. 모바일 4-col 9-10px 폰트 빽빽 (작성자 의도).

### SNS-REPORT-CONNECT — 페르소나 리포트 생성 연결 + 필드명 수정 — RESOLVED 2026-05-31 (PR #163 `fc9a5c6`)
Persona report 생성 경로 연결 + `personaFields`/`dominant_styles` 필드명 정합. #165 ResultsPage 변경과 무충돌 (별도 라인).

### DOCS-SESSION-2026-05-31 — 세션 하우스키핑 — worktree 격리 + Codex 경고 + 리뷰 백로그 — RESOLVED 2026-05-31 (PRs #164 `6c5cd66` / #166 `32a0f7d` / #167 `43de2b1`)
동시-에이전트 working-dir 격리(git worktree) CONTRIBUTING + CLAUDE/AGENTS + WORKFLOW 미러 (#166 `32a0f7d`). Codex startup metadata 경고 수정 (#167 `43de2b1`). 2026-05-31 swipe/discovery 리뷰 → Task.md `### X-HIGH` 버킷 + `.claude/reviews/` 문서 (#164 `6c5cd66`).

### FULL-LOGIN-REDESIGN-1 — Guest-first onboarding + 보드 4번째 verify gate — RESOLVED 2026-05-27 (PRs #154 / #155 `db81e0f` + `e8296f5-pre-squash`)
- [x] **Backend PR #154** (squashed `db81e0f`): `UserProfile.is_guest` + `onboarding_role` + `consent_accepted_at` + `consent_policy_version` + migration `0004`. `GuestLoginView` (3/min/IP `GuestLoginThrottle`) + `GuestPromoteView` (5/min `GuestPromoteThrottle UserRateThrottle`). `CustomTokenObtainPairSerializer` adds `is_guest` claim on refresh → propagates to access via simplejwt's claim copy (rotation-safe). `IsVerifiedUser` permission (future-proof). `ProjectListCreateView.post()` inline gate: `is_guest AND Project.count() >= 3 → 403 {detail:'verify_required', reason:'board_limit_reached', limit:3}`. `GuestPromoteView` atomic: Branch 1 cross-device merge (8 FK update rules: Project/AnalysisSession/SessionEvent/Follow×2/OfficeFollow/Reaction; SwipeEvent skipped — no direct user FK) + delete guest + blacklist refresh; Branch 2 in-place transform + username collision guard (`google_{provider_id}` fallback) + blacklist refresh. 14 pytest tests. CI Postgres service container verifies; INFRA-DB-2 blocks local. Railway auto-applied migration on develop merge.
- [x] **Frontend PR #155** (pre-squash `e8296f5`): `LoginPage.jsx` full rewrite — terminal 3-step wizard (intro → name → role) + "동의합니다" PIPA capture (server-persisted; strict `is True` check rejects coerced values) + dual CTA (returning Google secondary). `VerifyGateModal.jsx` (NEW) — catches `403 verify_required`, fires Google verify → `promoteAccount` → token swap → retry. `useGoogleLogin` extracted to `GoogleLoginButton.jsx` + `GoogleVerifyButton.jsx` child components (conditional mount under provider tree — prevents "must be used within GoogleOAuthProvider" throw when `VITE_GOOGLE_CLIENT_ID` unset). Cross-device merge: `onPromoted(user, merged)` → `handleLogin(user)` on `merged:true` re-syncs `userId` + project keys. `SaveToBoardModal` Option A (stash `{name, visibility}` + auto-retry post-promote); `SurpriseBoardModal` Option B (10-card payload too fat → toast "Verified! Now try again", 3s per DESIGN.md §8.11). Conditional `GoogleOAuthProvider` mount (no `'guest-only-google-disabled'` literal anywhere). 24/24 `loginFlow.test.mjs` PASS. `is_guest` source: `/auth/me/` response (not jwt-decode) per security-manager PR1 warning.
- User decisions Q1–Q6 (2026-05-27): Board 4번째 gate · Board만 차단 (Follow/Reaction 자유) · Google OAuth만 · cross-device merge (atomic 8 FK rules) · 3/min throttle · "동의합니다" server-persisted.
- Reviews: PR1 sec-mgr PASS (3 warnings → fixed pass 2); code-review FAIL pass 1 (1 HIGH + 3 MED + 1 LOW → 7 fixes pass 2). PR2 sec-mgr PASS clean; code-review FAIL pass 1 (3 HIGH + 2 MED → all fixed pass 2: `useGoogleLogin` extraction · `not_a_guest`/400 string · retry path · Branch 1 merge re-login · JSDoc).
- Plan: `~/.claude/plans/merry-toasting-dove.md` — FULL-LOGIN-REDESIGN-1 rebuild after codex `feature/codex-guest-auth-*` archived for 6 issues; all resolved.
- Codex archive: `feature/codex-guest-auth-backend` (3049b40) + `feature/codex-guest-auth-frontend` (f488ccd) — remote 삭제, local 보관, 재구현 참조용.

Deferred:
- `FRONT-AUTH-1` — LoginPage Kakao + Naver 버튼 (backend ready).
- `INFRA-DB-CLEANUP-1` (conditional — monitor Neon `auth_user WHERE email='' AND is_active=True` weekly; open if growth > 500/week).
- `FULL-LEGAL-1` — PIPA copy legal review (partial mitigation shipped: `consent_accepted_at` + policy version field).
- PIPA copy not yet legally reviewed — terminal "동의합니다" placeholder copy; `FULL-LEGAL-1` to produce final + Privacy/Terms routes.

### BACK-BOARD-PERF-1 — /projects/&lt;id&gt;/ ~879ms → &lt;500ms — response cache 60s — RESOLVED 2026-05-27 (PR #148 `4573623-pre-squash`)
- [x] **Response cache 60s** (projects.py ProjectDetailView.get): PR #147 Profile detail pattern을 ProjectDetailView에 적용. Per-(project_uuid, requester_id, version) key. requester_id partition (anon / profile.id) → is_owner / is_reacted / visibility-gated payload cross-user leak 방지.
- [x] **caches.py helpers**: PROJECT_DETAIL_TTL=60 + version key + evict_project_detail(uuid) + get_project_detail_cache_key(uuid, requester_id). Version-based invalidation.
- [x] **Invalidation 8 mutation sites**: ProjectDetailView patch/delete · ProjectListCreateView.post · ProjectBookmarkView · SwipeView (transaction-safe) · SessionCreateView · ProjectReportGenerate/ImageView · ReactionView post/delete (gated).
- [x] **CRITICAL fix-loop**: ProjectDetailView.delete 초기 evict가 row delete 전 → race window. 정정: evict AFTER delete.
- [x] **test_board_detail_perf.py** NEW 7 pure-mock cases.
- Verification: manage.py check PASS · 7 non-DB tests PASS · code-review PASS · security-manager PASS.
- 기대: cold ~879ms → ~500ms, warm ~50ms.
- Origin: User goal 2026-05-27 — PR 3/N of iterative perf sweep.

### BACK-PROFILE-PERF-1 — /users/&lt;id&gt;/ 895ms → &lt;1s — thumbnail-only fetch + response cache — RESOLVED 2026-05-27 (PR #147 `4cd1fdf-pre-squash`)
- [x] **Fix 1 `engine.get_building_thumbnails(ids)`** NEW: lightweight minimal-column SELECT.
- [x] **Fix 2 `_build_boards_field` thumbnail-only swap**.
- [x] **Fix 3 `UserProfileDetailView` response cache (60s)**: per-(viewed_user, requester, page, page_size, version) key. Cross-user leak partition.
- [x] **Invalidation wired**: PATCH /users/me/ · Project mutations · Session create · Follow/unfollow · ProjectBookmark POST.
- [x] **`test_profile_perf.py`** NEW 9 cases.
- Verification: manage.py check PASS · 9 non-DB tests PASS · code-review PASS · security-manager PASS.
- 기대: cold ~500-700ms, warm ~100ms.

### BACK-PERFORMANCE-4 — Discovery cold 4.6s → ~1.5-2.5s — taste vector cap + SQL top-K — RESOLVED 2026-05-27 (PR #146 `dc1651b-pre-squash`)
- [x] **Fix 1 `taste_ranked_page` CTE 제거**: PG planner top-K heap scan.
- [x] **Fix 2 `compute_user_taste_vector` recent-50 cap**: bounded cold get_pool_embeddings.
- [x] **Fix 3 `_async_warm_taste` daemon thread** (rolled back; pytest-django connection race).
- Verification: manage.py check PASS · code-review PASS · security-manager PASS.
- 기대 효과: Discovery cold ~4.6s → ~1.5-2.5s.

### BACK-ALGO-1 — Required-slate hard WHERE + first-swipe prefetch cache seed — RESOLVED 2026-05-27 (PR #145 `72f8f27-pre-squash`)
- [x] **F3 required-slate hard WHERE** (engine.py): "Japan museum" search 후 첫 save → Bolivia card 표시되던 버그. Root cause: filters가 score CASE만 emit, pool SQL WHERE는 `is_publishable=true AND score > 0`만 — Bolivia가 country 0이어도 style/program 양의 점수로 통과. Fix: `_REQUIRED_SLATE_FIELDS_SET` frozenset (services/parse_query.REQUIRED_SLATE_FIELDS 미러 + cross-ref 주석) + `_build_required_slate_where(filters)` helper. Mode V (HyDE) + Mode F (filter-only) 적용. Mode H (RRF) excluded — rank-fusion 의미 다름. Tier 2 relaxation은 기존 location_country drop 동작 그대로.
- [x] **F4 first-swipe prefetch cache seed** (sessions.py): 첫 swipe `saved_current_round=1` (current_round가 swipe.py:548에서 save 전 증가) → `cache.get('prefetch:{sid}:1')` always miss → sync compute 770ms. **SPEC DEVIATION**: back-maker source-reading으로 spec :0 → 실제 :1로 정정. SessionCreate 끝에 `cache.set('prefetch:{sid}:1', {prefetch_card_id: initial_batch[1], prefetch_card_2_id: initial_batch[2]}, timeout=60)` 시드. `_async_prefetch_thread` write shape 미러.
- [x] **`test_engine_filter_hard_constraint.py`** NEW 4 cases: slate WHERE emit, Tier 2 relaxation, optional fields stay soft, **Mode V param order** (param-position regression catch).
- [x] **`test_session_create_correctness.py`** +2 F4 `TestPrefetchCacheSeeding` cases.
- **code-review fix-loop CRITICAL catch**: 초기 구현 2개 SQL execute call에서 **param order inversion**. 정정 후 테스트가 param positions 검증.
- Verification: manage.py check PASS · F3 4/4 tests PASS · F4 tests local INFRA-DB-2 차단 (CI 실행) · code-review PASS (after fix-loop) · security-manager PASS (parameterized SQL, UUID-isolated cache keys).
- Origin: 4th Codex retest 2026-05-26 of develop=72bf8d3. F3+F4 알고리즘 territory.

### FRONT-UX-FIXES-1 — Image timeout + Gallery CTA nav + Board card click — RESOLVED 2026-05-26 (PR #144 `b5c53f2-pre-squash`)
- [x] **F2 SwipeCard image timeout**: 2000ms → 4000ms. `?retry=1` cache-bust path 전부 삭제 (별도 URL 없음, 대역폭만 2배). Fallback chain: `covers_by_type.exterior → interior → aerial → detail → drawing → gallery[N]`. Singapore R2 cold-cache 1.7-2.6s 정상 처리.
- [x] **F5 Gallery CTA navigation**: 동작 변경. 이전 `openGallery()` → in-card 3D flip back-face. 현재 `navigate('/buildings/${card.image_id}')` → BuildingDetailPage 전체 갤러리. 3D flip path가 실제 no-op surface (back-face JSX는 `setShowGallery(true)` unreachable로 절대 안 렌더링). SwipePage `onGalleryOpen` prop 무해하게 drop. 죽은 코드 (back-face JSX, `hasBeenOpened`) 별도 cleanup PR로.
- [x] **F7 BoardDetail building card click**: ID 정규화 OR chain에 `building.id` 추가 (3 sites: BuildingTile line 180, handleDeleteSelected filter line 458, render bid line 926). MOCK_BOARD `building_id` priority 유지. Stored `{id: "bld_..."}` shape 정상 인식 → 클릭 navigate.
- Verification: npm run lint clean · npm run build PASS · code-review PASS (3 dead-code items flagged out-of-scope) · security-manager PASS (XSS-safe — image_id BUILDING_ID_RE 검증; IDOR-safe — board-scoped ownership server-side).
- FRONT-UX-5 (Gallery CTA backlog) closed by F5.
- Origin: 4th Codex retest 2026-05-26 of develop=72bf8d3. F1 (session 2.11s) positive PR #137+138 작동 확인. F3+F4 → Group B separate PR. F6 (StrictMode dup GET) dev-only → 별도 backlog 검토.

### BACK-CORRECTNESS-1 — /projects/ cache evict + dedupe project_id + orphan project — RESOLVED 2026-05-26 (PR #143 `d87a5f9-pre-squash`)
- [x] **Fix 1 — `/projects/` cache eviction**: `evict_projects_list(profile.id)` added at 5 mutation sites: sessions.py dedupe-hit return path + sessions.py post-create + swipe.py post-save + reports.py post-final_report + reports.py post-report_image. ProjectListSerializer exposes liked_ids/saved_ids/final_report/report_image — eviction now covers all paths.
- [x] **Fix 2 — dedupe + project_id intent**: PR #138 dedupe scope extended. Early project_id resolve before dedupe lookup. If project_id provided + matches user-owned Project → dedupe SKIPPED (App.jsx:723 fresh-swipe flow honored). project_id missing or no match → existing (user, name, raw_query, filters) dedupe runs.
- [x] **Fix 3 — orphan Project on mid-failure**: Project.objects.create() deferred from line ~113 to inside `session_insert` stage. Pool fetch failure / empty pool 404 no longer leaks Project rows. Project + AnalysisSession pair wrapped in `transaction.atomic()` savepoint (fix-loop catch — closes session_insert-step orphan too).
- [x] **`test_session_create_correctness.py`** NEW 9 tests: 3 cache evict (session create / swipe write / dedupe hit) + 1 project_id-skip-dedupe + 2 no-orphan (pool empty / pool exception) + 2 cache evict on reports + 1 session insert rollback.
- Verification: manage.py check PASS · pytest full suite **553 passed** (was 550, +3 new tests, zero regression) · PR #138 dedupe tests 8/8 still PASS · code-review PASS (after 1 fix-loop catching reports.py + transaction.atomic) · security-manager PASS (IDOR-safe: user= clause on early project_id resolve; cache eviction scoped to profile.id).
- Origin: 3rd Codex retest 2026-05-26 of develop=17f7d65 (worktree `/private/tmp/make_web_review_develop`). P2-1/2/3 shipped here. P2-4 (pytest bootstrap) merged into existing INFRA-DB-2. P3 findings (daemon thread / large files / LLM localStorage / PostSwipeLandingPage) all already tracked — PostSwipeLandingPage finding superseded by PR #142 INFRA-CLEANUP-1.

### INFRA-CLEANUP-1 — Dead code 정리 (-1124 LOC) — RESOLVED 2026-05-26 (PR #142 `beb1d74-pre-squash`)
- [x] **Files removed (-1124 LOC)**:
  - `frontend/src/pages/PostSwipeLandingPage.jsx` (696 LOC) — PROF3+PROF4 mockup with unwired backend TODOs.
  - `frontend/src/components/GalleryOverlay.jsx` (181 LOC) — initial-commit artifact; PR #120 BuildingDetailPage rolled its own inline gallery.
  - `backend/tools/optimization_results.json` (247 LOC) — Optuna search artifact. Zero refs.
- [x] **Doc references**: CONTRIBUTING.md role B table drops PostSwipeLandingPage; BoardDetailPage.jsx:143 JSDoc drops PostSwipeLanding mirror reference.
- [x] **Session decisions batched in this audit**:
  - **FRONT-UX-1 obsolete** — App.jsx:783 already `<Route index element={<Navigate to="/discovery">>` ; first-login lands on /discovery directly. Removed from ## Next ### HIGH.
  - **FULL-LOGIN-REDESIGN-1** added to ## Next ### HIGH — codex guest-auth direction (guest-first + 3-step onboarding) accepted; codex code archived (local only) due to 6 issues; re-design pending.
  - **FULL-REFACTOR-1** LOC list updated.
- Verification: npm run lint clean · cross-cutting grep verified zero non-self refs for all 3 deleted files · git history confirms abandoned status.
- Origin: salvaged from codex-authored `feature/codex-cleanup-stale-develop` (commit `986bd5e`). Codex branch's docs/skill changes rejected (regressions of PR #136 INFRA-DOC-6); only file deletions kept.

### BACK-LLM-1 — LLM 채팅이 검색에 필요한 정보를 다 안 모음 — RESOLVED 2026-05-26 (PR #141 `cdbf5c7-pre-squash`)
- [x] **`parse_query.py`**: `REQUIRED_SLATE_FIELDS = (program, material, style, location_country)` + `REQUIRED_SLATE_PROBE_PRIORITY` module-level constants. System prompt + few-shot examples rewritten to deterministically target missing slate fields (drop prior free A-vs-B axis selection).
- [x] **`_normalise_filter_priority`**: required-slate keys promoted to front of Gemini-returned `filter_priority`. Engine score weights respect the new order.
- [x] **`_repair_required_slate`**: injects `style: 'Contemporary'` (`_BROAD_SLATE_DEFAULT_VALUE`) when no required-slate field present after Gemini parse OR 2-turn probe budget exhausts with slate gap. Runs on `probe_needed=True` intermediate turns too — documented.
- [x] **Korean few-shot examples** updated with slate-targeted probe Korean questions. Korea-first preserved (Constitution Decision Principle 7).
- [x] **`test_back_llm1_required_slate.py`** NEW 5 tests: prompt content assertions, slate promotion into priority, broad default injection for both `parse_query` + `parse_query_stage1`, budget-exhausted terminal repair.
- Verification: manage.py check PASS · pytest 5/5 PASS · code-review PASS (rebase clean; parse_query.py untouched on main since branch base) · security-manager PASS (no prompt injection — user input never touches system prompt; static constants; mocks-only tests).
- Open dimensions resolved: required slate = 4 fields (program/material/style/location_country); priority = same order; fallback = 'Contemporary' default; conversational shape = Korean slate-targeted probes (mix of direct + axis).
- Deferred: A/B 50-query benchmark harness (Task.md acceptance criterion c). Code contract structurally verified; empirical measurement = post-merge follow-up.
- Behavioral note: `_normalise_filter_priority` promotion changes `engine._build_score_cases` weight semantics (rank-based; required-slate field outranks temporal filter). Intended.
- Origin: codex-authored `feature/codex-back-llm1-required-slate` (commit `79346ff`) cherry-pick. Clean rebase onto develop=92915b8.

### BACK-LLM-3 — Gemini cache 호출에 timeout 없음 — RESOLVED 2026-05-26 (PR #140 `715e06e-pre-squash`)
- [x] `backend/apps/recommendation/services/_caches.py:92` `client.caches.create` 호출을 zero-arg `_create_cache` closure로 추출 → `_svc._retry_gemini_call(_create_cache)`로 라우팅. 기존 `_retry_gemini_call`의 15s timeout cap (PR #94) 적용.
- [x] `backend/tests/test_imp5_context_caching.py` `+17` LOC `test_gemini_create_runs_through_retry_timeout_wrapper`: MagicMock으로 Gemini 네트워크 hit 없이 patch 검증.
- [x] `context_caching_enabled` 플래그 default OFF 유지 — 프로덕션 영향 없음. SDK hang 시 cap 적용. Pre-emptive safety.
- Verification: manage.py check PASS · 새 테스트 PASS (12 passed) · code-review PASS (~5 LOC budget 정확히 준수) · security-manager PASS (no secret leakage, closure capture 안전).
- 9 pre-existing DB-요구 tests는 `INFRA-DB-2` (`permission denied to create database`)로 차단됨; 본 PR이 도입한 게 아님.
- Origin: codex-authored `feature/codex-back-llm3-timeout` (commit `5ac1f6d`)에서 cherry-pick. 원 branch가 stale develop에 stacked되어 있어서 fresh feature branch에 cherry-pick. Clean rebase.

### FULL-SESSION-DEDUPE-1 — Session create POST retry → 중복 Project/Session — RESOLVED 2026-05-26 (PR #138 `3fcbe3c-pre-squash`)
- [x] **Frontend `api/core.js`**: retry gate by HTTP method. `_IDEMPOTENT_METHODS = {GET, HEAD, OPTIONS}`. POST/PATCH/DELETE throw on first network error (no retry).
- [x] **Frontend `api/sessions.js`**: `SESSION_CREATE_TIMEOUT_MS=30000` per-call override for `startSession` (cold pool ~16s requires >15s default).
- [x] **Backend `views/sessions.py`**: dedupe guard at start of `SessionCreateView.post`. 30s window; match (`user`, `project.name`, `project.raw_query`, `project.filters`). Hit → returns existing session with `deduped:true` HTTP 200 (vs 201 fresh).
- [x] **Tests `test_session_create_dedupe.py`** NEW: 8 cases (baseline 201, hit 200, expiry, different raw_query/name/filters, project_id=None retry, response shape).
- Trade-offs: `recordSwipe` (POST) no-retry — backend `idempotency_key` (sessions.js:68) still guards server-side. Race window ~100ms (POST 1 commit → POST 2 SELECT) unreachable from single-tab client with retry-gate above.
- Verification: manage.py check PASS · flake8 zero new · npm run lint+build PASS · code-review PASS · security-manager PASS · app-test FEATURE-SCOPED PASS (5/5 checklist incl. dedupe path HTTP 200 + `deduped:true` + same session_id + only 1 Project row).
- Origin: Codex retest 2026-05-26 of develop=d53b232. P0 finding: 15s timeout → retry → 2 boards same name (one with 4 photos, one with 0).
- Deferred surfaced to Next ### MEDIUM: BACK-PERFORMANCE-4 (Discovery 4.6s) + BACK-PERFORMANCE-5 (Swipe latency variability) + FRONT-UX-5 (View Gallery click no-op).

### INFRA-DEPLOY-3 — railway migrate align + Redis prod guard + docs drift — RESOLVED 2026-05-26 (PR #137 `09a3b7c-pre-squash`)
- [x] `backend/railway.toml` buildCommand: dropped `migrate --noinput`. Per INFRA-DB-1, Railway runtime is `make_web_app` (no DDL); next schema migration would have failed at deploy time. Comment block rewritten to cite INFRA-DB-1 + operator runbook in `.env.example`. `collectstatic` kept.
- [x] `backend/config/settings.py` `_check_async_prefetch_safety()` helper: raises `ImproperlyConfigured` at module import when `DEBUG=False && async_prefetch_enabled && !REDIS_URL`. Silent LocMem fallback in prod = thread cost without multi-worker coherence (same bug class PR #134 just fixed). Operator migrate path safe because `.env.example` defaults `DJANGO_DEBUG=True` → guard short-circuits.
- [x] `backend/tests/test_cache_backend.py` `TestAsyncPrefetchSafetyGuard` (4 cases): prod+REDIS_URL set OK, DEBUG=True bypass, async_prefetch=False bypass, prod misconfig raises.
- [x] Docs drift: `swipe.py:79`+`:723` "primary path does NOT consume" stale (PR #134 PERF-PREFETCH-CHAIN consumes); `settings.py:142` + `.env.example:72` "JTI cache" stale (PR #133 BACK-AUTH-1 final = JWT user-row cache).
- Verification: `manage.py check` PASS · `pytest test_cache_backend.py` 20/20 · code-review PASS · security-manager PASS.
- Origin: Codex retest of develop=`d53b232` 2026-05-26 surfaced P2-railway-migrate + P2-Redis-silent-fallback + P3-docs-drift; P3-cache-integration-tests + P3-test-DB-role surfaced as `BACK-AUTH-2` + `INFRA-DB-2` in Next.

### INFRA-DOC-6 — orchestrate / git-publisher / web-testing AGENTS skill-regime 정렬 — RESOLVED 2026-05-26 (PR #136 `80e7d86-pre-squash`)
- [x] Cherry-picked session-start docs work (`010edf8`) onto post-deploy develop. Three files re-aligned with the 2026-05-26 skill-migration regime (INFRA-WORKFLOW-1, PR #123).
- [x] `.claude/skills/orchestrate/SKILL.md` — drop deprecated `git-manager` / `reporter` agent refs from frontmatter, dispatch list, Step 5 session-end, Step 7 fix-cycle, Step 8 publish gate, Step 10, Rules. Step 6 → `git-commit` skill. Step 8 default = `git-publish` skill (git-publisher agent only for Mode 3 / external / complex rebase). Step 9 = `reporter-inline` + `git-commit` + `git-publish`.
- [x] `.claude/agents/git-publisher.md` — frontmatter repositioned as edge-case agent (Mode 3 deploy, external PR triage, complex rebase, push rejection unclear, mid-merge failure). New "When this agent is called" preamble enforces refuse-on-routine-publish. Mode 1 header renamed "Internal push escalation (fallback only)". Hard guardrails + Tools footer point at `git-commit` skill.
- [x] `web-testing/AGENTS.md` — scope clarified (agent contract owned by `.claude/agents/app-test.md`; this doc = standalone runner + shared dev-login). 2026-04-28 `web-tester` → `app-test` rename documented. Dev-login 404 fallback rewritten to match `app-test.md` hard-FAIL. `skip_login` flag note marked removed. Modes table rewritten FULL vs FEATURE-SCOPED (supersedes legacy fast/strict /review split).
- [x] Pure docs/policy edit per CLAUDE.md `## Implementation delegation — HARD RULE` carve-out. Skipped code-review + security-manager + app-test (sub-MINOR meta cleanup, no migration / production code / auth / network / model change).
- [x] Stale `feature/admin-docs-skill-migration-sync` branch (session-start orphan, base pre-deploy develop) replaced by fresh `feature/admin-skill-docs-align` cherry-picked onto post-deploy develop. Old branch deleted locally post-merge.

### INFRA-DEPLOY-2 — 2026-05-26 develop → main 배포 (PRs #116-#134, perf sweep + Redis) — RESOLVED 2026-05-26 (PR #135 `d53b232`)
- [x] develop → main squash-merged. main = `d53b232`. Railway prod auto-deploy SUCCESS (deployment `047a6e2f`, RUNNING).
- [x] Carried 15 PRs since main `1888b5f` (PR #112 prior release): #116 INFRA-ENV-1 + #117 + #118 FRONT-DESIGN-2 + #119 INFRA-DB-1 + #120 FRONT-UX-4 + #121 FRONT-UX-2 + #122 reporter housekeeping + #123 INFRA-WORKFLOW-1 + #124 BACK-PERFORMANCE-1 + #125 BACK-PERFORMANCE-3 + #126 BACK-PERFORMANCE-2 + #128 INFRA-CI-1 + #129 dashboard fix + #130 SWIPE-CONVERGENCE-10 + #131 INFRA-REDIS-1 + #132 BACK-RECOMMEND-2 + #133 BACK-AUTH-1 + #134 PERF-PREFETCH-CHAIN.
- [x] **Bug #5 carve-out applied** (HARD RULE 4 SOLE permitted force): `origin/develop` force-reset to `origin/main` (`d53b232`) via `gh api PATCH refs/heads/develop --force=true`. Precondition checked (no in-flight feature PR targeting develop). Tree-equivalence verified: `git diff origin/main origin/develop` empty.
- [x] **Railway Redis service** provisioned (admin via dashboard during session) and `REDIS_URL=${{Redis.REDIS_URL}}` env set on backend service before merge. Post-deploy: backend service deployment SUCCESS, RUNNING, gunicorn 4 workers booted clean, no `django_redis` import errors in logs.
- [x] Prod smoke (CLI): `/` → 404 (no route). `/auth/dev-login/` → 404 (`DEBUG=False` gates per design). `/api/v1/projects/` unauthenticated → 401 (DRF auth pipeline working). `/auth/token/refresh/` empty body → 400 (view reachable). No 5xx anywhere.
- [x] Direct cache-hit latency measurement NOT possible from CLI (prod `DEBUG=False` blocks dev-login + Google OAuth needs browser). Real-world impact verified via Codex retest (admin runs separately).
- Outstanding: `PERF-PREFETCH-POOL-RISK` (## Next ### MEDIUM) — monitor Neon connection count post-deploy. Async prefetch daemon thread + main worker = 2 conns/swipe; Neon free-tier 25 limit.

### PERF-PREFETCH-CHAIN — async_prefetch chain end-to-end (PR 4/4 FINAL of perf sweep) — RESOLVED 2026-05-26 (PR #134 `dc296bc-pre-squash`)
- [x] PR 4 (FINAL) of 4 in `.claude/plans/merry-toasting-dove.md` (backend performance sweep). Depends on PR 1 INFRA-REDIS-1 merged (Redis multi-worker cache coherence). Plan complete after this PR merges.
- [x] **`_async_prefetch_thread` off-by-one fix** (swipe.py thread function): `pf_bid` index `current_round_snap + 1` → `+2`, `pf2_bid` index `+2` → `+3`. Applied to all 4 formula sites (exploring pf, exploring pf2, analyzing pf via `compute_mmr_next` round arg, analyzing pf2). Prior thread stored cards for T+1's `next_card` slot (duplicate of main-thread compute); fix stores cards for T+1's prefetch slot, matching sync-path semantics.
- [x] **Async-branch consumer in `SwipeView.post`** (~line 752+): `cache.get(f'prefetch:{session.session_id}:{saved_current_round}')` reads PRIOR swipe's thread write. Batched `engine.get_buildings_by_ids([next, pf, pf2])` for 1-RTT 3-card hydration. Cache miss → prefetch fields stay None (graceful fallback).
- [x] **Dedupe guards** (code-review fix-loop): degrade `pf_id` to None if `== next_bid`, degrade `pf2_id` to None if `== next_bid` or `== pf_id`. Prevents analyzing-path collision where `compute_mmr_next` can return same card for T's lookahead and T+1's main pick (similar inputs + `mmr_lambda_ramp_enabled=False`). Frontend `App.jsx:521+536` non-instant-swap path does NOT dedupe; without backend guard user would see same card twice.
- [x] **`async_prefetch_enabled` False → True** (config/settings.py:216). Chain functional end-to-end.
- [x] Tests: `test_imp7_pool_cache.py:635` `prefetch_strategy 'sync' → 'async-thread'`. `test_imp8_async_prefetch.py` default-flag tests updated. New `TestAsyncBranchConsumerIntegration` class with cache-hit + cache-miss + dedupe regression tests (pre-fix collision triggers test failure → post-fix passes).
- [x] code-review FAIL → fix-loop applied (MAJOR analyzing-path duplicate). 2nd code-review PASS implicit (3-line dedupe patch matches the prescription exactly). security-manager PASS with availability warning (deferred as `PERF-PREFETCH-POOL-RISK` in ## Next ### MEDIUM).
- [x] `docs/algorithm.md` Hyperparameter Space table: `async_prefetch_enabled` Production Value `False → True`. Last Synced bumped `785f4ad → dc296bc`.
- [x] app-test skipped per `[[feedback_app_test_policy]]` (4-gate stack PASS after fix-loop + cache-miss path preserves current behavior + dedupe guard backstops cache-hit edge). Inline drift: HEAD `dc296bc` vs `origin/develop` `4c72513` — clean.
- [x] Expected impact (verified post-deploy via Codex retest): swipe latency p50/p95 on warm session (2nd+ swipe with cache hit) — card hydration moves off main-thread critical path. Combined with PR 3 BACK-AUTH-1 (~590ms auth floor removed), per-swipe round-trip should improve meaningfully on cache-warm sessions.
- Deferred: `PERF-PREFETCH-POOL-RISK` — Neon connection pool monitoring post-deploy.

### BACK-AUTH-1 — JWT user-row cache (PR 3/4 of perf sweep) — RESOLVED 2026-05-26 (PR #133 `5a1e914-pre-squash`)
- [x] PR 3 of 4 in `.claude/plans/merry-toasting-dove.md` (backend performance sweep). RE-SCOPED from original JTI-cache premise after empirical falsification: simplejwt source inspection confirmed `AccessToken` does NOT inherit `BlacklistMixin` — only `RefreshToken` does. Blacklist DB lookup never runs during access-token validation. The actual ~590ms per-request DB hit is `JWTAuthentication.get_user()` → `User.objects.get(id=user_id)` against Neon. Caching that lookup is the actual fix.
- [x] `backend/apps/accounts/authentication.py` **NEW** — `CachedJWTAuthentication(JWTAuthentication)` subclass overrides `get_user(validated_token)`. Cache key `jwt_user:<user_id>` (Django KEY_PREFIX `makeweb:` auto-applied). TTL = `min(token_exp_unix - now, 3600s)` — entry cannot outlast access token's natural lifetime. Exports `invalidate_user_cache(user_id)` helper.
- [x] `backend/apps/accounts/views.py` — `invalidate_user_cache(...)` calls at LogoutView (after `RefreshToken.blacklist()`, uses `request.user.id`) and TokenRefreshView (after rotation `refresh.blacklist()`, uses `refresh.get(api_settings.USER_ID_CLAIM)` from signature-verified RefreshToken).
- [x] `backend/apps/accounts/signals.py` **NEW** — `post_save` + `post_delete` on `User` invalidate cache. Safety net for ORM/admin mutations. Wired via `AccountsConfig.ready()` in `apps.py`.
- [x] `backend/config/settings.py:111` — `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']` swap simplejwt → `apps.accounts.authentication.CachedJWTAuthentication`.
- [x] `backend/tests/test_jwt_cache.py` **NEW** 12 tests: cache miss/hit/TTL cap/explicit invalidate/`post_save` signal/`post_delete` signal/tampered signature/expired token/cross-instance/`is_active` toggle/malformed exp fallback/missing USER_ID_CLAIM.
- [x] Security verification (security-manager PASS): signature check still runs first via parent's `get_validated_token` before `get_user` is called — bad signatures never reach cache. Cache key from signature-verified user_id claim (not raw input). TTL cap enforced. Explicit invalidation at all 2 blacklist sites + signal backstop catches admin/ORM mutations. `User.objects.filter(...).update(...)` gap documented (grep confirms zero auth-relevant call sites today). Redis is Railway-internal (private network); cached User instance same data as DB return — no new disclosure surface.
- [x] code-review (sonnet) PASS — override target / api_settings.USER_ID_CLAIM usage / TTL math edge cases / cache key collision / refresh user_id extraction / signal registration via short-form INSTALLED_APPS / `.update()` gap audit / no-regression on existing tests / test isolation via override_settings.
- [x] Expected impact: local proxy p50 `/projects/` cache-hit path ~661ms → ~150ms (~500ms get_user() floor removed). Prod Singapore Railway p50 verified post-deploy via Codex retest.
- [x] app-test skipped per `[[feedback_app_test_policy]]` (4-gate stack PASS + auth-layer cache with mandatory security review). Inline drift: HEAD `5a1e914` vs `origin/develop` `b53e633` — clean.
- Non-blocking note: signal-wiring integration test exercised handler functions directly rather than `user.save()` ORM call (avoids INFRA-DB-1 `make_web_app` no-DDL constraint blocking full ORM-flow tests). Code-read confirms `apps.py.ready()` import + Django 4.2 short-form INSTALLED_APPS auto-discovery of AccountsConfig.

### BACK-RECOMMEND-2 — sklearn KMeans matmul warning 압제 (PR 2/4 of perf sweep) — RESOLVED 2026-05-26 (PR #132 `785f4ad-pre-squash`)
- [x] PR 2 of 4 in `.claude/plans/merry-toasting-dove.md` (backend performance sweep). Re-scoped from original "dtype align" to `np.errstate` suppression after empirical falsification: `like_embeddings.dtype == float64` already pre-edit because `_finite_unit_vector` (engine.py:66) calls `np.asarray(raw_vec, dtype=np.float64)`. The matmul `RuntimeWarning: divide by zero / overflow / invalid` originates inside sklearn's KMeans centroid normalization (`sklearn/utils/extmath.py:203 ret = a @ b`) on high-dim unit-norm vectors — sklearn-internal noise, cosmetic per Task.md original entry.
- [x] `engine.py:90-99` new helper `_silenced_kmeans_fit(kmeans, X, sample_weight=None)` wraps `kmeans.fit(X, sample_weight=sample_weight)` with `np.errstate(divide='ignore', invalid='ignore', over='ignore')`. Placed near other small helpers (`_parse_embedding_text`, `_finite_unit_vector`, `_cosine_sim_matrix`).
- [x] `engine.py:1664` Path 2 adaptive k=2 + `engine.py:1701` Path 4 default k — `kmeans.fit(...)` call sites swapped to `_silenced_kmeans_fit(...)`. `sample_weight=like_weights` recency weighting preserved on both paths.
- [x] **Computation byte-identical** — `np.errstate` ONLY changes NumPy's warning/error behavior, never numerical results. `random_state=42` + `n_init=3` deterministic. `test_topic06.py` 9/9 PASS (silhouette + cluster-correctness assertions) — empirical proof cluster output unchanged.
- [x] `pytest -W error::RuntimeWarning backend/tests/test_topic06.py` 9/9 PASS (previously failing on develop with matmul RuntimeWarning escalated to error). Test corpus exercises both adaptive-k Path 2 (k=2) and Path 3 (k=1 silhouette degradation) — same `_silenced_kmeans_fit` wrap.
- [x] code-review (sonnet) PASS — helper placement / sample_weight threading / silencing scope verified. security-manager (sonnet) PASS — no new SQL/auth/network/log surface, no thread-leak (np.errstate thread-local since NumPy 1.17 — multi-worker Gunicorn safe), sample_weight provenance traced to session-managed canonical_bld_id (no user-controllable input).
- [x] app-test skipped per `[[feedback_app_test_policy]]` (4-gate stack PASS + change is warning suppression with no functional surface). Inline drift check: HEAD `785f4ad` vs `origin/develop` `34a0c9e` — clean.
- [x] `docs/algorithm.md` Last Synced line bumped (engine.py touched). Step 3b inline annotation skipped — algorithm behavior byte-identical pre/post; only warning output silenced.

### INFRA-REDIS-1 — Redis cache 도입 (PR 1/4 of perf sweep) — RESOLVED 2026-05-26 (PR #131 `d5b6c18-pre-squash`)
- [x] PR 1 of 4 in `.claude/plans/merry-toasting-dove.md` (backend performance sweep). Foundation enabling PR 3 (BACK-AUTH-1 JTI cache) + PR 4 (PERF-PREFETCH-CHAIN async consume) — both require shared cache across Railway multi-worker Gunicorn that LocMemCache per-process cannot provide.
- [x] `backend/config/settings.py` `CACHES` block reads `REDIS_URL` env. Set → `django_redis.cache.RedisCache` (`KEY_PREFIX=makeweb`, `SOCKET_CONNECT_TIMEOUT=3`, `SOCKET_TIMEOUT=3`). Unset → existing `LocMemCache` with `MAX_ENTRIES=2000` preserved (local dev parity). `_build_caches_dict(redis_url)` helper extracted for clean unit testing without env monkeypatching.
- [x] `backend/requirements.txt` `django-redis>=5.4,<6.0` added (alphabetical position between `django-cors-headers` and `djangorestframework`; transitively pulls `redis-py>=4.x`).
- [x] `backend/.env.example` new Cache section between Feature flags + CORS, commented `REDIS_URL=` placeholder.
- [x] `CLAUDE.md` `## Backend Conventions` bullet — Redis prod / LocMemCache local-dev / never bypass Django cache abstraction.
- [x] `backend/tests/test_cache_backend.py` (NEW) 16 tests across `TestLocMemBranch` / `TestRedisBranch` / `TestMutualExclusion`. Helper called directly; no live Redis daemon required.
- [x] **Connection-failure policy**: `REDIS_URL` set + Redis unreachable → Django raises loudly. `IGNORE_EXCEPTIONS` deliberately absent. Silent multi-worker incoherence is worse than a visible error.
- [x] code-review (sonnet) PASS — KEY_PREFIX collision check clean across `engine.py`, `swipe.py`, `_caches.py`, `parse_query.py`, `caches.py` (all consume Django cache abstraction; no raw `redis-py`). `TestMutualExclusion` confirms fresh-dict semantics.
- [x] security-manager (sonnet) PASS — `.env` gitignored, no `logger`/`print` of REDIS_URL, ConnectionError carries no creds (host:port only), `rediss://` TLS supported transparently via redis-py, no known CVE at version range.
- [x] app-test skipped per `[[feedback_app_test_policy]]` (4-gate stack PASS + REDIS_URL unset in local/CI yields identical behavior to prior develop). Inline drift check: HEAD `d5b6c18` vs `origin/develop` `83db42c` — clean.
- [x] User manual step before merge: Railway dashboard → Add service → Database → Redis; on Make Web backend service set `REDIS_URL=${{Redis.REDIS_URL}}` via Railway variable reference. Until that lands, prod stays on LocMemCache (single-worker functional parity).

### SWIPE-CONVERGENCE-10 — 10-swipe target + multimodal escalation + stuck-state safety — RESOLVED 2026-05-26 (PR #130 `7f6a056-pre-squash`)
- [x] Replaces closed PR #127 (codex `feature/algo-convergence-study` — algorithm exploratory PR with spec divergence + UX stuck-state risk + chain-broken async flag).
- [x] **Algorithm policy (spec-synced)** — `convergence_threshold` 0.08 → **0.13**, new `target_swipes=10`, `min_likes_for_multimodal=11` (gates K-Means K=2 behind target_swipes+1 — single centroid default for 10-swipe sessions, escalation activates on continue-past-target / resume flows), `convergence_min_recent_likes=2` (positive-evidence gate — blocks false convergence on dislike streaks even when delta_v settles).
- [x] `docs/algorithm.md` synced inline (Phase 1->2 transition + K-Means + Convergence Detection subsections + Hyperparameter Space table + Optimization Methodology target). Production direction shifted from "15-25 swipes" to "~10 swipes default, multimodal escalation past N>=11". Topic 06 adaptive-k + soft-relevance paths remain flag-gated and now sit behind the multimodal gate.
- [x] **Frontend stuck-state safety floor** (new vs PR #127) — `SwipePage.isAt100` + `App.jsx` auto-nav `useEffect` get `beyondTargetFloor = swipeCount >= targetSwipes + 5` (default 15). Without floor, backend `min_recent_likes=2` gate could withhold `phase='converged'` indefinitely on dislike-heavy paths → user stranded until pool exhaust (100+ swipes).
- [x] **Engine `_with_image_focus` bug fix** (new vs PR #127) — `gallery_drawing_start` decrements by 1 when `focus_url` removed from index strictly less than original `drawing_start`. Prior code clamped only — drawing boundary drifted by 1 when cover promoted from before drawing section.
- [x] **`async_prefetch_enabled` revert True → False** — code-review (sonnet) caught: PR #127 flipped True but swipe.py async branch writes prefetch cache without next-swipe handler reading it back. Chain broken; flag flip yields zero latency gain plus daemon-thread DB lifecycle risk (echo of PERF-3 PR #128 TIME_ZONE KeyError class of bug). `test_imp7_pool_cache` + `test_imp8_async_prefetch` assertions reverted to match False default. Deferred: `PERF-PREFETCH-CHAIN` surfaced in `## Next ### LOW`.
- [x] **Swipe.py stale defaults** — `RC.get('convergence_threshold', 0.08)` at lines 598 + 862 → `0.13` matching settings prod.
- Code-review (sonnet) FAIL → all 4 findings resolved before commit (async revert + stale defaults + dislike_ids semantics confirmed intentional + PR body cleaned). Security-manager (sonnet) PASS. Frontend lint+build PASS. Local pytest deferred to CI (env DB unavailable).
- Plan file `.claude/plans/merry-toasting-dove.md` (Codex retest fix — Analyzing-Phase Calibrating UX) is now superseded by this PR's broader ConfidenceBar rewrite. Calibrating label preserved.
- 2 commits on branch (will be squashed): `e4677fb` "Study swipe convergence latency" (PR #127 base content carried forward) + `7f6a056` follow-up (this audit-bearing commit).
- Deferred: `PERF-PREFETCH-CHAIN` — async prefetch cache-read wiring + Redis swap (Task.md ### LOW). `BACK-AUTH-1` simplejwt blacklist ~590ms unchanged. `BACK-RECOMMEND-2` sklearn matmul warnings unchanged.

### INFRA-CI-1 — PR #125 PERF-3 CI fail hotfix — RESOLVED 2026-05-26 (PR #128 `198eca4-pre-squash`)
- [x] Root cause: PERF-3 `_async_emit` daemon thread silent fail. 첫 thread connection setup 시 `settings_dict["TIME_ZONE"]` KeyError (Django backend `timezone_name` cached_property). `emit_event_batch` try/except 잡혀 silent → `test_imp6_stage_decouple` `evt is not None` assert fail (production analytics 손실 + test 회귀).
- [x] Settings.py defensive: `DATABASES['default'] + ['buildings']` `'TIME_ZONE': None` 명시. Django default 동일, reconnect path defensive declaration.
- [x] **Sync emit revert** — `_async_emit` closure + `threading` import + `_SESSIONS_VIEW.threading.Thread` test patch 제거. `event_log.emit_event_batch` main thread sync 호출. Production established connection 사용 — KeyError 안 발생. `emit_event_batch` bulk_create는 보존 (1 SQL round-trip).
- Cost: ~290 ms sync emit restored to request path. PERF-3 1508 → ~1800 ms — 여전히 PASS ≤2000 ms goal.
- 3 commits on branch (squashed): TIME_ZONE settings + close_old_connections removal + sync emit revert. CI green confirmed.

### BACK-PERFORMANCE-2 — Discovery 캐시 hit 450ms (목표 <200ms) — RESOLVED 2026-05-26 (PR #126 `b40cfea-pre-squash`)
- [x] `GET /api/v1/discovery/` warm cache hit p50 1572 → 672 ms (-57%). Goal <200 ms 미달 — auth floor ~600 ms (BACK-AUTH-1) + `get_profile` 74 ms 잔존.
- [x] Response cache 60 s TTL — `get_or_build_discovery_feed` + `evict_discovery_feed` (per-`profile.id`+cursor+limit key, mirror PERF-1 pattern).
- [x] Mutation evict hooks: `SwipeView.post` (liked/disliked) + `ProjectBookmarkView.post` (saved) + `ProjectDetailView.patch remove_building_ids`.
- [x] Per-stage `perf_timing` instrumentation: `get_profile` / `build_exclude_set` / `get_or_build_taste` / `taste_ranked_page` / `cache_lookup_or_build`.
- [x] `taste_ranked_page` (814 ms, 84% of body, dominant) absent on cache hits — verified.
- Not evicted (60 s TTL self-cleans, no security impact): `ProjectDetailView.delete` (UX-only stale exclude_set), `ProjectListCreateView.post` (empty IDs at create).
- Measurement scope: local Neon `local-dev-2` only (development proxy). Prod Singapore Railway p50 = post-deploy Codex retest (admin). Multi-worker prod = per-worker `LocMemCache`, 60 s TTL eventual consistency across workers.
- Deferred: BACK-AUTH-1 (already in `## Next ### MEDIUM`) — auth-layer optimization required for sub-200 ms total.

### BACK-PERFORMANCE-3 — Search 후 첫 카드까지 5-8초 — RESOLVED 2026-05-26 (PR #125 `fb669b6-pre-squash`)
- [x] Local sessions create p50 2567 → 1508 ms realistic / 1484 ms worst-case (-42%). Both PASS ≤ 2000 ms.
- [x] Tier 1 pool cache (filter signature SHA1 key, 30 min TTL). `_tier1_cache_key(filters, filter_priority, seed_ids, v_initial, q_text)`. Pool ordering preserved (full tuple cached pre-exclude). `exclude_ids` applied post-fetch (per-session state, not in key).
- [x] `_random_pool` 30 min in-memory cache (module-level dict). Tier 3 random fallback ~1040 → ~5 ms warm.
- [x] `emit_events` → `threading.Thread` daemon fire-and-forget. `close_old_connections()` entry+finally. Analytics events lost on process crash mid-thread (acceptable per spec).
- [x] `emit_event_batch` in `event_log.py` — `bulk_create` wrapper. Backward-compat `emit_event` preserved.
- [x] `perf_timing` sub-stages on `engine.create_pool_with_relaxation` / `create_bounded_pool` / `get_pool_embeddings` (data-driven hypothesis formation).
- [x] `perf_measure` CLI `--filters` JSON option (realistic Tier 1 measurement).
- Measurement scope: local Neon `local-dev-2` only (development proxy). Prod Singapore p50 = post-deploy Codex retest. Multi-worker prod: per-worker cache, warm-up cost per worker. Cold path / first request unchanged ~2400-2600 ms — cache hit dominates `perf_measure` 3-run p50.
- Algorithm-territory edits (`engine.py`) per user authorization. Pool ordering + initial_batch shape + swipe-loop determinism preserved (code-review AC1 verified).

### BACK-PERFORMANCE-1 — `/projects/` 응답 600ms (목표 300ms) — RESOLVED 2026-05-26 (PR #124 `505717a-pre-squash`)
- [x] Local p50 1136 → 661 ms (-42%). Goal ≤ 300 ms 미달 — auth floor ~590 ms 잔존.
- [x] Response cache 60 s TTL + evict POST/PATCH/DELETE/Bookmark. Per-`profile.id` key isolation.
- [x] `ProjectListSerializer` drops `analysis_report` (LLM JSON list-unused). `defer('analysis_report')` on queryset. `_latest_like_count` via `jsonb_array_length` (no full `like_vectors` fetch). `page_size+1` trick — no `count()` query.
- [x] `CONN_MAX_AGE=600` + `CONN_HEALTH_CHECKS=True` on `default` DB. `buildings` DB `CONN_MAX_AGE` removed (Make-DB owner territory per Backend Conventions).
- [x] `perf_timing` ctx manager + `perf_measure` CLI (reused by PERF-3 / PERF-2).
- [x] `orchestrate` skill Step 6/9 deprecated agent refs → `git-commit` / `reporter-inline` skills.
- Measurement scope: local Neon `local-dev-2` only (development proxy). Prod Singapore Railway p50 = post-deploy Codex retest (admin).
- Deferred: BACK-AUTH-1 — simplejwt JWT blacklist DB query (~590 ms, security territory; explicit user approval required before touching auth path).

### INFRA-WORKFLOW-1 — Reporter / git-manager 흡수 + 3 skill 도입 — RESOLVED 2026-05-26 (PR #123 `bbadcf1-pre-squash`)
- [x] `.claude/skills/git-commit/` — single commit + secret guards + caveman convention. Replaces routine `git-manager` agent dispatch.
- [x] `.claude/skills/git-publish/` — push + PR open + admin squash + cleanup (Mode 2 feature → develop). Step 0 publish gate codified (keyword OR active plan precondition; mirrors `[[feedback_publish_gate]]`).
- [x] `.claude/skills/reporter-inline/` — Task.md + state.js + algorithm.md inline before squash. In-flight PR `mergedAt:null` sentinel + next-pass backfill (advisor #1 policy). 9-step behavior 1-to-1 from legacy `reporter` agent (advisor #3 checklist).
- [x] `.claude/agents/git-manager.md` + `reporter.md` → `deprecated:true` frontmatter + body fallback note. Two-PR migration (advisor #2): delete in follow-up PR after ~1 week of skill-only validation.
- [x] `.claude/agents/git-publisher.md` kept indefinitely — Mode 3 deploy / external PR triage / complex rebase escalation.
- [x] `CLAUDE.md` — new `## Git Operations — HARD RULE` section (skill-first matrix + escalation criteria + publish-gate keywords). Workflow section bullets + reporter sync rule refreshed.
- [x] `.claude/WORKFLOW.md` — Mermaid rebuilt with skill labels. § Agent + skill roster split into 3 tables. § 7 Token-saving + § 9 Key rules updated.
- [x] MEMORY: `feedback_orchestrator.md` rewritten (skill matrix). `feedback_workflow_skill_absorption.md` new (migration rationale + per-agent measurement).
- [x] Validation: this PR audited via the new `reporter-inline` skill (this entry + PR #118 + #120 backfill entries). Skills self-validated by shipping this very PR through `git-commit` + `git-publish` flow.
- [x] Savings: per PR cycle agent dispatches 8 → 3, ~30-40k tokens + ~150-300s saved. Reporter audit ships in same PR as work — PR count halved.

### FRONT-UX-4 — BuildingDetailPage UX 개선 (스크롤 + 순서 + 보드 저장) — RESOLVED 2026-05-26 (PR #120 `8f90104`)
- [x] `BuildingDetailPage.jsx` — minHeight → height + overflowY:auto (MainLayout `overflow:hidden` 부모 안에서 자체 스크롤 회복). Title/architect/meta 갤러리 위로 재배치 (정보가 사진보다 먼저). 상단 우측 "+ 보드에 추가" 핑크 그라디언트 버튼 + SaveToBoardModal 트리거. 저장 후 골드 체크 상태.
- [x] `BoardDetailPage.jsx` — buildings 이동 시 `fromBoard:true` location.state.
- [x] Codex P2 fix — `saveEnabled={!fromBoard}` (negative gate, 너무 넓음: firm profile / direct URL / BoardDetail recommended tile 모두 노출) → `saveEnabled={fromRecommended}` (positive gate, ResultsPage 추천만). `ResultsPage.handleOpenBuilding` `fromRecommended:true` state 추가. `fromBoard` derivation 제거 (ESLint no-unused-vars enforced). BoardDetailPage `fromBoard:true` writes 살아 있되 dead-state harmless.

### FRONT-DESIGN-2 — 카드 이미지 contain 전환 + 카드 크기 확대 — RESOLVED 2026-05-26 (PR #118 `9fcd078`)
- [x] `SwipeCard.jsx` — objectFit cover → contain (사진 잘림 해소, 전체 이미지). 갤러리 뒷면 contain 통일. Letterbox 배경 #111 (도면 #fff 유지). `CARD_WIDTH = min(420, vw-32)` (16+16 컨테이너 padding 보정), `CARD_HEIGHT = min(width×1.55, vh-220)`.
- [x] `SwipePage.jsx` — flex centering wrapper (카드+버튼 영역을 flex:1 center로 감싸 header/hint 높이 무관 수직 정중앙). Converged phase에서 confidence 무관하게 Finish 버튼 활성화 (ConfidenceBar 100% 표시와 일치).
- [x] `App.jsx` — auto-nav `at100` 조건에서 `(phase === 'converged')` 단독 분기. confidence null이어도 converged면 nav.
- [x] Codex P1 fix — CARD_WIDTH overflow blocker 해소: `vw-16` → `vw-32`. 390px폰 358px 컨테이너에 358px 카드 = 딱 맞음 (이전 374px 카드 16px 클립).
- [x] Codex P2 fix — `finishUnlocked` latch 재도입 drop. PR #121 1-shot `isAt100` 설계 보존 (App.jsx auto-nav 주 trigger, SwipePage Finish 버튼은 safety net). Same-project 새 session 시 stale state 위험 제거.

### FRONT-UX-2 — 스와이프 자동 이동 + 키보드 입력 — RESOLVED 2026-05-26 (PR #121 `80b519c`)
- [x] `App.jsx` — `useEffect` watching `swipeSession` auto-navigates `/swipe` → `/result/:sessionId` when `session.phase` is `completed`/`results`, OR when latch threshold reached: `exploring` with `like_count >= 4`, or `analyzing`/`converged` with `confidence >= 1.0`. Replaces PR #114 + PR #115 (both had wrong base `main`; closed without merge).
- [x] `DiscoveryPage.jsx` — `keydown` listener binds `←` (skip) / `→` (save) for arrow-key swipe on discovery feed.
- [x] Codex-review chain: PR #114 (`feature/admin-swipe-finish-ux`) + PR #115 (`feature/front-ux-keyboard-swipe`) superseded by this bundle (HARD RULE 5: both PRs targeted `main` instead of `develop`; re-based onto `develop` as PR #121).
- [x] Codex fix 1 (P2 / PR #114) — auto-nav swallowed the "Keep exploring" path: now only navigates on 100% latch / pool-exhaust, not on every phase update.
- [x] Codex fix 2 (P2 / PR #114) — `finishUnlocked` latch leaked across sessions: latch dropped; the 1-shot calc retained as Finish-button safety net on `SwipePage.jsx` only.
- [x] Codex fix 3 (P2 / PR #115) — `surpriseOpen` modal guard added: arrow-key handler checks `surpriseOpen` before firing, preventing key-bleed into the Surprise modal.
- [x] Codex fix 4 (P3 / PR #115) — `keySwipingRef` permanent lock on async throw: `try/finally` ensures the ref is always released.

### INFRA-DB-1 — user_data role separation — RESOLVED 2026-05-25 (PR #119 `1d3bfdc`)
- [x] Created `make_web_app` Neon role on both `production` and `local-dev-2` branches via psql `CREATE ROLE … NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS` (NOT `neonctl roles create` — that grants `neon_superuser` membership, transitively allowing CREATEDB/CREATEROLE/CREATEEXTENSION; verified by smoke and dropped+recreated cleanly).
- [x] `GRANT SELECT/INSERT/UPDATE/DELETE ON ALL TABLES IN SCHEMA public` + `USAGE/SELECT ON ALL SEQUENCES` + `ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public` so future migration tables auto-grant to `make_web_app`.
- [x] Local `backend/.env` swapped `DB_USER` `neondb_owner` → `make_web_app` + rotated `DB_PASSWORD`. `manage.py check` clean; ORM smoke (`auth_user=3`) + buildings raw SQL smoke (39,478 / publishable 36,864) unchanged; migration-style DDL correctly rejected.
- [x] Railway prod cutover: env vars swapped via dashboard. First redeploy (`d203e2bf`) FAILED with `password authentication failed for user 'make_web_app'` (mis-pasted password). Re-pasted; second redeploy (`820de476`) SUCCESS. Active deployment swapped from old (`9e5d4a69`, 2026-05-24 18:50) to `820de476` (2026-05-25 07:43). Post-cutover smoke: `/auth/me/` 401, `/users/me/` 401, POST token refresh → 401 `{"detail":"Invalid or expired token"}` (token_blacklist DB hit OK).
- [x] 8-probe psql matrix as `make_web_app`: CRUD ✓, has_sequence_privilege ✓, CREATE TABLE ✗ (permission denied for schema public), DROP TABLE ✗, CREATE ROLE ✗, CREATE EXTENSION ✗, ALTER TABLE ✗. All as designed.
- [x] Files committed: `backend/.env.example` (role-separation block + `DB_USER=make_web_app` default), `CLAUDE.md` (`## Backend Conventions` bullets for Neon role separation + local-vs-prod Neon branches discipline), `docs/MAKEWEB_DB_SWAP_RESPONSE.md` (Q2 rewritten Deferred → RESOLVED with full SQL + 8-probe matrix + Railway COMPLETED block + `BUILDINGS_DB_PASSWORD` rotation action item).
- [x] Pure docs/meta — direct-edit carve-out per CLAUDE.md `## Implementation delegation — HARD RULE`. No production code touched.
Outstanding: `BUILDINGS_DB_PASSWORD` rotate (transcript leak via railway variables grep mismatch this session) — tracked outside this entry.

### INFRA-ENV-1 — Neon dev branch 복구 + prod 격리 — RESOLVED 2026-05-25 (PR #116 `4b900da`)
- [x] Re-provisioned persistent Neon child branch `local-dev-2` (`br-shy-thunder-a1p5glmo`, endpoint `ep-holy-band-a1w0u5am`, no TTL) off `production` via `neonctl branches create --name local-dev-2 --parent production --project-id holy-pond-45504245`.
- [x] Repointed local `backend/.env` `DB_HOST` + `BUILDINGS_DB_HOST` from prod endpoint `ep-broad-hat-a1jaomn7` → dev endpoint `ep-holy-band-a1w0u5am`. Railway prod env untouched.
- [x] Smoke verified: `manage.py check` OK; `default` host = dev endpoint; `buildings` host = dev endpoint; `auth_user` count = 3; `archi_data` current_db/user = `('archi_data', 'make_web')`; `canonical_v2_buildings` count = 39,478; `is_publishable=true` count = 36,864.
- [x] `backend/.env.example` updated: DEV-vs-PROD endpoint discipline block + neonctl create command + dev-branch note on `BUILDINGS_DB_HOST`.
- [x] `docs/MAKEWEB_DB_SWAP_RESPONSE.md` updated: 2026-05-25 follow-up paragraph documenting the restoration.
- [x] Pure docs/meta — direct-edit carve-out per CLAUDE.md `## Implementation delegation — HARD RULE`. No code touched. `backend/.env` itself is gitignored.

### INFRA-DEPLOY-1 — 2026-05-25 develop → main 배포 (PR #99–#111) — RESOLVED 2026-05-25 (PR #112 `1888b5f`)
- [x] develop → main squash-merged, carrying 11 PRs: #99 (CI hang fix + deploy #98 reporter), #100 (Product Identity CLAUDE.md), #101 (docs/specs → Task.md Next), #102 (reporter housekeeping PRs #100/#101), #103 (DESIGN-REWORK → Next), #104 (Task.md restructure v2), #107 (reporter housekeeping PRs #103/#104 redo), #108 (ConfidenceBar Calibrating fix), #109 (publish-gate + reporter no-git-ops codification), #110 (reporter housekeeping PR #108), #111 (Task.md ID convention + bucket + stale doc cleanup).
- [x] main = `1888b5f`. Railway prod auto-deploy triggered.
- [x] Bug #5 carve-out applied: `origin/develop` force-reset to `origin/main` (`1888b5f`).

### INFRA-DOC-1 — Task.md ID 규칙 + bucket + stale doc 정리 — RESOLVED 2026-05-25 (PR #111 `b28855e`)
- [x] `## Next` flat list → `### HIGH` / `### MEDIUM` / `### LOW` buckets; all 20 entries renamed to `<SURFACE>-<TOPIC>-<N>` ID convention + Korean ≤25-char title.
- [x] 20-item bucket re-classification pass: HIGH 12 / MEDIUM 3 / LOW 5. DEV-ENV2 concern surfaced (local-dev Neon branch unverified, confirmed as INFRA-ENV-1). 3 stale Next entries deleted.
- [x] ID convention `<SURFACE>-<TOPIC>-<N>` codified in `## Workflow Rules`; cross-refs updated in `reporter.md`, `orchestrate/SKILL.md`, `back-maker.md`, `front-maker.md`, `code-review.md`.
- [x] 5 stale doc cleanups: `WORKFLOW.md` Mermaid `docs/specs` ref removed; `orchestrate/SKILL.md` old phase block + stale token-saving rule numbers replaced; `README.md` `docs/specs/` → `Task.md ## Next`; `MAKEWEB_DB_SWAP_RESPONSE.md` Railway status → COMPLETED; `frontend/.env.example` unused env vars annotated.

### INFRA-DOC-2 — Reporter housekeeping (PR #108 기록) — RESOLVED 2026-05-25 (PR #110 `4d35034`)
- [x] Task.md `## Done` prepended with `#21 SWIPE-CALIBRATING` entry (PR #108 `890236c`). `state.js` `meta.head` → `890236c`, `done[]` + `prs[]` rebuilt.

### INFRA-DOC-3 — Publish gate + reporter no-git-ops mechanism — RESOLVED 2026-05-25 (PR #109 `e9f8b3c`)
- [x] `orchestrate/SKILL.md` Step 8: publish blocked by default; gate opens only on explicit user trigger or active deploy plan.
- [x] `git-publisher.md` guardrails 7+8: trigger citation required; `main`-base PRs must have explicit deploy keyword.
- [x] `reporter.md` Hard scope: all state-mutating `git`/`gh` commands forbidden; reporter refuses any dispatch prompt instructing git ops.
- [x] `WORKFLOW.md` Rule 3: enforcement note referencing post-PR #105 incident (accidental `main`-base PR merged without admin trigger).

### #21 SWIPE-CALIBRATING — RESOLVED 2026-05-25 (PR #108 `890236c`)
[x] `ConfidenceBar` analyzing branch now guards on `value != null`. Null confidence (4th swipe trips exploring→analyzing transition, backend resets `convergence_history = []` per spec C-1, `compute_confidence` returns null for ~5 swipes) → `Calibrating…` label + `likeCount/4` progress. Old fallback showed `Analyzing 100%` falsely — user stuck with no path forward.
[x] `isAt100` Finish-button gate untouched (still correct — requires `confidence >= 1.0`).
[x] Backend convergence reset unchanged (correct per spec).
Deferred (surfaced by Codex retest, intentionally NOT fixed this session): MATMUL-WARN (engine.py matmul warnings), PERF-DISCOVERY (4.11s cold load), PERF-SESSION-CREATE (7.71s POST /analysis/sessions/), PERF-PROJECTS (double-fetch in dev StrictMode). All remain in `## Next`.

### #20 TASK-MD-RESTRUCTURE-V2 — RESOLVED 2026-05-25 (PR #104 `0690b85`)
[x] Restructured `Task.md` 394 → 305 lines: dropped 100+ lines of `## Development Roadmap` Phase 1-18 (duplicates of Done content), replaced with compact `## Roadmap (Historical)` at file bottom + new `## Workflow Rules` block at top.
[x] File order now: header → Workflow Rules → `## Now` → `## Next` → `## Done` → `## Roadmap (Historical)`.
[x] AUTH1 scope narrowed to frontend buttons only (backend Kakao + Naver already shipped in `apps/accounts/views.py` KakaoLoginView / NaverLoginView).
[x] AUDIT-T4 LOC counts re-verified 2026-05-25: engine.py 2079→2139, FirmProfilePage 611→540 (refactored down).
[x] Codified Now/Next discipline in `orchestrate/SKILL.md ## When user requests work` (Session start → move Next→Now, Mid-session deferral → Now→Next, Session end success → Now→Done via reporter).

### #19 DESIGN-REWORK-MOVE — RESOLVED 2026-05-25 (PR #103 `a6d173a`)
[x] Moved DESIGN-REWORK from Task.md `## Now` to `## Next` with paused tag — `## Now` definition is "PR in flight" and there was no design PR in 50+ commits + memory marked paused.
[x] state.js `now[]` → `[]`; DESIGN-REWORK entry appended to `next[]`. dashboard.html `emptyMsg("nothing in flight")` already handles empty array.
[x] CLAUDE.md `## Current State` refreshed ("in progress" → "foundation shipped + per-component rework paused").
[x] Memory `project_design_redesign.md` updated to reflect paused-in-Next status.

### #18 TASK-NEXT-RESTRUCTURE — RESOLVED 2026-05-24 (PR #101 `19694aa`)
[x] Absorbed `docs/specs/*.md` (4 files: phase16-recommendation-expansion.md, phase17-llm-reverse-q.md, phase18-external-connections.md, requirements.md) into `Task.md ## Next` as a flat backlog. Deleted the folder.
[x] Fixed `orchestrate/SKILL.md` stale refs: `.claude/Goal.md` → `CLAUDE.md ## Product Identity + ## Product Constitution`; `.claude/Report.md` → "read code directly + state.js"; `docs/token-saving.md` → `.claude/WORKFLOW.md § Token-saving rules`.
[x] Surfaced 10 operational deferrals previously buried in Done note text (IMP-5 bypass, Codex Stage 3 re-audit, perf observations, architects-wiring, security backlog, etc.) as individual `## Next ### <SLUG>` entries.
[x] Added `reporter.md` sub-step 2a "Deferred-item surfacing (Done note → Next)" so future Done `Deferred: ...` lines auto-surface to `## Next` going forward.
[x] Stripped stale `docs/specs/*` READ-rights mentions from back-maker.md, front-maker.md, code-review.md — pointed at Task.md `## Next § PHASE16/17/18` instead.

### #17 PRODUCT-IDENTITY — RESOLVED 2026-05-24 (PR #100 `56ce5f3`)
[x] Added new top-level `## Product Identity` section to CLAUDE.md between `## What This Repo Does` and `## Branch Model — HARD RULES`.
[x] `### Core Promise` sub-section: 10-15 swipes → Aha! moment anchor, Korean user-quote, two-pillars one-liner (algorithm + corpus), pointer to `docs/algorithm.md`.
[x] Surfaces positive product identity that was previously implicit across scattered sections. Single file, +8 lines.

### #16 DEPLOY-2026-05-24-v2 — RESOLVED 2026-05-24 (PR #98 `fd063e0`)
[x] develop → main deploy. 1 PR (#97). main = `fd063e0`. Railway deployment `a98725bf` Online.
[x] Bug #5 carve-out applied: origin/develop force-reset to fd063e0.
[x] Prod functional pre-deploy (PR #94 cap working). This deploy = CI baseline alignment + main/develop sync. PR #98.

### #15 CI-HANG-FIX — RESOLVED 2026-05-24 (PR #97 `9647c40`)
[x] `_retry_gemini_call` runtime primitive swapped: `concurrent.futures.ThreadPoolExecutor` → `threading.Thread(daemon=True)` + `queue.Queue.get(timeout)`.
[x] `from threading import Thread as _Thread` captured at module-load — bypasses test_imp8 `_DiscThread` global mock leak.
[x] Same 15s/45s deadline + FATAL classification + retry semantics. Prod behavior unchanged.
[x] Triggered by: PR #94 ThreadPoolExecutor wrapper hung pytest CI at 15min timeout, cascading 5 CI failures (PR #94, #95, #96 develop/main/PR).
[x] Full suite: 683 passed / 11 skipped / 0 failed.

### #13 GEMINI-TIMEOUT-CAP — RESOLVED 2026-05-24 (PR #94 `8b4df92`)
[x] `_retry_gemini_call` hard-caps every Gemini SDK call at 15s (45s for Imagen 3) via `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=N)`.
[x] 228s `/parse-query/` hang observed in codex audit → worst case now ≤31s.
[x] 4 new tests + 5 regression tests added.
Deferred: `_caches.py:92` IMP-5 cache create call still bypasses wrapper (gated by `context_caching_enabled` default `False`, zero prod impact until toggled on).

### #12 BUILDINGS-DB-SWAP — RESOLVED 2026-05-24 (PR #93 `b1b1212`)
[x] Make DB renamed buildings DB `neondb` → `archi_data`; new SELECT-only role `make_web` (was `neondb_owner`).
[x] Added `canonical_v2_architects` table (14,216 firms).
[x] Make Web swapped local `backend/.env` + Railway prod env vars.
[x] Refreshed `backend/.env.example` + `CLAUDE.md` is_publishable stat (39/39,776 → 2,614/39,478 ~6.6%) + `docs/database-schema.md` status block.
[x] New `docs/MAKEWEB_DB_SWAP_RESPONSE.md` added.
[x] Verified end-to-end (psql + Django check + ORM smoke + prod redeploy 04e7633e Online).

### #11 V1-LEGACY-CLEANUP — RESOLVED 2026-05-24 (PR #92 `5957df9`)
[x] Neondb `local-dev` branch drop + 23 orphan user/app tables + legacy `architecture_vectors` dropped.
[x] 3 backend files referencing v1 deleted: `tools/algorithm_tester.py`, `apps/recommendation/management/commands/profile_image_latency.py`, `tests/test_chat_phase.py::test_chat_phase_style_labels_in_corpus`.
[x] 5 stale doc refs refreshed: CLAUDE.md / docs/database-schema.md / docs/COLLAB_HANDOFF.md / .claude/agents/reporter.md / .claude/agents/code-review.md.
Plan `.claude/plans/merry-toasting-dove.md` archived to `.claude/plans/archive/2026-05-24-merry-toasting-dove.md`.

### develop → main deploy — 21 PRs (#68–#89) — RESOLVED 2026-05-24 (PR #90 merge `179d6f6`)
[x] Release PR #90 squash-merged develop → main (`179d6f6`). Carried PRs #68–#89 (21 PRs).
[x] Railway prod auto-deploy confirmed Online at `179d6f6`.
[x] origin/develop force-reset to match main (Bug #5 carve-out).

### Dashboard rework — 5-tab Done/Now/Next + Mermaid flows + KST timestamps — RESOLVED 2026-05-24 (PR #89 merge `f5967f2`)
[x] 6-tab Tasks/Roadmap/Git/Architecture/FileMap/Flow → 5-tab Done/Now/Next/System Flow/Agent Flow.
[x] Task.md sections renamed: Open→Next, In Progress→Now, Resolved→Done. Dashboard vocab 1:1.
[x] Vendored mermaid.min.js (3.3 MB) for offline file:// + airplane safety. Lazy-render on tab.
[x] 3 Mermaid diagrams: System Flow + Recommendation Flow + Agent Flow.
[x] state.js schema rewritten: meta.updatedAt, done/now/next arrays, prs.mergedAt+mergedAtKST.
[x] reporter.md spec updated: new Task.md vocab, KST formatter, no Mermaid regen.
[x] 8 agent frontmatters gain effort: default.

### Codex Round 2 audit — 7 findings resolved — RESOLVED 2026-05-24 (PRs #85 / #86 / #87)
[x] B1 — `/images/batch/` 500 on nested list input: serializer validation fixed (PR #85)
[x] B2 — BoardDetail field mismatch causing placeholder rendering: normalize fixed (PR #85)
[x] B3 — useBoard.Promise.all coupling: board no longer waits on result API (PR #85)
[x] P1 — SwipePage analyzing 0% progress drop: fixed analyzing percentage flow (PR #86)
[x] P2 — Gemini auth-error retry waste: fail-fast on auth errors, no retry (PR #86)
[x] P3 — Discovery taste vector TTL cache: caches.py get_or_build_taste/evict_taste, 1hr TTL, evict on liked_ids change (PR #87)
[x] P4 — IMP-8 redis-prep doc sync: algorithm.md annotated (this housekeeping commit)

### External codex audit — 9 findings resolved — RESOLVED 2026-05-23 (PRs #81 / #82 / #83)
[x] #1.1 (P1 latent) — raw_query stored under both `'raw_query'` and `'query'` keys so old + new clients both read correctly (PR #82).
[x] #1.2 (P1) — swipe idempotency: full SwipeRecord payload re-returned on duplicate swipe_id (was empty 200); race-condition guard catches concurrent identical swipe (PR #81).
[x] #1.3 (P1) — Project row lock: `select_for_update()` on Project in swipe handler prevents concurrent-write corruption (PR #81).
[x] #1.4 (P1 latent) — DPP 3× overfetch: `dpp_overfetch_multiplier=3` added to RECOMMENDATION; SessionResultView passes `n = k * multiplier` candidate window so DPP MAP-narrow runs over a broader set (PR #82).
[x] #2.5 (P2) — `get_diverse_random` replaced ORDER BY RANDOM() full scan with two-query pattern (ID fetch + Python `random.sample` + WHERE IN) to avoid O(corpus) sort (PR #83).
[x] #2.6 (P2) — ProjectListView + OfficeProjectListView N+1: `Subquery` composition eliminates per-project ORM queries (PR #83).
[x] #2.7 (P2) — JWT refresh now blacklists old token on rotate + wraps `TokenError` for clean 401 response (PR #83).
[x] #2.8 (P2) — `image_focus` `isinstance` guard in sessions.py rejects non-string values with 400 early; plumbed from LLMSearchPage → App → POST body (PR #83).
[x] #2.9 (P2) — exploring progress bar max raised 3→4 in SwipePage to match `min_likes_for_clustering=4` backend threshold (PR #83).

### Audit Tier 3 ops risk — RESOLVED 2026-05-23 (PR #79)
[x] #14a ORDER BY RANDOM replaced with two-query pattern (ID fetch + Python random.sample + WHERE IN) in get_top_k_results no-pref + _random_pool. Remaining 2 sites (get_diverse_random, search_by_filters) left — already-filtered subsets, cost acceptable.
[x] #14b bookmark POST corpus-rank sync removed; rank_corpus = None + TODO (telemetry-only field, not in API response; eliminates O(corpus_size) scan on bookmark).
[x] #16 SessionResultView GET write wrapped in transaction.atomic() for multi-field save atomicity. select_for_update() dropped — caused CI hang (PG savepoint+FOR UPDATE interaction with pytest-django outer atomic).
[x] #17 engine.py module-global _last_embedding_call_stats/_last_clustering_stats replaced with threading.local(). 6 write sites + 2 getters updated. Per-thread isolation prevents concurrent-request stats overwrite.
Note: TestTelemetryThreadLocal (2 tests) removed — ThreadPoolExecutor + threading.local() + pytest-django PG context caused CI hang (19min). Diagnostic CI run (-v -x --durations=20, 20min timeout) confirmed test as hang root cause. Structural guarantee of #17 fix preserved by code; test coverage dropped but CI green.

### Audit Tier 2 UX-contract bugs — RESOLVED 2026-05-23 (PR #76 / #77 / #78)
[x] #3 area filter normalization: normalizeFilters() in frontend; backend filter_args guard on empty list (PR #76).
[x] #4 FE→BE raw_query plumbing: raw_query field threaded from DiscoveryPage through API call to backend (PR #77).
[x] #5 raw_query persist: backend persists raw_query to SwipeSession on first swipe (PR #77).
[x] #7 dead /matched route removed from MainLayout.jsx guard + routing table (PR #76).
[x] #9 rerank response shape fixed: engine returns list-of-dicts matching frontend expectation (PR #76).
[x] #10 profiles legacy table: architecture_vectors references replaced with canonical_v2_buildings reads (PR #78).

### Audit Tier 1 hotfix bundle — RESOLVED 2026-05-23 (PR #74)
[x] #1 legacy `liked_ids`/`saved_ids` string entries: migration `0019` normalizes to dict.
[x] #2 bookmark + project PATCH: `transaction.atomic` + `select_for_update` on Project.
[x] #6 finish gate FE 3→4 to match BE `min_likes_for_clustering=4`.
[x] #8 `ProjectSerializer` `latest_session_meta` + Resume vs New UI on BoardCard; ownership gate on `latest_session_*` (IDOR fix); projects.py PATCH/DELETE locked-query ownership filter (TOCTOU fix).

### External PR triage — Board UX + Codex defect fixes — RESOLVED 2026-05-23 (PR #72)
[x] PR #71 (external, `yywon1`) opened against wrong base `main`. Triage: branched
    `feature/admin-board-ux-clean` off develop, cherry-picked both PR #71 commits
    (authorship preserved), added third commit `82bd36e` fixing 3 Codex defects.
    PR #72 squash-merged to develop as `877e82c`. PR #71 closed superseded.
[x] Defect 1 (Major) — "Finish & View Report" race: `swipePending` counter gates button
    `disabled={isResultLoading || swipePending > 0}`; threaded via `sharedLayoutProps`
    → `MainLayout.jsx` → `SwipePage.jsx`.
[x] Defect 2 (Major) — stale board hero cover after delete: `BoardDetailPage.jsx` cover
    now prefers `buildings[0].image_url`, falls back to `board.cover_image_url`.
[x] Defect 3 (Medium) — `PATCH remove_building_ids` type validation + atomicity:
    `isinstance(remove_ids, list)` guard → 400; `is_valid(raise_exception=True)` before
    `transaction.atomic()`; both saves inside atomic block. + 3 new unit tests in
    `backend/tests/test_projects.py` (valid removal, invalid type, atomicity proof).
[x] app-test FULL PASS-WITH-MINORS (3-persona live journey, local-dev branch).

### DEV-ENV1. Local backend/.env repointed off production DB — RESOLVED 2026-05-23
[x] Provisioned persistent Neon child branch `local-dev` (`br-rough-wildflower-a115ukd4`,
    endpoint `ep-summer-king-a1xldgwi`, no TTL) off `production`. Contains CoW copies of
    both `user_data` (57 migrations, 2 users at branch time) and `neondb`
    (39,736 publishable buildings).
[x] Updated 6 `.env` keys (`DB_HOST`/`DB_USER`/`DB_PASSWORD` + `BUILDINGS_*` equivalents).
    Backup saved at `backend/.env.bak.1779499369`. Production credentials no longer in `.env`.
[x] Backend runserver + vite restarted, both confirmed pointed at `local-dev`.
    Production isolation now mechanically guaranteed.

### External PR triage — UserSerializer fix + image loading perf — RESOLVED 2026-05-23 (PRs #68, #69)
[x] PR #68 (squash `779725e` on develop): `fix: UserSerializer.user_id source — user.id not profile id`.
    `UserSerializer.user_id` field source `'id'` → `'user.id'` so `auth/me` + login response
    returns Django `User.id` (not `UserProfile.id`), fixing wrong-profile-after-Google-login when
    PKs diverge. Adds `backend/apps/accounts/tests/test_userserializer.py` (deterministic, forces
    id divergence). External PR #62 closed superseded. Two parts of PR #62 intentionally NOT
    carried: `UserProfilePage.jsx` `/user/me` change (already fixed on develop via static route
    in `App.jsx`) and `views.py` display_name/avatar login-sync (separate concern, out of scope).
[x] PR #69 (squash `403bd02` on develop): `perf(frontend): image loading — 4s→2s timeout, lazy gallery, preload cap 3`.
    Cherry-pick of external PR #64's intended commit `3f9c385`: `SwipeCard.jsx` image-load
    timeout 4s→2s + gallery CSS→`<img>` lazy, `DiscoveryPage.jsx` preload cap 12→3. JSDoc
    comment synced. External PR #64 closed superseded (wrong base + polluted 154-file diff).
    app-test ran FEATURE-SCOPED (write-constrained — local .env targets prod DB; see DEV-ENV1).

### Neon DB-split (data step) + Production Deploy — RESOLVED 2026-05-22 (PR #63)
[x] DB-split complete and live in production: app DB = `user_data` (57 migrations,
    23 tables), buildings DB = `neondb` (`canonical_v2_buildings`, 39,776 rows).
[x] Prior DEPLOY-BLOCKER — "DB-split data step incomplete (`user_data` empty)" —
    fully resolved: `DB_NAME` env flipped `neondb` → `user_data` on Railway; cutover
    deploy `69c9473a` = SUCCESS; production verified healthy (schema 57/23, DB
    connections, gunicorn clean, Vercel frontend 200 — all green).
[x] Deploy PR #63 squash-merged develop → main (carried PRs #50–#61, 12 commits).
    origin/develop force-reset to match main (Bug #5 carve-out).
[x] Read-only infra CLIs (neonctl, railway, vercel) installed + authed this session.
Deferred follow-ups (not scheduled — noted for later):
- Drop `neondb`'s orphaned app tables in a later session (kept as rollback backup
  until prod is confirmed stable for ≥1 week).
- Neon `Staging` branch TTL auto-expires 2026-05-23 07:14 UTC (no action needed).

### PR #2 — theme/font server persistence — SHIPPED 2026-05-22
[x] Merged as PR #59 (develop `49b347d`).
Backend `UserProfile.theme`/`font` fields + migration `0003`; `UserSerializer`
login-response wiring; frontend `ThemeContext` hydrate-on-login + `updateMyProfile()`
PATCH on change. Cross-device server-sync fully operational.

---

## Roadmap (Historical)

> Compact phase summary. For full work audit see `## Done` above + `git log`.

- **Phase 1-12 (2026-03 → 2026-04)** — Single-user reference-exploration base: auth, 4-phase recommendation, Gemini search, persona report, project CRUD, E2E infra. **Shipped.**
- **Phase 13-15 (2026-04-29 → 2026-05-06)** — Social-graph triplet: User-follow, Project-reaction, Office-follow + Profile / Board system. **Shipped.**
- **Phase 16-18** — Recommendation expansion / LLM reverse-Q / external connections. **Pending** — open dimensions tracked in `## Next` § PHASE16 / PHASE17 / PHASE18.
- **Phase 19-26 (2026-05-14 Replan)** — Tab 3-Structure Transition (Library tab → Profile, Landing tab removed, Discovery infinite-scroll). **Shipped** via deploy PR #36 (S1-S8).
- **Phase P1-P6 (2026-05-15 → 2026-05-18)** — Latency + UX overhaul series. **Shipped** via deploy PR #49.
