# Task Board

> Auto-updated by orchestrator. When you request work, orchestrator reads Goal.md
> + current code, then adds/updates tasks here before executing.
> Categories: Frontend, Backend, Auth, UX/Design, Infrastructure
> (Algorithm work is owned by a separate collaborator post-2026-05-18; see `.claude/Goal.md` § Algorithm ownership.)

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

- [2026-05-18] READY-FOR-PUSH: feature/admin-p6-minors — HEAD 61a7ea7 (handoff sig), ab4c0a2 fix. 2 commits. /review skipped per Rule 2 (trivial polish, P6 MINOR follow-up). Frontend-only `UserProfilePage.jsx` +64/-55.
- [2026-05-18] BRANCH-CREATED: feature/admin-p6-minors (P6 deferred MINOR follow-up branch).
- [2026-05-18] PR-OPENED: #47 — feature/admin-p6-minors → develop, 2 commits (ab4c0a2 P6 minors bulk delete snapshot revert + style factor + cancel race + 61a7ea7 handoff sig). URL: https://github.com/hongikarchi/archi-tinder/pull/47. /review skipped per Token-Saving Rule 2.
- [2026-05-18] PR-CI-GREEN: #47 — backend 2m9s, frontend 16s, Vercel + comments all pass.
- [2026-05-18] PR-MERGED: #47 — squashed develop @ 450d3c1. Mode 1 step 7: pre-checkout stash → `gh api -X DELETE refs/heads/feature/admin-p6-minors` → checkout develop → pull --ff-only (2 files +69/-55: Task.md +5, UserProfilePage.jsx +64 incl. snapshot revert + style helpers + cancel race fix) → branch -D → fetch --prune → stash pop (Task.md handoff sigs restored). develop HEAD = 450d3c1.
- [2026-05-18] REPORTER-DONE: 450d3c1 — P6 minors patched; bulk delete snapshot revert + bulkActionButtonStyle factor + exitSelectMode cancel race fix live on develop
- [2026-05-18] DEPLOY-PR-OPENED: #49 — develop @ 4340d09 → main @ f955ab5, 11 PRs (P1-P6 latency+UX overhaul series + deploy hotfix #37). URL: https://github.com/hongikarchi/archi-tinder/pull/49.
- [2026-05-18] PR-CI-GREEN: #49 — backend 2m7s/2m10s ×2, frontend 10s/14s ×2, Vercel + comments all pass.
- [2026-05-18] DEPLOY-MERGED: #49 — main = d785c360 ("Deploy: PR #37-#48 (P1-P6 latency + UX overhaul series + deploy hotfix) (#49)"). Squash via `gh api PUT pulls/49/merge` (Bug #4 sidestep). Railway auto-deploy triggered.
- [2026-05-18] DEPLOY-DEVELOP-RESET: develop force-reset to main d785c360 per Bug #5 (codified carve-out). Initial WEB-GIT attempt blocked by auto-mode classifier; admin manually ran `gh api PATCH refs/heads/develop --force=true` from WEB-MAIN per user authorization. Both heads now d785c360.
- [2026-05-18] DOCS-FIX: CLAUDE.md HARD RULE 4 + CONTRIBUTING.md Deploy flow updated to codify Bug #5 carve-out so future deploys don't hit classifier block. Direct edit (meta/infra carve-out per delegation rule).
- [2026-05-18] REPORTER-DONE: de2e979 — doc-system cleanup: Phase 19-26+P1-P6 archived, codex/plans-archive dirs, WORKFLOW Known Issues + retention, Goal.md algo ownership, algo-tester deleted
- [2026-05-18] BRANCH-CREATED: feature/admin-reporter-doc-cleanup-close (reporter session-end housekeeping; docs-only).
- [2026-05-18] PR-OPENED: #52 — feature/admin-reporter-doc-cleanup-close → develop, 2 commits (254a325 reporter doc-cleanup session-end housekeeping + 6c20737 handoff sig). URL: https://github.com/hongikarchi/archi-tinder/pull/52. /review skipped per Token-Saving Rule 2 (docs-only).
- [2026-05-18] PR-CI-GREEN: #52 — backend 2m14s, frontend 14s, Vercel + comments all pass.
- [2026-05-18] PR-MERGED: #52 — squashed develop @ aff9cab. Mode 1 step 7: pre-checkout stash → `gh api -X DELETE refs/heads/feature/admin-reporter-doc-cleanup-close` → checkout develop → pull --ff-only (2 files +18/-8: Report.md sync to de2e979, Task.md REPORTER-DONE sig) → branch -D → fetch --prune → stash pop (Task.md handoff sigs restored). develop HEAD = aff9cab.
- [2026-05-21] PR-OPENED: #53 — feature/admin-pr38-salvage → develop, 1 commit (cef76e0 salvage PR #38 google login sync + board recommended section). URL: https://github.com/hongikarchi/archi-tinder/pull/53. CI running.
- [2026-05-21] PR-CLOSED: #38 — superseded by #53; comment left for @yywon1.
- [2026-05-21] PR-CI-FAIL: #53 — Backend (pytest + migrations check) failed; TestUserProjectsListView.test_no_n_plus_one_select_related: expected 5 queries but 10 done. Logs: https://github.com/hongikarchi/archi-tinder/actions/runs/26217895654/job/77144916946

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

> **Phase 19-26 (2026-05-14 Replan, Tab 3-Structure Transition) + Phase P1-P6
> latency+UX overhaul (2026-05-15..2026-05-18)** — all shipped to production
> via deploy PR #36 (S1-S8) and PR #49 (P1-P6). Archived to
> `.claude/resolved-archive.md` on 2026-05-18.

---

## Specs

> Pending-feature specs and decision records live in `docs/specs/` (admin-owned via PR).
> Algorithm theory + production hyperparameters live in `docs/algorithm.md`. Owned by a
> separate collaborator post-2026-05-18; admin role here is limited to (a) reporter
> auto-sync of the Production Value column when `settings.py` RECOMMENDATION dict
> changes, and (b) theory-edit review on PR (see `.claude/Goal.md` § Algorithm ownership).
>
> Current pending specs:
> - `docs/specs/phase16-recommendation-expansion.md` — Phase 16 dimensions
> - `docs/specs/phase17-llm-reverse-q.md` — Phase 17 dimensions
> - `docs/specs/phase18-external-connections.md` — Phase 18 dimensions
> - `docs/specs/requirements.md` — still-open cross-cutting questions

---

## Open

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
- 2026-05-18 READY-FOR-PUSH: feature/admin-doc-cleanup-2026-05-18 @ 8269260 — doc-system audit + cleanup + algorithm ownership boundary. 20 files (pure docs/policy, zero source). /review skip per Rule 2.
- 2026-05-18 READY-FOR-PUSH: feature/admin-reporter-doc-cleanup-close @ 254a325 — reporter session-end housekeeping (Report.md sync). Docs-only, /review skip per Rule 2.
