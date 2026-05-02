# Deep Review: main (origin/main..HEAD)

- **Date:** 2026-04-25
- **Branch:** main
- **Range:** origin/main..HEAD  (7 commits, +1442 / -104 lines, 17 files)
- **Reviewer:** Claude (/deep-review)

## Executive Summary

Seven coherent commits covering: (1) Topic 10 convergence signal-integrity fix (the headline work, with end-to-end tests), (2) both MINORs from the prior d12b2d4 review addressed, (3) new spec-based research handoff protocol, (4) frontend profile page mocks, (5) orchestrator `Agent`-tool clarification. The convergence fix is surgical, well-tested, and documents the known dislike-Delta-V asymmetry as accepted per spec. The doc/workflow changes are internally consistent across CLAUDE.md, WORKFLOW.md, Task.md, deep-reviewer.md, and deep-review.md. One MINOR — residual pre-existing textual drift on 3 lines between the subagent and slash-command mirrors (not introduced by this branch, but the branch fixed 1 of 4 drift points so the asymmetric cleanup is worth noting).

## Verdict
OVERALL: **PASS-WITH-MINORS**
- CRITICAL: 0
- MAJOR: 0
- MINOR: 1

## Findings

### 1. [MINOR] Residual textual drift between `deep-reviewer.md` and `deep-review.md` in Steps 1–6
- **File:** `.claude/agents/deep-reviewer.md` vs `.claude/commands/deep-review.md`
- **Axis:** 7 (Cross-commit drift / SYNC NOTICE compliance)
- **Issue:** Commit `2cb3c71` correctly fixed the `6b → 6c` typo that d12b2d4.md Finding 1 flagged — that's 1 drift point closed. But three other pre-existing textual differences inside Steps 1–6 remain:
  - Line 30: subagent says "emit exactly"; slash command says "abort with exactly".
  - Line 103: subagent says "Reviewer: Claude (deep-reviewer)"; slash command says "Reviewer: Claude (/deep-review)". This one is intentional (author attribution reflects the invocation path).
  - Line 148: subagent heading "Step 5 — Emit summary"; slash heading "Step 5 — Print a one-line summary".
  The SYNC NOTICE banner at the top of both files says "Any change to Steps 1–6 or Rules below MUST be applied to BOTH files". The policy is stricter than what the files actually do.
- **Why it matters:** Low-impact — the differences are wording-level and do not change semantics. But the SYNC NOTICE is a passive enforcement mechanism, and a maintainer running `diff` on the two files after the `2cb3c71` typo fix would still see 3 differences and wonder which is authoritative. If the intent is "Step 5 text is author-attributed per invocation path, other wording variance is permissible", that exception should be called out in the SYNC NOTICE itself; otherwise the 3 remaining lines should be reconciled.
- **Suggested fix:** Either (a) reconcile the 3 lines — standardize on "abort with exactly" / keep the Reviewer attribution as-is / standardize one heading; OR (b) amend the SYNC NOTICE to declare: "frontmatter + intro + reviewer-attribution line may differ per invocation path; Steps 1–6 body text must match verbatim". Option (b) is lower-friction.

## Architecture Alignment

Excellent. Each commit targets exactly the scope it claims:

- **`3ee9c77` Convergence fix (Topic 10 Option A)** — bugfix in `backend/apps/recommendation/views.py` SwipeView. Two unconditional structural fixes:
  - Bug 1: on exploring → analyzing transition (line 573-583), clear `convergence_history` and `previous_pref_vector`. Prevents the first analyzing Delta-V from being a cross-metric `||K-Means centroid − exploring pref_vector||` distance. Mirrors the reset already present in the action-card "Reset and keep going" path (views.py:437-446) — consistency is load-bearing.
  - Bug 2: remove `action == 'like'` gate from the analyzing Delta-V append. `convergence_window = 3` now counts rounds, not likes. Comment at views.py:538-544 transparently documents the accepted side effect (dislike Delta-V < like Delta-V biases the moving average downward on dislike-heavy sequences, acceptable per `research/spec/requirements.md` Section 11 Tier A Topic 10 Option A).
  - Ordering is correct: Step 5 convergence calc → Step 5a buffer merge → Step 6 phase transition+reset. The reset fires AFTER the last exploring-phase Delta-V append, so the transition correctly clears whatever the exploring branch just wrote.

- **`2cb3c71` Address 2 MINORs from d12b2d4.md** — fixes the canonical `.claude/agents/deep-reviewer.md:62` 6b→6c typo (SYNC NOTICE compliant with the slash-command mirror, which already had 6c); adds push-fail-then-rebase discipline note to all three referenced files (CLAUDE.md Code Review section, deep-reviewer.md Step 6d, deep-review.md Step 6d).

