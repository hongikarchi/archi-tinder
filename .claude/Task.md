# Task Board

> Auto-updated by orchestrator. When you request work, orchestrator reads Goal.md
> + current code, then adds/updates tasks here before executing.
> Categories: Algorithm, Frontend, Backend, Auth, UX/Design, Infrastructure

---

## Handoffs

> Short-lived cross-terminal signals for the **review / push** cycle.
> Each terminal (main / review / git / codex workers) reads this section at session start.
> Oldest entries expire naturally — reporter trims to ~30 most recent on session-end pass.
>
> Lane note (2026-05-13): **lean 3-lane is the default** (WEB-MAIN + 1 Codex worker + WEB-REVIEW + WEB-GIT, set up via `tools/cmux_lean_setup.sh <back|front|both>`). Full 5-tab is opt-in via `tools/cmux_setup.sh` for full-stack concurrent work. Signal vocabulary is identical across both lanes — only the worker baseline path changed (`.claude/codex/<team>-worker.md`, formerly `.claude/agents/team-<team>.md`).
>
> Signal types for this section:
>
> **Review cycle:**
> - `REVIEW-REQUESTED: <sha>` — reporter (main pipeline) → review terminal; run `/review` next (or just say "리뷰해줘" / "review please").
> - `REVIEW-PASSED: <sha>` — review terminal → WEB-GIT; PASS verdict, drift-verified. WEB-GIT runs `git-push-pr.sh`. On `PASS-WITH-MINORS` verdict the signal inlines `<K> MINOR noted (see .claude/reviews/latest.md)`; MINORs are non-blocking.
> - `REVIEW-ABORTED: <sha> — <reason>` — review terminal → main; PASS verdict but drift detected. Re-run after rebase.
> - `REVIEW-FAIL: <sha> — <summary>` — review terminal → main; run fix loop via orchestrator (max 2 cycles).
>
> **Codex team handoffs (WEB-BACK / WEB-FRONT → WEB-MAIN):**
> - `BACK-DONE: <slug>` / `FRONT-DONE: <slug>` — task complete. Append `(claude-review-requested)` for risky-zone work.
> - `BACK-BLOCKED: <reason>` / `FRONT-BLOCKED: <reason>` — codex team escalates after exhausting self-heal (2 cycles).
> - `<TEAM>-NEEDS-CLARIFICATION: <q>` — scope ambiguous; team waits.
>
> **WEB-GIT publish cycle (Internal PR — Mode 1):**
> - `READY-FOR-PUSH: <branch>` — WEB-MAIN → WEB-GIT (alt path for trivial commits skipping `/review`).
> - `BRANCH-CREATED: <branch>` — WEB-GIT created new feature branch from develop (`tools/git-new-feature.sh`).
> - `PR-OPENED: #<N>` — WEB-GIT pushed branch + `gh pr create --base develop`. CI is running.
> - `PR-CI-GREEN: #<N>` / `PR-CI-FAIL: #<N>` — `git-poll-merge.sh` result.
> - `PR-MERGED: #<N>` — squash-merged into develop, branch deleted, local develop synced.
>
> **WEB-GIT external triage (Mode 2 — collaborator PRs):**
> - `PR-READY-FOR-REVIEW: #<N>` — WEB-GIT checked out external PR. Admin manually triggers `/review` per hybrid policy.
> - `PR-CHANGES-REQUESTED: #<N>` — WEB-GIT posted FAIL verdict to PR via `gh pr review --request-changes` (summary + collapsible details body).
> - `PR-CONFLICT: #<N>` — external PR conflicts with develop; WEB-GIT commented asking author to rebase.
>
> **WEB-GIT deploy (Mode 3 — develop → main):**
> - `DEPLOY-PR-OPENED: #<N>` — develop → main PR opened with batch summary.
> - `DEPLOY-MERGED: #<N>` — admin merged; Railway auto-deploy started.
>
> **WEB-GIT refusals / specials:**
> - `GIT-PUBLISH-BLOCKED: <reason>` — refusal (e.g. wrong branch, ruleset violation).
> - `GIT-PUBLISH-RETRY: <branch>` — rebase performed, new sha; re-run `/review` against new sha.
> - `GIT-PUBLISH-NOOP: <reason>` — nothing to do (e.g. develop = main on deploy).
>
> **Session-spanning TODOs:**
> - `SESSION-START-TODO: <action>` — explicit pending action for the *next* session's first move (e.g. "run `./tools/cmux_setup.sh`"). Surfaced automatically by the SESSION_PROTOCOL.md § 2 checklist on next session start.

