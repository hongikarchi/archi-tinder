# Review: main (origin/main..HEAD)

- **Date:** 2026-05-02
- **Branch:** main
- **Range:** origin/main..HEAD  (7 commits, +9043 / -90 lines, 77 files)
- **Reviewer:** Claude (/review)

## Executive Summary

7-commit range: 3 carryover from prior FAIL cycle (`d735666` PROF3 frontend / `3894bbe` Image hosting Path C backend / `c605f0c` Image hosting Path C frontend) + 4 new commits — `15d44a9` SOC1 user-to-user follow backend, `a1f5371` SOC1 follow frontend wiring, `ba757eb` SOC2 Project reaction backend, `36ecbf3` gitignore relaxation + collaboration prep. **The prior CRITICAL persists and still blocks**: dev DB still has 23 columns of `architecture_vectors` (no divisare cols); `engine.py`'s 7 modified SELECTs still 500 with `column "cover_image_url_divisare" does not exist`; `GET /api/v1/users/2/` and `POST /api/v1/images/batch/` empirically reproduced as broken. Per `.claude/commands/review.md` Step A6, Part B is skipped — would deterministically fail on the same 500 across the swipe pipeline. The 4 new commits ARE individually well-engineered: SOC1 has DB-level self-follow CheckConstraint + signal-based counter caches + race-safe filter().delete() + throttle (60/min); SOC2 mirrors SOC1's pattern with the *correct* visibility-gate asymmetry (POST gates private+non-owner; DELETE has no gate so users can retract reactions on public→private flip cleanly); SOC1 frontend has numeric ID guard + optimistic update + rollback + race guard; gitignore changes are surgical and the supplemental scan confirms 0 secrets in newly-tracked files. 546 passed + 1 skipped (vs prior 499 → +47 from 24 follow + 23 reaction tests). All 3 social migrations applied and `apps/social/migrations/__init__.py` is now tracked. **Verdict: FAIL on the carryover CRITICAL alone**; the 4 new commits would be a clean PASS in isolation.

## Static Review Verdict (Part A)
OVERALL: **FAIL**
- CRITICAL: 1 (carryover, persists)
- MAJOR: 2 (carryover from prior cycle; both still apply)
- MINOR: 2 (1 carryover, 1 new)

## Findings (Part A)

### 1. [CRITICAL] **CARRYOVER & UNCHANGED** — engine SQL references columns absent from dev DB; entire recommendation pipeline 500
- **Status:** No remediation since `c605f0c.md`. Local dev DB still has 23 columns. Re-verified now:
  ```
  total_cols: 23
  divisare_cols: []                                       # cover_image_url_divisare, divisare_gallery_urls absent
  GET /api/v1/users/2/        → 500 ProgrammingError
  POST /api/v1/images/batch/  → 500 ProgrammingError
  ```
- **File:** `backend/apps/recommendation/engine.py:148-150, 199, 247-249, 257-259, 277-279, 296-298, 1417-1418` (7 SELECTs)
- **Axis:** 2 (Correctness) + 1 (Architecture alignment)
- **Why this matters now (and why FAIL persists despite 4 new commits)**: SOC1's `is_following` injection lives on `UserProfileDetailView` (`GET /users/{id}/`), which calls `_build_boards_field` → `engine.get_buildings_by_ids` → broken SELECT. Verified empirically just now: `GET /users/2/` still 500s. So **even though SOC1 endpoints work in isolation**:
  - `POST /users/9999/follow/` → 404 ✓
  - `POST /users/2/follow/` → 400 self-follow ✓
  - `GET  /users/2/followers/` → 200 ✓
  - `GET  /users/2/` → **500** ✗ (SOC1 frontend can't read `is_following` here)
  …the entire SOC1 frontend round-trip is blocked in dev because the page-load fetch crashes before `data.is_following` is read. Same pattern would block SOC2's `is_reacted` injection on `ProjectDetailView` (which is healthy because `ProjectSerializer` doesn't go through engine SELECT).
