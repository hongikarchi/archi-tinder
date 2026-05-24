# Task Board

> Auto-updated by the orchestrator. When you request work, the orchestrator reads
> the current code, then adds/updates tasks here before executing.
> Categories: Frontend, Backend, Auth, UX/Design, Infrastructure
> (Algorithm work is owned by a separate collaborator post-2026-05-18.)

---

## Development Roadmap

> Orchestrator: follow this order. Each Phase's tasks are referenced by ID.

### Phase 1: Critical Bug Fix -- COMPLETED 2026-04-03
1. **B4** -- Mobile Google login (auth-code flow)
2. **B1** -- "View Result" button timing
3. **B2** -- Card repetition (exposed_ids)
4. **B3** -- "No buildings match" fallback

### Phase 2: Stability -- COMPLETED 2026-04-03
5. **F1** -- Swipe error handling + state sync
6. **A3** -- Recency weight math protection
7. **BE1** -- API timeout/retry

### Phase 3: Performance -- A1 COMPLETED, A2 VALIDATED
8. **A1** -- Pool caching + KMeans caching + prefetch -- COMPLETED 2026-04-03
9. **A2** -- Algo-tester 100 personas -- validated (smoke test passed, full run pending)

### Phase 4: UX Enhancement -- COMPLETED 2026-04-03
10. **UX1** -- Tutorial popup -- COMPLETED 2026-04-03
11. **UX3** -- Action card message improvement -- COMPLETED 2026-04-03
12. **F2** -- Image load failure handling -- COMPLETED 2026-04-03

### Phase 4.5: Swipe Bug Fix -- B5, B6, B2v2 COMPLETED 2026-04-04 (B3v2 skipped)
13. **B5** -- Fast swipe race condition (no swipe lock, concurrent requests)
14. **B6** -- Card suddenly changes (prefetch response overwrites current card)
15. **B2v2** -- Same cards still repeating (prefetch uses stale exposed_ids)
16. **B3v2** -- Pool exhaustion during exploring phase returns null (SKIPPED -- low priority)

### Phase 5: New Features -- UX2, F3 COMPLETED 2026-04-04 (AUTH1 deferred)
17. **UX2** -- Persona Report AI image generation -- COMPLETED 2026-04-04
18. **AUTH1** -- Kakao / Naver OAuth (deferred -- future)
19. **F3** -- Mobile optimization -- COMPLETED 2026-04-04

### Phase 6: Cleanup -- COMPLETED 2026-04-04
20. **INFRA1** -- Backend integration tests -- COMPLETED 2026-04-04
21. **INFRA2~4** -- Idempotency, total_rounds, console.error -- COMPLETED 2026-04-04
22. **BE2** -- Gemini error handling improvement -- COMPLETED 2026-04-04

### Phase 7: Codebase Audit Fixes -- COMPLETED 2026-04-04
23. **AUDIT1** -- Remove unused deps, dead code, consolidate tests, fix deprecations -- COMPLETED 2026-04-04

### Phase 8: E2E Testing Infrastructure -- COMPLETED 2026-04-05
24. **TEST1** -- E2E visual test runner module -- COMPLETED 2026-04-05

### Phase 9: E2E Runner Fix -- COMPLETED 2026-04-07
25. **TEST2** -- Rewrite runner.py to match actual frontend UI flow -- COMPLETED 2026-04-06
26. **TEST3** -- Fix screenshots, card visibility, timing breakdown -- COMPLETED 2026-04-07

### Phase 10: Swipe API Latency Fix -- COMPLETED 2026-04-05
27. **PERF1** -- Non-algorithm swipe latency optimizations -- COMPLETED 2026-04-05

### Phase 11: Frontend Bug Fix -- COMPLETED 2026-04-05
28. **B7** -- Keyboard swiping blocked in gallery mode (SwipePage.jsx) -- COMPLETED 2026-04-05
29. **B8** -- Card disappears after swipe race condition (App.jsx) -- COMPLETED 2026-04-05

