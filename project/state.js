/*
 * project/state.js — ArchiTinder Make Web project state.
 *
 * Maintained by `reporter-inline` skill (2026-05-26+) — runs INLINE in the
 * feature PR before squash merge. Legacy `reporter` agent kept as deprecated
 * fallback. Hand-edited only inside `systemFlow` / `recommendationFlow` /
 * `agentFlow` Mermaid bodies and the `milestones` archive (semi-static); all
 * other sections are rebuilt from `.claude/Task.md`, `gh pr list`, and
 * `.claude/agents/*.md` + `.claude/skills/*/SKILL.md` frontmatter.
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
// Reporter: Mermaid sources may be stale — commit bbadcf1 touched .claude/agents/{git-manager,reporter}.md (deprecate marker) + .claude/skills/{git-commit,git-publish,reporter-inline}/ (new). Next session should refresh `agentFlow` to reflect the skill-first roster.
window.PROJECT_STATE = {
  meta: {
    name: 'ArchiTinder — Make Web',
    updatedAt: '2026-05-26 01:51 KST',
    head: '8f90104',
    branch: 'feature/admin-workflow-skill-absorption',
  },

  done: [
    {
      id: 'INFRA-WORKFLOW-1',
      title: 'Reporter / git-manager 흡수 + 3 skill 도입',
      completedAt: '2026-05-26',
      prs: [123],
      note: '3 new skills replace routine agent paths: git-commit (single commit + secret guards), git-publish (push + PR + admin squash + Step 0 publish gate), reporter-inline (Task.md + state.js + algorithm.md inline before squash; in-flight PR mergedAt:null sentinel + next-pass backfill; 9-step behavior 1-to-1 from reporter agent). git-manager + reporter agents → deprecated:true frontmatter + body fallback note (two-PR migration; delete in follow-up PR after ~1 week skill-only validation). git-publisher kept (Mode 3 deploy / external PR triage / complex rebase). CLAUDE.md new ## Git Operations — HARD RULE section. WORKFLOW.md Mermaid rebuilt with skill labels. MEMORY feedback_orchestrator rewritten + new feedback_workflow_skill_absorption. Per PR cycle agent dispatches 8 → 3, ~30-40k tokens + ~150-300s saved. Reporter audit ships in same PR as work — PR count halved. sha bbadcf1-pre-squash (post-squash backfill at next reporter-inline pass).',
    },
    {
      id: 'FRONT-UX-4',
      title: 'BuildingDetailPage UX 개선 (스크롤 + 순서 + 보드 저장)',
      completedAt: '2026-05-26',
      prs: [120],
      note: 'BuildingDetailPage minHeight → height + overflowY:auto (MainLayout overflow:hidden 부모 안에서 자체 스크롤 회복). Title/architect/meta 갤러리 위로 재배치. 상단 우측 "+ 보드에 추가" 핑크 그라디언트 버튼 + SaveToBoardModal 트리거. 저장 후 골드 체크 상태. BoardDetailPage buildings 이동 시 fromBoard:true location.state. Codex P2 fix: saveEnabled={!fromBoard} (negative gate too broad — firm profile / direct URL / BoardDetail recommended tile 모두 노출) → saveEnabled={fromRecommended} (positive gate, ResultsPage 추천만). ResultsPage.handleOpenBuilding fromRecommended:true state 추가. fromBoard derivation 제거 (ESLint no-unused-vars). BoardDetailPage fromBoard:true writes 살아 있되 dead harmless. sha 8f90104.',
    },
    {
      id: 'FRONT-DESIGN-2',
      title: '카드 이미지 contain 전환 + 카드 크기 확대',
      completedAt: '2026-05-26',
      prs: [118],
      note: 'SwipeCard objectFit cover → contain (사진 잘림 해소). 갤러리 뒷면 contain 통일. Letterbox 배경 #111 (도면 #fff 유지). CARD_WIDTH min(420, vw-32) (16+16 컨테이너 padding 보정), CARD_HEIGHT min(width×1.55, vh-220). SwipePage flex centering wrapper (header/hint 높이 무관 수직 정중앙). Converged phase confidence 무관 finish 버튼 활성화. App.jsx auto-nav at100 조건에서 (phase === \'converged\') 단독 분기 (confidence null이어도 nav). Codex P1 fix: CARD_WIDTH vw-16 → vw-32 (390폰 16px 클립 해소). Codex P2 fix: finishUnlocked latch 재도입 drop. PR #121 1-shot isAt100 설계 보존 (App.jsx auto-nav 주 trigger, Finish 버튼 safety net). sha 9fcd078.',
    },
    {
      id: 'FRONT-UX-2',
      title: '스와이프 자동 이동 + 키보드 입력',
      completedAt: '2026-05-26',
      prs: [121],
      note: 'App.jsx useEffect auto-navigates /swipe → /result/:sessionId on phase=completed/results, or latch threshold (exploring like_count>=4, analyzing/converged confidence>=1.0). DiscoveryPage.jsx keydown ← (skip) / → (save) arrow-key swipe. Supersedes PR #114 (feature/admin-swipe-finish-ux) + PR #115 (feature/front-ux-keyboard-swipe) — both had wrong base main (HARD RULE 5); re-based as PR #121 onto develop. 4 Codex fixes baked in: (1) P2/#114 auto-nav swallowed Keep-exploring path — only nav on 100% latch or pool-exhaust; (2) P2/#114 finishUnlocked latch leaked across sessions — dropped, 1-shot calc kept as SwipePage Finish-button safety net; (3) P2/#115 surpriseOpen modal guard — arrow-key handler checks surpriseOpen before firing; (4) P3/#115 keySwipingRef permanent lock on async throw — try/finally ensures ref release. sha 80b519c.',
    },
    {
      id: 'INFRA-DB-1',
      title: 'Django app이 owner 권한으로 DB 접근',
      completedAt: '2026-05-25',
      prs: [119],
      note: 'Created make_web_app Neon role on production + local-dev-2 via psql CREATE ROLE (NOT neonctl — that grants neon_superuser transitively). GRANT SELECT/INSERT/UPDATE/DELETE on ALL TABLES + USAGE/SELECT on ALL SEQUENCES + ALTER DEFAULT PRIVILEGES for future migration tables. Local .env swapped DB_USER neondb_owner → make_web_app + rotated password; manage.py check clean; ORM + buildings smoke unchanged; DDL rejected. Railway prod: first redeploy d203e2bf FAILED (password mispaste), second redeploy 820de476 SUCCESS (active deployment 2026-05-25 07:43). 8-probe psql matrix: CRUD pass, CREATE TABLE/DROP TABLE/CREATE ROLE/CREATE EXTENSION/ALTER TABLE all blocked. Files: .env.example (role-separation block), CLAUDE.md (Backend Conventions Neon role bullets), docs/MAKEWEB_DB_SWAP_RESPONSE.md (Q2 RESOLVED block + BUILDINGS_DB_PASSWORD rotation action item). Pure docs/meta carve-out — no production code touched. Outstanding: BUILDINGS_DB_PASSWORD rotation tracked outside this entry. sha 1d3bfdc.',
    },
    {
      id: 'INFRA-ENV-1',
      title: 'Neon dev branch 복구 + prod 격리',
      completedAt: '2026-05-25',
      prs: [116],
      note: 'Re-provisioned local-dev-2 (br-shy-thunder-a1p5glmo, ep-holy-band-a1w0u5am, no TTL) off production. Repointed local .env DB_HOST + BUILDINGS_DB_HOST from prod ep-broad-hat-a1jaomn7 → dev endpoint; Railway prod env untouched. Smoke: manage.py check OK, default+buildings host = dev endpoint, auth_user count = 3, canonical_v2_buildings = 39,478, is_publishable=true = 36,864. Docs: .env.example DEV-vs-PROD discipline block + neonctl command + dev-branch note; MAKEWEB_DB_SWAP_RESPONSE.md restoration paragraph. Pure docs/meta carve-out — no code touched. sha 4b900da.',
    },
    {
      id: 'INFRA-DEPLOY-1',
      title: '2026-05-25 develop → main 배포 (PR #99–#111)',
      completedAt: '2026-05-25',
      prs: [112],
      note: 'develop → main squash-merged carrying 11 PRs (#99–#111). main = 1888b5f. Railway prod auto-deploy triggered. Bug #5 carve-out applied: origin/develop force-reset to origin/main (1888b5f).',
    },
    {
      id: 'INFRA-DOC-1',
      title: 'Task.md ID 규칙 + bucket + stale doc 정리',
      completedAt: '2026-05-25',
      prs: [111],
      note: '## Next flat list → HIGH/MEDIUM/LOW buckets; 20 entries renamed to <SURFACE>-<TOPIC>-<N> + Korean ≤25-char title. ID convention codified in Workflow Rules; cross-refs updated in reporter.md, orchestrate/SKILL.md, maker agents. 5 stale doc spots cleaned (WORKFLOW.md Mermaid, orchestrate old phase block, README.md, SWAP_RESPONSE doc status, .env.example unused vars). INFRA-ENV-1 status upgraded confirmed (prod endpoint direct write risk).',
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
        note: 'Same Project can host multiple AnalysisSession rows; user "Resume" creates a fresh session while Project.liked_ids accumulates. Today session #2 algorithm state (like_vectors, convergence_history, phase) starts from scratch despite the user having liked 12 buildings in session #1. Open: carry policy (A independent / B exposure-only / C dislike-only / D fade-decay / E full warm-start / F user toggle); warm-start phase entry; SessionCreateView wiring at views/sessions.py:28 (currently just resolves project_id, carry would seed like_vectors from Project.liked_ids embeddings at create time). Acceptance: deterministic behaviour, session #2 TTFC not regressed, A/B on saved_ids growth + completion rate.',
      },
      {
        id: 'FRONT-UX-1',
        title: '신규 사용자에게 홈이 빈 화면',
        note: 'First-time user with 0 projects lands on Home → project picker — currently shows nothing deliberate. Frontend-only (HomePage / ProjectListPage). Open: onboarding shape (guided CTA / placeholder + create button / demo query / hybrid), copy + voice, visual illustration. Acceptance: 0-project user sees deliberate empty state; CTA path to first swipe ≤2 clicks; no regression on existing-projects rendering.',
      },
      {
        id: 'FULL-LANGUAGE-1',
        title: '한/영 언어 설정 토글 없음',
        note: 'Decision 2026-05-25: language is a user setting (Korean / English), not browser-locale auto-detected. Pattern mirrors PR #54 + PR #59 theme/font persistence. Backend: UserProfile.language CharField, default ko. Frontend: LanguageContext mirroring ThemeContext, toggle in AppearanceSettings (or sibling page). Drives LLM chat answer language (parse_query.py reads from profile, overrides message-language inference) + UI label rendering (hand-rolled t() helper, no react-i18next dependency). Open: scope priority (TabBar first?), translation source (admin / Gemini + review), settings UI placement, untranslated fallback. Acceptance: language PATCH round-trip, LLM chat follows setting, ≥1 high-traffic UI surface bilingual, no theme/font regression.',
      },
      {
        id: 'BACK-LLM-2',
        title: '채팅 기록이 다른 기기에서 사라짐',
        note: 'Decision 2026-05-25: persist chat conversation to backend DB, not just browser localStorage. Today LLMSearchPage.jsx:186–205 stores conversationHistory in localStorage — single-browser, lost on logout / device switch / cache clear. Resume + Exit UX already shipped (SwipePage.jsx ExitConfirmPopup). Backend currently has no conversation field. Plan: add Project.conversation_history JSONField (or ConversationTurn table — open) + migration + serializer + idempotent append endpoint; swap LLMSearchPage localStorage reads for API; optionally keep localStorage as write-through cache. Open: storage shape (JSONField vs table), per-session vs per-project, localStorage retention, retention policy, migration of existing local data. Acceptance: logout + re-login on any browser re-hydrates conversation; idempotent append survives network retry; Resume/Exit UX unchanged.',
      },
      {
        id: 'BACK-LLM-3',
        title: 'Gemini cache 호출에 timeout 없음',
        note: '_caches.py:92 IMP-5 Gemini context-cache create call bypasses the _retry_gemini_call timeout wrapper (PR #94 15s cap). Gated by context_caching_enabled flag (default OFF) — zero prod impact until toggled on. Fix: wrap call in _retry_gemini_call; ~5 LOC backend edit. Pre-emptive safety before flag toggle. Acceptance: _caches.py:92 flows through wrapper; existing IMP-5 tests pass; flag behaviour unchanged.',
      },
      {
        id: 'BACK-PERFORMANCE-1',
        title: '/projects/ 응답 600ms (목표 300ms)',
        note: 'Codex Round 2 measured p50 = 600 ms vs spec 300 ms. Codex retest 2026-05-25 also saw dev double-fetch (StrictMode + real prefetch). User-visible: post-login first paint surface. Investigation: SQL-count probe → port PR #83 Subquery/prefetch_related pattern if N+1 → trim serializer or add light ProjectListSerializer → cache layer last resort. Acceptance: p50 ≤300 ms Singapore deploy, no serializer-shape regression on HomePage/BoardCard.',
      },
      {
        id: 'BACK-PERFORMANCE-2',
        title: 'Discovery 캐시 hit 450ms (목표 <200ms)',
        note: 'Codex Round 2: discovery cache-hit p50 = 450 ms vs spec <200 ms. Retest 2026-05-25: cache-cold 4.11 s with external image retries. Taste cache shipped PR #87 (1h TTL, evict on liked_ids change). Suspect: serialization floor on 12 cards / raw SQL still on hit path / low true hit-rate from key fragmentation. Investigation: per-stage timing in views/discovery.py → trim payload, batch URLs, extend cache to hold card payloads, audit key shape. Acceptance: hit-path p50 <200 ms Singapore deploy; no SwipePage card-shape regression.',
      },
      {
        id: 'BACK-PERFORMANCE-3',
        title: 'Search 후 첫 카드까지 5-8초',
        note: 'Single heaviest delay in the funnel — 5–8 s between Search click and first swipe card. Pipeline (views/sessions.py:28-160): project resolve → v_initial embedding → create_pool_with_relaxation (3-tier SQL fan-out) → get_pool_embeddings (150 × 384) → tier-ordered initial_batch via repeated farthest_point_from_pool matmul (same code path emitting Codex divide/overflow/invalid warnings) → AnalysisSession INSERT. Investigation: per-step timing log on prod → cache by (filter_signature, tier) if pool dominates / batch-prefetch embeddings / vectorise initial-batch farthest-point loop. Acceptance: p50 ≤ 2 s Singapore deploy (≈ 3× improvement); pool + initial_batch determinism preserved.',
      },
      {
        id: 'FRONT-DESIGN-1',
        title: '디자인 시스템 컴포넌트 리워크 (paused)',
        note: 'Foundation shipped: PR #54 (tokens.css 4 themes + ThemeContext + AppearanceSettings) + PR #59 (theme/font server persistence). Remaining: per-component visual rework (~7,700 LOC) — inline styles → CSS Modules + :hover/:focus/:active, light-theme polish, leaf→hub order. Resume via /plan per slice; each slice ships its own PR via orchestrate skill. Acceptance per slice: lint+build clean, light+dark variants regression-free, no token added without DESIGN.md update.',
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
        id: 'BACK-RECOMMEND-2',
        title: 'engine.py matmul warning 정리',
        note: 'sklearn emits matmul dtype warning during clustering. Cosmetic noise but indicates float32/float64 mismatch — quick fix is dtype-align embedding ndarrays before kmeans.',
      },
    ],
    low: [
      {
        id: 'FRONT-AUTH-1',
        title: 'LoginPage에 Kakao/Naver 버튼 없음',
        note: 'Backend Kakao + Naver implementation shipped: apps/accounts/views.py KakaoLoginView + NaverLoginView, urls.py auth/social/kakao/ + auth/social/naver/. Frontend LoginPage.jsx has Google button only — Kakao + Naver buttons remaining.',
      },
      {
        id: 'FULL-REFACTOR-1',
        title: '큰 파일 분해 필요 (engine.py 2139 LOC 등)',
        note: 'File decomp (LOC verified 2026-05-25): engine.py 2139 (+60 since first flagged), App.jsx 817, BoardDetailPage 1045, UserProfilePage 992, PostSwipeLandingPage 696, SwipePage 666, FirmProfilePage 540 (recently refactored down from 611).',
      },
      {
        id: 'BACK-RECOMMEND-3',
        title: 'Profile-tab 사무소/유저 추천 endpoint 없음',
        note: 'REC1 shipped as Push S3. REC2 (firm) + REC3 (user) target GET /api/v1/recommendations/profile/ returning {offices, users} for a Profile-tab button. Open: firm vector composition, user taste vector, cold-start strategy, match score visibility, diversity/follow-exclusion, tie-breakers, trigger surface UX. Acceptance: p95 ≤800ms Singapore, cold-start graceful, is_publishable=true gating preserved.',
      },
      {
        id: 'BACK-EXTERNAL-1',
        title: 'FirmProfilePage에 외부 기사 surface 없음',
        note: 'Surfaces external articles about a firm on FirmProfilePage (Space / ArchDaily / news keyword match). Phase 15 already shipped External DM wiring. Open: article source priority, crawl freshness, storage, article fallback. Acceptance: ≤10 most recent articles per firm, open in new tab, no FirmProfilePage TTFC regression.',
      },
      {
        id: 'INFRA-QUEUE-1',
        title: 'corpus_rank telemetry 꺼져있음',
        note: 'corpus_rank telemetry field currently None on every swipe (PR #79 turned off the synchronous O(corpus_size) scan; product does not consume the field). Re-enabling requires Celery + Redis + worker process + monitoring — over-investment for one telemetry column. Revisit when multiple background jobs accumulate (image batch, embedding refresh, scheduled snapshot drops) so the infra cost amortises.',
      },
    ],
  },

  prs: [
    {
      number: 123,
      title: 'feat(workflow): absorb reporter + git-manager into 3 skills (PR cycle halved)',
      mergedAt: null,
      mergedAtKST: null,
    },
    {
      number: 122,
      title: 'chore(reporter): session-end housekeeping — PR #119 + #121',
      mergedAt: '2026-05-25T15:32:52Z',
      mergedAtKST: '2026-05-26 00:32 KST',
    },
    {
      number: 121,
      title: 'feat(swipe,discovery): auto-result nav + arrow-key swipe (supersedes #114 #115)',
      mergedAt: '2026-05-25T15:24:53Z',
      mergedAtKST: '2026-05-26 00:24 KST',
    },
    {
      number: 120,
      title: 'feat: BuildingDetailPage UX 개선 — 스크롤·순서·보드 저장',
      mergedAt: '2026-05-25T16:06:40Z',
      mergedAtKST: '2026-05-26 01:06 KST',
    },
    {
      number: 119,
      title: 'docs(INFRA-DB-1): Railway cutover COMPLETED 2026-05-25 — make_web_app live in prod',
      mergedAt: '2026-05-25T07:50:10Z',
      mergedAtKST: '2026-05-25 16:50 KST',
    },
    {
      number: 118,
      title: 'feat(FRONT-DESIGN-2): 카드 이미지 contain 전환 + 카드 크기 확대',
      mergedAt: '2026-05-25T15:57:48Z',
      mergedAtKST: '2026-05-26 00:57 KST',
    },
    {
      number: 117,
      title: 'chore(INFRA-DOC-5): session-end reporter housekeeping — PR #116 INFRA-ENV-1',
      mergedAt: '2026-05-25T07:00:05Z',
      mergedAtKST: '2026-05-25 16:00 KST',
    },
    {
      number: 116,
      title: 'chore(INFRA-ENV-1): restore Neon child branch for local dev (prod isolation)',
      mergedAt: '2026-05-25T06:50:38Z',
      mergedAtKST: '2026-05-25 15:50 KST',
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
  Gemini["Gemini API"]
  R2["Cloudflare R2 image CDN"]
  OAuth["Google · Kakao · Naver OAuth"]

  Browser --> Vercel --> ApiClients --> Django --> Apps --> Views
  Views --> Engine
  Views --> DefaultDB
  Engine --> BuildingsDB
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