- **Production status (per `research/infra/03-make-db-snapshot.md:26-41`)**: divisare columns are documented as "Additional columns NOT in make_web CLAUDE.md (already in production)" — production Neon SHOULD have them and SHOULD work. Verification cannot be performed from this terminal.
- **Suggested remediation** (same 4 paths from `c605f0c.md`):
  1. Verify production schema directly (`\d architecture_vectors` against Neon).
  2. Sync local dev DB to current Make DB snapshot.
  3. Make SELECTs forward-compatible via `information_schema.columns` probe at boot.
  4. Defer the column adds and ship telemetry-only.
- **Why I'm not silently downgrading** — the empirical local 500 is dispositive for any environment whose `architecture_vectors` lacks the divisare columns. The /review push gate exists to catch exactly this kind of environment-coordination break; production-might-work is not the same as production-does-work.

### 2. [MAJOR] **CARRYOVER** — No integration test coverage for the modified SQL paths (still applies)
Same as `c605f0c.md` Finding #2. The 13 `_row_to_card` tests use synthetic dict input; the 25 new follow + reaction tests exercise apps/social, not engine SQL. A `@pytest.mark.django_db def test_get_buildings_by_ids_returns_card_shape(): cards = engine.get_buildings_by_ids(["B00001"]); assert "image_url" in cards[0]` would have caught CRITICAL #1 pre-commit. **No new regression on this axis** — the gap simply hasn't been closed.

### 3. [MAJOR] **CARRYOVER** — Dev / prod schema drift not asserted anywhere (still applies)
Same as `c605f0c.md` Finding #3. CLAUDE.md's `## Database` block describes the canonical 33-column schema; dev DB has 23. No `manage.py check_canonical_schema` or pytest startup assertion exists. **`36ecbf3` made env.example complete** (HF_TOKEN / STAGE_DECOUPLE_ENABLED / VITE_GEMINI_API_KEY) — that's collaboration onboarding, not schema drift. The schema-sentinel gap remains.

### 4. [MINOR] **CARRYOVER** — Docstring in `_row_to_card` ("drawing_start == 0 == len(gallery)" should be "drawing_start == len(gallery)")
Same as `c605f0c.md` Finding #4. Cosmetic; logic correct.

### 5. [MINOR] **NEW** — Test count off-by-one in `ba757eb` commit body
- **File:** Commit body `ba757eb`
- **Axis:** 5 (Code quality / commit hygiene)
- **Issue:** Body claims "Tests: 545 passed, 1 skipped, 0 failed (23 new reaction tests + existing)". Actual on this branch is **546 passed + 1 skipped** (per `python3 -m pytest -q` just now). One test added between authoring and submission (likely a follow-up assertion in a related file). Cosmetic.
- **Suggested fix:** None required. Note it for future commit hygiene if the user wants to maintain bookkeeping discipline; the prior PROF1 / PROF2 / BOARD1 commit bodies all had similar ±1 drift.

## Architecture Alignment

The 4 new commits are well-grounded and demonstrate consistent design discipline:

- **`15d44a9` SOC1 (Follow)** — `research/spec/phase13-social-discovery.md` §3.1 confirmed direction (asymmetric User→User follow). Office follow correctly deferred to Phase 15 dialogue gate (§3.2 open dimension). The `apps/social/` Django app is the right home — independent of `accounts/` (whose serializers stay clean of social fields) and `recommendation/` (whose Project ownership stays clean).

- **`a1f5371` SOC1 frontend** — wires UserProfilePage to live `POST/DELETE /users/{id}/follow/` while leaving FirmProfilePage's Office follow as TODO marker per spec dialog gate. Designer-territory JSX preserved (no MOCK_USER restructure).

- **`ba757eb` SOC2 (Reaction)** — same architectural pattern as SOC1 (signal-based counter cache via `Greatest(F('reaction_count') - 1, 0)` floor, `unique_together` on (user, project), `filter().delete()` race-safe pattern, scoped throttle). Spec citation: `research/spec/phase13-social-discovery.md` §3.1 — single ❤️ tier, Project target, Behance pattern. Other targets (Office/Building/User) and 2-tier deferred to dialogue gate.

- **`36ecbf3` gitignore relaxation** — surgical, well-justified. Whitelisting `.claude/plans/` + `.claude/reviews/` makes /review reports + plan-mode artifacts available as PR context. Tracking `backend/tools/optimization_results.json` + `backend/_validation_*.md` shares hyperparameter decision history without committing real secrets. The fix for missing `apps/social/migrations/__init__.py` is critical for fresh-clone deployability — without it, Django silently can't import the migrations package on Python ≥3.3 (PEP 420 namespace packages might let Python "find" the package, but Django's migration loader specifically scans `__init__.py`-bearing packages). **Verified `__init__.py` is now tracked at HEAD** (`git ls-tree -r HEAD -- backend/apps/social/migrations/__init__.py` → blob `e69de29` = empty file).