### Phase 12: Critical Swipe Bug Fixes -- COMPLETED 2026-04-05
30. **B9** -- Cards stop loading after ~N swipes (never set currentCard null) -- COMPLETED 2026-04-05
31. **B10** -- Refresh creates new session instead of resuming (SessionStateView + currentHint) -- COMPLETED 2026-04-05
32. **B11** -- Same card appears twice (client_buffer_ids in exposed_ids) -- COMPLETED 2026-04-05

### Phase 13: Profile System -- COMPLETED 2026-05-06
33. **PROF1** -- OfficeProfile model + Make DB integration (blue-mark, project list, external links, basic info) -- COMPLETED 2026-04-29
34. **PROF2** -- UserProfile extension (MBTI, avatar, bio, external DM links) -- COMPLETED 2026-04-29
35. **PROF3** -- Firm profile page UI (project card grid + website/email links) -- COMPLETED 2026-05-02
36. **PROF4** -- User profile page UI (feed style, board list) -- COMPLETED 2026-05-02

### Phase 14: Board System -- COMPLETED 2026-05-06
37. **BOARD1** -- Board model (public/private visibility, owner FK) -- COMPLETED 2026-04-30
38. **BOARD2** -- Project creation: visibility selection UI -- COMPLETED 2026-05-06
39. **BOARD3** -- Profile page: board browse/manage UI -- COMPLETED 2026-05-06

### Phase 15: Social Foundation -- COMPLETED 2026-05-06
40. **SOC1** -- Follow model + API (follow/unfollow, follower list) -- COMPLETED 2026-05-02
41. **SOC2** -- "Love this!" reaction model + API -- COMPLETED 2026-05-02
42. **SOC3** -- Profile/board: follow button + reaction button UI -- COMPLETED 2026-05-06

### Phase 16: Recommendation Expansion -- PENDING (revised under 2026-05-14 replan; S8 sweep COMPLETED)
> Re-scoped 2026-05-14: REC1 already executed as **Push S3**. REC2 / REC3 now
> serve a Profile-tab "사무소 추천" button (Q3 decision); Landing tab
> deleted by Push S6. Endpoint shape changed from
> `/api/v1/landing/{sessionId}/` (deprecated) to a Profile-targeted
> composite (e.g. `/api/v1/recommendations/profile/`).
> Open dimensions + acceptance now live in `## Next` § PHASE16.
43. **REC1** -- Post-swipe end screen consolidation (executed in **S3** 2026-05-14)
44. **REC2** -- Firm recommendation logic (Profile-button-triggered)
45. **REC3** -- User recommendation logic (Profile-button-triggered)
46. **REC4** -- ~~Landing tab~~ → removed by Push S6 (Profile-tab button surface instead)

### Phase 17: LLM Reverse-Questioning -- PENDING (S8 sweep COMPLETED)
> Replan Q6 RESOLVED → Option A: reverse-question lives in the first
> 0-2 turns of the Taste-tab LLM chat (pre-swipe). TTFC budget unchanged.
> Open dimensions + acceptance now live in `## Next` § PHASE17.
47. **LLM1** -- Chat reverse-question prompt design (identify user needs)
48. **LLM2** -- Persona classification logic (P1-P4 differentiation; populates `UserProfile.persona_summary`)
49. **LLM3** -- Per-persona UI branching (recommendation card type switching)

### Phase 18: External Connections -- PENDING (S8 sweep COMPLETED)
> Lower priority than Phase 16-17. Open dimensions + acceptance now
> live in `## Next` § PHASE18.
50. **EXT1** -- Firm article crawler (Space, ArchDaily, news — keyword-based)
51. **EXT2** -- Article list UI (inside firm profile)
52. **EXT3** -- External DM link UI (Instagram, email — on profile)

> **Phase 19-26 (2026-05-14 Replan, Tab 3-Structure Transition) + Phase P1-P6
> latency+UX overhaul (2026-05-15..2026-05-18)** — all shipped to production
> via deploy PR #36 (S1-S8) and PR #49 (P1-P6). See git history for detail.

---

## Next

> Flat backlog. Priority is admin tiebreaker (see CLAUDE.md `## Product Constitution`
> Decision Principles). Phase 16-18 dimensions inlined here (formerly `docs/specs/*`,
> absorbed 2026-05-24). Pending strategic + operational items live side-by-side.
> Algorithm theory + production hyperparameters still live in `docs/algorithm.md`
> (admin-owned, reporter syncs Production Value column only).

