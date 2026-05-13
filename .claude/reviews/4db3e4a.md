# Review: feat/sj-0512-dbspeed (origin/develop..HEAD)

- **Date:** 2026-05-14
- **Branch:** feat/sj-0512-dbspeed
- **Range:** origin/develop..HEAD  (2 commits, +641 / -190 lines, 9 files)
- **Reviewer:** Claude (/review)
- **PR:** #22 (external — ksangjo/feat/sj-0512-dbspeed → develop)

## Executive Summary

Core refactor is sound: swipe-path DB round-trip collapsed from 3 → 1 (next + prefetch + prefetch2 batched via new `get_buildings_by_ids` cache-aware path), MMR rewritten from per-candidate Python loop to vectorized numpy ops, and `get_building_card` now sits behind a per-process Django cache. Tests follow with an autouse `get_buildings_by_ids` mock in `conftest.py` and a matching patch in `test_confidence.py`. **However**, the same commit silently deletes both `backend/.env.example` and `frontend/.env.example` while leaving `README.md` and `CONTRIBUTING.md` referencing them as the canonical bootstrap + onboarding template — this breaks the documented `cp .env.example .env` flow for every future collaborator and is unrelated to the stated commit purpose. Part B browser verification SKIPPED per Step A6 (Part A FAIL on MAJOR ≥ 1).

## Static Review Verdict (Part A)
OVERALL: FAIL
- CRITICAL: 0
- MAJOR: 1
- MINOR: 4

## Findings (Part A)

### 1. [MAJOR] `.env.example` files deleted while still required by README + CONTRIBUTING (onboarding break)
- **Files:** `backend/.env.example` (43 lines, deleted), `frontend/.env.example` (14 lines, deleted)
- **Axis:** 1 (Architecture alignment / drift) + 5 (Code quality / dead references)
- **Issue:** Commit `5fd4bb7` ("refactor: optimize full-stack data flow and caching architecture") also deletes both `.env.example` files. No replacement template was added (searched repo; only artifact left is `frontend/.gitignore:4 !.env.example` exception now pointing to nothing). Live doc references are stale:
  - `README.md:40` — backend bootstrap step `cp .env.example .env` (will fail with "No such file or directory")
  - `README.md:46` — frontend bootstrap step `cp .env.example .env`
  - `CONTRIBUTING.md:45` — file-ownership table lists `backend/.env.example` / `frontend/.env.example` as the place to "Append [new env vars] to the bottom; comment what the var does"
  - `CONTRIBUTING.md:215` — "Adding a backend dependency" step 3: "If the dep needs an API key or env var, append to backend/.env.example with a comment"
- **Why it matters:** First-clone onboarding for any new collaborator (admin / Role A / Role B per CONTRIBUTING.md) cannot follow the documented setup. The deletion is also unrelated to the stated commit purpose ("optimize full-stack data flow and caching architecture"), suggesting accidental removal — neither the commit message nor any companion doc update explains it. Affects all three role onboardings + the dependency-addition flow.
- **Suggested fix:** Either (a) restore both files (`git checkout origin/develop -- backend/.env.example frontend/.env.example`) since their deletion was not intentional per the commit message; or (b) if the deletion IS intentional, update `README.md` + `CONTRIBUTING.md` in the same commit to point to whatever replaced them (env vars listed in a single doc, .env.template, etc.) and remove the orphaned `!.env.example` line from `frontend/.gitignore`. Either path needs a commit; the current state is internally inconsistent.

### 2. [MINOR] `card_cache_ttl` not declared in `RECOMMENDATION` dict (discoverability)
- **File:** `backend/apps/recommendation/engine.py:285`
- **Axis:** 5 (Code quality) + 1 (Architecture alignment)
- **Issue:** `_card_cache_ttl()` reads `RC.get('card_cache_ttl', 3600)`. Every other tunable in this codebase is declared in `backend/config/settings.py` `RECOMMENDATION` dict (see lines 151–~200 — `mmr_penalty`, `convergence_threshold`, `async_prefetch_enabled`, `context_caching_ttl_seconds`, etc.) with the algorithm.md "Production Value" column tracking the same. `card_cache_ttl` is a runtime-tunable knob that affects card freshness, but a developer scanning settings.py won't see it exists — they'd have to grep engine.py.
- **Why it matters:** Operationally invisible knobs are how production tuning surprises happen (e.g., "why is data 1hr stale?" — answer is buried in engine.py, not the canonical settings file).
- **Suggested fix:** Add `'card_cache_ttl': 3600,  # seconds — building-card LocMemCache TTL` to the `RECOMMENDATION` dict in `backend/config/settings.py`. No engine.py change required (`RC.get` already has the 3600 fallback).