The CRITICAL is structural-environment, not architectural. The architecture is sound across all 7 commits; the failure is the dev/prod schema-coordination gap.

## Optimization Opportunities

- **`UserProfileDetailView.get` is_following lookup is a single-shot `EXISTS` query per request** (`Follow.objects.filter(...).exists()`). Cheap. If a future `/users/me/feed/` view ever needs is_following per row in a paginated list, this would need a `Prefetch` or `annotate(is_following=Exists(...))`. Not a current concern.
- **`FollowersListView` / `FollowingListView` use `.order_by('-following_set__created_at')`** which generates a JOIN-with-DESC sort. Correct, indexed (Index on (followee, -created_at) covers the hot path), but worth noting that for a user with millions of followers the JOIN sort would prefer a covering index. Not a current concern.
- **Tests for SOC1 + SOC2 add 47 new entries** (24 follow + 23 reaction). Solid coverage; no gap I can see.
- **`backend/apps/social/serializers.py` is mostly a re-export** — 8 lines for `from apps.accounts.serializers import UserMiniSerializer`. Could be removed once social-specific serializers exist; for now the `noqa: F401` re-export is documentation that someone made a deliberate choice.

## Security Analysis

The 4 new commits introduce 6 new endpoints + 2 model classes. All security-relevant aspects look hardened:

**SOC1 / Follow (`15d44a9`)**
- `POST/DELETE /users/{id}/follow/` — `IsAuthenticated` + `FollowWriteThrottle (scope=follow_write, 60/min)`. Mass-follow bot defense via DRF user-rate throttle.
- Self-follow defense in depth: (a) view-layer 400 with friendly message; (b) **DB-level CheckConstraint** `social_follow_no_self_follow` via migration 0002. Even a direct `Follow.objects.create(follower=u, followee=u)` from shell raises IntegrityError. The redundancy is correct — view-layer check is for UX (clean 400 instead of 500); DB-level is the actual security boundary.
- DELETE race condition: `.filter().delete()` returns deleted_count instead of `.get(); .delete()` (which would have a TOCTOU window). Counter decrement is signal-based per deleted instance — race-safe.
- `Greatest(F(...) - 1, 0)` underflow floor prevents negative counters.
- CASCADE coverage: `on_delete=CASCADE` + `post_delete` signal means deleting a UserProfile correctly drops all Follow rows AND decrements all surviving counter caches. Tested by commit body's "CASCADE delete left counter caches stale" cycle-1 fix — addressed.
- `GET /users/{id}/followers/` and `following/` are AllowAny + paginated (page_size capped 50). No CSRF concern (read-only); information disclosure risk is minimal (the user→user graph is intentionally public per Behance / Instagram pattern).

**SOC2 / Reaction (`ba757eb`)**
- `POST /projects/{project_id}/react/` — gates `project.visibility != 'public' AND project.user_id != requester.pk` → 403. Correct: blocks new reactions on private projects from non-owners.
- `DELETE /projects/{project_id}/react/` — **no visibility gate**. The commit body's reasoning is correct: a user must always have sovereignty over their own reaction row, even after the owner flips public→private. Otherwise reactions become orphaned permanently. The post→flip→delete flow is tested empirically per commit body.
- 404 if not reacted (DELETE returns `{'detail': 'Not reacted.'}` with 404). 403 only fires on POST attempts against private+non-owner. The asymmetry is documented inline.
- `ReactionWriteThrottle (scope=reaction_write, 60/min)` mirrors FollowWriteThrottle. Bulk-reaction bot defense.