- **`c1c8ad6` Extend REVIEW-PASSED signal for PASS-WITH-MINORS** — signal format change propagated across 3 referenced files:
  - Task.md Handoffs header (the vocabulary definition) — inlines `<K> MINOR noted (see .claude/reviews/latest.md)`.
  - deep-reviewer.md Step 6d — two-variant conditional append (K=0 vs K>0).
  - deep-review.md Step 6d — same two-variant conditional (mirror).
  - CLAUDE.md Code Review section — documents the new variant + semantics (non-blocking for push by definition).
  Coherent; no drift between the spec and the agent definitions.

- **`c87ff07` Spec-based research handoff adoption** — `.claude/Task.md ## Research Ready` section migrated from 12 per-topic `[RESEARCH-READY]` markers to a single persistent `[SPEC-READY]` pointer + `SPEC-UPDATED` in Handoffs on version bumps. `.claude/WORKFLOW.md` rewritten research row + new "Research ↔ Main: Spec-based Coordination" subsection with incremental re-read policy. `research/spec/requirements.md` v1.0 (510 lines) + `research/spec/research-priority-rebaselined.md` (140 lines) are the binding + non-binding companions. The authority boundary is explicit: requirements.md is binding, rebaselined.md is research-terminal recommendation only.

- **`8095ee7` Profile page mocks** — `FirmProfilePage.jsx` + `UserProfilePage.jsx` are scaffolds with `MOCK_*` consts and `// TODO(claude):` + `// TODO: Replace with API call` markers. Routes wired in App.jsx (`user/me`, `office/:officeId`). TabBar gets a 4th "Profile" tab + `getActiveTab` handles `/user` paths. MainLayout hides the header theme+logout controls on `/user/*` and `/office/*` paths (profile pages have their own sticky header). The `isProfile` variable is computed but only used inside the header-controls display conditional — consumed in one place. `MainLayout`'s outlet visibility rule flipped from `isHome ? 'block' : 'none'` to `(!isSwipe && !isLibrary) ? 'block' : 'none'` — necessary for `/user/*` and `/office/*` to render via Outlet, and doesn't broaden to unknown paths because App.jsx:620 has a catch-all redirect to `/`.

- **`e938fae` Mark CONV1 resolved** — Task.md ## Resolved gets new "Sprint 0 Topic 10" section with CONV1 checklist + commit reference; Report.md gets new feature-list bullet + updated `Last Updated (Claude)` entry (Gemini section preserved per CLAUDE.md rule). The engine.py/views.py/test_sessions.py file-description rows in Report.md are updated to reflect the new capability ("convergence signal integrity (Topic 10 Option A)").

- **`ded38be` Orchestrator `Agent`-tool clarification** — new "Spawning subagents (tool reference)" section at the top of `.claude/agents/orchestrator.md` that explicitly names `Agent` (with `subagent_type`) as the spawner, lists the naming pitfalls (`Task` is obsolete; `TaskCreate/Update/List` are todo tools, not spawners), and adds a rule: "If `Agent` itself returns an error (not 'tool not found'), report the error to the user and stop — do NOT bypass delegation by writing source code yourself." Also tightens the Rules-section invariant: "Never write source code yourself. Always delegate to back-maker or front-maker via the `Agent` tool. If `Agent` appears unavailable, STOP and report the blockage to the user — do not work around it by editing files directly."

All 7 commits align with the stated scope and don't over-reach. Cross-commit, no contradictions.

## Optimization Opportunities

- **Unconditional K-Means recompute on analyzing-phase dislikes** (views.py:545-548): the Bug 2 fix intentionally computes centroids every analyzing swipe, including dislikes. This is correct per spec — centroids shift slightly due to recency-weight drift — but it's an extra `compute_taste_centroids` call on every dislike. At session-typical scale (≤20 likes), each call is single-digit ms; total hot-path cost is negligible. No action needed. Noted for completeness.
- **Test mock deterministic preference vector** (test_sessions.py:77-80): `_mock_update_pref` returns the same `np.random.RandomState(42).randn(384)` regardless of input. Fine for convergence structural tests, but any future test wanting to verify preference drift would need a richer mock. Not in scope.

## Security Analysis

