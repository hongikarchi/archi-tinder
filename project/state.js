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
window.PROJECT_STATE = {
  meta: {
    name: 'ArchiTinder — Make Web',
    updatedAt: '2026-05-26 20:27 KST',
    head: '17f7d65',
    branch: 'feature/back-llm3-gemini-cache-timeout',
  },

  done: [
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
    {
      id: 'INFRA-DEPLOY-3',
      title: 'railway migrate align + Redis prod guard + docs drift',
      completedAt: '2026-05-26',
      prs: [137],
      note: 'Codex retest of develop=d53b232 surfaced 3 prod-safety drifts. railway.toml buildCommand: dropped migrate --noinput per INFRA-DB-1 (Railway runtime make_web_app has no DDL; next schema migration would have failed); operator runs migrate manually with DB_USER=neondb_owner swap. collectstatic kept. settings.py _check_async_prefetch_safety() helper: raises ImproperlyConfigured at module import when DEBUG=False && async_prefetch_enabled && !REDIS_URL — silent LocMem fallback in prod = thread cost without multi-worker coherence (same bug class PR #134 PERF-PREFETCH-CHAIN just fixed). Helper extracted mirroring _build_caches_dict pattern; called after RECOMMENDATION dict closes. .env.example default DJANGO_DEBUG=True keeps operator migrate path safe (guard short-circuits). tests/test_cache_backend.py TestAsyncPrefetchSafetyGuard 4 cases (prod+REDIS_URL OK, DEBUG bypass, async_prefetch=False bypass, prod misconfig raises). Docs drift: swipe.py:79+:723 "primary path does NOT consume" stale (PR #134 now consumes); settings.py:142 + .env.example:72 "JTI cache" stale (PR #133 final = JWT user-row cache). manage.py check PASS · pytest 20/20 · code-review PASS · security-manager PASS. Deferred surfaced to Next ### MEDIUM: BACK-AUTH-2 (cache JWT integration test hardening) + INFRA-DB-2 (test DB role CREATE DATABASE permission). sha 09a3b7c-pre-squash.',
    },
    {
      id: 'INFRA-DOC-6',
      title: 'orchestrate / git-publisher / web-testing AGENTS skill-regime 정렬',
      completedAt: '2026-05-26',
      prs: [136],
      note: 'Cherry-picked session-start docs work (010edf8) onto post-deploy develop. 3 files re-aligned with 2026-05-26 skill-migration regime (INFRA-WORKFLOW-1, PR #123). orchestrate/SKILL.md: drop git-manager/reporter agent refs from frontmatter, Step 5/7/8/10, Rules. Step 6→git-commit skill, Step 8 default=git-publish skill, Step 9=reporter-inline+git-commit+git-publish. git-publisher.md: edge-case role (Mode 3 deploy / external PR / complex rebase / push rejection / mid-merge failure). New "When this agent is called" preamble refuses routine publish. Mode 1 renamed "Internal push escalation (fallback only)". web-testing/AGENTS.md: scope split (agent contract → .claude/agents/app-test.md, this doc → runner + shared dev-login). web-tester→app-test rename 2026-04-28. Dev-login 404 hard-FAIL (no skip-auth fallback). skip_login flag removed. Modes table FULL vs FEATURE-SCOPED (supersedes fast/strict /review). Pure docs/policy edit per CLAUDE.md carve-out. Skipped code-review + security + app-test (sub-MINOR meta). Old feature/admin-docs-skill-migration-sync branch (orphan, base pre-deploy) replaced. sha 80e7d86-pre-squash.',
    },
    {
      id: 'INFRA-DEPLOY-2',
      title: '2026-05-26 develop → main 배포 (PRs #116-#134, perf sweep + Redis)',
      completedAt: '2026-05-26',
      prs: [135],
      note: 'develop → main squash-merged. main = d53b232. Railway prod auto-deploy SUCCESS (deployment 047a6e2f RUNNING). Carried 15 PRs since main 1888b5f (PR #112 prior release): #116-#134 inclusive. Bug #5 carve-out applied (HARD RULE 4 SOLE permitted force) — origin/develop force-reset to origin/main via gh api PATCH refs/heads/develop --force=true. Precondition checked (no in-flight feature PR targeting develop). Tree-equivalence verified empty diff origin/main origin/develop. Railway Redis service (redis:8.2.1) provisioned admin via dashboard + REDIS_URL=${{Redis.REDIS_URL}} env set on backend service before merge. Post-deploy: gunicorn 4 workers booted clean, no django_redis import errors. Prod smoke (CLI): / 404 no-route, /auth/dev-login/ 404 (DEBUG=False gates per design), /api/v1/projects/ unauthenticated 401, /auth/token/refresh/ empty 400. No 5xx. Direct cache-hit latency NOT measurable from CLI (DEBUG=False blocks dev-login + Google OAuth needs browser) — admin runs Codex retest separately. Outstanding: PERF-PREFETCH-POOL-RISK monitoring (Neon free-tier 25 conn limit; async prefetch daemon thread + main worker = 2 conns/swipe at peak).',
    },
    {
      id: 'PERF-PREFETCH-CHAIN',
      title: 'async_prefetch chain end-to-end (PR 4/4 FINAL of perf sweep)',
      completedAt: '2026-05-26',
      prs: [134],
      note: 'PR 4 (FINAL) of 4 in plan merry-toasting-dove.md. Three changes restore IMP-8 chain: (1) _async_prefetch_thread off-by-one fix — pf_bid +2, pf2_bid +3 (4 sites: exploring pf/pf2 + analyzing pf/pf2 via compute_mmr_next round arg). Prior stored cards for next_card slot not prefetch slot. (2) Async-branch consumer in SwipeView.post: cache.get(prefetch:{sid}:{saved_current_round}) reads prior thread write; batched get_buildings_by_ids 1-RTT. Cache miss preserves None graceful fallback. (3) Dedupe guards (code-review fix-loop): pf_id=None if ==next_bid, pf2_id=None if ==next_bid or ==pf_id. Prevents analyzing-path collision (compute_mmr_next can return same card for T lookahead + T+1 main pick; frontend non-instant-swap path no dedupe). async_prefetch_enabled False→True. test_imp7 sync→async-thread. test_imp8 new TestAsyncBranchConsumerIntegration. docs/algorithm.md Hyperparameter Space async_prefetch_enabled False→True. security-manager PASS with availability warning (PERF-PREFETCH-POOL-RISK filed). sha dc296bc-pre-squash (squash 26626a4).',
    },
    {
      id: 'BACK-RECOMMEND-2',
      title: 'sklearn KMeans matmul warning 압제 (PR 2/4 of perf sweep)',
      completedAt: '2026-05-26',
      prs: [132],
      note: 'PR 2 of 4. Re-scoped from "dtype align" to np.errstate suppression after empirical falsification (input already float64). Real cause: sklearn KMeans centroid normalization on high-dim unit-norm vectors. Helper engine.py:90-99 _silenced_kmeans_fit. Two call sites swapped (1664 + 1701). sample_weight preserved. Byte-identical (random_state=42 + n_init=3 deterministic; topic06 9/9 PASS under -W error::RuntimeWarning). code-review + security-manager PASS. sha 785f4ad-pre-squash (squash b53e633).',
    },
    {
      id: 'SWIPE-CONVERGENCE-10',
      title: '10-swipe target + multimodal escalation + stuck-state safety',
      completedAt: '2026-05-26',
      prs: [130],
      note: 'Replaces closed PR #127 (codex feature/algo-convergence-study). Algorithm policy synced to docs/algorithm.md: convergence_threshold 0.08→0.13, target_swipes=10, min_likes_for_multimodal=11 (K-Means K=2 gated behind target+1), convergence_min_recent_likes=2. Frontend stuck-state safety floor beyondTargetFloor. Engine _with_image_focus bug fix. async_prefetch_enabled True→False reverted (chain broken; later resolved in PR 4). Swipe.py stale 0.08 defaults → 0.13. 2 commits squashed at merge to 83db42c.',
    },
  ],

  now: [],

  next: {
    high: [
      {
        id: 'BACK-LLM-1',
        title: 'LLM 채팅이 검색에 필요한 정보를 다 안 모음',
        note: 'parse_query.py already implements a 0-2 turn probe budget with free-choice abstract A-vs-B axes. This task drops persona classification (P1-P4) and re-scopes the work to (1) define an explicit "required info slate" the chat must collect (filter fields like program / style / material / location_country), and (2) refine LLM probe behaviour so it deterministically targets missing slate fields instead of free-choice axes. Open: which fields are required vs optional, probe priority order, optional-slate inclusion, fallback when 2-turn budget exhausts with slate gap, conversational shape (abstract A-vs-B vs direct field-asking), cross-language posture (Korea-first preserved). Acceptance: TTFC budget 4000ms not regressed; 2-turn probe always lands required-slate ≥1 field; A/B slate-completion-rate vs current prompt.',
      },
      {
        id: 'BACK-RECOMMEND-1',
        title: 'Project 두번째 세션이 이전 taste를 모름',
        note: 'Same Project can host multiple AnalysisSession rows; user "Resume" creates a fresh session while Project.liked_ids accumulates. Today session #2 algorithm state (like_vectors, convergence_history, phase) starts from scratch despite the user having liked 12 buildings in session #1. Open: carry policy (A independent / B exposure-only / C dislike-only / D fade-decay / E full warm-start / F user toggle); warm-start phase entry; SessionCreateView wiring at views/sessions.py:28. Acceptance: deterministic behaviour, session #2 TTFC not regressed, A/B on saved_ids growth + completion rate.',
      },
      {
        id: 'FRONT-UX-1',
        title: '신규 사용자에게 홈이 빈 화면',
        note: 'First-time user with 0 projects lands on Home → project picker — currently shows nothing deliberate. Frontend-only (HomePage / ProjectListPage). Open: onboarding shape, copy + voice, visual illustration. Acceptance: 0-project user sees deliberate empty state; CTA path to first swipe ≤2 clicks; no regression on existing-projects rendering.',
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
        id: 'BACK-LLM-3',
        title: 'Gemini cache 호출에 timeout 없음',
        note: '_caches.py:92 IMP-5 Gemini context-cache create call bypasses the _retry_gemini_call timeout wrapper (PR #94 15s cap). Gated by context_caching_enabled flag (default OFF) — zero prod impact until toggled on. Fix: wrap call in _retry_gemini_call; ~5 LOC backend edit.',
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
      number: 140,
      title: 'fix(BACK-LLM-3): wrap Gemini cache creation with timeout',
      mergedAt: null,
      mergedAtKST: null,
      sha: null,
    },
    {
      number: 139,
      title: 'Release: 2026-05-26 — Codex retest follow-ups + skill docs alignment (PRs #136-#138)',
      mergedAt: '2026-05-26T10:18:28Z',
      mergedAtKST: '2026-05-26 19:18 KST',
      sha: '17f7d65',
    },
    {
      number: 138,
      title: 'fix(FULL-SESSION-DEDUPE-1): session create POST retry → duplicate Project/Session',
      mergedAt: '2026-05-26T10:30:00Z',
      mergedAtKST: '2026-05-26 19:30 KST',
      sha: 'b209aa1',
    },
    {
      number: 137,
      title: 'fix(INFRA-DEPLOY-3): railway migrate align + Redis prod guard + docs drift',
      mergedAt: '2026-05-26T09:33:00Z',
      mergedAtKST: '2026-05-26 18:33 KST',
      sha: 'ffc55e3',
    },
    {
      number: 136,
      title: 'docs(INFRA-DOC-6): align orchestrate + git-publisher + web-testing with skill regime',
      mergedAt: '2026-05-26T08:34:41Z',
      mergedAtKST: '2026-05-26 17:34 KST',
      sha: '54d4d1e',
    },
    {
      number: 135,
      title: 'Release: 2026-05-26 — perf sweep + Redis + swipe fixes (PRs #116-#134)',
      mergedAt: '2026-05-26T08:11:28Z',
      mergedAtKST: '2026-05-26 17:11 KST',
      sha: 'd53b232',
    },
    {
      number: 134,
      title: 'feat(PERF-PREFETCH-CHAIN): wire async prefetch chain end-to-end',
      mergedAt: '2026-05-26T07:38:03Z',
      mergedAtKST: '2026-05-26 16:38 KST',
      sha: '26626a4',
    },
    {
      number: 133,
      title: 'feat(BACK-AUTH-1): cache JWTAuthentication.get_user() per-user',
      mergedAt: '2026-05-26T06:47:23Z',
      mergedAtKST: '2026-05-26 15:47 KST',
      sha: '4c72513',
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
