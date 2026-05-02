# Review: main (origin/main..HEAD)

- **Date:** 2026-04-30
- **Branch:** main
- **Range:** origin/main..HEAD  (3 commits, +958 / -71 lines, 14 files)
- **Reviewer:** Claude (/review)

## Executive Summary

Three-commit range carrying Phase 13 PROF3 frontend integration (`d735666`) + Image hosting Path C backend (`3894bbe` 1/2) + Image hosting Path C frontend (`c605f0c` 2/2). Image hosting Path C ships defensive fallback (R2 → Divisare hotlink) in `engine._row_to_card`, telemetry endpoint with hardened security gates (throttle stack + ownership check + load_ms guard), and frontend telemetry hook. PROF3 wires UserProfilePage + FirmProfilePage to backend per BOARD1's boards[] contract. Backend engine.py adds `cover_image_url_divisare, divisare_gallery_urls` to **7 raw-SQL SELECT statements**. **CRITICAL push-blocker discovered**: those columns do NOT exist in the local dev DB (23-column schema). Empirically reproduced — multiple core endpoints (`GET /api/v1/users/{id}/`, `POST /api/v1/images/batch/`) return **500 ProgrammingError: column "cover_image_url_divisare" does not exist**. Production Neon DB is documented to have these columns (per `research/infra/03-make-db-snapshot.md:26-41` "Additional columns NOT in make_web CLAUDE.md (already in production)") — but production verification cannot be performed from this terminal. Part B browser test cannot proceed (would hit the same 500 across the entire swipe pipeline). Test coverage gap: 25 new tests cover `_row_to_card` with synthetic dict input but no integration test exercises the actual SELECTs.

## Static Review Verdict (Part A)
OVERALL: **FAIL**
- CRITICAL: 1
- MAJOR: 2
- MINOR: 1

## Findings (Part A)

### 1. [CRITICAL] Engine SQL references columns absent from dev DB; multiple endpoints 500
- **File:** `backend/apps/recommendation/engine.py:148-150, 199, 247-249, 257-259, 277-279, 296-298, 1417-1418`
- **Axis:** 2 (Correctness & logic depth) + 1 (Architecture alignment)
- **Issue:** All 7 raw-SQL SELECT statements were extended to read `cover_image_url_divisare, divisare_gallery_urls`. The local dev DB's `architecture_vectors` table has only 23 columns and does NOT include either of those two. Every endpoint that calls these functions therefore raises `psycopg2.errors.UndefinedColumn` → DRF returns 500. Empirically reproduced:
  ```
  $ curl GET /api/v1/users/2/  → 500 ProgrammingError: column "cover_image_url_divisare" does not exist
  $ curl POST /api/v1/images/batch/ {"building_ids":["B00001"]} → 500 (same)
  ```
  Affected endpoints (transitively):
  - `GET /api/v1/users/{user_id}/`           (UserProfileDetailView → `_build_boards_field` → `engine.get_buildings_by_ids`)
  - `POST /api/v1/images/batch/`             (BuildingBatchView → `engine.get_buildings_by_ids`)
  - `POST /api/v1/analysis/sessions/`        (SessionCreateView → initial pool path → `engine.get_diverse_random` / `engine.get_top_k_results`)
  - `POST /api/v1/swipe/`                    (SwipeView → next-card recommendation → `engine.get_top_k_mmr`)
  - `GET /api/v1/buildings/{id}/`            (single-card detail → `engine.get_building_card`)
  - `GET /api/v1/buildings/{id}/related/`    (related-search → `engine.search_by_filters`)
  Effectively the entire recommendation + card pipeline is broken on the dev DB.