**SOC1 frontend (`a1f5371`)**
- `effectiveUserId` numeric guard: `/^\d+$/.test(String(rawUserId || ''))` → null if non-numeric. Defense-in-depth: backend `<int:user_id>` route already 404s on non-numeric, but rejecting at the frontend prevents path-traversal-shaped values from ever hitting `fetch()`. Subtle but correct.
- `isMe` self-follow guard: `isMe || isFollowingPending` short-circuits handler. Plus the button is hidden when isMe. Triple-redundant: button hidden / handler short-circuits / backend 400 / DB CheckConstraint.
- Race guard: `isFollowingPending` prevents rapid double-click double-toggle. Button disabled while in flight. Optimistic update + rollback on error.
- Server-authoritative count: `res?.follower_count != null && setFollowerCount(res.follower_count)` — when present, server count wins over the optimistic local update.
- Client-side underflow guard: `Math.max(0, c + (wasFollowing ? -1 : 1))` — even if the optimistic math goes wrong, count doesn't go negative.

**`36ecbf3` gitignore changes**
- Newly-tracked: `.claude/plans/` (1 file), `.claude/reviews/` (32 files), `backend/tools/optimization_results.json`, `backend/_validation_imp5.md`, `backend/_validation_imp6.md`. Independent secret scan: `grep -rEi "(=\s*[A-Za-z0-9_-]{20,}|sk-...|hf_...|AIza...|glpat-...)"` returns 0 matches. Long hex strings present are git SHAs, not secrets. ✓
- Confirmed kept ignored: `.env`, `.env.*` (real secrets), `node_modules/`, `dist/`, `__pycache__/`, `*.sqlite3`, etc.
- `.env.example` adds placeholder values only — `your_huggingface_api_token`, etc. No real secrets exposed.

No new auth surface, no token handling change, no permissions broadening. Clean security verdict on the 4 new commits.

## Test Coverage Gaps

- **Unchanged from prior cycle**: SQL paths in 7 modified `engine.py` functions remain untested at the integration level. CRITICAL #1 / MAJOR #2 still apply.
- **SOC1 + SOC2 coverage**: the 47 new tests look thorough — `test_follow.py` covers create/idempotent/self-follow/non-existent-user/throttle/CASCADE/counter-drift scenarios; `test_reaction.py` covers same patterns + the public→private→unreact regression test specifically.
- **SOC1 frontend has no JSX-level tests** — same as prior frontend commits. Acceptable per project convention.

## Cross-Commit Drift

- **The 4 new commits stack cleanly**: 15d44a9 backend → a1f5371 frontend (SOC1) ; ba757eb backend (SOC2 follows the same pattern) ; 36ecbf3 collaboration / cleanup (whitelist plans + reviews + the missing __init__.py fix that 15d44a9 silently lacked).
- **No accumulated cleanup debt** — each commit lands its own fix-loop cycle and explicit deferred-marker decisions (Office follow → §3.2 dialogue, articles[] → Phase 18, is_following on lists → handled per-request not pre-fetched).
- **Carryover risk**: the longer the prior CRITICAL is deferred, the more downstream PRs (PROF3, BOARD1, SOC1, SOC2, future frontend integrations) accumulate behind it without any of them being able to be E2E-verified locally. Either fix the schema gap NOW or accept that all subsequent /review cycles will be Part-B-impossible until it's resolved.

## Commit-by-Commit Notes

### `d735666` PROF3 frontend integration (carryover)
Already reviewed clean in `c605f0c.md`. No code change since.

### `3894bbe` Image hosting Path C backend 1/2 (carryover)
Already reviewed in `c605f0c.md` — clean code, but introduces the SQL changes that the dev DB doesn't support. CRITICAL persists.

### `c605f0c` Image hosting Path C frontend 2/2 (carryover)
Already reviewed clean in `c605f0c.md`. No code change since.

### `15d44a9` feat: SOC1 user-to-user follow/unfollow backend (Phase 15)
- **Good**: 6 cycle-1 hardening fixes from reviewer + security FAIL all addressed:
  - DB-level CheckConstraint for self-follow (migration 0002).
  - Signal-based counter sync handles CASCADE deletes.
  - DELETE race fixed via `filter().delete()` + deleted_count return.
  - FollowWriteThrottle (60/min) wired.
  - Greatest underflow floor on counter decrement.
  - Doc + test docstring stray-reference cleanup.