### 3. [MINOR] LocMemCache default `MAX_ENTRIES=300` vs ~150-per-session card cache footprint (thrash risk)
- **File:** `backend/config/settings.py:128-132` (CACHES config) + `backend/apps/recommendation/engine.py:289` (`bcard:<id>` key family)
- **Axis:** 3 (Performance & optimization)
- **Issue:** Django LocMemCache defaults are `MAX_ENTRIES=300, CULL_FREQUENCY=3` (Django 4.2 docs). With the new per-building card cache populated by every swipe (`bcard:<id>`, ~150 buildings per session pool) plus IMP-5 Gemini context-cache entries living in the same default cache, two concurrent active sessions will saturate the 300-entry budget and trigger cull (which drops 1/3 of entries). The hit-rate benefit of the new cache layer is then eroded by churn.
- **Why it matters:** Settings.py:124-127 already flags "Production multi-worker deploys SHOULD swap LocMemCache for Redis" for cross-worker visibility; the same comment block should call out `MAX_ENTRIES` sizing now that two distinct cache populations share the cache. Single-worker dev runs may not surface this, but staging/multi-user load tests will.
- **Suggested fix:** Either bump LocMemCache `OPTIONS={'MAX_ENTRIES': 2000, 'CULL_FREQUENCY': 4}` or commit to Redis sooner. At minimum extend the comment at settings.py:124 to mention the building-card cache population.

### 4. [MINOR] Analyzing-phase: MMR returns ID but card DB-miss loses action-card fallback (defensive regression)
- **File:** `backend/apps/recommendation/views/swipe.py:619-628` (new) vs old logic at the same site
- **Axis:** 2 (Correctness & logic depth)
- **Issue:** Old code converted *either* `compute_mmr_next(...) → None` *or* `get_building_card(...) → None` into "action card + phase = converged". New code only converges on `compute_mmr_next → None` (the `next_bid` check at line 624). If MMR returns an ID but the row is missing from `architecture_vectors` between transaction commit and post-transaction batch fetch (line 752), the new path:
  1. appends `next_bid` to `session.exposed_ids` (line 630) ;
  2. exits the transaction normally;
  3. `engine.get_buildings_by_ids([next_bid, ...])` returns no card for that ID, so `next_card = _fetched.get(next_bid) = None`;
  4. response carries `next_image: null` while session stays in `analyzing` phase.
- **Why it matters:** The MMR-returns-ID-but-DB-missing case is unlikely (architecture_vectors is read-only from Make DB, but does pull from a different store than session.pool_ids during pool refresh / external rebuild). Old code handled this defensively; new code silently drops to a null-card response. Self-recovers next swipe (MMR will pick another candidate; the now-exposed dead ID is excluded), but the user sees an empty card slot meanwhile.
- **Suggested fix:** After the batch fetch at swipe.py:752, if `next_bid is not None` AND `next_card is None`, convert to the action-card fallback the old code provided: set `next_card = engine.build_action_card()` and persist `session.phase = 'converged'` in a follow-up `save()`. Or accept the regression and document it.

### 5. [MINOR] `bcard:<id>` cache key carries no schema version (rolling-deploy stale-shape risk)
- **File:** `backend/apps/recommendation/engine.py:289-290`
- **Axis:** 2 (Correctness) + 3 (Performance)
- **Issue:** Cache key is `bcard:<building_id>` with no schema tag. When the `_row_to_card` output shape changes (new required field added, existing field renamed, etc.), old cached entries returned by `cache.get(...)` will have the OLD shape — serving stale frontend contracts during the 1hr TTL after deploy. With the current LocMemCache (per-process, reset on restart), this auto-recovers on the next process spin; with a future Redis swap (already foreshadowed in settings.py:124-127), the stale entries persist across restarts and can break the frontend.
- **Why it matters:** Latent risk that becomes a real bug the day the cache backend is swapped. Cheap to prevent now, more expensive to discover during a deploy.
- **Suggested fix:** Use `f'bcard:v1:{building_id}'` (or a settings constant) so a future shape change can bump the version and force-evict at deploy time. Same applies if `get_pool_embeddings` ever moves to Django cache.

## Architecture Alignment

The refactor matches the spec direction (spec §11.1 IMP-8 references the cache-write pattern for prefetch; this commit completes the symmetric read-side cache for next_card / prefetch_card / prefetch_card_2). The transaction-shortening is a clean win: the row lock is now released before the multi-RTT card fetch, reducing tail-latency under concurrent swipes from the same session and aligning with the Neon-Frankfurt RTT-dominated cost profile flagged in `.claude/reviews/57b3244-improvements.md`. The MMR vectorization is straightforward NumPy matmul reuse — same shape as `_apply_recency_weights` and the existing centroid computation, so no new pattern is introduced.

The `.env.example` deletion does NOT match any explicit architectural decision in CLAUDE.md, Goal.md, or the spec, and breaks the documented onboarding contract — see Finding 1.

## Optimization Opportunities