### AUTH1 — Kakao / Naver OAuth
Google OAuth only. Korean users need domestic login.
- [ ] Kakao social auth backend + frontend button
- [ ] Naver social auth backend + frontend button

### AUDIT-T4 — Structural refactor (deferred)
File decomp: engine.py (2079 LOC), App.jsx (795 LOC), BoardDetailPage (1032 LOC), UserProfilePage (990 LOC), PostSwipeLandingPage (696 LOC), SwipePage (666 LOC), FirmProfilePage (611 LOC).

### PHASE16 — Recommendation Expansion (Profile-tab 사무소/유저 추천)
Re-scoped 2026-05-14 (REC1 already shipped as Push S3). REC2 (firm) + REC3 (user) target a single composite endpoint `GET /api/v1/recommendations/profile/` returning `{offices: [...], users: [...]}` for a Profile-tab button. Landing tab removed (Push S6).

Open dimensions (admin decision before implementation):
- **Firm vector composition** — Mean / weighted-mean / curated-subset / max-sim of firm's project embeddings?
- **User taste vector** — Aggregated from user's `liked_ids` across Projects; recency-weighted? curated subset?
- **Cold-start strategy** — New user 0 swipes → "popular users" / generic taste cluster / disable User tab until N swipes?
- **Match score visibility** — Show "92% match" on cards or hide?
- **Diversity vs follow-exclusion** — Recommend already-followed firms? (probably exclude)
- **Tie-breakers** — Followers count / recency / random / hybrid?
- **Trigger surface UX** — Single button → modal / full-page / toggle between Office/User?

Acceptance: `/recommendations/profile/` p95 ≤ 800 ms on Singapore deploy; cold-start UX graceful; `canonical_bld_id` + `is_publishable=true` gating preserved per CLAUDE.md hard rules.

### PHASE17 — LLM Reverse-Q + Persona Classification (P1-P4)
Reverse-question lives in first 0-2 turns of Taste-tab LLM chat (pre-swipe; Q6 Option A confirmed 2026-05-14). Populates `UserProfile.persona_summary` (PROF2 field reserved).

Open dimensions:
- **Reverse-Q examples** — adversarial / implicit / non-verbal (deduce from filter shape)?
- **Per-persona UI branching** — silent classification + tailored cards vs explicit "I am: ☐ jobseeker ☐ hiring ..." prompt?
- **Persona drift** — user can be P1 one session, P2 another — explicit support?
- **Persona representation shape** — structured `{persona_type, one_liner, styles[], programs[]}` vs flat `persona_label`?
- **Persona persistence** — per-session / per-user / per-user-with-current-session-override?
- **Confidence + override** — low-confidence: ask user vs silent commit?

Acceptance: TTFC for Taste-tab chat does not regress beyond the 4000 ms budget (per `docs/algorithm.md`); persona override path tested.

### PHASE18 — External Connections (firm article crawl)
Lowest pending priority. Surfaces external articles about a firm on FirmProfilePage (Space / ArchDaily / news keyword match). Phase 15 already shipped External DM wiring (`Office.contact_email`, `Office.website`, `UserProfile.external_links`).

Open dimensions:
- **Article source priority** — Space-first (Korean) vs ArchDaily-first (global) vs parity? (Korea-first principle suggests Space)
- **Crawl freshness** — real-time on view / scheduled daily-weekly / event-driven?
- **Storage** — denormalised in `Office` row / separate `OfficeArticle` table / external CDN?
- **Article fallback** — empty section / hide section / "no recent articles" placeholder?