- **Good**: signals as single source of truth — `_follow_post_save` increments only when `created=True` (no double-increment on update); `_follow_post_delete` always decrements (covers CASCADE).
- **Good**: `unique_together = [('follower', 'followee')]` + DB CheckConstraint + view-layer get_or_create + view-layer self-follow check = four layers of defense against duplicate / self-follow.
- **Good**: `select_related('user')` on followers/following list views prevents N+1 on the per-row UserMiniSerializer call.
- **Sub-MINOR**: 0002 migration's auto-generated name `0002_rename_social_foll_followee_idx_social_foll_followe_0eabb0_idx_and_more` is Django's auto-naming for "rename + add constraint" combined operations — works but ugly. Could rename to `0002_self_follow_constraint`. Cosmetic.

### `a1f5371` feat: SOC1 frontend follow/unfollow wiring
- **Good**: numeric ID guard (`/^\d+$/.test(...)`) added in cycle-1 security fix.
- **Good**: optimistic update + rollback pattern is canonical.
- **Good**: race guard via `isFollowingPending` + disabled button + `cursor: not-allowed` style transition.
- **Good**: server-authoritative count override when present (`res?.follower_count != null`).
- **Good**: client-side `Math.max(0, ...)` underflow guard.

### `ba757eb` feat: SOC2 Project reaction backend (Phase 15)
- **Good**: cycle-1 fix corrected the visibility-gate asymmetry — POST gates private+non-owner with 403; DELETE has no gate. This is the right fix because the alternative (gating DELETE too) creates orphaned reactions when a project owner flips public→private. Test inversion `test_unreact_private_non_owner_returns_403 → test_react_then_flip_private_then_unreact_succeeds` documents the change cleanly.
- **Good**: Reaction model mirrors Follow's pattern exactly — same `unique_together`, same `Greatest` floor, same signal-based counter, same throttle. Architectural consistency.
- **Good**: 23 new tests including the public→private→unreact regression case.

