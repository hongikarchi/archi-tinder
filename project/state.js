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
// Reporter: Mermaid sources may be stale — commit dc296bc touched apps/recommendation/views/swipe.py (async prefetch thread off-by-one + consumer cache.get + dedupe guards + flag flip). Recommendation flow Mermaid still accurate at function-graph level; system flow Redis node already reflects async prefetch usage from PR #131.
window.PROJECT_STATE = {
  meta: {
    name: 'ArchiTinder — Make Web',
    updatedAt: '2026-05-26 16:31 KST',
    head: '4c72513',
    branch: 'feature/algo-prefetch-chain-consume',
  },

  done: [
    {
      id: 'PERF-PREFETCH-CHAIN',
      title: 'async_prefetch chain end-to-end (PR 4/4 FINAL of perf sweep)',
      completedAt: '2026-05-26',
      prs: [134],
      note: 'PR 4 (FINAL) of 4 in plan merry-toasting-dove.md. Depends on PR 1 INFRA-REDIS-1 (Redis multi-worker coherence). Plan complete after merge. Three changes restore IMP-8 chain: (1) _async_prefetch_thread off-by-one fix — pf_bid index +2, pf2_bid +3 (prior was +1, +2; stored cards matched next_card slot not prefetch slot). 4 formula sites updated (exploring pf/pf2 + analyzing pf/pf2 via compute_mmr_next round arg). (2) Async-branch consumer in SwipeView.post: cache.get(prefetch:{sid}:{saved_current_round}) reads prior thread write; batched engine.get_buildings_by_ids([next, pf, pf2]) for 1-RTT hydration; cache miss preserves None graceful fallback. (3) Dedupe guards (code-review fix-loop MAJOR): pf_id=None if ==next_bid, pf2_id=None if ==next_bid or ==pf_id. Prevents analyzing-path collision where compute_mmr_next can return same card for T lookahead + T+1 main pick. Frontend App.jsx:521+536 non-instant-swap path does NOT dedupe; without backend guard user would see same card twice. async_prefetch_enabled False→True. test_imp7_pool_cache line 635 sync→async-thread. test_imp8_async_prefetch new TestAsyncBranchConsumerIntegration with cache-hit + miss + dedupe regression tests. docs/algorithm.md Hyperparameter Space async_prefetch_enabled False→True. security-manager PASS with availability warning (filed as PERF-PREFETCH-POOL-RISK in Next medium — Neon conn pool monitoring; under high concurrent swipe, conns ≈ requests×2 could approach 25 free-tier limit). sha dc296bc-pre-squash.',
    },
    {
      id: 'BACK-AUTH-1',
      title: 'JWT user-row cache (PR 3/4 of perf sweep)',
      completedAt: '2026-05-26',
      prs: [133],
      note: 'PR 3 of 4 in plan merry-toasting-dove.md. RE-SCOPED: simplejwt source inspection confirmed AccessToken does NOT inherit BlacklistMixin, so blacklist DB never runs on access-token validation. Real ~590ms hit is JWTAuthentication.get_user() → User.objects.get(id=user_id). CachedJWTAuthentication subclass overrides get_user to Redis-cache the User row. Key jwt_user:<user_id>, TTL min(token_exp_unix - now, 3600). Invalidation contract: LogoutView post-blacklist + TokenRefreshView post-rotation explicit invalidate_user_cache calls; post_save + post_delete signals on User as safety net (wired via AccountsConfig.ready). settings.py:111 DEFAULT_AUTHENTICATION_CLASSES swap. tests/test_jwt_cache.py NEW 12 tests. Security: sig check via parent get_validated_token runs BEFORE get_user override, bad sig never reaches cache. Expected ~590ms → ~10-20ms on cache hit. code-review + security-manager PASS (12 critical-chain checks clear). sha 5a1e914-pre-squash (squash 4c72513).',
    },
    {
      id: 'BACK-RECOMMEND-2',
      title: 'sklearn KMeans matmul warning 압제 (PR 2/4 of perf sweep)',
      completedAt: '2026-05-26',
      prs: [132],
      note: 'PR 2 of 4 in plan merry-toasting-dove.md. Re-scoped from "dtype align" to np.errstate suppression after empirical falsification: like_embeddings.dtype already float64 (_finite_unit_vector engine.py:66 np.asarray dtype=np.float64). Real cause: sklearn KMeans centroid normalization on high-dim unit-norm vectors. New helper engine.py:90-99 _silenced_kmeans_fit. Two call sites swapped: engine.py:1664 + 1701. sample_weight=like_weights preserved. Computation byte-identical (random_state=42 + n_init=3 deterministic; topic06 silhouette tests 9/9 PASS under -W error::RuntimeWarning). code-review + security-manager PASS (np.errstate thread-local NumPy>=1.17, multi-worker safe). sha 785f4ad-pre-squash (squash b53e633).',
    },
    {
      id: 'INFRA-REDIS-1',
      title: 'Redis cache 도입 (PR 1/4 of perf sweep)',
      completedAt: '2026-05-26',
      prs: [131],
      note: 'PR 1 of 4 in plan merry-toasting-dove.md. Foundation enabling PR 3 + PR 4. settings.py CACHES reads REDIS_URL env: set → django_redis.cache.RedisCache (KEY_PREFIX=makeweb, SOCKET_TIMEOUT=3), unset → LocMemCache fallback with MAX_ENTRIES=2000 preserved. _build_caches_dict(redis_url) helper. requirements.txt django-redis>=5.4,<6.0. .env.example Cache section + CLAUDE.md Backend Conventions bullet. backend/tests/test_cache_backend.py NEW 16 tests. Connection failure NOT swallowed. KEY_PREFIX prevents cross-service collision. code-review + security-manager PASS. User manual step: Railway dashboard Redis service + REDIS_URL=${{Redis.REDIS_URL}}. sha d5b6c18-pre-squash (squash 34a0c9e).',
    },
    {
      id: 'SWIPE-CONVERGENCE-10',
      title: '10-swipe target + multimodal escalation + stuck-state safety',
      completedAt: '2026-05-26',
      prs: [130],
      note: 'Replaces closed PR #127 (codex feature/algo-convergence-study). Algorithm policy synced to docs/algorithm.md: convergence_threshold 0.08→0.13, target_swipes=10, min_likes_for_multimodal=11 (K-Means K=2 gated behind target+1), convergence_min_recent_likes=2 (positive-evidence gate). Frontend stuck-state safety floor beyondTargetFloor (swipe_count >= target+5). Engine _with_image_focus bug fix. async_prefetch_enabled True→False reverted (chain broken; later resolved in PR 4 PERF-PREFETCH-CHAIN). Swipe.py stale 0.08 defaults → 0.13. 2 commits squashed at merge to 83db42c.',
    },
    {
      id: 'INFRA-CI-1',
      title: 'PR #125 PERF-3 CI fail hotfix',
      completedAt: '2026-05-26',
      prs: [128],
      note: 'Root cause: PERF-3 _async_emit daemon thread silent fail. settings_dict["TIME_ZONE"] KeyError on first thread connection setup. Sync emit revert achieved CI green. Cost ~290ms sync emit restored. PERF-3 ~1800 ms still PASS ≤2000 ms goal. sha 198eca4-pre-squash.',
    },
    {
      id: 'BACK-PERFORMANCE-2',
      title: 'Discovery 캐시 hit 450ms (목표 <200ms)',
      completedAt: '2026-05-26',
      prs: [126],
      note: 'GET /api/v1/discovery/ warm cache hit p50 1572 → 672 ms (-57%). Goal <200 ms 미달 — auth floor ~600 ms (BACK-AUTH-1) + get_profile 74 ms 잔존. Response cache 60 s TTL. Mutation evict hooks. taste_ranked_page absent on cache hits. sha b40cfea-pre-squash (squash 28b7242).',
    },
    {
      id: 'BACK-PERFORMANCE-3',
      title: 'Search 후 첫 카드까지 5-8초',
      completedAt: '2026-05-26',
      prs: [125],
      note: 'POST /api/v1/analysis/sessions/ local p50 2567 → 1508 ms (-42%) / PR #128 hotfix ~1800 ms still PASS. Tier 1 pool cache (filter SHA1, 30 min TTL). _random_pool 30 min cache. emit_events: PR #125 threading.Thread → PR #128 sync revert. perf_timing + perf_measure --filters CLI. sha fb669b6-pre-squash (squash 5593f6c).',
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
        title: 'Neon connection pool 모니터링 (post PR #134)',
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
      number: 134,
      title: 'feat(PERF-PREFETCH-CHAIN): wire async prefetch chain end-to-end',
      mergedAt: null,
      mergedAtKST: null,
      sha: null,
    },
    {
      number: 133,
      title: 'feat(BACK-AUTH-1): cache JWTAuthentication.get_user() per-user',
      mergedAt: '2026-05-26T06:47:23Z',
      mergedAtKST: '2026-05-26 15:47 KST',
      sha: '4c72513',
    },
    {
      number: 132,
      title: 'fix(BACK-RECOMMEND-2): silence sklearn KMeans matmul warnings',
      mergedAt: '2026-05-26T05:26:32Z',
      mergedAtKST: '2026-05-26 14:26 KST',
      sha: 'b53e633',
    },
    {
      number: 131,
      title: 'feat(INFRA-REDIS-1): Redis cache + LocMemCache fallback',
      mergedAt: '2026-05-26T04:56:32Z',
      mergedAtKST: '2026-05-26 13:56 KST',
      sha: '34a0c9e',
    },
    {
      number: 130,
      title: 'fix: swipe convergence — 10-swipe target + multimodal escalation + stuck-state safety',
      mergedAt: '2026-05-26T02:23:10Z',
      mergedAtKST: '2026-05-26 11:23 KST',
      sha: '83db42c',
    },
    {
      number: 129,
      title: 'fix(dashboard): state.js block comment */ early termination',
      mergedAt: '2026-05-26T00:52:54Z',
      mergedAtKST: '2026-05-26 09:52 KST',
      sha: 'b4d24d6',
    },
    {
      number: 128,
      title: 'fix(ci): PR #125 CI fail — settings TIME_ZONE + test patch',
      mergedAt: '2026-05-26T00:25:28Z',
      mergedAtKST: '2026-05-26 09:25 KST',
      sha: '9681270',
    },
    {
      number: 126,
      title: 'perf(BACK-PERFORMANCE-2): /discovery/ cache-hit p50 1572→672ms',
      mergedAt: '2026-05-25T20:20:03Z',
      mergedAtKST: '2026-05-26 05:20 KST',
      sha: '28b7242',
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
      role: 'Push + PR open/poll + squash merge + branch cleanup + develop→main deploy PRs. Never commits source code. Default Mode 2 routine path absorbed by .claude/skills/git-publish/; agent still fires for Mode 3 deploy / external PR triage / complex rebase.',
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