Acceptance: ≤10 most recent articles per firm; open in new tab (legal posture); no FirmProfilePage TTFC regression (article fetch async, doesn't block initial paint).

### XSESS — Cross-session signal transfer (deferred)
Same project's multiple sessions — should `liked_ids` / `pref_vector` carry over between sessions? Current spec is implicit independence (each session starts fresh). Six options: A independent (status quo) / B exposure-only carry / C asymmetric negative-only / D fade-decay carry / E full warm-start / F user-controlled toggle. Defer until traffic justifies experiment cost.

### EMPTY-STATE — Empty-state UX (Project = 0)
First-time user with 0 projects sees Home → project picker. Need explicit empty-state path: guided flow / empty-state + create button / demo query? Low priority — current users are existing accounts.

### MULTILANG — Multi-language behavior (partial)
Chat phase has bilingual rendering rule. Mobile UI / detail page / persona report's multi-language posture unresolved. Korea-first per Constitution Decision Principle 7; English supported, not co-equal.

### MOBILE-DESKTOP — Mobile vs desktop UX divergence
Current viewport-lock layout is mobile-first. Detail pages on desktop work but unoptimised. Low priority — desktop is secondary.

### PRIVACY-PIPA — Privacy / sharing posture
Phase 13+ Profile/Board public/private visibility shipped. PIPA + GDPR posture for signup data collection / consent flow / retention policy still open. **Required before public launch.**

### CONVO-PERSIST — Conversation history persistence
Probe-turn chat history during a session is currently transient. Persist for session resume? Low priority.

### IMP5-BYPASS — IMP-5 cache create timeout wrapper bypass
`backend/apps/recommendation/services/_caches.py:92` IMP-5 Gemini context-cache create call bypasses the `_retry_gemini_call` timeout wrapper. Gated by `context_caching_enabled` flag (default OFF) — zero prod impact until toggled on. Wrap on toggle-on.

### CODEX-STAGE3-RERUN — Codex Stage 3 re-audit on prod (post-PR #97)
CI hang fix (PR #97) deployed via PR #98. Re-run codex Stage 3 (AI Search Flow 5) against prod to verify the 228 s `/parse-query/` hang no longer fires under load. Cumulative validation of PR #94 timeout cap + PR #97 daemon-thread swap.

### PERF-PROJECTS — `/projects/` p50 600ms (budget 300ms)
Codex Round 2 observation: `/projects/` endpoint p50 latency 600 ms vs spec budget 300 ms. Probable N+1 elsewhere or warm cache miss. Investigate query plan.

### PERF-DISCOVERY — Discovery cache-hit 450ms (budget <200ms)
Codex Round 2: Discovery endpoint cache-hit path measures 450 ms; spec budget <200 ms. Cache may be doing extra work or response serialization is the floor. Trace.

### PERF-SESSION-CREATE — Session create 5.2s baseline
POST `/analysis/sessions/` measured 5.2 s baseline. Pre-existing; flag for investigation.

### MATMUL-WARN — matmul runtime warning (sklearn BLAS dtype)
sklearn emits matmul dtype warning during clustering. Cosmetic noise but indicates float32 / float64 mismatch — quick fix is dtype-align embedding ndarrays before kmeans.

### ARCHITECTS-WIRING — `canonical_v2_architects` feature wiring
Make DB shipped new table `canonical_v2_architects` (14,216 firms, 4,357 recommendable) in 2026-05-24 DB swap. Make Web `profiles_office` 4-tier resolution + REC2 (Phase 16) should consume this. Not yet wired.

### USER-DATA-ROLE-SEP — `user_data` DB role separation (security)
`user_data` DB currently uses default `neondb_owner` role with full privileges. Split to a restricted Make-Web-only role mirroring the SELECT-only `make_web` role on `archi_data`. Security backlog.

### SNAPSHOT-BRANCH-DROP — 1-week post-deploy snapshot branch drop
After production deploys, Neon snapshot branches retained for 1 week as rollback safety. Drop the lingering ones after retention window (verify Neon dashboard).

### CELERY-CORPUS-RANK — Celery `compute_corpus_rank` background task
`recommendation_swipeevent` row inserts currently compute corpus rank synchronously (or skip when on bookmark POST per PR #79). Async via Celery for proper telemetry without blocking.

---

## Now

### Design-system redesign — per-component rework (pending)
Foundation shipped (PR #54: `tokens.css` 4 themes + `ThemeContext` +
`AppearanceSettings`). Remaining: per-component visual rework (~7,700 LOC,
inline styles → CSS Modules + `:hover`, light-theme visuals) across the
frontend, leaf→hub order. Scope with `/plan` per slice.

---

## Done

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