- **No new endpoints.** Convergence fix is a pure internal state update; no request surface changed.
- **No new authorization boundaries.** `_get_profile()`, `select_for_update()`, and idempotency-key checks are unchanged.
- **Mock profile pages render client-side only** with `MOCK_*` constants embedded in the JSX bundle. No backend endpoint handles `GET /api/v1/users/<id>/` or `GET /api/v1/offices/<id>/` yet (correctly — the pages are scaffolds). No sensitive data exposed.
- **`pathname.startsWith('/office')` check** in MainLayout.jsx:30 — used only for UI display hiding. Not an auth check.
- **`/user/me` route does not enforce auth beyond `ProtectedRoute`** — consistent with the rest of the app. ProtectedRoute is wrapping the outer route (App.jsx:567-570), so `/user/me` inherits auth-gating correctly.
- **Secret exposure:** reviewed the diff — no accidentally-committed credentials.
- **Research terminal authority boundary** (WORKFLOW.md § Research Terminal): hard rule that research never writes backend/frontend/Claude settings/agents/etc. The spec governance section (requirements.md §12) enumerates the same prohibition. Reinforces defense-in-depth for the role separation.

No vulnerabilities introduced.

## Test Coverage Gaps

- **New tests cover the branch's main work well:**
  - `TestConvergenceSignalIntegrity.test_phase_transition_resets_convergence_state` — drives 3 likes, asserts post-transition both `convergence_history == []` and `previous_pref_vector == []`.
  - `TestConvergenceSignalIntegrity.test_analyzing_dislike_appends_delta_v` — seeds an analyzing-phase session directly with non-empty `like_vectors` + valid `previous_pref_vector`, posts one dislike, asserts exactly 1 new Delta-V entry (`[0.05]` from the mock). Pre-fix this test would fail (history would stay `[]`).
  - `TestClientBufferMerge` — verifies buffer merge, invalid-shape ignore, action-card marker filter.
  - `TestSessionStateResume` — resume endpoint returns current state + handles 404 + handles completed session.
- **Gap (low-priority, out of scope):** no unit test for the pool-exhaustion-mid-analyzing path (`if not remaining and session.phase not in ('converged', 'completed'): session.phase = 'converged'`, views.py:592-595). Exercised implicitly when integration tests hit pool depletion, but a direct test would harden the guard.
- **No runtime tests for doc/workflow changes** — expected; these are prompt artifacts.

## Commit-by-Commit Notes

### `2cb3c71` fix: address 2 MINOR findings from d12b2d4 review
- **Good**: both MINORs from `.claude/reviews/d12b2d4.md` closed in one commit. Typo fix is one-char; push-fail-rebase note is a defensive doc addition in all 3 referenced files.
- No new concerns.

### `c1c8ad6` feat: extend REVIEW-PASSED signal to inline MINOR count
- **Good**: signal format propagated consistently across 3 files. Two-variant conditional at Step 6d is clean. Rationale ("MINORs are non-blocking by definition — if they were blocking they would be MAJOR or CRITICAL and the verdict would be FAIL") makes the design explicit.
- **Good**: doesn't break prior PASS semantics — the K=0 branch emits the same line as before.

### `c87ff07` docs: adopt spec-based research handoff + publish search spec v1.0
- **Good**: authority boundary explicit in WORKFLOW.md ("Research terminal does not commit"), Task.md Handoffs vocabulary updated with `SPEC-UPDATED` signal type, requirements.md §12 Governance enumerates the role separation as a hard rule.
- **Good**: clean migration from 12 per-topic markers to 1 persistent `[SPEC-READY]` pointer + `SPEC-UPDATED` version-bump signals. The rebaselined.md companion is explicitly non-binding, preserving main-terminal autonomy over sprint planning.
- **Observation**: requirements.md is 510 lines; re-read on every session would be heavy. WORKFLOW.md correctly prescribes "incremental re-read" — only affected sections on `SPEC-UPDATED`. Load policy is sound.

### `8095ee7` feat: wire firm/user profile page routes with mock data
- **Good**: explicit `MOCK_*` + `TODO(claude):` + `// TODO: Replace with API call` markers. Clear scaffold vs real-code signal.
- **Observation (forward-compat, not a finding)**: `/user/me` is a static path — when real API wires in, the route will likely become `user/:userId` with `me` either redirected or resolved by the current session user. `UserProfilePage.jsx:45` has `isMe = true` hardcoded with a `TODO(claude)` to compare `profile user_id === active session user_id`.
- **Observation (forward-compat, not a finding)**: `MainLayout.jsx:30` hides the header theme+logout controls on `/office/*` but FirmProfilePage has no built-in logout. Currently no TabBar path links to `/office/*`, so not reachable in normal flow, but when real linking lands, users on `/office/:officeId` will need an exit affordance (TabBar still works).

