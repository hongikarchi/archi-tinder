/*
 * project/state.js — ArchiTinder Make Web project state.
 *
 * Maintained by `reporter-inline` skill (2026-05-26+) — runs INLINE in the
 * feature PR before squash merge. Legacy `reporter` agent kept as deprecated
 * fallback. Hand-edited only inside `systemFlow` / `recommendationFlow` /
 * `agentFlow` Mermaid bodies and the `milestones` archive (semi-static); all
 * other sections are rebuilt from `.claude/Task.md`, `gh pr list`, and
 * `.claude/agents/<name>.md` + `.claude/skills/<slug>/SKILL.md` frontmatter.
 *
 * Loaded via <script> by `project/dashboard.html`, which opens by double-click
 * via file:// — no fetch, no server, no build step.
 *
 * Three-bucket model:
 *   - `done`      = resolved work (merged, shipped, archived)
 *   - `now`       = current initiative slice (one or more PRs in flight)
 *   - `next`      = backlog grouped by priority: { high: [], medium: [], low: [] }
 *                   HIGH   = next initiative slice candidate (specced, ready to pull)
 *                   MEDIUM = uncategorised pending (review needed before promotion)
 *                   LOW    = explicitly deferred / skipped (revisit when context shifts)
 *
 * Time convention: all human-facing timestamps are `YYYY-MM-DD HH:mm KST`.
 * PRs additionally carry the raw `mergedAt` (ISO 8601 UTC from `gh pr list`)
 * so the value can be re-parsed by any consumer. In-flight (not-yet-merged)
 * PRs carry `mergedAt: null` sentinel; next reporter-inline pass backfills.
 */