- The `bcard:<id>` cache is per-process (LocMemCache). For multi-worker prod (post-Redis swap), the dominant savings is the avoided Neon-Frankfurt RTT (~100-250 ms per `get_building_card` call). With a Redis backend, write-through under contention is cheap; consider adding a one-shot warm-up on `SessionCreateView` for the entire `initial_batch[:N]` (currently only the first 3 are batched).
- `compute_mmr_next` vectorization is 1-shot per swipe — fine. If MMR is ever called for top-K instead of top-1 (Topic 11 "Better layer 3" diverse-seed selection), the same `sim_mat` can drive an argpartition; consider exposing the matmul as a reusable internal helper.
- `_card_cache_ttl()` resolves the TTL lazily on every call (single `RC.get`). Cheap, but functions as effectively immutable once warmed — could memoize on import; minor.

## Security Analysis

No new authentication, authorization, or input-handling surface introduced. The new code paths operate on:
- `session.pool_ids` (already validated by session ownership check earlier in the view)
- `building_id` strings used in parameterized SQL (`'... WHERE building_id = %s'` / `IN (...)` via `placeholders`) — no string interpolation into SQL.
- Cache keys are server-derived from `building_id` (UUID-shaped); user input cannot influence cache key namespace.

`profile_image_latency.py` is a new management command behind Django's CLI — runs server-side under operator privilege, not user-reachable. The new file path follows the existing `apps/recommendation/management/commands/` convention.

No secrets in the diff. The `.env.example` deletion does not leak secrets (those files were templates with placeholder values), so removal is a docs/onboarding regression, not a security finding.

## Test Coverage Gaps

The `conftest.py` autouse fixture is correctly scoped: it patches `engine.get_buildings_by_ids` globally for `backend/tests/`, so the new batch path is exercised by every session-create + swipe test without per-file boilerplate. `test_confidence.py:106` adds the matching patch inside its `_SESSION_PATCHES` dict to preserve behavior when tests override per-test.

Gaps:
- **No test asserts the cache-hit branch** of `get_buildings_by_ids` / `get_building_card`. The Phase 1 (cache lookup) / Phase 2 (DB fetch for misses only) / Phase 3 (input-order reassembly) flow has no unit coverage — a regression that swaps Phase 1/Phase 2 order, or breaks input-order, would not be caught.
- **No test asserts the `bcard:<id>` cache TTL** is honored / that cache.set is actually invoked. The whole new cache layer is currently exercised by integration paths only.
- **Test for the swipe.py batch-fetch consolidation**: `test_confidence.py` mock satisfies the new signature, but no test specifically asserts that the post-transaction code-path issues exactly ONE `get_buildings_by_ids` call per swipe (the stated optimization). A counter on the mock would lock this in.

Severity: MINOR (the integration path is covered; unit coverage would harden against regression).

## Commit-by-Commit Notes

### 5fd4bb7 refactor: optimize full-stack data flow and caching architecture
- + Cache-aware `get_building_card` + `get_buildings_by_ids` (1 RTT batching) — clean
- + Vectorized MMR (per-swipe `O(N·K)` matmul instead of Python loop) — clean
- + Swipe.py: ID selection inside transaction, DB fetch outside — lock-hold-time win
- + `profile_image_latency` management command — useful diagnostic, isolated from prod code path
- − `.env.example` deletion unrelated to commit message; breaks docs (Finding 1)
- − `card_cache_ttl` not exposed in RECOMMENDATION dict (Finding 2)
- − Cache cap / schema-version concerns not addressed (Findings 3, 5)
- − Analyzing-phase action-card fallback narrowed (Finding 4)

### 4db3e4a fix: resolve backend pytest failures and update test logic
- + `conftest.py` autouse mock — appropriate scope, well-documented in module docstring (explains override pattern)
- + `test_confidence.py` patch dict addition — surgical, matches new call surface
- (legitimate test fixup for the new `get_buildings_by_ids` call site; not a "relax assertions" commit)

## Part B — Browser Verification
Skipped per review.md Step A6 — Part A produced 1 MAJOR finding which forces FAIL. Browser-test effort is reserved for code on its way through the push gate; failing Part A short-circuits to Step C3 emit. Once the MAJOR is resolved (Finding 1) and `/review` is re-invoked, Part B will run per the standard 3-persona × ≥25-swipe gate.

## References
- Goal.md sections consulted: §0 Working Principle, §1 Why we exist (problem + thesis), §3 Target personas (P1-P3) — no acceptance-criteria conflict.
- Report.md sections consulted: System Architecture (cache backend), Algorithm Pipeline (MMR pre/post vectorization).
- Spec / algorithm.md sections consulted: docs/algorithm.md headers + §IMP-5 / IMP-8 annotations at lines 30-32 (LocMemCache → Redis swap requirement).
- Other files consulted: `backend/config/settings.py` (CACHES + RECOMMENDATION), `CONTRIBUTING.md` (file ownership table, dep-add flow), `README.md` (bootstrap), `frontend/.gitignore` (orphaned `!.env.example`).