- **Why it matters:** Push-blocking for two reasons: (a) push-gate workflow itself cannot proceed — Part B browser test cannot run because the swipe pipeline is broken in dev; web-tester E2E runs likewise broken; developer self-smoke-test is impossible; (b) any environment whose `architecture_vectors` instance lacks the divisare columns will fail in the same way. Production Neon has them per `research/infra/03-make-db-snapshot.md:26` ("Additional columns NOT in make_web CLAUDE.md (already in production)"), so production likely works — but this needs explicit verification before a production push, especially because this is the first commit that *requires* those columns.
- **Suggested fix (in order of preference):**
  1. **Verify production schema directly**: `\d architecture_vectors` against Neon, confirm both columns exist + `cover_image_url_divisare TEXT` + `divisare_gallery_urls TEXT[]`. If yes, the prod risk is bounded; sync the local dev DB next (point 3).
  2. **Sync local dev DB to production schema**: pull a snapshot of `architecture_vectors` from Neon (or run the Make DB Divisare migration locally per `research/infra/03-make-db-snapshot.md` Section 2). Goal: 23-column dev schema → ~33-column current canonical schema. The CLAUDE.md schema doc already describes the canonical shape.
  3. **Make the SELECTs forward-compatible**: probe `information_schema.columns` once at boot, build the SELECT column list dynamically. Drops the hard schema dependency and matches the `row.get(...)` defensive style already used in `_row_to_card`. Higher complexity but avoids future drift breakage.
  4. **Defer the divisare columns from the SELECTs in this PR** — keep `_row_to_card` Python defensive (works when columns are absent from the row dict), but leave the SELECT column lists alone until Make DB sync is verified. Ships telemetry-only this round; the divisare fallback chain in `_row_to_card` is a no-op for now (cover always falls through to `''`).

### 2. [MAJOR] No integration test coverage for the modified SQL paths
- **File:** `backend/tests/test_image_hosting_fallback.py:51-202` (TestRowToCardDivisareFallback) — 13 tests use synthetic dict input only; none execute the modified SELECT against a real / test DB.
- **Axis:** 6 (Test coverage)
- **Issue:** The 13 `_row_to_card` tests pass dict literals like `{'image_photos': [...], 'cover_image_url_divisare': 'https://...'}` and assert the Python transformation. None of them exercise the path that actually broke: `cur.execute('SELECT ... cover_image_url_divisare ...')` against an `architecture_vectors` instance that may or may not have the column. A single integration test against the dev DB (or even a smoke against `engine.get_buildings_by_ids(["B00001"])`) would have caught the CRITICAL above pre-commit.
- **Why it matters:** The exact gap that allowed CRITICAL #1 to ship. This bug class will recur whenever a dev DB drifts from the production canonical schema unless an integration assert is added.
- **Suggested fix:** Add one test per modified function that round-trips a real DB row:
  ```python
  @pytest.mark.django_db
  def test_get_buildings_by_ids_returns_card_shape(self):
      cards = engine.get_buildings_by_ids(["B00001"])
      assert cards and "image_url" in cards[0] and "gallery" in cards[0]
  ```
  Plus a `conftest.py`-level fixture that asserts `architecture_vectors` has the divisare columns on first use, failing fast with a clear message if dev DB is out of sync.

### 3. [MAJOR] Dev / production schema drift is not asserted anywhere
- **File:** Build / CI / dev-onboarding (no specific file)
- **Axis:** 1 (Architecture alignment) + 7 (Cross-commit drift)
- **Issue:** The dev DB has 23 columns. Production has ~33 (per `research/infra/03-make-db-snapshot.md`). CLAUDE.md documents the canonical schema as ~33 columns. There is no automated check, no `make doctor`, no Makefile target, no startup probe that flags the drift. New code that depends on canonical schema columns ships against an environment where those columns silently don't exist.
- **Why it matters:** Make DB ships canonical-schema migrations independently of Make Web. Make Web's CLAUDE.md `## Rules` correctly forbids creating / migrating `architecture_vectors` from this repo. But the boundary needs a **read-only schema sentinel** — at minimum a one-shot SQL probe at backend boot (or a pytest startup hook) that warns / fails on missing canonical columns.
- **Suggested fix:** Add a `manage.py` command `check_canonical_schema` that runs `SELECT column_name FROM information_schema.columns WHERE table_name='architecture_vectors'` and diffs against the canonical column set documented in CLAUDE.md. Run it as: (a) a pytest session-start fixture (warn-only in dev; fail in CI), (b) optionally a pre-commit hook for back-maker. Cost: <100 lines + 1 doc note. Payoff: the recurring drift class is fenced.

### 4. [MINOR] Docstring inaccuracy on `_row_to_card` divisare-only edge case
- **File:** `backend/apps/recommendation/engine.py:55-58`
- **Axis:** 5 (Code quality)
- **Issue:** Docstring says: *"Divisare-only buildings (no R2 photos/drawings) correctly get drawing_start == 0 == len(gallery), so the drawing zone is empty and all divisare items are treated as photos."* For the divisare-only case (photos=[], drawings=[], divisare_gallery=['url1','url2']):
  - extra_photos = [] (since photos[1:] is empty)
  - drawing_urls = []
  - gallery = ['url1', 'url2']
  - gallery_drawing_start = 0 + 2 = 2 == len(gallery)
  Math is correct (drawing zone is empty, len 2 == drawing_start 2). But the docstring's "drawing_start == 0" is only true when divisare_gallery is also empty (i.e., the no-image case, not the divisare-only case). The intended invariant is "drawing_start == len(gallery)" — that's what makes the drawing zone empty.