### `36ecbf3` chore: gitignore relaxation + env.example completeness
- **Good**: `.gitignore` change is surgical — only relaxes 4 patterns + 2 whitelists. Real secrets stay ignored.
- **Good**: env.example completeness fixes "code doesn't run after pull" reports — HF_TOKEN, STAGE_DECOUPLE_ENABLED, VITE_GEMINI_API_KEY all needed for the IMP-6 + Gemini paths.
- **Critical fix (good)**: `backend/apps/social/migrations/__init__.py` was missing in `15d44a9` — fresh clones couldn't apply the social migrations because Python couldn't import the migrations package. This commit fixes that with the empty file (verified tracked at HEAD as blob `e69de29`).
- **Good**: independent secret scan returns 0 hits on newly-tracked files. Commit body's claim is accurate.
- **Sub-MINOR (Finding #5)**: `ba757eb` commit body claims 545 passed; actual is 546. Off-by-one bookkeeping; not blocking.

## Observations (sub-MINOR, not flagged as findings)

1. **0002 migration auto-name** is unwieldy. Cosmetic. Future migrations might benefit from explicit naming via `--name self_follow_constraint`.
2. **Test count drift in commit body** (Finding #5) — pattern continues across PROF1/PROF2/BOARD1/SOC2. Not blocking.
3. **`apps/social/serializers.py` is just a re-export** of `UserMiniSerializer`. Minimal but acceptable; serves as a "we're not creating a parallel serializer for social" marker.
4. **Brief check of `frontend/src/api/client.js`**: SOC1 wrappers `followUser` / `unfollowUser` are clean. `followUser` returns the response (caller uses follower_count); `unfollowUser` doesn't (DELETE returns 204). Asymmetric by design.
5. **`is_following` is computed per-request** via `Follow.objects.filter(...).exists()`. Cheap on indexed queries; would benefit from `Exists`/`annotate` if extended to list views in future.

## Part B — Browser Verification

**Skipped — Part A FAIL halts the pipeline before browser test** (per `.claude/commands/review.md` Step A6: CRITICAL ≥1 → skip Part B and Part C drift). The browser test would deterministically FAIL on the same 500 across the entire swipe pipeline (`POST /api/v1/analysis/sessions/`, `POST /api/v1/swipe/`, `POST /api/v1/images/batch/`, `GET /api/v1/users/{id}/`) — all share the broken SELECT path through `engine.get_*`.

This is the **second consecutive cycle** Part B has been skipped for this reason. If the user is iterating on Phase 13 / Phase 15 frontend without resolving the schema gap, future /review cycles will continue to skip Part B until the CRITICAL clears. The longer this persists, the more accumulated frontend changes ship without empirical browser verification — which is precisely the risk the push gate exists to surface.

## References

- **`.claude/reviews/c605f0c.md`** — full prior-cycle FAIL report; CRITICAL details + 3 remediation paths.
- `research/spec/phase13-social-discovery.md` §3.1, §3.2 (SOC1 direction — User→User asymmetric follow; Office follow at dialogue gate)
- `research/infra/03-make-db-snapshot.md:26-41` — production schema includes divisare cols (per snapshot doc; cannot verify from this terminal)
- `backend/apps/social/models.py:1-143` (Follow + Reaction + signals)
- `backend/apps/social/views.py:1-234` (FollowView, FollowersListView, FollowingListView, ReactionView)
- `backend/apps/social/migrations/0001_initial.py` (Follow CreateModel)
- `backend/apps/social/migrations/0002_rename_..._and_more.py` (CheckConstraint addition)
- `backend/apps/social/migrations/0003_reaction.py` (Reaction CreateModel)
- `backend/apps/social/migrations/__init__.py` (empty — newly tracked in 36ecbf3)
- `backend/apps/recommendation/views.py:223-228` (`is_reacted` injection on ProjectDetailView)
- `backend/apps/accounts/views.py:390-398` (`is_following` injection on UserProfileDetailView)
- `backend/config/settings.py:96-105` (DEFAULT_THROTTLE_RATES — image_load_telemetry/follow_write/reaction_write/anon/user)
- `backend/config/urls.py:9` (apps.social.urls mount)
- `frontend/src/api/client.js:434-442` (followUser / unfollowUser wrappers)
- `frontend/src/pages/UserProfilePage.jsx:540-544, 587-606, 941, 954` (numeric ID guard + handleToggleFollow + button disabled state)
- `.gitignore:1-40` (relaxation diff)
- `backend/.env.example:18-26` (HF_TOKEN, STAGE_DECOUPLE_ENABLED additions)
- `frontend/.env.example:8-9` (VITE_GEMINI_API_KEY addition)
- Empirical: `python3 manage.py shell` → `architecture_vectors` still has 23 cols (no divisare)
- Empirical: `curl GET /api/v1/users/2/` → 500 (carryover CRITICAL active)
- Empirical: `curl POST /api/v1/users/9999/follow/` → 404 ✓; `POST /users/2/follow/` self-follow → 400 ✓; `GET /users/2/followers/` → 200 ✓ (SOC1 endpoints work in isolation)
- Empirical: `python3 -m pytest -q` → **546 passed + 1 skipped + 124 warnings in 587.65s** (vs commit body 545 → off-by-one, Finding #5)
- Empirical: `git ls-tree -r HEAD -- backend/apps/social/migrations/__init__.py` → blob `e69de29` (tracked, empty file as expected)
- Empirical: `python3 manage.py showmigrations social` → all 3 migrations applied
- Empirical: independent secret scan on newly-tracked files → 0 matches
- Empirical: `git diff origin/main..HEAD --name-only | grep -E '^(research/|DESIGN.md|\.claude/agents/design)'` → 0 entries (governance clean)

## Recommended action (path forward)

The verdict is REVIEW-FAIL purely on the carryover CRITICAL. The 4 new commits (SOC1 backend + frontend, SOC2 backend, gitignore) are **clean** and would PASS in isolation — they are NOT contributing to the FAIL.

The remediation is exactly the same 3 paths from `c605f0c.md`:

**(a) Fast path — verify production schema and override-push.** Run `\d architecture_vectors` against Neon. If columns present, override-push and add MAJOR #2 (integration test) + MAJOR #3 (schema sentinel) follow-ups in next sprint.

**(b) Standard path — sync local dev DB.** Pull current Make DB snapshot to local Postgres; restart backend; re-run /review (Part B becomes runnable).

**(c) Strict path — make SELECTs forward-compatible.** Probe `information_schema.columns` once at boot; build SELECT column list dynamically. Drops the hard schema dependency entirely.

**Recommendation**: at minimum verify production schema before pushing. The 4 new commits are good work that deserves to land — but they should land on top of confirmed production-readiness, not on top of a known-untested code path.