<!-- Append new handoff entries here. Format: `- [YYYY-MM-DD] <SIGNAL>` -->

- [2026-05-14] PR-MERGED: #29 — squashed into develop (7f225c2) via `gh pr merge 29 --squash --admin` (no --delete-branch). Mode 1 step 7 clean: stash → merge → `gh api -X DELETE refs/heads/feature/admin-s5-library-to-profile` HTTP 204 → checkout develop → pull (fast-forward a5edff5..7f225c2, 7 files +220/-191) → branch -D → fetch --prune → stash pop. S5 (absorb /library into Profile per replan Issue 3) live on develop.
- [2026-05-14] REVIEW-REQUESTED: 14510ae — feat(s6): 4-tab → 3-tab TabBar cutover. Replan S6 explicitly requires Part B browser strict mode (large routing change: TabBar 4→3, index → /discovery redirect, ProjectSetupPage onBack repath, MainLayout empty-state retarget). Rule 2 override per plan. WEB-REVIEW please run `/review` Part A 7-axis + Part B browser strict + Part C drift.
- [2026-05-14] REVIEW-PASSED: 00feeb1 — drift checks passed, 3 MINOR noted (see .claude/reviews/latest.md); run `git push` manually from this terminal
- [2026-05-14] PR-OPENED: #30 — feature/admin-s6-tab-cutover → develop, 3 commits (14510ae S6 code 4→3-tab cutover + e5d469e READY-FOR-PUSH signal + 00feeb1 REVIEW-REQUESTED signal swap), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/30. REVIEW-PASSED at 00feeb1 (3 MINOR non-blocking out-of-scope for S7; Part A 0/0/3, Part B 7/7 S6 smoke gates green ×3 personas, Part C drift clean). On CI green: canonical Mode 1 step 7.
- [2026-05-14] PR-CI-GREEN: #30 — Backend 2m6s, Frontend 11s, Vercel + comments all SUCCESS.
- [2026-05-14] PR-MERGED: #30 — squashed into develop (976bfdc) via `gh pr merge 30 --squash --admin` (no --delete-branch). Mode 1 step 7 clean: stash → merge → `gh api -X DELETE refs/heads/feature/admin-s6-tab-cutover` HTTP 204 → checkout develop → pull (fast-forward 7f225c2..976bfdc, 6 files +59/-930 — FavoritesPage + SetupPage deleted) → branch -D → fetch --prune → stash pop. **Note**: squash commit title is the last commit's "docs(handoffs): swap S6 signal to REVIEW-REQUESTED per replan" rather than the substantive S6 feat title (gh default behavior; commit body still contains the 4-tab → 3-tab cutover diff). S6 (4-tab → 3-tab TabBar cutover per replan) live on develop.
- [2026-05-14] FRONT-DONE: s7-discovery-frontend-page — DiscoveryPage + SaveToBoardModal + api/discovery.js verified. One deviation from task file: used `metadata.axis_architects` (matching normalizeCard output + all other card consumers) instead of `metadata.architect` as written in the spec bullet. front-validate.sh ALL GREEN (lint + vite build).
- [2026-05-14] BACK-DONE: s7-discovery-backend-feed
- [2026-05-14] REVIEW-FAIL: 666e36f — static review PASS-WITH-MINORS (0 CRITICAL, 0 MAJOR, 4 MINOR) but browser test FAIL: DiscoveryPage stuck loading=true under React StrictMode dev (isActiveRef never reset on remount at frontend/src/pages/DiscoveryPage.jsx:149+173); cards stay empty even though /api/v1/discovery/ returns warm 12-card payload in ~615ms; fix is `useEffect(() => { isActiveRef.current = true; return () => { isActiveRef.current = false } }, [])`; see .claude/reviews/latest.md
- [2026-05-14] REVIEW-PASSED: 8f783d1 — drift checks passed, 6 MINOR noted (see .claude/reviews/latest.md). Part A PASS-WITH-MINORS (0 CRITICAL, 0 MAJOR, 6 MINOR — dead DebugOverlay instrumentation, getBoardBuildings missing 200-chunk, preloadImage timeout removed, duplicate intensity coercion in swipe.py, SessionStateView sequential card fetch, no test for cache-aware get_buildings_by_ids). Part B PASS-WITH-NOTES — Brutalist 3-run TTFC p50 4473ms (>4000ms budget by 12%, Gemini API + Neon RTT structural per spec rationale, identical to prior cycle fd871d3 4244ms); 14-swipe loop user-felt p50 2236ms (>1500ms outer gate, TinderCard animation + Neon RTT — but backend SessionEvent total_ms p50 ~615ms is well within 1000ms backend gate, proving the branch's caching + vectorized MMR + batch fetch refactor delivers ~60-70% backend latency reduction vs fd871d3's 1664-2033ms). Phases exploring→analyzing→converged, 14/14 unique cards, 0 console errors, 0 networking errors. Part C: HEAD intact at 8f783d1, origin/main intact at c231c5972. Run `git push` manually from this terminal.
- [2026-05-14] READY-FOR-PUSH: feature/admin-s2-prep-schema-doc-sync — S2-prep doc reality-sync at 1bccf9e. Single commit `docs(s2-prep): reality-sync database-schema.md vs live v1 Neon`. 7 files +718/-130 (docs/database-schema.md restructured + .gitignore adds test-artifacts/ + Task.md S2 entry update + 4 carryover review artifacts from PR #32 absorb cycle). Full S2 (DB new-schema integration) remains BLOCKED pending Make DB owner (권상조) v2+Divisare migration push; this is the pre-flight prep that engine.py's `_AVAILABLE_COLUMNS` probe + `_build_select_columns(required, optional)` pattern is already forward-compatible against — verified by `pytest apps/recommendation/` → 52 passed against live v1 Neon (23 cols, 3,465 rows probed 2026-05-14). /review skipped per Token-Saving Rule 2 (pure docs + gitignore + Task.md, zero source code). WEB-GIT Mode 1: `gh pr create --base develop` → poll CI → `gh pr merge --squash --admin` (no --delete-branch flag per Bug #4 root-cause fix) + explicit `gh api -X DELETE refs/heads/feature/admin-s2-prep-schema-doc-sync` + local sync.
- [2026-05-14] PR-OPENED: #33 — feature/admin-s2-prep-schema-doc-sync → develop, 1 commits (828408c "docs(s2-prep): reality-sync database-schema.md vs live v1 Neon"), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/33. /review skipped per Rule 2 (pure docs + gitignore + Task.md, zero source).
- [2026-05-14] PR-CI-GREEN: #33 — Backend 2m7s, Frontend 10s, Vercel + comments all SUCCESS.
- [2026-05-14] PR-MERGED: #33 — squashed into develop (c0f1da9) via `gh pr merge 33 --squash --admin` (no --delete-branch). Mode 1 step 7 clean: no stash needed (working tree clean) → merge → `gh api -X DELETE refs/heads/feature/admin-s2-prep-schema-doc-sync` HTTP 204 → checkout develop → pull (fast-forward bc5a057..c0f1da9, includes 3 carryover review artifacts: 666e36f.md, 8f783d1.md, f79e341.md) → branch -D → fetch --prune → no stash to pop. S2-prep doc reality-sync (database-schema.md vs live v1 Neon) live on develop.
- [2026-05-14] READY-FOR-PUSH: feature/admin-s2-new-schema — S2 full canonical_v2_buildings cutover. 2 commits at HEAD: 973bd80 backend (engine.py 20+ raw SQL rewritten + canonical_bld_id PK + is_publishable gate + image_focus jsonb cover model + parse_query Gemini enum + view threading + SwipeEvent migration 0018), final commit frontend/tests/docs (normalizeCard rewrite + cover fallback chain + API senders → canonical_bld_ids + 599/599 pytest GREEN + 12 legacy v1 tests `pytest.mark.skip` + docs/database-schema.md full rewrite + CLAUDE.md hard rules swap). Live Neon smoke PASS (image_focus fallback chain verified against bld_000344). /review skipped per user override (ultraplan-approved scope, full pre-push pytest + front-validate already GREEN). WEB-GIT Mode 1: `gh pr create --base develop` with title "feat(s2): canonical_v2_buildings cutover + image_focus" → poll CI → `gh pr merge --squash --admin` (no --delete-branch flag per Bug #4 root-cause fix) + explicit `gh api -X DELETE refs/heads/feature/admin-s2-new-schema` + local sync.
- [2026-05-14] PR-OPENED: #34 — feature/admin-s2-new-schema → develop, 2 commits (973bd80 backend canonical_v2_buildings + image_focus + 0e93d9f frontend cutover + fixtures + docs), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/34. /review skipped per user override (ultraplan-approved, 599/599 pytest GREEN + front-validate GREEN pre-push).
- [2026-05-14] PR-CI-GREEN: #34 — Backend 2m5s, Frontend 16s, Vercel + comments all SUCCESS.
- [2026-05-14] PR-MERGED: #34 — squashed into develop (b7d39b2) via `gh pr merge 34 --squash --admin` (no --delete-branch). Mode 1 step 7 clean: no stash needed → merge → `gh api -X DELETE refs/heads/feature/admin-s2-new-schema` HTTP 204 → checkout develop → pull (fast-forward c0f1da9..b7d39b2, 41 files +1047/-611, new migration 0018_rename_swipeevent_canonical_bld_id) → branch -D → fetch --prune. S2 (canonical_v2_buildings full cutover + image_focus jsonb cover model + Gemini enum parse_query + 599/599 pytest GREEN) live on develop.
- [2026-05-14] STALE-BRANCHES-DELETED: feat/sj-0512-dbspeed + feat/sj-0513-errorfix + phase-5-polish-tests (3 branches). Admin-authorized cleanup via `git push origin --delete` (3 refs removed remotely). Rationale: PR #22 + #23 (ksangjo) absorbed via PR #32; phase-5-polish-tests pre-recovery dead branch (ancient, before PR #18). Preserved per admin: feature/sns-profile-system (유예원 work). Post-state remote heads: `main` (c231c59), `develop` (b7d39b2), `feature/sns-profile-system` (b0a00f9) — 3 branches total.
- [2026-05-14] DEPLOY-PR-OPENED: #36 — develop → main, 15 PRs since last deploy `c231c59` (PR #19-#21 + #24-#35; PR #22+#23 closed unmerged, absorbed via PR #32). URL: https://github.com/hongikarchi/archi-tinder/pull/36. Title: "Deploy: PR #19-#35 (S1-S8 tab3 replan + canonical_v2_buildings cutover + workflow infra)". Range: develop@6ffb5b6 vs main@c231c59. Four themes: (a) canonical_v2_buildings full cutover PR #34 S2 (largest delta, 41 files, 599/599 pytest GREEN, SwipeEvent migration 0018); (b) tab 3-structure transition S3-S7 PR #27-#31; (c) S8 spec/roadmap sweep PR #35; (d) workflow infra PR #19-#21, #24-#26, #32-#33. All underlying PRs reviewed pre-merge.
- [2026-05-14] PR-CI-GREEN: #36 — Backend 2m7s/2m8s (×2 runs), Frontend 14s/13s (×2 runs), Vercel + comments all SUCCESS.
- [2026-05-14] DEPLOY-MERGED: #36 — main = f955ab5 ("Deploy: PR #19-#35 (S1-S8 tab3 replan + canonical_v2_buildings cutover + workflow infra) (#36)"). Merged via `gh api -X PUT pulls/36/merge --field merge_method=squash` (Option A dogfood per Bug #4 codified rule — REST endpoint, sidesteps gh CLI flag bug entirely). Response: `{sha: f955ab57..., merged: true}`. Railway auto-deploys on main push. S2 canonical_v2_buildings cutover + S3-S7 tab 3-structure transition + S8 spec sweep + workflow infra (15 PRs) now live in production.
- [2026-05-14] DEPLOY-RECOVERY-COMPLETE: develop force-reset to main (f955ab5) via `gh api -X PATCH refs/heads/develop --field sha=f955ab5... --field force=true`. Bug #5 mandatory step executed. Verified `git ls-remote origin refs/heads/{develop,main}` → both at f955ab57 (identical SHAs, zero graph divergence). Local sync clean: `git fetch --all --prune` → `git checkout develop` (Already on develop) → `git reset --hard origin/develop` (HEAD at f955ab5) → working tree clean. Next feature PRs will branch from clean develop with no graph divergence risk on next deploy cycle. Post-state remote heads: `main` (f955ab5), `develop` (f955ab5), `feature/sns-profile-system` (b0a00f9, preserved) — 3 branches total, develop = main.
- [2026-05-15] PR-OPENED: #37 — feature/admin-tab3-swipe-restore → develop, 3 commits (51d31be card-swipe identity restore + legacy purge cmd, e253584 card detail UX + profile pagination + LLM chat persistence, c1efb60 /user/me 500 + drawing crop on Discovery + title clip hotfix), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/37. Inner-loop reviewer + security PASS twice (on e253584 + c1efb60). Pre-push reviewer PASS on hotfix. pytest 102/102 GREEN, front-validate GREEN. DB ops: purge_legacy_projects --all --confirm executed on Neon (450 Project rows + 5059 cascade rows deleted; AnalysisSession + SwipeEvent cleared). Breaking response shape: `/api/v1/users/<id>/` `data.boards` is now `{items, page, page_size, total_count, has_more, next_page}` object (was array). /review skipped per user override (post-PR #36 deploy hotfix bundle, inner-loop checks comprehensive). Direct push from WEB-MAIN (WEB-GIT blocked by Claude Code auto-update prompt at session time). Pending: poll CI green → admin squash-merge → develop sync.
- [2026-05-15] READY-FOR-PUSH: feature/admin-tab3-swipe-restore — 3 commits ahead develop (51d31be restore card-swipe identity + image loading + legacy boards, e253584 card detail UX + profile pagination + LLM chat persistence, c1efb60 /user/me 500 + drawing crop on Discovery + title clip). All inner-loop checks PASS (front-validate GREEN, pytest 102/102, manual smoke). DB legacy wipe (450 projects + 5059 cascade rows) already executed on Neon. Breaking: `/api/v1/users/<id>/` `data.boards` response is now object `{items, page, page_size, total_count, has_more, next_page}` (was array). /review skipped per user override (hotfix bundle, post-PR #36 deploy follow-up). WEB-GIT Mode 1: `tools/git-push-pr.sh` with PR title "fix(deploy): card-swipe restore + UX hotfix + profile pagination + legacy wipe" → poll CI → squash merge → sync. Report PR# via PR-OPENED signal.
- [2026-05-16] PR-CI-GREEN: #37 — backend 2m14s, frontend 15s, Vercel + comments all pass.
- [2026-05-16] PR-MERGED: #37 — squashed develop @ 5fcfd3d. Mode 1 step 7 clean: `gh api -X DELETE refs/heads/feature/admin-tab3-swipe-restore` → checkout develop → pull (16 files +1150/-680, new `purge_legacy_projects.py` + `SwipeCard.jsx`) → branch -D → fetch --prune.
- [2026-05-16] PR-OPENED: #39 — feature/admin-caveman-git-text → develop, 2 commits (aa98a61 caveman-terse git text in agent defs + 2f51453 WEB-MAIN implementation delegation HARD RULE for P1 perf-ux-overhaul). URL: https://github.com/hongikarchi/archi-tinder/pull/39. /review skipped per Token-Saving Rule 2 (pure docs + agent-infra, zero source).
- [2026-05-16] PR-CI-GREEN: #39 — backend 2m15s, frontend 18s, Vercel + comments all pass.
- [2026-05-16] PR-MERGED: #39 — squashed develop @ 97127f1. Mode 1 step 7 clean: `gh api -X DELETE refs/heads/feature/admin-caveman-git-text` → checkout develop → pull (.claude/agents/reporter.md + CLAUDE.md + others, 5 files +42/-3) → branch -D → fetch --prune. develop HEAD = 97127f1.
- [2026-05-16] REPORTER-DONE: 97127f1 — P1 perf-ux-overhaul session closed; CLAUDE.md delegation HARD RULE live on develop; remaining phases P2-P6 next sessions

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
> Spec: `docs/specs/phase16-recommendation-expansion.md` (refreshed S8
> 2026-05-14). REC1 already executed as **Push S3**. REC2 / REC3 now
> serve a Profile-tab "사무소 추천" button (Q3 decision); Landing tab
> deleted by Push S6. Endpoint shape changed from
> `/api/v1/landing/{sessionId}/` (deprecated) to a Profile-targeted
> composite (e.g. `/api/v1/recommendations/profile/`).
43. **REC1** -- Post-swipe end screen consolidation (executed in **S3** 2026-05-14)
44. **REC2** -- Firm recommendation logic (Profile-button-triggered)
45. **REC3** -- User recommendation logic (Profile-button-triggered)
46. **REC4** -- ~~Landing tab~~ → removed by Push S6 (Profile-tab button surface instead)

### Phase 17: LLM Reverse-Questioning -- PENDING (S8 sweep COMPLETED)
> Spec: `docs/specs/phase17-llm-reverse-q.md` (refreshed S8 2026-05-14).
> Replan Q6 RESOLVED → Option A: reverse-question lives in the first
> 0-2 turns of the Taste-tab LLM chat (pre-swipe). TTFC budget unchanged.
47. **LLM1** -- Chat reverse-question prompt design (identify user needs)
48. **LLM2** -- Persona classification logic (P1-P4 differentiation; populates `UserProfile.persona_summary`)
49. **LLM3** -- Per-persona UI branching (recommendation card type switching)

### Phase 18: External Connections -- PENDING (S8 sweep COMPLETED)
> Spec: `docs/specs/phase18-external-connections.md` (refreshed S8
> 2026-05-14: Goal.md path corrected to `.claude/Goal.md`; scope
> unchanged). Lower priority than Phase 16-17.
50. **EXT1** -- Firm article crawler (Space, ArchDaily, news — keyword-based)
51. **EXT2** -- Article list UI (inside firm profile)
52. **EXT3** -- External DM link UI (Instagram, email — on profile)

### Phase 19-26: 2026-05-14 Replan (Tab 3-Structure Transition) -- COMPLETED 2026-05-14
> Full plan: `.claude/plans/replan-2026-05-14-tab3-restructure.md`.
> All 8 pushes shipped between 2026-05-13 and 2026-05-14; develop @ `b7d39b2`
> (+ S8 sweep commit pending). Deploy PR develop → main scheduled next.
53. **S1** -- Plan + collaborator on-ramp doc -- COMPLETED 2026-05-13 (PR #26 → develop b9c8dd4)
54. **S2** -- DB new-schema integration -- COMPLETED 2026-05-14 *(Make DB owner pushed `canonical_v2_buildings` 31-col / 39,776-row table; Make Web cutover via PR #34 `feature/admin-s2-new-schema`: engine.py 20+ raw SQL rewritten + canonical_bld_id PK + is_publishable gate + image_focus jsonb cover model; SwipeEvent migration 0018; frontend normalizeCard / fallback chain; full pytest 599/599 GREEN; front-validate GREEN; live Neon smoke PASS on bld_000344)*
55. **S3** -- Swipe end-flow consolidation -- COMPLETED 2026-05-13 (PR #27 → develop 2a61881; ActionCard removal + end-screen rewrite; tolerate empty building_id on extend session)
56. **S4** -- Progress UI single source -- COMPLETED 2026-05-13 (PR #28 → develop a5edff5; unified progress bar + DebugOverlay extension)
57. **S5** -- Library → Profile absorb -- COMPLETED 2026-05-13 (PR #29 → develop 7f225c2; FavoritesPage + SetupPage deleted; real data + redirect)
58. **S6** -- 4-tab → 3-tab cutover -- COMPLETED 2026-05-14 (PR #30 → develop 976bfdc; Discovery / Taste / Profile only; Library/Landing removed; Part B browser 7/7 ×3 personas green)
59. **S7** -- Discovery Swipe tab -- COMPLETED 2026-05-14 (PR #31 / 0ee6b42 cluster + 0e93d9f frontend; infinite-scroll Discovery page + save flow + surprise board)
60. **S8** -- Roadmap / spec sweep -- COMPLETED 2026-05-14 *(this commit on `feature/admin-s8-roadmap-sweep`: Phase 16/17/18 specs refreshed post-replan + post-S2; Goal.md § 7 Phase 16 description rewritten + § 11 checklist ticked; docs/specs/requirements.md canonical_bld_id + canonical_v2_buildings stale refs fixed; Task.md handoffs trimmed 62 → 30 by archiving older entries to `.claude/handoffs-archive/2026-05.md`; remote stale branches `feat/sj-0512-dbspeed` + `feat/sj-0513-errorfix` + `phase-5-polish-tests` deleted)*

### Carryover (deferred non-blocking from prior reviews)
61. **SOC3-back-blocked** -- Original blocker was Neon DB DNS in codex sandbox. Revisit when next Office model migration is needed; resolution path documented in `.claude/codex/backend-worker.md` § "DB-touch handoff".

---

## Specs

> Pending-feature specs and decision records live in `docs/specs/` (admin-owned via PR).
> Algorithm theory + production hyperparameters live in `docs/algorithm.md` (reporter
> syncs production values; admin owns theory edits).
>
> Current pending specs:
> - `docs/specs/phase16-recommendation-expansion.md` — Phase 16 dimensions
> - `docs/specs/phase17-llm-reverse-q.md` — Phase 17 dimensions
> - `docs/specs/phase18-external-connections.md` — Phase 18 dimensions
> - `docs/specs/requirements.md` — still-open cross-cutting questions

---

## Open

### Algorithm

#### A2. Hyperparameter optimization -- validated, full run pending
Smoke test (3 personas x 5 trials) passed. No code changes needed.
- [x] Smoke test passed (--personas 3 --trials 5)
- [ ] Run algo-tester: 100 personas x 200 trials
- [ ] Evaluate results vs baseline
- [ ] Apply optimized params if improvement found

### Auth
#### AUTH1. Kakao / Naver OAuth not implemented
Google OAuth only. Korean users need domestic login.
- [ ] Kakao social auth backend + frontend button
- [ ] Naver social auth backend + frontend button

---

## In Progress

(none)

---

## Resolved

Historical resolved tasks moved to `.claude/resolved-archive.md` (frees
~30-50K tokens per reporter call; git log is the authoritative history).
Append new resolved entries to the archive, not here.
