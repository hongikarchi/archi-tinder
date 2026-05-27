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
// Reporter: Mermaid sources may be stale — commit e8296f5 touched frontend/src/api/{auth,projects,client}.js + new components/{GoogleLoginButton,GoogleVerifyButton,VerifyGateModal}.jsx. Next session should refresh systemFlow + agentFlow diagrams by hand.
window.PROJECT_STATE = {
  meta: {
    name: 'ArchiTinder — Make Web',
    updatedAt: '2026-05-27 20:23 KST',
    head: 'db81e0f',
    branch: 'feature/admin-guest-auth-frontend',
  },

  done: [
    {
      id: 'FULL-LOGIN-REDESIGN-1',
      title: 'Guest-first onboarding + 보드 4번째 verify gate',
      completedAt: '2026-05-27',
      prs: [154, 155],
      note: 'Rebuilt after codex feature/codex-guest-auth-* archived for 6 issues — all resolved. Backend PR #154 db81e0f: UserProfile.is_guest + onboarding_role + consent_accepted_at + consent_policy_version + migration 0004 + GuestLoginView (3/min throttle) + GuestPromoteView (atomic Branch 1 merge 8 FK rules + Branch 2 in-place transform w/ username collision guard) + CustomTokenObtainPairSerializer is_guest claim on refresh→access + IsVerifiedUser + ProjectListCreateView inline gate (403 verify_required). 14 pytest. Frontend PR #155 e8296f5-pre-squash: LoginPage terminal 3-step wizard + 동의합니다 PIPA + dual CTA + VerifyGateModal + useGoogleLogin extracted to GoogleLoginButton/GoogleVerifyButton (conditional mount safety) + cross-device merge onPromoted(user,merged) handleLogin re-sync + SaveToBoardModal Option A auto-retry + SurpriseBoardModal Option B toast + conditional GoogleOAuthProvider mount (no literal fallback). 24/24 loginFlow.test.mjs. Plan: ~/.claude/plans/merry-toasting-dove.md.',
    },
    {
      id: 'BACK-BOARD-PERF-1',
      title: '/projects/<id>/ ~879ms → <500ms — response cache 60s',
      completedAt: '2026-05-27',
      prs: [148],
      note: 'Board detail PR #147 pattern applied. PROJECT_DETAIL_TTL=60 + version key + evict_project_detail. Invalidation 8 sites. CRITICAL fix-loop: delete evict order race. test_board_detail_perf.py 7 cases. sha be6c8f5.',
    },
    {
      id: 'BACK-PROFILE-PERF-1',
      title: '/users/<id>/ 895ms → <1s — thumbnail-only fetch + response cache',
      completedAt: '2026-05-27',
      prs: [147],
      note: 'engine.get_building_thumbnails NEW + thumbnail swap + UserProfileDetailView 60s cache + invalidation 5 sites + test_profile_perf.py 9 cases. 기대: cold ~500-700ms, warm ~100ms. sha d3e110c.',
    },
    {
      id: 'BACK-PERFORMANCE-4',
      title: 'Discovery cold 4.6s → ~1.5-2.5s — taste vector cap + SQL top-K',
      completedAt: '2026-05-27',
      prs: [146],
      note: '2/3 fixes (warm thread rolled back). taste_ranked_page CTE removed + compute_user_taste_vector recent-50 cap. 기대: 4.6s → ~1.5-2.5s. sha 4af6b4d.',
    },
    {
      id: 'BACK-ALGO-1',
      title: 'Required-slate hard WHERE + first-swipe prefetch cache seed',
      completedAt: '2026-05-27',
      prs: [145],
      note: '2 backend algorithm/perf fixes from 4th Codex retest 2026-05-26. F3 required-slate hard WHERE: _REQUIRED_SLATE_FIELDS_SET frozenset + _build_required_slate_where(filters) helper for Modes V+F. F4 first-swipe prefetch cache seed: SessionCreate seeds cache.set(prefetch:{sid}:1, ...). code-review fix-loop CRITICAL caught SQL param order inversion. test_engine_filter_hard_constraint.py NEW 4 cases. sha 3894ffd.',
    },
    {
      id: 'FRONT-UX-FIXES-1',
      title: 'Image timeout + Gallery CTA nav + Board card click',
      completedAt: '2026-05-26',
      prs: [144],
      note: '3 frontend UX correctness fixes. F2 SwipeCard image timeout 2000ms→4000ms + retry path removed. F5 Gallery CTA: navigate(/buildings/${card.image_id}). F7 BoardDetail building card click: building.id OR chain at 3 sites. FRONT-UX-5 (Gallery CTA backlog) closed by F5. sha 77e1aef.',
    },
    {
      id: 'BACK-CORRECTNESS-1',
      title: '/projects/ cache evict + dedupe project_id + orphan project',
      completedAt: '2026-05-26',
      prs: [143],
      note: '3 backend correctness fixes. Fix 1 cache evict: evict_projects_list at 5 sites. Fix 2 dedupe scope: early project_id resolve. Fix 3 orphan Project: deferred to inside session_insert + transaction.atomic. tests/test_session_create_correctness.py NEW 9 tests. sha 6e23c82.',
    },
    {
      id: 'INFRA-CLEANUP-1',
      title: 'Dead code 정리 (-1124 LOC)',
      completedAt: '2026-05-26',
      prs: [142],
      note: 'Salvaged from codex feature/codex-cleanup-stale-develop. Removed: PostSwipeLandingPage.jsx (696 LOC) + GalleryOverlay.jsx (181 LOC) + optimization_results.json (247 LOC). Doc refs cleaned. FRONT-UX-1 obsolete (App.jsx already redirects to /discovery). FULL-LOGIN-REDESIGN-1 added to backlog after codex archive. sha 9872ab0.',
    },
  ],

  now: [],

  next: {
    high: [
      {
        id: 'BACK-RECOMMEND-1',
        title: 'Project 두번째 세션이 이전 taste를 모름',
        note: 'Code audit 2026-05-27: SessionCreateView resolves project_id only to skip dedupe; session_insert still creates phase=exploring with empty like_vectors/convergence/preference state. Project.liked_ids/disliked_ids/saved_ids persist but are not read. Primary edit: views/sessions.py warm-start policy + engine.get_pool_embeddings(project liked_ids) scoped to active project; tests in test_session_create_correctness.py for no cross-project leakage and progress semantics.',
      },
      {
        id: 'FULL-LANGUAGE-1',
        title: '한/영 언어 설정 토글 없음',
        note: 'Code audit 2026-05-27: UserProfile preferences are theme/font only; UserSerializer and UserProfileSelfUpdateSerializer need language parity. ThemeContext + AppearanceSettings are the local persistence/UI pattern. ParseQueryView currently calls services.parse_query(conversation_history) with no user preference, so language must be passed from request.user.profile.language and prompt inference overridden.',
      },
      {
        id: 'BACK-LLM-2',
        title: '채팅 기록이 다른 기기에서 사라짐',
        note: 'Code audit 2026-05-27: LLMSearchPage stores messages/conversationHistory/latest* under archithon_chat_${userId}_${mode}_${projectId||new}; backend Project only has raw_query and AnalysisSession has no chat field. ParseQueryView validates conversation_history but does not persist it. Likely edit: Project conversation_history or ConversationTurn + dedicated idempotent append endpoint + frontend write-through cache.',
      },
      {
        id: 'FRONT-DESIGN-1',
        title: '디자인 시스템 컴포넌트 리워크 (paused)',
        note: 'Code audit 2026-05-27: 581 inline style call sites. Largest FE files: BoardDetailPage 1049, UserProfilePage 992, App 838, BuildingDetailPage 711, SwipePage 683, FirmProfilePage 540. tokens.css exists; index.css is mostly utilities. Slice leaf components first (ArticleCard/ProjectCard/BoardCard), then SwipeCard/BuildingDetailPage; each slice lint+build+screenshot.',
      },
    ],
    medium: [
      {
        id: 'BACK-PERFORMANCE-5',
        title: 'Swipe latency 0.7-1.5s 흔들림',
        note: 'Code audit 2026-05-27: SwipeView still does update/phase/refresh_pool/get_pool_embeddings/MMR-or-farthest selection in request transaction. Async prefetch only helps after next_bid is selected. Use existing [SWIPE TIMING] lock/embed/select/prefetch/total + embedding cache stats to bucket variance before code changes.',
      },
      {
        id: 'BACK-AUTH-2',
        title: 'Cache JWT 통합 테스트 hardening',
        note: 'Code audit 2026-05-27: CachedJWTAuthentication cache-hit returns cached_user directly; signals invalidate User save/delete but not bulk update. test_jwt_cache is unit-level with patched cache and mocked tokens. Add DRF pipeline tests via /auth/me, signal invalidation test, stale inactive-user cache negative test, and cross-instance shared-cache check.',
      },
      {
        id: 'INFRA-DB-2',
        title: 'test DB role CREATE DATABASE permission',
        note: 'Code audit 2026-05-27: settings.py imports PG default/buildings from env; .env.example correctly says runtime role make_web_app has NOCREATEDB. Root conftest tries SQLite/mirrored buildings, but app-local conftests differ and some invocations still hit pytest-django DB creation. Decide make_web_test CREATEDB vs --reuse-db preprovisioned test_user_data vs temporary owner swap; document in CONTRIBUTING + backend/.env.example.',
      },
      {
        id: 'FRONT-LAYOUT-1',
        title: 'Desktop wide-screen 레이아웃 어색함',
        note: 'Code audit 2026-05-27: body is 100vh/overflow hidden and each page owns scroll. BuildingDetail stays maxWidth 820 with only masonry media query; BoardDetail/UserProfile maxWidth 1100 but hero/profile remain mobile-centered. Start with BuildingDetail desktop split, then Board/User grids.',
      },
      {
        id: 'FULL-LEGAL-1',
        title: 'PIPA/GDPR consent 없음 (public launch 차단)',
        note: 'Partial mitigation shipped via FULL-LOGIN-REDESIGN-1: UserProfile.consent_accepted_at + consent_policy_version fields + terminal-style "동의합니다" capture on guest wizard. Still pending: legally-reviewed copy, Privacy/Terms routes, retention/export/delete flow. PIPA-compliant copy + UI/UX legal review required before public launch.',
      },
      {
        id: 'PERF-PREFETCH-POOL-RISK',
        title: 'Neon connection pool 모니터링 (post PR #134 deploy)',
        note: 'Code audit 2026-05-27: SwipeView can spawn _async_prefetch_thread and _emit_telemetry_thread; both close connections in finally but can open thread-local DB connections while main request holds one. Practical transient footprint is main + telemetry + prefetch, depending on timing. Monitor Neon active conns during swipe bursts; consider bounded executor if peak rises.',
      },
      {
        id: 'INFRA-DB-CLEANUP-1',
        title: 'Unverified guest row 누적 정리 (conditional)',
        note: 'FULL-LOGIN-REDESIGN-1 PR #154/#155 ships guest accounts with no cleanup (user explicit decision — Q5). Throttle is 3/min/IP for /auth/guest/ but botnet w/ IP rotation can still grow rows. Monitor Neon "auth_user WHERE email = \'\' AND is_active = True" row count weekly. If growth > 500 rows/week sustained, open this and implement: Django management command "delete unverified WHERE last_active < 30 days AND swipe_count == 0" + cron/Railway scheduled job.',
      },
    ],
    low: [
      {
        id: 'FRONT-AUTH-1',
        title: 'LoginPage에 Kakao/Naver 버튼 없음',
        note: 'Code audit 2026-05-27: api/auth.js already supports generic socialLogin(provider). Backend has Kakao/Naver endpoints; LoginPage rewrite (FULL-LOGIN-REDESIGN-1 PR #155) now uses terminal-style wizard but Kakao/Naver still missing. After FULL-LOGIN-REDESIGN-1 ships, Kakao/Naver should be secondary upgrade options on returning-user CTA + Settings → linked-providers section.',
      },
      {
        id: 'FULL-REFACTOR-1',
        title: '큰 파일 분해 필요 (engine.py 2383 LOC 등)',
        note: 'Code audit 2026-05-27: engine.py 2383, BoardDetailPage 1049, UserProfilePage 992, App 838, BuildingDetailPage 711, SwipePage 683, FirmProfilePage 540. engine.py mixes SQL/search/pool/embedding/MMR/telemetry; App owns auth/session/routing; big pages mix data+mutations+styles. Refactor only behavior-neutral slices with tests/screenshots.',
      },
      {
        id: 'BACK-RECOMMEND-3',
        title: 'Profile-tab 사무소/유저 추천 endpoint 없음',
        note: 'Code audit 2026-05-27: no /recommendations/profile/ route exists. Office + OfficeProjectLink models and OfficeDetail project hydration exist; social Follow/OfficeFollow exists for exclusions. engine.compute_user_taste_vector helps requester taste only; firm/user recommendations need cached/precomputed vectors, not per-request loops. Cold-start branch required.',
      },
      {
        id: 'BACK-EXTERNAL-1',
        title: 'FirmProfilePage에 외부 기사 surface 없음',
        note: 'Code audit 2026-05-27: FirmProfilePage already renders office.articles when present and ArticleCard expects {title,url,source,date}; backend serializer explicitly excludes articles and Office model has no article table. Add async/cached endpoint or OfficeArticle model; do not block OfficeDetail TTFC.',
      },
      {
        id: 'INFRA-QUEUE-1',
        title: 'corpus_rank telemetry 꺼져있음',
        note: 'Code audit 2026-05-27: engine.compute_corpus_rank still exists as corpus-wide pgvector ROW_NUMBER query, but ProjectBookmarkView sets bookmark telemetry rank_corpus=None and tests assert it is not called. Do not restore sync path; only background queue with tests moving from placeholder-null to enqueued-job semantics. Low until more background jobs justify worker infra.',
      },
    ],
  },

  prs: [
    {
      number: 155,
      title: 'feat(FULL-LOGIN-REDESIGN-1): terminal wizard + verify gate (PR 2 of 2)',
      mergedAt: null,
      mergedAtKST: null,
      sha: null,
    },
    {
      number: 154,
      title: 'feat(FULL-LOGIN-REDESIGN-1): guest auth + board-4 verify gate (PR 1 of 2)',
      mergedAt: '2026-05-27T10:47:11Z',
      mergedAtKST: '2026-05-27 19:47 KST',
      sha: 'db81e0f',
    },
    {
      number: 152,
      title: 'docs(BACKLOG-DETAIL-1): code-audit detail for pending Task.md backlog items',
      mergedAt: '2026-05-27T01:16:56Z',
      mergedAtKST: '2026-05-27 10:16 KST',
      sha: '91a4771',
    },
    {
      number: 151,
      title: 'fix(BACK-CI-HOTFIX-1): expose prefetch_strategy in swipe response — PR #145 test repair',
      mergedAt: '2026-05-27T00:55:45Z',
      mergedAtKST: '2026-05-27 09:55 KST',
      sha: 'f4eeee9',
    },
    {
      number: 150,
      title: 'perf(BACK-SWIPE-PERF-1): drop wasteful card lookups in _async_prefetch_thread',
      mergedAt: '2026-05-27T01:16:31Z',
      mergedAtKST: '2026-05-27 10:16 KST',
      sha: '7d62d43',
    },
    {
      number: 149,
      title: 'perf(FRONT-IMG-LAZY-1): image lazy-load gap fill — 2 sites + LCP fetchpriority',
      mergedAt: '2026-05-27T01:13:23Z',
      mergedAtKST: '2026-05-27 10:13 KST',
      sha: '77ab03a',
    },
    {
      number: 148,
      title: 'perf(BACK-BOARD-PERF-1): /projects/<id>/ ~879ms → <500ms — response cache (60s)',
      mergedAt: '2026-05-27T01:09:47Z',
      mergedAtKST: '2026-05-27 10:09 KST',
      sha: 'be6c8f5',
    },
    {
      number: 147,
      title: 'perf(BACK-PROFILE-PERF-1): /users/<id>/ 895ms → <1s — thumbnail-only fetch + response cache',
      mergedAt: '2026-05-27T01:02:21Z',
      mergedAtKST: '2026-05-27 10:02 KST',
      sha: 'd3e110c',
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