// Reporter: Mermaid sources may be stale — commit dc1651b touched backend/apps/recommendation/engine.py (taste_ranked_page CTE removal + compute_user_taste_vector recent-50 cap) and views/swipe.py (_async_warm_taste daemon thread post-atomic). recommendationFlow Engine + Views nodes affected. Next session may add cache-warm annotation.
window.PROJECT_STATE = {
  meta: {
    name: 'ArchiTinder — Make Web',
    updatedAt: '2026-05-27 01:00 KST',
    head: '3894ffd',
    branch: 'feature/admin-discovery-perf',
  },

  done: [
    {
      id: 'BACK-PERFORMANCE-4',
      title: 'Discovery cold 4.6s → <1s — taste vector cap + SQL top-K + async warm',
      completedAt: '2026-05-27',
      prs: [146],
      note: '3 backend perf fixes targeting Discovery cold-load 4.6s → <1s per user goal 2026-05-27 (all pages <1s). Codex retest measured get_or_build_taste 1.55s + taste_ranked_page 2.23s + /images/batch 1.06s. Fix 1 (engine.py:2347 taste_ranked_page): CTE removed; direct ORDER BY embedding <=> v OFFSET LIMIT lets PG planner top-K heap scan k=12 vs N=37k publishable rows. Fix 2 (engine.py:2280 compute_user_taste_vector): recent-50 cap via Project.objects.order_by(updated_at) ASC + all_likes[-50:]; bounds cold get_pool_embeddings SQL size. Fix 3 (swipe.py _async_warm_taste daemon thread post-atomic): evict 후 background thread가 get_or_build_taste 호출해서 cache repopulate; next Discovery navigation cache hit. CRITICAL fix-loop catch: 초기 spawn 위치가 transaction.atomic() 안이라 READ COMMITTED isolation으로 uncommitted project.save 못 봄 → permanent 1-swipe-behind cache. Spawn을 atomic block 외부 (line 758)로 이동. Invariant 주석 양쪽 site에 추가. test_discovery_perf.py NEW 4 cases. test_imp8_async_prefetch.py 3 thread count assertions bumped. manage.py check PASS · 9 non-DB tests PASS · @django_db tests INFRA-DB-2 차단 (CI 실행). code-review PASS after race fix-loop · security-manager PASS. 기대: Discovery cold 4.6s → <1s. pgvector ANN index Make-DB owned 추가 불가. sha dc1651b-pre-squash.',
    },
    {
      id: 'BACK-ALGO-1',
      title: 'Required-slate hard WHERE + first-swipe prefetch cache seed',
      completedAt: '2026-05-27',
      prs: [145],
      note: '2 backend algorithm/perf fixes from 4th Codex retest 2026-05-26 (base 72bf8d3). F3 required-slate hard WHERE: "Japan museum" search → Bolivia card bug. Root cause filters as score CASE only; pool SQL WHERE only is_publishable=true AND score > 0. Bolivia 통과 because style/program positive score. Fix: _REQUIRED_SLATE_FIELDS_SET frozenset (mirrors services/parse_query.REQUIRED_SLATE_FIELDS + cross-ref comment) + _build_required_slate_where(filters) helper. Mode V (HyDE blend) + Mode F (filter-only) applied; Mode H (RRF) excluded — rank-fusion semantics differ. Tier 2 relaxation drops location_country before create_bounded_pool — slate WHERE auto-absent. F4 first-swipe prefetch cache seed: saved_current_round=1 (incremented at swipe.py:548 BEFORE save) → cache.get(prefetch:{sid}:1) always miss → sync compute 770ms vs 156ms cache hit. SPEC DEVIATION: back-maker source-reading caught — spec :0 → actual :1. SessionCreate seeds cache.set(prefetch:{sid}:1, {prefetch_card_id: initial_batch[1], prefetch_card_2_id: initial_batch[2]}, timeout=60). code-review fix-loop CRITICAL caught SQL param order inversion in 2 execute call sites: _slate_params + params + ... → corrected to params + ... + _slate_params + params + .... Without fix, mixed slate+non-slate filters caused psycopg2 cast errors (Mode V silent fallback) or filter cross-contamination (Mode F). test_engine_filter_hard_constraint.py NEW 4 cases incl Mode V param order regression catch. test_session_create_correctness.py +2 F4 cases. code-review PASS after fix-loop. security-manager PASS (parameterized SQL, UUID-isolated cache). F4 tests local INFRA-DB-2 blocked; CI runs them. sha 72f8f27-pre-squash.',
    },
    {
      id: 'FRONT-UX-FIXES-1',
      title: 'Image timeout + Gallery CTA nav + Board card click',
      completedAt: '2026-05-26',
      prs: [144],
      note: '3 frontend UX correctness fixes from 4th Codex retest 2026-05-26 of develop=72bf8d3. F2 SwipeCard image timeout 2000ms→4000ms + ?retry=1 cache-bust 삭제 (별도 URL 없음 대역폭만 2배). Singapore R2 1.7-2.6s 정상 처리. Fallback chain covers_by_type.exterior→interior→aerial→detail→drawing→gallery[N]. F5 Gallery CTA: 이전 openGallery() in-card 3D flip이 실제 no-op (back-face JSX setShowGallery(true) unreachable). 현재 navigate(/buildings/${card.image_id}) → BuildingDetailPage. SwipePage onGalleryOpen prop 무해 drop. 죽은 코드 (back-face JSX, hasBeenOpened) 별도 cleanup PR. F7 BoardDetail building card click: building.id를 OR chain 3 sites 추가 (BuildingTile 180, handleDeleteSelected 458, render bid 926). Stored {id: bld_...} shape 정상 인식 → 클릭 navigate. FRONT-UX-5 (Gallery CTA backlog) closed by F5. code-review PASS · security-manager PASS (XSS-safe — image_id BUILDING_ID_RE 검증; IDOR-safe — board-scoped ownership). npm run lint clean + build PASS. sha b5c53f2-pre-squash.',
    },
    {
      id: 'BACK-CORRECTNESS-1',
      title: '/projects/ cache evict + dedupe project_id + orphan project',
      completedAt: '2026-05-26',
      prs: [143],
      note: '3 backend correctness fixes from 3rd Codex retest 2026-05-26 of develop=17f7d65. Fix 1 cache evict: evict_projects_list(profile.id) added at 5 sites — sessions.py dedupe-hit return path + sessions.py post-create + swipe.py post-liked/disliked save + reports.py post-final_report + reports.py post-report_image. ProjectListSerializer exposes liked_ids/saved_ids/final_report/report_image so all 5 sites needed eviction. Fix 2 dedupe scope: PR #138 dedupe extended — early project_id resolve before dedupe lookup; if project_id provided + matches user-owned Project, dedupe SKIPPED (App.jsx:723 fresh-swipe flow honored); project_id missing or no match → existing (user, name, raw_query, filters) scope runs. Fix 3 orphan Project: Project.objects.create() deferred to inside session_insert stage AND wrapped in transaction.atomic() with AnalysisSession.objects.create() (fix-loop catch — closes session_insert-step orphan too). tests/test_session_create_correctness.py NEW 9 tests. Full suite 553 passed (zero regression). code-review PASS after 1 fix-loop (reports.py + transaction.atomic). security-manager PASS (IDOR-safe — user= clause on early project_id resolve; cache eviction scoped to profile.id). P2-4 pytest bootstrap finding merged into existing INFRA-DB-2 backlog. sha d87a5f9-pre-squash.',
    },
    {
      id: 'INFRA-CLEANUP-1',
      title: 'Dead code 정리 (-1124 LOC)',
      completedAt: '2026-05-26',
      prs: [142],
      note: 'Salvaged from codex feature/codex-cleanup-stale-develop (commit 986bd5e). Codex branch docs/skill changes rejected as PR #136 INFRA-DOC-6 regressions; only file deletions kept. Removed: frontend/src/pages/PostSwipeLandingPage.jsx (696 LOC, PROF3+PROF4 mockup with unwired backend TODOs), frontend/src/components/GalleryOverlay.jsx (181 LOC, initial-commit artifact; PR #120 BuildingDetailPage rolled its own inline gallery), backend/tools/optimization_results.json (247 LOC, Optuna search artifact, zero refs). Doc refs cleaned: CONTRIBUTING.md role B table drops PostSwipeLandingPage; BoardDetailPage.jsx:143 JSDoc drops PostSwipeLanding mirror. Session decisions batched in this audit: (1) FRONT-UX-1 obsolete (App.jsx:783 already redirects index → /discovery, no empty home needed); removed from ## Next ### HIGH. (2) FULL-LOGIN-REDESIGN-1 added to ## Next ### HIGH after codex guest-auth branches (guest-first onboarding direction) archived locally; 6 issues require re-design before re-implementation (upgrade path, PIPA consent, JWT distinction, cleanup job, clientId fix, LoginPage conflict). (3) FULL-REFACTOR-1 LOC list updated. npm run lint clean. Cross-cutting grep verified zero non-self refs for all 3 deleted files. sha beb1d74-pre-squash.',
    },
    {
      id: 'BACK-LLM-1',
      title: 'LLM 채팅이 검색에 필요한 정보를 다 안 모음',
      completedAt: '2026-05-26',
      prs: [141],
      note: 'codex-authored branch cherry-pick. parse_query.py +87 LOC refines LLM chat-phase to deterministically target missing required-slate filter fields. REQUIRED_SLATE_FIELDS=(program, material, style, location_country) + REQUIRED_SLATE_PROBE_PRIORITY module constants. System prompt + few-shot examples rewritten (drop prior free A-vs-B axis selection). _normalise_filter_priority promotes required-slate keys to front. _repair_required_slate injects style: Contemporary when slate gap present (intermediate probe OR terminal). Korean probe examples updated; Korea-first preserved. test_back_llm1_required_slate.py NEW 5 tests (prompt content, slate promotion, default injection, terminal repair). Open dimensions resolved: 4-field slate; priority = program > material > style > location; fallback = Contemporary; mix of direct + axis Korean probes. Deferred: A/B 50-query benchmark harness (acceptance criterion c) = post-merge measurement. Behavioral note: _normalise_filter_priority shifts engine._build_score_cases rank weights (required-slate outranks temporal). Intended. code-review PASS · security-manager PASS (no prompt injection; user input never touches system prompt; mocks-only tests). sha cdbf5c7-pre-squash.',
    },
    {
      id: 'BACK-LLM-3',
      title: 'Gemini cache 호출에 timeout 없음',
      completedAt: '2026-05-26',
      prs: [140],
      note: 'codex-authored branch cherry-pick. _caches.py:92 client.caches.create wrapped in zero-arg _create_cache closure routed through _svc._retry_gemini_call(_create_cache) — inherits existing 15s timeout cap (PR #94). context_caching_enabled flag default OFF preserved; zero prod impact. Pre-emptive safety. test_imp5_context_caching.py +17 LOC test_gemini_create_runs_through_retry_timeout_wrapper — MagicMock-based, no Gemini network hit. code-review PASS (~5 LOC budget honored). security-manager PASS (closure captures no secrets, _retry_gemini_call logs only type+str(e) no API key). 9 pre-existing DB-requiring tests blocked by INFRA-DB-2 (permission denied to create database); not introduced by this PR. sha 715e06e-pre-squash.',
    },
    {
      id: 'FULL-SESSION-DEDUPE-1',
      title: 'Session create POST retry → 중복 Project/Session',
      completedAt: '2026-05-26',
      prs: [138],
      note: 'P0 data-integrity bug surfaced by Codex retest 2026-05-26 of develop=d53b232. POST /analysis/sessions/ takes ~15s on cold pool (execute_pool_sql=14.7s). Frontend api/core.js retry loop retried ALL methods on AbortError → server created 2 Project + 2 AnalysisSession rows. User reproduction: 2 boards same name, one with 4 photos one with 0. Belt + suspenders fix. Frontend api/core.js: _IDEMPOTENT_METHODS={GET,HEAD,OPTIONS}; POST/PATCH/DELETE throw on first network error. Frontend api/sessions.js: SESSION_CREATE_TIMEOUT_MS=30000 per-call override. Backend views/sessions.py: dedupe guard at start of SessionCreateView.post; 30s window matching (user, project.name, project.raw_query, project.filters); hit returns existing session with deduped:true HTTP 200 (vs 201 fresh). tests/test_session_create_dedupe.py 8 cases (baseline 201, hit 200, 30s expiry, different raw_query/name/filters, project_id=None retry, response shape). Trade-off: recordSwipe (POST) no-retry; backend idempotency_key still guards server-side. Race window ~100ms unreachable from single-tab client with retry-gate. code-review + security-manager PASS. app-test FEATURE-SCOPED PASS 5/5 incl. dedupe path 200 + deduped:true + same session_id + only 1 Project row (Django shell verified). Deferred to Next ### MEDIUM: BACK-PERFORMANCE-4 (Discovery 4.6s) + BACK-PERFORMANCE-5 (Swipe latency variability) + FRONT-UX-5 (View Gallery click no-op). sha 3fcbe3c-pre-squash.',
    },
  ],

  now: [],

  next: {
    high: [
      {
        id: 'BACK-RECOMMEND-1',
        title: 'Project 두번째 세션이 이전 taste를 모름',
        note: 'Same Project can host multiple AnalysisSession rows; user "Resume" creates a fresh session while Project.liked_ids accumulates. Today session #2 algorithm state (like_vectors, convergence_history, phase) starts from scratch despite the user having liked 12 buildings in session #1. Open: carry policy (A independent / B exposure-only / C dislike-only / D fade-decay / E full warm-start / F user toggle); warm-start phase entry; SessionCreateView wiring at views/sessions.py:28. Acceptance: deterministic behaviour, session #2 TTFC not regressed, A/B on saved_ids growth + completion rate.',
      },
      {
        id: 'FULL-LOGIN-REDESIGN-1',
        title: 'Guest-first onboarding + login UX 재설계',
        note: 'User decision 2026-05-26: codex guest-auth branches (guest-first + 터미널 UX + 3-step intro/name/role wizard + OAuth secondary) 방향 채택. 단 codex 구현은 6 issues로 폐기 (local archive). 6 issues to resolve: (1) upgrade path — guest → OAuth 시 swipe history merge 로직, (2) PIPA consent 라인 재추가 (LoginPage), (3) unbounded row 누적 — CAPTCHA + cleanup job, (4) JWT 구분 — is_guest claim + IsNotGuest permission, (5) clientId guest-only-google-disabled literal 제거, (6) LoginPage 충돌 surface 확인. Open: guest vs OAuth balance, onboarding step 수, role enum 매핑 P1-P4, terminal UI vs DESIGN.md §3 적합성. Acceptance: guest+upgrade round-trip preserves history+boards; PIPA 유지; JWT 구분; cleanup job 운영.',
      },
      {
        id: 'FULL-LANGUAGE-1',
        title: '한/영 언어 설정 토글 없음',
        note: 'Decision 2026-05-25: language is a user setting (Korean / English), not browser-locale auto-detected. Pattern mirrors PR #54 + PR #59 theme/font persistence. Backend: UserProfile.language CharField, default ko. Frontend: LanguageContext mirroring ThemeContext. Drives LLM chat answer language + UI label rendering. Acceptance: language PATCH round-trip, LLM chat follows setting, ≥1 high-traffic UI surface bilingual, no theme/font regression.',
      },
      {
        id: 'BACK-LLM-2',
        title: '채팅 기록이 다른 기기에서 사라짐',
        note: 'Decision 2026-05-25: persist chat conversation to backend DB, not just browser localStorage. Today LLMSearchPage.jsx stores conversationHistory in localStorage — single-browser, lost on logout / device switch. Backend currently has no conversation field. Plan: add Project.conversation_history JSONField (or ConversationTurn table — open) + migration + serializer + idempotent append endpoint. Acceptance: logout + re-login on any browser re-hydrates conversation; idempotent append survives network retry.',
      },
      {
        id: 'FRONT-DESIGN-1',
        title: '디자인 시스템 컴포넌트 리워크 (paused)',
        note: 'Foundation shipped: PR #54 (tokens.css 4 themes) + PR #59 (theme/font server persistence). Remaining: per-component visual rework (~7,700 LOC) — inline styles → CSS Modules, light-theme polish, leaf→hub order. Resume via /plan per slice. Acceptance per slice: lint+build clean, light+dark variants regression-free, no token added without DESIGN.md update.',
      },
    ],
    medium: [
      {
        id: 'BACK-PERFORMANCE-4',
        title: 'Discovery 첫 로딩 4.6s',
        note: 'Codex retest 2026-05-26: /discovery 4.63s + /images/batch 1.61s. Backend stage breakdown: get_or_build_taste 1.55s + taste_ranked_page 2.23s. Origin: Discovery computes taste vector then pgvector rank page. Target: warm-cache <500ms, cold <1.5s. Investigate caching of taste vector (per-user TTL?) + pgvector index tuning.',
      },
      {
        id: 'BACK-PERFORMANCE-5',
        title: 'Swipe latency 0.7-1.5s 흔들림',
        note: 'Codex retest 2026-05-26: browser swipe 1.82s/1.75s/1.12s/1.81s; server swipe 1.50s/1.38s/0.746s/1.36s. PR4 async prefetch consume IS working — 3rd swipe with cache hit drops to 156ms prefetch stage. But variability is high. Identify which stage causes 0.7→1.5s spread (DB latency? embedding cache miss? pgvector?). Target swipe p95 ≤1.0s and p50 ≤0.5s on Singapore prod.',
      },
      {
        id: 'FRONT-UX-5',
        title: 'View Gallery 클릭 가끔 no-op',
        note: 'Codex retest 2026-05-26: Profile card View Gallery 버튼 클릭 시 가끔 navigate 안 됨. 재현 1회. 직접 /board/<id> URL 접근은 정상. 원인 의심: button handler event propagation 또는 React Router race. 로그 + 재현 시나리오 필요.',
      },
      {
        id: 'BACK-AUTH-2',
        title: 'Cache JWT 통합 테스트 hardening',
        note: 'apps/accounts/authentication.py:74 cache-hit path skips parent get_user(). Current tests unit-level (CachedJWTAuthentication.get_user direct). Need integration: DRF authenticate() pipeline end-to-end, User.save() post_save signal auto-invalidation, is_active=False stale cache must NOT return 200, cross-instance Redis multi-worker correctness. Codex retest 2026-05-26 P3 hardening. Not a blocker (security-manager PASS\'d PR #133); defense-in-depth for future cache-key drift or signal-wiring regression.',
      },
      {
        id: 'INFRA-DB-2',
        title: 'test DB role CREATE DATABASE permission',
        note: 'Codex retest 2026-05-26 — Full test_imp8_async_prefetch.py blocked at DB setup; make_web_app role has no CREATE DATABASE permission. test_user_data DB creation fails. Options: (a) operator migrate / test-DB-provision with DB_USER=neondb_owner pre-pytest, (b) dedicated make_web_test role with CREATEDB grant on Neon, (c) pytest-django --reuse-db against pre-provisioned test_user_data. Choose one + document in CONTRIBUTING.md / .env.example.',
      },
      {
        id: 'FRONT-LAYOUT-1',
        title: 'Desktop wide-screen 레이아웃 어색함',
        note: 'Current viewport-lock layout is mobile-first. Detail pages on desktop work but unoptimised. Low priority — desktop is secondary.',
      },
      {
        id: 'FULL-LEGAL-1',
        title: 'PIPA/GDPR consent 없음 (public launch 차단)',
        note: 'Phase 13+ Profile/Board public/private visibility shipped. PIPA + GDPR posture for signup data collection / consent flow / retention policy still open. Required before public launch.',
      },
      {
        id: 'PERF-PREFETCH-POOL-RISK',
        title: 'Neon connection pool 모니터링 (post PR #134 deploy)',
        note: 'PR 4 PERF-PREFETCH-CHAIN flipped async_prefetch_enabled True — every prod swipe now spawns a daemon thread holding its own DB connection until _connections.close_all() runs in finally. Under high concurrent swipe load: connections ≈ (concurrent_requests × 2) — main worker + prefetch thread. Neon free tier 25 conns; Railway Gunicorn 2-4 workers. Acceptable current scale (~tens of daily users). Monitor Neon dashboard post-deploy + revisit if peak concurrency exceeds 8-10 conns. Mitigation: (a) connection pool size increase, (b) explicit thread-local pool, (c) PgBouncer in front. security-manager flagged on PR #134.',
      },
    ],
    low: [
      {
        id: 'FRONT-AUTH-1',
        title: 'LoginPage에 Kakao/Naver 버튼 없음',
        note: 'Backend Kakao + Naver implementation shipped. Frontend LoginPage.jsx has Google button only — Kakao + Naver buttons remaining.',
      },
      {
        id: 'FULL-REFACTOR-1',
        title: '큰 파일 분해 필요 (engine.py 2139 LOC 등)',
        note: 'File decomp: engine.py 2139, App.jsx 817, BoardDetailPage 1045, UserProfilePage 992, PostSwipeLandingPage 696, SwipePage 666, FirmProfilePage 540.',
      },
      {
        id: 'BACK-RECOMMEND-3',
        title: 'Profile-tab 사무소/유저 추천 endpoint 없음',
        note: 'REC1 shipped as Push S3. REC2 (firm) + REC3 (user) target GET /api/v1/recommendations/profile/. Acceptance: p95 ≤800ms Singapore, cold-start graceful, is_publishable=true gating preserved.',
      },
      {
        id: 'BACK-EXTERNAL-1',
        title: 'FirmProfilePage에 외부 기사 surface 없음',
        note: 'Surfaces external articles about a firm on FirmProfilePage (Space / ArchDaily / news keyword match). Phase 15 shipped External DM wiring. Acceptance: ≤10 most recent articles per firm, open in new tab, no FirmProfilePage TTFC regression.',
      },
      {
        id: 'INFRA-QUEUE-1',
        title: 'corpus_rank telemetry 꺼져있음',
        note: 'corpus_rank telemetry field currently None on every swipe (PR #79 turned off the synchronous O(corpus_size) scan; product does not consume the field). Re-enabling requires Celery + Redis + worker process + monitoring — over-investment for one telemetry column. Revisit when multiple background jobs accumulate.',
      },
    ],
  },

  prs: [
    {
      number: 146,
      title: 'perf(BACK-PERFORMANCE-4): Discovery cold 4.6s → <1s — taste vector cap + SQL top-K + async warm',
      mergedAt: null,
      mergedAtKST: null,
      sha: null,
    },
    {
      number: 145,
      title: 'fix(BACK-ALGO-1): required-slate hard WHERE + first-swipe prefetch cache seed',
      mergedAt: '2026-05-27T00:25:00Z',
      mergedAtKST: '2026-05-27 09:25 KST',
      sha: '3894ffd',
    },
    {
      number: 144,
      title: 'fix(FRONT-UX-FIXES-1): image timeout + Gallery CTA nav + Board card click',
      mergedAt: '2026-05-26T14:50:00Z',
      mergedAtKST: '2026-05-26 23:50 KST',
      sha: '77e1aef',
    },
    {
      number: 143,
      title: 'fix(BACK-CORRECTNESS-1): /projects/ cache evict + dedupe project_id + orphan project',
      mergedAt: '2026-05-26T13:50:00Z',
      mergedAtKST: '2026-05-26 22:50 KST',
      sha: '6e23c82',
    },
    {
      number: 142,
      title: 'chore(INFRA-CLEANUP-1): prune dead pages + optuna artifact (-1124 LOC)',
      mergedAt: '2026-05-26T12:50:00Z',
      mergedAtKST: '2026-05-26 21:50 KST',
      sha: '9872ab0',
    },
    {
      number: 141,
      title: 'fix(BACK-LLM-1): enforce LLM required slate',
      mergedAt: '2026-05-26T11:38:00Z',
      mergedAtKST: '2026-05-26 20:38 KST',
      sha: '72bf8d3',
    },
    {
      number: 140,
      title: 'fix(BACK-LLM-3): wrap Gemini cache creation with timeout',
      mergedAt: '2026-05-26T11:31:00Z',
      mergedAtKST: '2026-05-26 20:31 KST',
      sha: '92915b8',
    },
    {
      number: 139,
      title: 'Release: 2026-05-26 — Codex retest follow-ups + skill docs alignment (PRs #136-#138)',
      mergedAt: '2026-05-26T10:18:28Z',
      mergedAtKST: '2026-05-26 19:18 KST',
      sha: '17f7d65',
    },
  ],

  agents: [
    {
      name: 'back-maker',
      role: 'Django/DRF backend code — only touches files inside backend/. Runs flake8 after changes.',
      model: 'sonnet',
      effort: 'default',
    },
    {
      name: 'front-maker',
      role: 'React/Vite frontend code — only touches files inside frontend/. Runs ESLint after changes.',
      model: 'sonnet',
      effort: 'default',
    },
    {
      name: 'code-review',
      role: 'Static code review — integration correctness, API contracts, logic bugs, error handling. Inner loop, per change, pre-commit.',
      model: 'sonnet',
      effort: 'default',
    },
    {
      name: 'security-manager',
      role: 'Security scan — SQL injection, auth bypass, secret leakage, XSS, token storage. Inner loop, per change, pre-commit.',
      model: 'sonnet',
      effort: 'default',
    },
    {
      name: 'app-test',
      role: 'Pre-push gate — live-browser 3-persona swipe journey + drift check. FULL or FEATURE-SCOPED mode.',
      model: 'sonnet',
      effort: 'default',
    },
    {
      name: 'git-manager',
      role: 'Single commit — stages changed files (excluding secrets), writes caveman-terse conventional-commit message. Never pushes. (deprecated — superseded by .claude/skills/git-commit/)',
      model: 'haiku',
      effort: 'default',
    },
    {
      name: 'git-publisher',
      role: 'Edge-case publisher. Mode 3 develop→main deploy + post-deploy develop force-reset + external PR triage + complex rebase + push rejection / mid-merge failure. Routine feature→develop publishes go through git-publish skill (not this agent).',
      model: 'sonnet',
      effort: 'default',
    },
    {
      name: 'reporter',
      role: 'Session-end — updates Task.md, regenerates this dashboard state, conditionally syncs docs/algorithm.md. (deprecated — superseded by .claude/skills/reporter-inline/)',
      model: 'sonnet',
      effort: 'default',
    },
  ],

  systemFlow: {
    title: 'System Flow — Browser → Vercel → Django → DBs / external services',
    mermaid: `flowchart LR
  Browser["Browser"]
  Vercel["Vercel React<br/>frontend/src"]
  ApiClients["Frontend API clients<br/>frontend/src/api/{auth,sessions,projects,<br/>discovery,profiles,social,images}.js"]
  Django["Django backend<br/>backend/config/urls.py"]
  Apps["apps.accounts · apps.recommendation<br/>apps.profiles · apps.social"]
  Views["views/{sessions,swipe,search,projects,<br/>reports,discovery,telemetry}.py"]
  Engine["engine.py<br/>services/parse_query.py"]
  DefaultDB[("default DB · Neon<br/>User · Project · AnalysisSession · SwipeEvent")]
  BuildingsDB[("buildings DB · Neon<br/>canonical_v2_buildings (read-only raw SQL)")]
  Redis[("Redis cache (prod) · LocMemCache (local)<br/>JWT user-row cache · async prefetch · response cache")]
  Gemini["Gemini API"]
  R2["Cloudflare R2 image CDN"]
  OAuth["Google · Kakao · Naver OAuth"]

  Browser --> Vercel --> ApiClients --> Django --> Apps --> Views
  Views --> Engine
  Views --> DefaultDB
  Views --> Redis
  Engine --> BuildingsDB
  Engine --> Redis
  Engine --> Gemini
  Views --> OAuth
  Browser -. images .-> R2`,
  },

  recommendationFlow: {
    title: 'Recommendation / Swipe Flow — LLM parse → swipe loop → result',
    mermaid: `flowchart TD
  Search["LLMSearchPage.jsx"]
  ParseAPI["POST /api/v1/parse-query/<br/>ParseQueryView"]
  ParseSvc["services/parse_query.py<br/>Gemini chat · structured_filters<br/>visual_description"]
  SessionCreate["POST /api/v1/analysis/sessions/<br/>SessionCreateView"]
  SwipeUI["SwipePage.jsx"]
  SwipeAPI["POST /api/v1/analysis/sessions/&lt;id&gt;/swipes/<br/>SwipeView"]
  Engine["engine.py<br/>compute_mmr_next · farthest_point_from_pool<br/>refresh_pool_if_low · compute_taste_centroids"]
  RawSQL[("canonical_v2_buildings<br/>raw SQL · is_publishable=true")]
  ResultUI["ResultsPage.jsx"]
  ResultAPI["GET /api/v1/analysis/sessions/&lt;id&gt;/result/<br/>SessionResultView"]
  Reports["reports.py<br/>generate_report · generate_report_image"]

  Search --> ParseAPI --> ParseSvc --> SessionCreate
  SessionCreate --> SwipeUI
  SwipeUI --> SwipeAPI --> Engine --> RawSQL
  Engine --> SwipeUI
  SwipeUI -- converged --> ResultUI --> ResultAPI --> Engine
  ResultUI --> Reports`,
  },

  agentFlow: {
    title: 'Agent + Skill Flow — Main Session → orchestrate skill → skills + agents',
    mermaid: `flowchart LR
  Session["Main Session<br/>opus 4.7 · architecture · plan · dispatch"]
  Orchestrate["orchestrate skill<br/>feature implementation playbook"]
  BackMaker["back-maker · sonnet"]
  FrontMaker["front-maker · sonnet"]
  Review["code-review · sonnet"]
  Security["security-manager · sonnet"]
  GCommit["git-commit skill<br/>(replaces git-manager agent)"]
  AppTest["app-test · sonnet"]
  RInline["reporter-inline skill<br/>(replaces reporter agent;<br/>inline before squash)"]
  GPublish["git-publish skill<br/>(Mode 2; replaces git-publisher agent<br/>default routine path)"]
  GPubAgent["git-publisher · sonnet<br/>(Mode 3 deploy / triage / rebase only)"]

  Session --> Orchestrate
  Orchestrate --> BackMaker
  Orchestrate --> FrontMaker
  BackMaker --> Review
  FrontMaker --> Review
  Review --> Security
  Security --> GCommit
  GCommit --> AppTest
  AppTest --> GPublish
  GPublish --> RInline
  RInline --> GCommit
  GCommit -.-> GPublish
  GPublish -. escalate edge .-> GPubAgent`,
  },

  milestones: [
    { phase: '1–12', focus: 'Single-user reference exploration base (auth, 4-phase recommendation, Gemini search, persona report, project CRUD, E2E infra)', status: 'shipped' },
    { phase: '13', focus: 'Profile system — firm + user profiles, public/private boards', status: 'shipped' },
    { phase: '14', focus: 'Board system — board detail view, follow, "Love this!" reaction', status: 'shipped' },
    { phase: '15', focus: 'Social foundation — external DM links, MATCHED! results screen', status: 'shipped' },
    { phase: '16', focus: 'Recommendation expansion — Profile-tab office + user recs', status: 'pending' },
    { phase: '17', focus: 'LLM chat refinement — reverse-Q to fill required info slate (persona classification dropped)', status: 'pending' },
    { phase: '18', focus: 'External connections — firm article crawl (Space, ArchDaily, news)', status: 'pending' },
    { phase: '19–26', focus: 'Tab 3-structure replan + P1–P6 latency/UX overhaul', status: 'shipped' },
    { phase: 'design', focus: 'Design-system redesign — light-mode tokens, 4-theme switcher, frontend rework', status: 'in progress' },
  ],
};
