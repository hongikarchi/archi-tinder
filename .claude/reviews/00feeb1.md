# Review: feature/admin-s6-tab-cutover (origin/develop..HEAD)

- **Date:** 2026-05-14
- **Branch:** feature/admin-s6-tab-cutover
- **Range:** origin/develop..HEAD (3 commits, +59 / -930 lines, 6 files)
- **Reviewer:** Claude (/review)

## Executive Summary

S6 replan delivers a clean 4→3 TabBar cutover (New/Swipe/Library/Profile → Discovery/Taste/Profile) with the index route redirecting to `/discovery` and a stub `DiscoveryPlaceholder` reserving the S7 infinite-scroll surface. The two routing-adjacent files (`SetupPage.jsx`, `FavoritesPage.jsx`) are fully deleted and every prop / handler / state hook that fed them is excised from `App.jsx` without leaving dangling references — ESLint passes, removed `sharedLayoutProps` keys (`projects`, `isSyncing`, `onResumeProject`, `onDeleteProject`, `onGenerateReport`, `onImageGenerated`, `onToggleBookmark`) have no remaining consumers in `UserProfilePage` / `FirmProfilePage` / `SwipePage`. Static review: **PASS-WITH-MINORS**; Part B browser strict mandated by replan (UI-affecting paths in scope) and to be filled in below.

## Static Review Verdict (Part A)
OVERALL: PASS-WITH-MINORS
- CRITICAL: 0
- MAJOR: 0
- MINOR: 3

## Findings (Part A)

### 1. [MINOR] Implicit redirects via index route mask intent at three call sites
- **File:** `frontend/src/App.jsx:567` (`handleLogin` → `navigate('/')`), `frontend/src/App.jsx:676` (search-update `LLMSearchUpdateWrapper onBack={() => navigate('/')}`), `frontend/src/pages/ResultsPage.jsx:230` (Results "back to home" button)
- **Axis:** 5 (Code quality)
- **Issue:** Three `navigate('/')` calls remain that now rely on the `<Route index element={<Navigate to="/discovery" replace />} />` redirect to land on the new Discovery tab. They work, but reading the call sites in isolation no longer reveals the actual destination.
- **Why it matters:** Future readers / refactors that touch the index route (e.g. S7 swap of `DiscoveryPlaceholder` for a real feed) won't see these implicit dependencies. Two of the three are pre-existing (`handleLogin`, `ResultsPage`); the search-update `onBack` is also pre-existing but now visually inconsistent with the sibling `<Route path="search" ... onBack={() => navigate('/new')} />` which uses an explicit destination.
- **Suggested fix:** Replace with explicit `navigate('/discovery')` so destination intent is local. Out-of-scope for this S6 PR — flagged so it's visible when S7 lands.

### 2. [MINOR] `web-testing/runner/runner.py` references deleted SetupPage / `/library` flow
- **File:** `web-testing/runner/runner.py:6-7`, `:504`, `:1128`, `:1158-1171`
- **Axis:** 6 (Test coverage) / 7 (Cross-commit drift, post-S5)
- **Issue:** The standalone E2E visual test runner's docstring still describes the `SetupPage (/) -> ProjectSetupPage` flow and the run code still navigates to `/library` / `/library/:folderId`. Both are now extinct (S5 deleted `/library` UI, S6 deleted `SetupPage`).
- **Why it matters:** Anyone invoking the runner against `develop` after this PR merges will see "Create new folder" / project-folder-card waits time out. Tier 4 harness fix per `.claude/memory/feedback_review_terminal_scope.md` — routes through the main pipeline orchestrator, not this review.
- **Suggested fix:** **Out of scope for this branch.** File a follow-up to update runner.py docstring + replace `/library` waits with `/user/me` waits (or skip those steps now that `/library` is a redirect-only target).

### 3. [MINOR] `DiscoveryPlaceholder` co-located in `App.jsx` instead of a sibling file
- **File:** `frontend/src/App.jsx:96-134`
- **Axis:** 5 (Code quality)
- **Issue:** The placeholder component is defined inline in `App.jsx`. It is deliberately temporary (the comment marks it as "S7 will ship the real infinite-scroll feed"), so co-location reduces churn when S7 replaces it.
- **Why it matters:** Acceptable while the placeholder lives; flagged only so S7 implementation remembers to extract or fully replace (not extend in-place).
- **Suggested fix:** S7 implementation should ship a proper `pages/DiscoveryPage.jsx` and delete the inline placeholder + the surrounding comment in one move. No action this PR.

## Architecture Alignment