### `3ee9c77` fix: convergence detection signal-integrity bugs (Topic 10 Option A)
- **Good**: surgical scope — exactly the 2 bug sites + 1 new test class. No refactors, no opportunistic cleanup elsewhere.
- **Good**: comment at views.py:538-544 documents the accepted dislike-Delta-V bias side effect transparently, with explicit spec pointer (`research/spec/requirements.md` Section 11 Tier A Topic 10 Option A).
- **Good**: mirrors the existing reset pattern in the action-card "Reset and keep going" path (views.py:437-446). Consistency with prior code is load-bearing — both phase-reset sites now clear the same two fields.
- **Good**: tests include pre-fix-behavior explanatory docstrings — a future regressor would read them and understand what's being prevented.

### `e938fae` docs: mark CONV1 resolved + update Report.md for Topic 10 fix
- **Good**: Last Updated (Claude) section updated; Last Updated (Gemini) preserved per CLAUDE.md rule.
- **Observation (not a finding)**: the `Commits: 3ee9c77` line in Last Updated (Claude) highlights only the headline work. The push candidate includes 7 commits, but the framing is accurate for the featured effort.

### `ded38be` docs: make orchestrator subagent-spawn tool name explicit
- **Good**: defensive documentation. Explicit `Agent`-tool reference with subagent_type examples closes a naming-confusion failure mode (if the orchestrator searches for a non-existent `Task` tool, it should not fall back to writing code itself — the new rule says STOP and report).
- **Good**: tightens an existing Rules-section invariant without introducing new rules.

## References

- `.claude/Goal.md`: Vision + Acceptance Criteria (grounding)
- `.claude/Report.md`: Backend Structure (engine.py / views.py / tests/test_sessions.py rows), Feature Status (new Convergence bullet), Last Updated (Claude)
- `.claude/WORKFLOW.md`: Agent Roster + Research ↔ Main spec-based coordination subsection (new)
- `.claude/Task.md`: Handoffs header (signal vocabulary including SPEC-UPDATED), Research Ready section (new [SPEC-READY] scheme), Resolved (CONV1)
- `.claude/agents/deep-reviewer.md`: full read — canonical Step 6d now two-variant
- `.claude/commands/deep-review.md`: full read — slash mirror, pre-existing 3-line drift noted
- `.claude/agents/orchestrator.md`: full read — new Agent-tool reference section + tightened Rule
- `CLAUDE.md`: Code Review section (PASS-WITH-MINORS + push-fail-rebase discipline)
- `research/spec/requirements.md`: full read — v1.0 binding spec; §11 Section consolidated actionable directives per topic
- `research/spec/research-priority-rebaselined.md`: full read — non-binding roadmap companion
- `backend/apps/recommendation/views.py`: full read (904 lines) — focused on SwipeView convergence path
- `backend/apps/recommendation/engine.py`: `compute_taste_centroids`, `compute_convergence`, `check_convergence` signatures verified at lines 451, 576, 590
- `backend/apps/recommendation/models.py`: `AnalysisSession.PHASE_CHOICES` + new `previous_pref_vector` field verified
- `backend/tests/test_sessions.py`: full read — 13+ tests including 2 new `TestConvergenceSignalIntegrity`
- `frontend/src/App.jsx`: full read — routes for `user/me` + `office/:officeId` verified
- `frontend/src/pages/FirmProfilePage.jsx`: full read — MOCK_OFFICE scaffold
- `frontend/src/pages/UserProfilePage.jsx`: full read — MOCK_USER scaffold, isMe=true + TODO
- `frontend/src/layouts/MainLayout.jsx`: full read — Outlet visibility rule change + header hiding on /user//office
- `frontend/src/components/TabBar.jsx`: full read — 4th Profile tab
- `frontend/src/pages/LoginPage.jsx`: diff only — removed page-level theme toggle, whitespace cleanup (LoginPage is outside MainLayout so theme toggle isn't available there now — acceptable for a pre-auth screen)
- `git log origin/main..HEAD`: 7 commits, verified via `git log --format` + `git diff --stat`
- Prior reviews: `.claude/reviews/d12b2d4.md` (both its MINORs closed by `2cb3c71`)

---

## Push Recommendation

Safe to push. The one MINOR is pre-existing drift that the branch partially cleaned (fixed 1 of 4), and the residual 3 differences are wording-level, not semantic. Proceeding to Step 6 drift checks — if HEAD and `origin/main` are both unchanged from Step 1 captures (`ded38be4a472ca38517f9790d77b63af28fc0a33` and `d12b2d4aadae5cea8de5cadfbf2c536b708582b2`), I'll emit `REVIEW-PASSED: ded38be — drift checks passed, 1 MINOR noted (see .claude/reviews/latest.md); run 'git push' manually from this terminal`.