- **Why it matters:** Cosmetic. Code is correct.
- **Suggested fix:** "Divisare-only buildings (no R2 photos/drawings) correctly get drawing_start == len(gallery), so the drawing zone is empty and all divisare items are treated as photos."

## Architecture Alignment

Each commit's intent is well-grounded:

- **`d735666` PROF3** — frontend wiring, no backend surface change. Designer-territory JSX preserved (MOCK_USER / MOCK_OFFICE retained as schema documentation, not used at runtime). Boards adapter `project_id → board_id` keeps the JSX accessor stable while wiring backend. `formatBoardDate` is correctly defensive (handles null / undefined / invalid). Avatar SVG fallback matches FirmProfilePage logo pattern. `useParams + sessionStorage` fallback for `/user/me` route is reasonable.
- **`3894bbe` Image hosting Path C 1/2** — implements `research/infra/02-image-hosting-strategy.md` §6 + §7 (Path C — cover CDN-mirror, gallery hotlink hybrid). Engine fallback chain logic is correct. Telemetry endpoint has the security hardening called out by prior reviewer/security cycle: throttle stack (scoped 120/min anon + 300/min user), session ownership filter, load_ms strict-finite guard, payload-size truncation. Migration 0016 is choices-only AlterField — reverse-safe.
- **`c605f0c` Image hosting Path C 2/2** — frontend layer matches backend contract. `getImageSource` host-anchored matching prevents subdomain spoofing (the prior MINOR fix). `emitImageLoadEvent` is fire-and-forget; errors swallowed at every level — telemetry never blocks UI. `useImageTelemetry` resets timer on `buildingId` change correctly. Sample-rate logic correct (5% success, 100% failure). Preconnect without crossorigin (per prior MINOR fix) is correct for `<img>` tags.

The CRITICAL is a **deployment-pipeline issue**, not a design issue. The architecture is sound; the SELECT changes are reasonable; the failure is an environment-coordination gap (dev DB lagged production schema, no sentinel asserted parity).

## Optimization Opportunities

