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
- [2026-05-16] SESSION-START-TODO: next P2 session — branch P2 from `feature/admin-reporter-p1-close` (NOT develop) to absorb pending reporter pass commit `7d9f306` (Rule 6 bundle). Command: `git checkout feature/admin-reporter-p1-close && git checkout -b feature/admin-p2-latency`. P2 PR then sweeps both 7d9f306 + P2 work in one push.
- [2026-05-16] REVIEW-PASSED: 50e4073 — drift checks passed, 4 MINOR noted (see .claude/reviews/latest.md); run `git push` manually from this terminal
- [2026-05-16] PR-OPENED: #40 — feature/admin-p2-latency → develop, 3 commits (7d9f306 reporter P1 housekeeping + e1fda98 SESSION-START-TODO handoff + 50e4073 P2 perf N+1 batch fetch + ring buffer instrumentation). URL: https://github.com/hongikarchi/archi-tinder/pull/40. REVIEW-PASSED at 50e4073 (4 MINOR non-blocking). Carryover edits (Task.md handoff sigs from #37/#39 + `.claude/reviews/50e4073.md` artifact + `latest.md` symlink) stashed pre-push; will reland on develop post-merge.
- [2026-05-16] PR-CI-GREEN: #40 — backend 2m7s, frontend 16s, Vercel + comments all pass.
- [2026-05-16] PR-MERGED: #40 — squashed develop @ 9c7d513. Mode 1 step 7 clean: `gh api -X DELETE refs/heads/feature/admin-p2-latency` → checkout develop → pull (7 files +53/-38, `sessions.py` + `core.js` etc.) → branch -D → fetch --prune → stash pop (carryover handoff edits restored to working tree on develop). develop HEAD = 9c7d513.
- [2026-05-16] REPORTER-DONE: 9c7d513 — P2 latency session closed; SessionResultView N+1 → batch fetch + discovery.py exclude_set bug fix + core.js 8-slot ring buffer instrumentation live on develop; 4 MINOR from /review non-blocking, deferred
- [2026-05-16] SESSION-START-TODO: next P3 session — branch P3 from `feature/admin-reporter-p2-close` (NOT develop) to absorb pending reporter pass commit (Rule 6 bundle). Command: `git checkout feature/admin-reporter-p2-close && git checkout -b feature/admin-p3-swipe-ux`. P3 PR sweeps reporter pass + P3 work. P3 scope: ConfidenceBar redesign (count + stage label), swipe failed error classification, exit/new-project button, X-confirm-popup. See approved ArchiTinder latency+UX plan.
- [2026-05-16] REVIEW-FAIL: 2c387df — static review PASS-WITH-MINORS (0 CRITICAL, 0 MAJOR, 5 MINOR) but browser test FAIL: F3 Exit session button click-occluded by global Logout button on `/swipe` (same right-16 top corner; Logout container z-index 200 wins clicks over Exit z-index 10). F1 (stage label + swipe count + percent) F2 (silent inner-retry on transient network err) F4 (first-left DismissConfirmPopup + `archithon_dismiss_tutorial_seen` persistence) all PASS end-to-end on Brutalist persona (13 swipes converged, 0 console err, swipe p50 1039 ms / p95 1133 ms, 1 over-1500 ms outlier within tolerance). Fix: add `pathname === '/swipe'` to MainLayout.jsx:25 Logout exclusion list, OR shift SwipePage Exit button right offset (e.g. right:60) so it sits left of Logout. See .claude/reviews/latest.md.
- [2026-05-16] REVIEW-PASSED: acefff8 — drift checks passed; run `git push` manually from this terminal. Fix-loop resolved all 5 prior-cycle findings: F3 collision (Exit right:16 → left:16; live rect [16,12,48,44] vs Logout [685,14,719,48], 637 px clear gap, elementFromPoint at Exit center returns Exit's own SVG child) + MINOR #1 (currentCardRef declared before mirror useEffect) + MINOR #2 (isNetworkError deleted; inner-try retry now reads classifySwipeError(err).kind === 'network', single classifier source) + MINOR #5 (both ExitConfirmPopup + DismissConfirmPopup carry role=dialog + aria-modal + aria-labelledby pointing at correct h2 id + Escape close + auto-focus primary action). Live browser verification: Exit popup opens with correct ARIA, focuses 새 프로젝트 시작; Escape + 취소 + 새 프로젝트 시작 (→/new) + 홈으로 (→/discovery) all route correctly; Dismiss popup ARIA spot-check via ArrowLeft also PASS (focuses 건너뛰기, Escape closes). 0 console errors across 5 page sessions. Deferred per fix-loop charter: MINOR #3 (mouse-drag flicker cosmetic) + MINOR #4 (setTimeout stale-closure low-probability hardening). See .claude/reviews/latest.md.
- [2026-05-16] PR-OPENED: #41 — feature/admin-p3-swipe-ux → develop, 3 commits (b6825f3 reporter P2 housekeeping + 2c387df P3 swipe UX feat + acefff8 P3 review fixes F3 collision + ARIA dialog + classifier dedup). URL: https://github.com/hongikarchi/archi-tinder/pull/41. REVIEW-PASSED at acefff8 (2 MINOR deferred: cosmetic mouse-drag flicker + setTimeout stale-closure low-prob). Carryover (Task.md handoff sigs + reviews/latest.md + reviews/acefff8.md) stashed pre-push; relands on develop post-merge.
- [2026-05-16] PR-CI-GREEN: #41 — backend 2m5s, frontend 14s, Vercel + comments all pass.
- [2026-05-16] PR-MERGED: #41 — squashed develop @ 824dc86. Mode 1 step 7 clean: `gh api -X DELETE refs/heads/feature/admin-p3-swipe-ux` → checkout develop → pull (9 files +904/-221, includes carryover review artifacts `.claude/reviews/2c387df.md` + `.claude/reviews/50e4073.md`) → branch -D → fetch --prune → stash pop (Task.md + reviews/latest.md + reviews/acefff8.md restored to working tree). develop HEAD = 824dc86.
- [2026-05-16] REPORTER-DONE: 824dc86 — P3 swipe-UX session closed; F1 ConfidenceBar redesign + F2 swipe error classification + F3 exit/new-project button (top-left, no Logout collision) + F4 first-dismiss tutorial popup live on develop; 2 MINORs deferred (mouse-drag flicker cosmetic, setTimeout stale-closure low-probability)
- [2026-05-16] SESSION-START-TODO: next P4 session — branch P4 from `feature/admin-reporter-p3-close` (NOT develop) to absorb pending reporter pass commit (Rule 6 bundle). Command: `git checkout feature/admin-reporter-p3-close && git checkout -b feature/admin-p4-building-detail`. P4 PR sweeps reporter pass + P4 work. P4 scope: Building Detail page redesign — Pinterest grid + multisource. See approved ArchiTinder latency+UX plan.

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
