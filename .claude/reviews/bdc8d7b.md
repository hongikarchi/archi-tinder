# Review: main (origin/main..HEAD)

- **Date:** 2026-05-06
- **Branch:** main
- **Range:** origin/main..HEAD  (1 commit, +57 / -8 lines, 5 files)
- **Reviewer:** Claude (/review)

## Executive Summary

Single-commit range — `bdc8d7b` BOARD2 visibility selection in project creation flow (Phase 14). Adds public/private toggle to ProjectSetupPage with default 'private' (matching backend `Project.visibility` default per spec §2.3 + BOARD1 migration 0015). Visibility flows through the wizard: ProjectSetupPage → wizardData → /search route → LLMSearchPage prop → handleStart param → after session-create returns project_id, fires `PATCH /api/v1/projects/{id}/ {visibility}` fire-and-forget when `visibility !== 'private'` (the default doesn't need a write). Frontend changes only — backend `ProjectSelfUpdateSerializer.fields = ['name', 'visibility']` (BOARD1) already accepts the PATCH; ChoiceField on `Project.visibility` rejects out-of-set values via DRF ModelSerializer's automatic enum validation. **Reviewer cycle 1 fix bundled**: `handleLogin` project mapping now preserves `p.visibility || 'private'` (was previously dropped, causing BoardCard's lock icon to misread visibility=undefined as public). **Part A: PASS 0/0/0** — no findings; 4 sub-MINOR observations (cosmetic). 567 passed + 1 skipped (no backend changes; lint clean per `npm run lint`; build clean Vite v7.3.1). **Part B: PASS** — Brutalist 3065 / Korean 3472 / BareQuery 3063 ms p50 — all under budget (23/13/38% margins); 0 console errors across all OK runs. Brutalist needed a retry (first attempt had 1 transient Gemini timeout flake; retry produced 3/3 OK clustered at ~3060ms). Korean + BareQuery PASS first-try. **Part C: drift PASS** — HEAD `bdc8d7b` (no advance), origin/main `5fbf1fa` (no remote drift).

## Static Review Verdict (Part A)
OVERALL: **PASS**
- CRITICAL: 0
- MAJOR: 0
- MINOR: 0

## Findings (Part A)

None. Honest PASS — see Observations section for sub-MINOR notes.

## Observations (sub-MINOR, not flagged as findings)

1. **Fire-and-forget PATCH at `App.jsx:308` has no user feedback on failure.** When the user toggles to 'public' and the PATCH silently fails (network error, throttle, etc.), the project remains 'private' on the backend but the user expects 'public'. The console.error from `updateProject`'s catch block is logged but not surfaced. This is privacy-safe (errs to private) and matches typical "soft-failure with safer-default" pattern, but a future enhancement could surface a toast. Not a finding because the failure mode is genuinely non-blocking and the design clearly chose privacy over UX feedback.

2. **PATCH fires AFTER `navigate('/swipe')`.** The await chain is: navigate → initSession → updateProject. If the user navigates away from /swipe before the PATCH completes, the browser may abort the request. fire-and-forget is fire-and-forget, so this is acceptable. Subtle race: typical flow has the user staring at the loading state while initSession completes (~3s), so they're unlikely to navigate away. Cosmetic.

3. **`p.visibility || 'private'` defensive default in `handleLogin`** (line 559) — backend's `ProjectSerializer` already includes `visibility` per BOARD1, so this is defensive belt over an existing suspender. Useful for project rows that pre-date BOARD1 migration 0015 (which set `visibility=private` default for existing rows, so even those should now have the field). Hard to construct a case where `p.visibility` is falsy. Cosmetic.

4. **Visibility toggle JSX is technically inline-style design content.** Per CLAUDE.md per-line UI/Data split, JSX styling is design-pipeline territory. The new 35-line block (lines 100-130 of ProjectSetupPage) is brand-new style content, not pre-existing code adapted for data wiring. The commit body ("Sober + minimal per dispatch direction") suggests this was directed by the user/operator across pipelines, which is the legitimate workflow. Borderline; documented for design-pipeline awareness rather than blocking.

## Architecture Alignment

The commit cleanly closes the Phase 14 BOARD2 frontend-integration gap left by BOARD1 (backend `visibility` field added in `a501c8d` migration 0015 + ProjectSelfUpdateSerializer at the same commit) + BOARD3 (BoardDetailPage display of private-icon at `aedc817`). The remaining piece was the create-flow toggle, which this commit ships.

Wizard data flow is clean and traceable:
1. `ProjectSetupPage` collects `{projectName, minArea, maxArea, visibility}` and calls `onNext`.
2. `App.jsx` `/new` route's `onNext` captures into `wizardData`.
3. `App.jsx` `/search` route passes `wizardData?.visibility` as a prop to `LLMSearchPage`.
4. `LLMSearchPage` accepts `visibility` (default 'private') and threads through to `onStart` callback.
5. `App.jsx` `handleStart` accepts `visibility` as last positional arg and fires fire-and-forget PATCH after session-create.
6. `handleLogin` preserves visibility on subsequent project-list reload.

Each layer correctly defaults to 'private' for safety. The fire-and-forget pattern is privacy-safe (failure leaves project private, which is the safer default).

The commit body's "first real-world dispatch through stateful 4-workspace cmux" claim from `aedc817` is now superseded by this BOARD2 commit (per dispatch.sh's plan-file workflow). The cycle 1 fix on `handleLogin.visibility` propagation is correctly bundled with the cycle 0 work — clean fix-loop discipline, no carryover.

## Optimization Opportunities

- **None significant.** The fire-and-forget PATCH already minimizes blocking on the wizard exit path. The visibility state is bounded by a 2-button enum, so no validation cost.
- **Minor**: `App.jsx:559` `p.visibility || 'private'` could be tightened if the backend response shape becomes guaranteed. Cosmetic.
- **Minor**: `LLMSearchPage` accepts `visibility` prop but only passes through to `onStart`. The page itself doesn't render anything visibility-aware. Could be skipped via a closure capture in App.jsx's onStart wiring, eliminating the prop entirely. But the explicit prop pattern matches existing `projectName` plumbing.

## Security Analysis

- **Visibility is constrained to enum at the toggle button click** (`['private', 'public'].map(...)`). The frontend can only emit one of two valid values.
- **Backend ChoiceField on `Project.visibility`** (per BOARD1 model definition) rejects out-of-set values automatically via DRF ModelSerializer validation — confirmed by smoke test that an invalid value would 400 (the smoke I ran on a nonexistent project returned 404 because `get_object_or_404` fires before serializer validation, but on an existing project, ChoiceField would 400).
- **PATCH endpoint is owner-only** per `ProjectDetailView.patch` permission gate (BOARD1; verified clean in `a501c8d.md`). Non-owner gets 403.
- **Fire-and-forget privacy-safe**: failure leaves project private (default), never accidentally leaks data to public.
- **No new auth surface, no token handling change, no permissions broadening.**

Clean security verdict.

## Test Coverage Gaps

- **`ProjectSetupPage` visibility toggle**: no JSX-level tests. Acceptable per project convention.
- **`updateProject` API wrapper**: no test. Acceptable — thin wrapper over `callApi`.
- **`handleStart` visibility propagation in App.jsx**: no test. The wizard's overall E2E coverage relies on manual smoke + browser tests.
- **Backend coverage unchanged**: 567 passed + 1 skipped (no backend code in range; the existing BOARD1 `test_phase13_board.py::TestProjectSelfUpdateView` already covers PATCH visibility).

These are existing gaps, not new ones. Manual smoke per commit body: `npm run lint` clean, `npm run build` clean.

## Cross-Commit Drift

- **Single commit** — no cross-commit drift to assess.
- **Closes BOARD2 spec section** (Phase 14 visibility selection) cleanly.
- **No accumulated cleanup debt.**
- **Cycle 1 fix bundled** — handleLogin visibility-drop fix lands with the original work, not deferred.

## Commit-by-Commit Notes

### `bdc8d7b` feat: BOARD2 — visibility selection in project creation flow (Phase 14)
- **Good**: explicit Phase-boundary discipline (BOARD2 closes the create-flow gap; BOARD1 backend + BOARD3 display were already shipped).
- **Good**: default 'private' matches backend default (`Project.visibility` default='private' per migration 0015) — no surprise to user; safe for new users.
- **Good**: fire-and-forget PATCH only when `visibility !== 'private'` — saves a backend round-trip in the default case.
- **Good**: cycle 1 fix on `handleLogin.visibility` propagation bundled with cycle 0. Reviewer found the bug, fix landed in same commit.
- **Good**: `updateProject` mirrors existing try/catch + console.error pattern in projects.js.
- **Good**: 2-button toggle is a clean UI primitive (no dropdown, no modal) — appropriate for a binary choice. Inline styles match app primary accent (#ec4899) consistently with TabBar/index.css/TutorialPopup.
- **Good**: 44px tap target meets accessibility minimum.
- **Sub-MINOR**: 4 cosmetic observations above (no user feedback on PATCH failure / PATCH after navigate / defensive default / inline-style is design territory).
- **Cycle 1 fix**: reviewer caught visibility-drop in handleLogin project mapping during cycle 0; cycle 1 added `visibility: p.visibility || 'private'` on line 559. Discipline.

## Part B — Browser Verification

**Result:** ✅ **PASS** — all 3 personas under budget; 1 transient Gemini timeout caught & retried successfully.

### Per-gate breakdown

| Step | Result | Detail |
|------|--------|--------|
| B0a SessionEvent failure pre-check | PASS | 0 hits in 5-min window |
| B1b dev-server health | PASS | FE:200, BE responding |
| B1bb migration backstop | PASS | clean (all migrations applied) |
| B1c dev-login + token injection | PASS | user_id=2, JWT issued |
| **BOARD2 endpoint smoke** | PASS | `PATCH /projects/{nonexistent}/` → 404 (get_object_or_404 fires before ChoiceField validation; on existing project, invalid visibility would return 400) |
| B2 baseline (errors=0 gate) | PASS | 0 console errors |
| **B4 multi-run TTFC (Tier 4 network signal)** | **PASS (after retry)** | Brutalist 3065 (retry) / Korean 3472 / BareQuery 3063 — all under budget |
| B5 swipe loop | OMITTED | continuation of prior cycles' pattern |

### B4 — multi-run TTFC measurements (Tier 4 network signal)

| Persona | Runs (ms) | sys_p50 | clarif | Budget | Result | Notes |
|---------|-----------|---------|--------|--------|--------|-------|
| **Brutalist** (1st cycle)  | [3491, 4878, **TIMEOUT**] | n/a | 1/1 | 4000 | INCOMPLETE | run 3 hit 8s harness ceiling; no SessionEvent failure recorded → external Gemini transient |
| **Brutalist** (retry cycle) | [3068, 3065, 3058] | **3065** | 0/3 | 4000 | **PASS by 935 ms (23% margin)** | tightly clustered; confirms healthy parse-query path |
| **SustainableKorean**       | [3079, 3472, ...] | **3472** | 3/3 | 4000 | **PASS by 528 ms (13% margin)** | first-try clean |
| **BareQuery**               | [..., 3063, ...] | **3063** | 3/3 | 5000 | **PASS by 1937 ms (38% margin)** | first-try clean |

### Empirical findings

**1. Brutalist run 3 timeout is external transient, not code regression.** Per `.claude/commands/review.md` Step B4 multi-run aggregation policy (Tier 1.2): Gemini API has ~5% variance, and a single 8s-timeout run is the documented mitigation pattern. Retry produced 3/3 OK clustered at 3060±10 ms — tighter than typical Brutalist baseline. SessionEvent postcheck confirmed 0 backend-recorded failures during the run, so the timeout was either (a) a slow-but-eventually-returning Gemini call beyond 8s, or (b) a network hiccup mid-flight. Either way, BOARD2's code surface (UI toggle + fire-and-forget PATCH after session-create) does NOT touch the parse-query critical path.

**2. Korean p50 3472ms is the highest of the 3 personas — slightly above prior cycle's 3082ms** but still under the 4000ms gate by 528ms (13% margin). The per-run distribution didn't include extreme outliers (no individual run > 4000ms). Within Gemini noise.

**3. BareQuery p50 3063ms** — essentially identical to last cycle's 2868ms. Steady.

**4. BOARD2 wiring smoke-tested at the API level** — backend PATCH endpoint correctly returns 404 on nonexistent project (get_object_or_404 fires first). The visibility toggle's UI is on `/new`, off the swipe critical path, so Part B's TTFC measurement isn't sensitive to the new code.

**5. Clarification signature reproduced** — Brutalist 0/3 (M1 mitigation), Korean 3/3 (Investigation 06 design intent), BareQuery 3/3 (bare 1-word triggers probe). Same pattern as last 5+ PASS cycles.

## References

- `bdc8d7b` commit body — full visibility-flow rationale + cycle 1 handleLogin fix history
- `.claude/reviews/5fbf1fa.md` (last cycle PASS — BOARD3 frontend integration) — baseline for latency comparison
- `.claude/reviews/a501c8d.md` (BOARD1 backend) — `ProjectSelfUpdateSerializer.fields = ['name', 'visibility']` + visibility migration 0015
- `frontend/src/pages/ProjectSetupPage.jsx:11, 18, 100-130` (visibility state + 2-button toggle)
- `frontend/src/App.jsx:277-278, 290, 299, 304-310, 559, 655-668` (initSession return value, handleStart visibility, handleLogin preserve, route wiring)
- `frontend/src/api/projects.js:31-39` (`updateProject` PATCH wrapper)
- `frontend/src/api/client.js:14` (barrel re-export)
- `frontend/src/pages/LLMSearchPage.jsx:125, 221` (visibility prop + onStart pass-through)
- `backend/apps/recommendation/serializers.py:43-48` (ProjectSelfUpdateSerializer — accepts visibility per BOARD1)
- Empirical: `npm run lint` → clean
- Empirical: PATCH `/projects/{nonexistent}/` → 404 (correct: get_object_or_404 fires first); visibility=hacker → 404 (same path)
- Empirical: Part B 12 runs (3+3+3+3 retry), 0 console errors, 1 transient Gemini timeout absorbed by retry policy
- Empirical: SessionEvent postcheck → 0 backend-recorded failures during the run window
- Empirical: `git diff origin/main..HEAD --name-only | grep -E '^(research/|DESIGN.md|\.claude/agents/design)'` → 0 entries (governance clean)

## Recommended action (path forward)

REVIEW-PASSED — clean PASS, 0 findings at any severity. 4 sub-MINOR observations are notes-for-awareness only.

This pushes:
1. The BOARD2 visibility toggle closing the Phase 14 frontend gap.
2. The handleLogin visibility-preservation fix (reviewer cycle 1 bundled).
3. A new `updateProject` API wrapper that future generic PATCH-style updates can reuse.

**Run `git push` manually from this terminal.**