- **Engine SQL column lists are duplicated 7 times** with full identical column sets except for `, embedding::text` on the vector-search variants. Could be refactored to a single `_BUILDING_COLUMNS_SQL` constant. Pure cleanup, not blocking.
- **Telemetry beacon batching**: 5% success-sample with sendBeacon is reasonable, but at peak swipe rate (~30 swipes/min × 4 cards visible) the user could emit 6 events/min. Acceptable. If telemetry becomes hot, batch every N seconds via a single endpoint call.
- **`_build_boards_field`** in `accounts/views.py` already calls `engine.get_buildings_by_ids` once per profile — broken now (CRITICAL #1) but well-batched (no per-row N+1).

## Security Analysis

The image-load telemetry endpoint is the only new security-relevant surface. Hardening is thorough:

- **Throttle stack**: `ImageLoadTelemetryThrottle (120/min scoped anon)` + `UserRateThrottle (300/min)`. DRF picks the stricter one per request. Anonymous flooding capped.
- **Session ownership**: `AnalysisSession.objects.filter(session_id=session_id, user=profile)` — anonymous users (`profile=None`) skip session linkage; authenticated users can only attach their own sessions. Cross-user injection vector closed.
- **Input validation**:
  - `outcome ∈ {'success', 'failure', 'timeout'}` — strict allowlist, 400 otherwise.
  - URL: non-empty + ≤2048 chars, 400 otherwise. `urlparse(url).netloc` for domain extraction with `'unknown'` fallback.
  - `load_ms`: rejects bool (Python `True`/`False` would otherwise become 1/0 silently), non-finite (NaN, ±Inf), out-of-range (0..60_000 ms cap). Otherwise `None`.
  - All payload string fields slice-truncated (url[:2048], domain[:128], building_id[:32], context[:32]) — bounded payload size.
- **No SQL injection surface**: telemetry view uses Django ORM (`SessionEvent.objects.create`); engine.py uses parameterized `%s` placeholders + static literals (column names) in f-strings (safe).
- **Frontend host classification** (`getImageSource`) uses `host === X || host.endsWith('.' + X)` — correctly fences `not-divisare.com.attacker.example` from matching `divisare.com`.

No new auth surface, no token handling change, no permissions broadening. Clean security verdict.

## Test Coverage Gaps

- **Untested**: SQL paths in 7 modified `engine.py` functions (CRITICAL #1, MAJOR #2 documented above).
- **Untested**: PROF3 frontend integration (`d735666`) — no JSX-level tests, only manual smoke in commit body. Acceptable per project convention (frontend tests are lighter).
- **Tested well**: `_row_to_card` 13 paths (no R2 / R2-only / divisare-only / hybrid / drawing-only / mixed), telemetry view 12 paths (success / failure / timeout / outcome enum / URL bound / domain extract / session ownership / load_ms guard).

## Cross-Commit Drift

- **Bundle is logically clean**: `3894bbe` (backend) + `c605f0c` (frontend) is a deliberate 1/2 + 2/2 split per commit body. Backend ships first, frontend wires it second. Both cite the same spec (`research/infra/02-image-hosting-strategy.md` §6 + §7) and reference each other. Good discipline.
- **`d735666` (PROF3 frontend)** rides along but is independent of Image hosting Path C. It does *consume* BOARD1 boards[] field which lands in `a501c8d` (just-pushed). Sequencing is correct.
- **No accumulated cleanup debt** — each commit lands its own fix-loop cycle rationale in the body.

## Commit-by-Commit Notes

### `d735666` feat: PROF3 UserProfile + FirmProfile frontend integration (Phase 13)
- **Good**: clean separation of designer territory (MOCK_USER, MOCK_OFFICE, JSX styles) from data wiring (useEffect + useState + getOffice/getUserProfile). Designer-pipeline contract preserved.
- **Good**: `formatBoardDate` is null-safe and `Number.isNaN(date.getTime())` defensive against invalid ISO strings.
- **Good**: avatar SVG fallback for null `avatar_url`. Matches FirmProfilePage logo pattern (visual consistency).
- **Good**: `is_following` defaults `false` with explicit "Phase 15 SOC1 territory" comment — correct phase-boundary discipline.
- **Good**: `articles[]` defaults `[]` with "Phase 18 External territory" comment — same.
- **Good**: cancellation token (`cancelled` flag) on the useEffect prevents setState after unmount.
- **Sub-MINOR**: `setUser({ ...data, boards })` re-spreads after the boards adapter — fine, just a one-liner you could split.

### `3894bbe` feat: Image hosting Path C — backend defensive fallback + telemetry (1/2)
- **Good**: 6 hardening fixes from reviewer + security FAIL applied in cycle 1, all correctly addressed (gallery_drawing_start / ImageLoadTelemetryThrottle / session ownership / load_ms guard / narrow except / explicit bool reject).
- **Good**: spec citation + commit-body math on throttle budget (120/min vs ~60-90/min observed peak).
- **Good**: defensive `row.get(...)` pattern at the Python level — would survive missing columns IF the SELECT itself didn't explicitly name them. The CRITICAL is that the SQL fails before Python sees the row.
- **Good**: 25 new tests (13 `_row_to_card` paths + 12 telemetry paths) — high coverage for the Python layer.
- **Bad — CRITICAL #1**: SQL changes ship without DB integration coverage and without a dev-DB sync. See Findings above.
- **Sub-MINOR**: commit body claims "Suite: 415 passed, 1 skipped". Actual on this branch is 499 passed + 1 skipped. Off-by-counting (other in-flight commits on the branch have stacked tests since 3894bbe was authored). Cosmetic.

### `c605f0c` feat: Image hosting Path C — frontend mitigations + telemetry beacon (2/2)
- **Good**: spec parity with backend commit; both reference `research/infra/02-image-hosting-strategy.md` §6 + §7.
- **Good**: 2 reviewer-cycle MINORs addressed (preconnect crossorigin removed; getImageSource host-anchored matching). Both substantive (perf + security).
- **Good**: telemetry beacon design — sendBeacon primary, fetch keepalive fallback, all errors swallowed.
- **Good**: SwipePage telemetry order: `telemetryOnError` fires BEFORE cache-bust retry mutates `e.target.src`. Prevents capturing the cache-busted URL as the "failed" URL. Subtle but correct.
- **Good**: hook deps are correct on `useCallback` (`[buildingId, context, sessionId]`).

## Observations (sub-MINOR, not flagged as findings)

1. **`_row_to_card` docstring**: Finding #4 above — "drawing_start == 0 == len(gallery)" should be "drawing_start == len(gallery)". Cosmetic; logic correct.
2. **3894bbe commit body test count**: 415 vs 499 actual. Off-by-counting; cosmetic.
3. **CLAUDE.md schema doc**: documents the canonical 33-column schema with a "Last synced 2026-04-29" comment. Doc is accurate; the dev DB just hasn't been updated to match. Worth a note in dev onboarding (see MAJOR #3).
4. **`useImageTelemetry` SSR safety**: hook calls `performance.now()` directly. Safe in Vite/browser env, but if the project ever adds SSR, would need a `typeof performance !== 'undefined'` guard. Not a current concern.

## Part B — Browser Verification

**Skipped — Part A FAIL halts the pipeline before browser test** (per `.claude/commands/review.md` Step A6: CRITICAL ≥1 → skip Part B and Part C drift). The browser test would deterministically FAIL on the same 500 across the entire swipe pipeline (`POST /api/v1/analysis/sessions/`, `POST /api/v1/swipe/`, `POST /api/v1/images/batch/` all share the broken SELECT path). No diagnostic value in re-running it.

## References

- `research/infra/02-image-hosting-strategy.md` §6 + §7 (Path C — cover CDN-mirror + gallery hotlink hybrid)
- **`research/infra/03-make-db-snapshot.md:26-41`** — "Additional columns NOT in make_web CLAUDE.md (already in production)" — production has divisare columns; dev DB does not (the CRITICAL).
- `CLAUDE.md` ## Database: architecture_vectors Schema — canonical 33-column shape
- `backend/apps/recommendation/engine.py:31-83` (`_row_to_card` defensive fallback chain — Python-level)
- `backend/apps/recommendation/engine.py:148-150, 199, 247, 257, 277, 296, 1417` (7 modified SELECTs)
- `backend/apps/recommendation/views.py:1671-1742` (ImageLoadTelemetryView + Throttle — security gates)
- `backend/apps/recommendation/migrations/0016_alter_sessionevent_event_type.py` (choices-only AlterField, reverse-safe)
- `backend/config/settings.py:92-100` (DEFAULT_THROTTLE_RATES — image_load_telemetry 120/min + anon 60/min + user 300/min)
- `frontend/src/api/client.js:128-176` (getImageSource host classifier + emitImageLoadEvent beacon)
- `frontend/src/hooks/useImageTelemetry.js:1-60` (5%/100% sampling hook)
- `frontend/src/pages/UserProfilePage.jsx`, `FirmProfilePage.jsx` (PROF3 wiring)
- `frontend/src/pages/SwipePage.jsx`, `BoardDetailPage.jsx` (telemetry wiring)
- Empirical: `python3 manage.py shell` → `architecture_vectors` has 23 cols (no divisare), should have ~33
- Empirical: `curl GET /api/v1/users/2/` → 500 ProgrammingError: column "cover_image_url_divisare" does not exist
- Empirical: `curl POST /api/v1/images/batch/` → same 500
- Empirical: `python3 -m pytest` → 499 passed + 1 skipped + 91 warnings in 390.08s (Python-layer coverage clean; SQL paths uncovered)
- Empirical: `git diff origin/main..HEAD --name-only | grep -E '^(research/|DESIGN.md|\.claude/agents/design)'` → 0 entries (governance clean — no research/ or design-pipeline writes)

## Recommended action (path forward)

The root cause is a dev/prod schema sync gap, not a code defect. Production should work (per snapshot doc). The user has three reasonable paths, in increasing rigor:

**(a) Fast path — verify prod and override-push.** Run `\d architecture_vectors` against Neon. If columns are present, override-push. Add the integration test (MAJOR #2) and schema sentinel (MAJOR #3) in a follow-up commit so the next regression is caught pre-push.

**(b) Standard path — sync dev DB.** Pull a current Make DB snapshot to local Postgres, restart backend, re-run /review. Adds the dev-DB sync to the regular workflow. Catches future drift the same way.

**(c) Strict path — make code dev-DB-tolerant.** Probe `information_schema` once at boot, build the SELECT column list dynamically. Drops the hard schema dependency entirely. Highest engineering cost, but eliminates the drift class going forward.

In all three cases, MAJOR #2 (integration test) and MAJOR #3 (schema sentinel) should be addressed in a follow-up commit, not deferred indefinitely.