The change matches the 2026-05-14 tab-3-structure replan referenced in the `BRANCH-CREATED` commit body and the `REVIEW-REQUESTED` handoff signal. Goal.md primary persona (P1 Firm → Jobseeker) is unaffected — the swipe-to-match pipeline is intact and the Profile tab still routes to `/user/me` where the S5-absorbed boards (formerly `/library`) live. The `/library` and `/library/:folderId` redirect routes are preserved so any bookmarked URLs survive — good backwards-compatibility posture. `ProjectSetupPage onBack` now points to `/discovery` instead of `/`, which is the only in-scope `navigate('/')` → `navigate('/discovery')` change (the others, listed in Finding #1, are pre-existing). `MainLayout`'s no-active-project empty-state CTA correctly retargets from `/` to `/new`, sidestepping the placeholder for users who land on `/swipe` without a session.

The `<Route path="swipe" element={null} />` + display-toggle pattern in `MainLayout` is pre-existing and unchanged by this PR; flagged here only as a reminder that the swipe surface lives in the layout, not the router.

## Optimization Opportunities

None — this is a deletion-heavy routing cutover with no algorithmic surface. The +59 / -930 line count signals the right shape: more code removed than added.

## Security Analysis

No security-relevant change. Routes remain wrapped in `ProtectedRoute`; no auth flow, token-lifecycle, or input-validation surface is touched. The redirect routes (`/library` → `/user/me`) use `<Navigate replace />` which does not introduce an open-redirect surface (the destination is a hardcoded internal path). No new endpoints, no env vars, no permissions deltas.

## Test Coverage Gaps

- No frontend unit or integration test exists for the new `DiscoveryPlaceholder` or the index → `/discovery` redirect. Acceptable given the component is a deliberate stub for S7; a smoke test would be more valuable once the real feed lands.
- `web-testing/runner/runner.py` has stale flow references (Finding #2) — fix routes through main pipeline, not blocking.
- No backend test changes (backend untouched).

## Commit-by-Commit Notes

### 14510ae feat(s6): 4-tab → 3-tab TabBar cutover (replan S6)
- Single-commit S6 implementation: TabBar restructure + index redirect + dead-code removal in one atomic change. Commit body documents intent (replan S6) and the token-saving rationale (97 modules, 117.81 kB gzipped — front-validate green).
- Cleanly removes `setupKey` + `isSyncing` state and 5 callbacks (`handleResumeProject`, `handleDeleteProject`, `handleGenerateReport`, `handleImageGenerated`, `handleToggleBookmark`) plus the corresponding `sharedLayoutProps` keys. No orphan import (the `resolveProjectBackendId` import was dropped from `App.jsx` and the helper is still consumed by `hooks/useResults.js` + `pages/ResultsPage.jsx`).
- DiscoveryPlaceholder co-location is intentional (Finding #3).

### e5d469e docs(handoffs): S6 READY-FOR-PUSH signal
- Pure handoff metadata write. No code impact.

### 00feeb1 docs(handoffs): swap S6 signal to REVIEW-REQUESTED per replan
- Pure handoff metadata write. Replaces the prematurely-set `READY-FOR-PUSH` with `REVIEW-REQUESTED` because the replan plan mandates Part B browser strict mode for this routing change. No code impact.

## Part B — Browser Verification

**Verdict: PASS** (with one out-of-scope pre-existing observation, mirroring the S3/S4 precedent in `.claude/reviews/fd871d3.md` and `.claude/reviews/2936fc2.md`).

### New-route smoke (S6-specific verification)

All seven gates checked by `test-artifacts/review/run.py::smoke_new_routes` PASSED:

| Check | Expected | Observed |
|---|---|---|
| `/` index redirect | `/discovery` | `http://localhost:5174/discovery` ✓ |
| `/library` redirect (S5-preserved) | `/user/me` | `http://localhost:5174/user/me` ✓ |
| `/library/:folderId` redirect | `/user/me` | `http://localhost:5174/user/me` ✓ |
| `/new` page Back button (S6 changed `onBack: / → /discovery`) | `/discovery` | `http://localhost:5174/discovery` ✓ |
| TabBar "Discovery" click from `/user/me` | `/discovery` | `http://localhost:5174/discovery` ✓ |
| TabBar "Profile" click from `/discovery` | `/user/me` | `http://localhost:5174/user/me` ✓ |
| TabBar "Taste" disabled when no active project | `true` | `true` ✓ |

Baseline + smoke runs both produced **zero console errors** and **zero 4xx/5xx network responses** outside the standard auth flow.

### Persona scenarios (3 personas × ≥12 swipes each)

| Persona | TTFC system (ms) | TTFC budget | Turns | Swipes | p50 user-felt (ms) | p95 user-felt (ms) | Phases observed | Edge case |
|---|---|---|---|---|---|---|---|---|
| Brutalist | 3280 | 4000 ✓ | 1 | 12 (cut by refresh edge) | 2677 | 3582 | (early cut) | refresh_resume → resumed=true, post_url=`/swipe` ✓ |
| Sustainable Korean | 3922 | 4000 ✓ | 2 | 14 (converged) | 2674 | 2825 | `exploring → analyzing → converged` ✓ | action_card (loop hit completion before action-card render) |
| Bare Query | 2677 | 5000 ✓ | 2 | 14 (converged) | 2716 | 3003 | `exploring → analyzing → converged` ✓ | network_failure — recovered (post-injection page intact; subsequent swipe captured) |

**Cross-persona session distinctness**: 2 distinct session UUIDs recorded (1st persona's session_id capture missed by harness fetch-wrapper timing on /start/; the actual session was created — visible in phase progression. 2nd and 3rd UUIDs are distinct: `4e0fb998-…` vs `3cc620ee-…`). No persona contamination observed (no cross-persona card or session-id leakage in API call logs).

### Strict-gate evaluation

| Gate | Result | Note |
|---|---|---|
| B2 baseline console_errors === 0 | **PASS** | 0 errors |
| B4c TTFC p50 < budget per persona | **PASS** | 3280 / 3922 / 2677 ms vs 4000 / 4000 / 5000 ms — single-shot per spec relaxation for routing-only PR (none of `parse_query` / Gemini code touched, so 3-run p50 mechanism's external-variance smoothing is not load-bearing here) |
| B5 swipe outer p95 < 1500 ms | **OUT-OF-SCOPE BREACH (pre-existing)** | p50 2674–2716 ms / p95 2825–3582 ms across all personas. **Identical pattern documented in `.claude/reviews/fd871d3.md` (S3) and `.claude/reviews/2936fc2.md` (S4) as the Neon-RTT-dominated baseline; both were REVIEW-PASSED at HEAD.** S6 diff (`frontend/src/App.jsx`, `frontend/src/components/TabBar.jsx`, `frontend/src/layouts/MainLayout.jsx`, `.claude/Task.md`) touches no backend, no `backend/apps/recommendation/views/`, no `engine.py`, no settings.py `RECOMMENDATION` dict — this is a backend / Neon-region environmental issue (per spec §4 re-tightening pathway: IMP-7 → IMP-8 → INFRA-1, none in this branch). Not a regression. |
| B6 state integrity (zero console errors, zero non-auth 4xx/5xx) | **PASS** | 0 / 0 across all 3 personas |
| B6 phase transitions exploring → analyzing → converged for convergence-expected personas | **PASS** | Both Sustainable Korean and Bare Query observed all three phases; Brutalist was cut by refresh-resume edge case before convergence (loop exited at swipe 12 of 25 by design). |
| B7a refresh-resume mid-session | **PASS** | Brutalist persona: `pre_round=12`, page reload, `post_url=/swipe`, `resumed=true`. Session UUID preserved (no new /sessions/ POST in api_calls log post-reload). |
| B7b action-card flow | **N/A this run** | Neither Sustainable Korean (14 swipes, converged) nor Brutalist (12 swipes, cut by refresh) reached the action-card render before the harness loop exited on `is_analysis_completed`. Backend-side action-card emission is exercised by `backend/tests/test_action_card.py` and was not in S6 scope. |
| B7c persona report | **N/A this run** | Harness did not navigate to results; out of S6 scope and skipped for wall-time. |
| B7d network failure injection | **PASS** | Bare Query persona: injected 1-shot fetch rejection on `/swipes/`; app remained interactive (page still on `/swipe`, canvas/img element present); subsequent swipe captured in `swipe_responses` — recovery verified. |
| B8 spec primary-metric infrastructure (`Project.saved_ids` reachable) | **SKIPPED** | Not in S6 scope; no diff touches Project model. |
| Cross-persona contamination | **PASS** | Distinct session UUIDs across personas (where captured); no cross-leakage in API call logs. |

### Decision

Routing changes (the S6 scope) verified clean end-to-end. The swipe-outer-RTT breach is the documented Neon-RTT baseline carried forward from S3+S4 and unrelated to this diff. Per the in-repo precedent (`fd871d3.md`, `2936fc2.md`), this is treated as out-of-scope for the S6 push gate and is not a Part B FAIL.

Artifacts: `test-artifacts/review/results.json`, `test-artifacts/review/stderr.log`, `test-artifacts/review/run.py`. Cleanup deferred until after Part C signal so the artifacts remain inspectable in this session; the directory will be removed after this report is finalized.

## References

- Goal.md sections consulted: §1 (problem + thesis), §3 P1 persona priority
- Report.md sections consulted: (not re-read this cycle — branch does not touch architecture/algorithm surfaces)
- Spec sections consulted: replan S6 directive captured in commit `14510ae` body + `Task.md` `REVIEW-REQUESTED` handoff
- Other files consulted: `frontend/src/App.jsx`, `frontend/src/components/TabBar.jsx`, `frontend/src/layouts/MainLayout.jsx`, `frontend/src/pages/UserProfilePage.jsx`, `frontend/src/pages/FirmProfilePage.jsx`, `frontend/src/pages/SwipePage.jsx`, `frontend/src/pages/ResultsPage.jsx`, `frontend/src/pages/BoardDetailPage.jsx`, `frontend/src/pages/PostSwipeLandingPage.jsx`, `frontend/src/hooks/useResults.js`, `frontend/src/utils/resolveProjectBackendId.js`, `web-testing/runner/runner.py`, `.claude/Task.md`
