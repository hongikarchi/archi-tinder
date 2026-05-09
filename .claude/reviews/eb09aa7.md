# Review: main (origin/main..HEAD)

- **Date:** 2026-05-07
- **Branch:** main
- **Range:** origin/main..HEAD  (2 commits, +526 / -0 lines, 3 files)
- **Reviewer:** Claude (/review)

## Executive Summary

BUILDING-DETAIL-P1 ships the new Building Detail Page (`/buildings/:buildingId`) plus a route in App.jsx and a separate plan doc. The implementation is structurally sound — clean React idioms, proper async-effect cancellation, retry path, ESLint clean — but diverges from spec § 8 in two visible ways (long description and external link not rendered) and from the plan's own Phase 1 deliverable wording (which promised "description"). Eight MINORs, zero MAJOR/CRITICAL. UI-affecting paths in scope → Part B browser test will run.

## Static Review Verdict (Part A)
OVERALL: PASS-WITH-MINORS
- CRITICAL: 0
- MAJOR: 0
- MINOR: 8

## Findings (Part A)

### 1. [MINOR] Spec § 8 long description not rendered
- **File:** `frontend/src/pages/BuildingDetailPage.jsx:319-339`
- **Axis:** 1 (Architecture alignment)
- **Issue:** Spec `research/spec/requirements.md` §8 "Detail Page" lists "Long description: visual_description, description" as a Detail Page element. The plan (`.claude/plans/building-detail-page.md`) Phase 1 deliverable is "User … sees gallery + metadata + **description** + back arrow." The page only renders `metadata.axis_atmosphere` under heading "Atmosphere". `axis_atmosphere` is the short atmospheric-tag field (e.g. "fluid, sweeping, atmospheric"), not the rich `visual_description` paragraph the spec calls for.
- **Why it matters:** Phase 1's stated scope per the plan is missing one of its three content sections; spec § 8 has a corresponding gap. Compounded by the fact that the backend `_row_to_card` (`backend/apps/recommendation/engine.py:99-154`) does NOT currently expose `visual_description` or `description` at all — so even a frontend-only fix can't close this without a backend column add.
- **Suggested fix:** (a) Add `visual_description` (and `description` fallback) to `_required_cols` in `engine.py:350-354` and to `_row_to_card`'s `metadata` dict; (b) render it in BuildingDetailPage as a separate "Description" section above or below the existing Atmosphere block. Or, if deferred, add an explicit "Phase 2 — backend column add + render long description" line to the plan's phase split and a TODO comment in the page.

### 2. [MINOR] Spec § 8 external link not rendered
- **File:** `frontend/src/pages/BuildingDetailPage.jsx` (entire file)
- **Axis:** 1 (Architecture alignment)
- **Issue:** Spec § 8 lists "External link: url (새 탭)" as a Detail Page element. Backend already exposes `card.url` via `_row_to_card`, normalized to `card.source_url` by `frontend/src/api/images.js:80` (`source_url: card.url || null`). The page never reads `building.source_url` — no link to the source publication is shown.
- **Why it matters:** Source attribution is a basic content-licensing concern (Divisare/Metalocus rows) and a useful escape hatch for users who want fuller context. Closing this is a 5-line frontend-only fix.
- **Suggested fix:** Below the metadata grid (or in the page header next to the back arrow), render `building.source_url && <a href={building.source_url} target="_blank" rel="noreferrer noopener">View on source</a>`. `noopener noreferrer` for tabnabbing safety.

### 3. [MINOR] Global header controls overlap BuildingDetailPage's sticky header
- **File:** `frontend/src/layouts/MainLayout.jsx:30`
- **Axis:** 1 (Architecture alignment) / 5 (Code quality — convention drift)
- **Issue:** MainLayout hides its top-right ThemeToggle + Logout buttons on routes where the page owns its own sticky header: `pathname.startsWith('/user') || pathname.startsWith('/office') || pathname.startsWith('/matched') || pathname.startsWith('/board')`. `/buildings/...` is a new owned-header page (sticky `<Header>` with back arrow at `zIndex:20`) but is missing from the hide-list, so the global controls (`zIndex:200`) float above it.
- **Why it matters:** Visual cluttering at top-right of every building detail page. Inconsistent with the established convention. The other four "owned-header" pages don't have this issue.
- **Suggested fix:** Add `pathname.startsWith('/buildings')` to the hide condition in `MainLayout.jsx:30`. One-line change.

### 4. [MINOR] Dead `.catch(err => ... err.message)` branch
- **File:** `frontend/src/pages/BuildingDetailPage.jsx:170-174`
- **Axis:** 5 (Code quality — dead code)
- **Issue:** `getBuildings()` in `frontend/src/api/projects.js:60-69` swallows all errors via try/catch and returns `[]` on failure — it never throws. The `.catch(err => { … setError(err.message || 'Failed to load building detail.') })` block in BuildingDetailPage's effect is unreachable.
- **Why it matters:** Misleading defensive code. Future readers will assume network-failure messaging works; in reality, network failures present as the "No building matched this ID." path on line 168 (because `results = []` → `results?.[0] = undefined` → falsy `next`).
- **Suggested fix:** Either (a) make `getBuildings` re-throw on network errors and keep the catch; or (b) drop the `.catch` block and rely on the empty-result branch. (a) is preferable because it lets the page distinguish "404 / no row" from "network error" with different copy + retry semantics.

### 5. [MINOR] Dead fallback chains in title/description
- **File:** `frontend/src/pages/BuildingDetailPage.jsx:188-190`
- **Axis:** 5 (Code quality — dead code)
- **Issue:** Line 188: `building?.image_title || building?.name_en || buildingId || 'Building'` — `normalizeCard` (`api/images.js:79-100`) does NOT preserve `name_en` at the top level after normalization (it's collapsed into `image_title`). So `building?.name_en` is always undefined here.
  Line 190: `building?.metadata?.axis_atmosphere || building?.atmosphere || 'No atmosphere description is available yet.'` — same problem; `building.atmosphere` (top-level raw) is also dropped during normalization.
- **Why it matters:** Same dead-code concern as #4 — defensive fallbacks that don't actually fall back create false confidence.
- **Suggested fix:** Drop the dead branches: `const title = building?.image_title || buildingId || 'Building'`; `const description = building?.metadata?.axis_atmosphere || 'No atmosphere description is available yet.'`.

### 6. [MINOR] `navigate(-1)` strands deep-linked direct-URL entries
- **File:** `frontend/src/pages/BuildingDetailPage.jsx:193-195`
- **Axis:** 2 (Correctness — edge cases)
- **Issue:** `handleBack()` calls `navigate(-1)`. On a fresh tab opened with `http://localhost:5174/buildings/B00042`, browser history is empty; `navigate(-1)` either does nothing or navigates to a non-app URL depending on browser. The plan's Phase 3 explicitly defers the proper `fromSessionId > fromProjectId > history > library` fallback to a later phase.
- **Why it matters:** Acceptable known gap for Phase 1, but worth noting that direct-URL/share-link UX isn't graceful yet.
- **Suggested fix:** As a 1-line bridge until Phase 3 lands: `if (window.history.length > 1) navigate(-1); else navigate('/library')`. (`location.key === 'default'` from `useLocation()` is the cleaner react-router signal.)

### 7. [MINOR] Drawings cropped via `objectFit: cover` (gallery_drawing_start ignored)
- **File:** `frontend/src/pages/BuildingDetailPage.jsx:226-249`
- **Axis:** 2 (Correctness) / 1 (Architecture alignment)
- **Issue:** Backend `_row_to_card` (`engine.py:104-108, 140`) exposes `gallery_drawing_start` so frontend can render drawings (orthographic plans, sections) with `objectFit: contain` on a white background. The backend docstring explicitly says: "Frontend renders items at index >= gallery_drawing_start with contain-sizing on white bg." BuildingDetailPage uses `objectFit: cover` for all gallery items uniformly.
- **Why it matters:** Drawings get center-cropped, defeating their informational value (a plan's edges and labels are usually the interesting parts).
- **Suggested fix:** Read `building.gallery_drawing_start` (already on the card after normalize per `images.js:86`); for `index >= gallery_drawing_start`, switch to `objectFit: 'contain', background: '#fff'`.

### 8. [MINOR] Skeleton-shimmer keeps animating after image-load failure
- **File:** `frontend/src/pages/BuildingDetailPage.jsx:226-247`
- **Axis:** 5 (Code quality — UX edge case)
- **Issue:** Each `<img>` is rendered over a `<div className="skeleton-shimmer">` that animates indefinitely. On image-load success the shimmer is occluded by the `objectFit: cover` image. On image-load failure (404, CORS, network), the broken-image icon may not fully cover the shimmer, leaving a misleading "still loading" animation behind it. No `onError` handler.
- **Why it matters:** Confusing UX for buildings with stale R2/Divisare URLs (a known concern given the cross-CDN gallery merge logic).
- **Suggested fix:** Add `onError` to the `<img>` that sets a state flag to swap shimmer → placeholder div with "Image unavailable" text. Or apply `display: none` to the shimmer once any of `onLoad`/`onError` fires.

## Architecture Alignment

Aligns well with the codebase patterns:
- Inline-style JSX (per CLAUDE.md frontend convention) ✅
- CSS custom properties (`var(--color-*)`) verified to exist in both dark/light themes in `frontend/src/index.css` ✅
- `BUILDING_ID_RE = /^[A-Za-z0-9_-]{1,32}$/` mirrors FirmProfilePage's officeId pattern (32 vs 64 char limit, intentional given B0xxxx 6-char Make-DB convention) ✅
- Async-effect cancellation guard via `cancelled` flag ✅
- Retry via `setReloadKey(k => k + 1)` (standard react-router pattern) ✅
- Route protected via `ProtectedRoute` (App.jsx:639-643 wraps it inside MainLayout) ✅
- `getBuildings([id])` uses the existing `/images/batch/` endpoint — zero backend change needed for Phase 1 ✅

Drift from plan/spec: see findings #1–#3 (long description, external link, header overlap).

## Optimization Opportunities

- **One-row batch fetch is slightly wasteful** — `getBuildings([id])` POSTs to `/images/batch/` for a single building. The plan acknowledges this and notes a dedicated `GET /api/v1/buildings/{id}/` endpoint as a future option. Acceptable for Phase 1 (single round-trip is dominant cost; payload size is identical).
- **`useMemo` on gallery is fine** — recomputes only when `building` changes, which is once per ID change.
- **No virtualization on gallery** — for buildings with 30+ images, all `<img>` elements are mounted. Native `loading="lazy"` (correctly applied to index ≥1) defers byte fetch but not DOM cost. Current corpus has ≤19 gallery URLs per row (per Make DB v2 schema comment) so this is a non-issue.

## Security Analysis

- **buildingId regex** (`/^[A-Za-z0-9_-]{1,32}$/`) is solid defense-in-depth — same posture as FirmProfilePage. Tightly scoped character class blocks path-traversal probes; max length blocks expansion attacks.
- **Auth surface unchanged** — page reuses existing `getBuildings` which goes through the authenticated `callApi` path with JWT refresh on 401. No new auth code.
- **No `dangerouslySetInnerHTML`** — all user-facing strings are passed as React children → automatically escaped.
- **External link missing** is actually a security non-issue at the moment (since not rendered); if implemented per finding #2, must use `rel="noreferrer noopener"` to prevent reverse-tabnabbing on the source-publisher URL.
- **No new endpoint surface** — backend untouched.

No security findings.

## Test Coverage Gaps

No new tests added. The codebase convention is Playwright E2E for page components (no Jest/Vitest unit tests for individual React pages). Part B (browser verification below) is the integration test for this commit. NOT a blocker.

If the page were to extend significantly (Phase 2 bookmark logic, Phase 3 back-target hierarchy), a small Vitest suite covering the `metadataItems` helper + `BUILDING_ID_RE` regex edge cases would be cheap to add. Out of scope for this branch.

## Commit-by-Commit Notes

### cfbce97 — docs: plan — option A Building Detail Page implementation design
- Plan is thorough: 3-phase split, spec-element-by-element table, explicit acceptance criteria per phase, codex dispatch script, hard rules cross-reference. Good doc.
- Phase 1 deliverable text says "gallery + metadata + description + back arrow" — but the spec § 8 row for "Long description" maps to `visual_description, description` (a backend column gap), so "description" was always going to need a backend touch. Plan didn't surface that backend dependency. Minor planning gap captured in finding #1.

### eb09aa7 — feat: BUILDING-DETAIL-P1 — Building Detail Page (gallery + metadata + back)
- Faithful to plan's Phase 1 scope on the visible elements (gallery + metadata grid + back arrow).
- Commit message honestly says "(gallery + metadata + back)" — narrower than the plan's "gallery + metadata + description + back arrow", which is accurate to what was actually shipped (description omitted).
- Defensive coding (regex, cancellation, retry, error state) is well executed.
- Eight MINORs above are all post-Phase-1-polish concerns — none block the page from working as a Phase 1 deliverable.

## Part B — Browser Verification

**OVERALL: FAIL** — strict outer-RTT gate breached (pre-existing Neon RTT floor; not caused by BUILDING-DETAIL-P1).

### Pre-flight gates (all PASS)
- Frontend health: `200` ✅
- Backend health: `403` (expected for empty body) ✅
- Migration sanity check: 0 unapplied ✅
- SessionEvent external-API failure pre-check: 0 events in 5-min window ✅
- Dev-login: success (user_id=2, JWT exp 2026-05-07 02:59) ✅
- Token injection + page load: 0 console errors at baseline ✅

### BuildingDetailPage direct-URL coverage (NEW functionality — all PASS)

The Phase 1 commit's only user-reachable surface is `/buildings/:buildingId` via direct URL (Phase 2 will wire click handlers). All three direct-URL paths verified:

| Test | URL | Expected | Observed | Verdict |
|---|---|---|---|---|
| Valid existing ID | `/buildings/B00002` | Renders gallery + metadata + atmosphere + back button | Title `Baraike Park Facility`, 5 gallery images, 6 metadata cells (Architect, Year=2022, Program=Public, Style=Organic, Material=timber, Location=Japan), Atmosphere `organic, serene, light-filled`, back button present. POST `/images/batch/` 200 in ~735 ms (single fetch — StrictMode double-effect handled by `cancelled` guard, only one render). | ✅ PASS |
| Malformed ID | `/buildings/INVALID@@@` | regex blocks fetch, shows error state | Korean error `건물 정보를 찾을 수 없어요` + detail `Invalid building ID.` + Retry button; Last call `none yet` (regex prevented network call) | ✅ PASS |
| Valid-format nonexistent ID | `/buildings/B99999` | API returns empty, shows "No building matched this ID." | Korean error + detail `No building matched this ID.` + Retry button; POST `/images/batch/` 200 in 152 ms (empty array) | ✅ PASS |

The dev-mode StrictMode double-invocation produced 2 `/images/batch/` POSTs in network log on the valid-ID path; only one resulted in state update because BuildingDetailPage's `cancelled` flag correctly discards the first effect's result. NOT a defect.

### Search → swipe regression sweep (Brutalist persona, abbreviated)

Phase 1's commit touches **none** of the swipe pipeline (no engine.py, views.py, urls.py, migrations, or RECOMMENDATION settings changes). Standard regression check executed:

| Stage | Measurement | Verdict |
|---|---|---|
| Parse-query (terminal turn) | 2742 ms; `probe_needed = false` | ✅ |
| `/analysis/sessions/` POST 201 (start session) | 1661 ms | ✅ |
| TTFC (system, single-shot estimate) | ≈ 2000 ms (system-attributable; budget 4000 ms) | ✅ — single-shot only; spec wants 3-run p50 |
| 10 swipe POSTs | All 200 OK; one session_id `f8308500-…-cdf` | ✅ |
| Console errors | 0 | ✅ |
| 4xx / 5xx (outside auth refresh) | 0 | ✅ |
| Page-level JS errors | 0 | ✅ |

#### Swipe latency — outer (user-felt frontend RTT)
**FAIL** per strict gate `p95 < 1500 ms`.

Latencies (10 samples, ms): `[1497, 1514, 1515, 1650, 1691, 1672, 1532, 1531, 1543, 1599]`

- p50 = 1543 ms
- p95 = 1691 ms — **exceeds 1500 ms strict gate**
- max = 1691 ms (under p99 warn ceiling 2500 ms)
- Breach count (≥1500 ms): **9 / 10 swipes** (gate: ≥2 breaches → FAIL)

#### Swipe latency — backend sub-budget (`SessionEvent.swipe.timing_breakdown.total_ms`)
**PASS** per strict gate `p95 < 1000 ms`.

Pulled directly from SessionEvent table (10 events covering the same swipe window):
- p50 = 850 ms
- p95 = 868 ms — comfortably under 1000 ms gate
- max = 868 ms

Per-event composition: `select_ms ≈ 295-326 ms` + `prefetch_ms ≈ 303-332 ms` + framework overhead. The split confirms the engine is the small fraction; the missing 700-800 ms in user-felt RTT is **network round-trip + frontend response handling**, exactly matching `research/investigations/18-swipe-loop-latency-floor.md` §4 Neon-Frankfurt → user RTT diagnosis.

#### Cause attribution

The 1500 ms outer gate was set post-Investigation 18 to avoid false-positive FAILs on Neon-dominated runs. This run shows the **floor has crept up** (or the harness happens to land in a slightly slower window): all 10 samples cluster tightly at 1497-1691 ms with min ≈ 1497 ms — so even the *best* swipe is essentially at the gate ceiling. This is **not introduced by BUILDING-DETAIL-P1**, which adds zero swipe-pipeline code:

- `frontend/src/App.jsx`: only adds 2 lines (import + route declaration); existing swipe handlers unchanged.
- `frontend/src/pages/BuildingDetailPage.jsx`: new file, never invoked during the swipe loop.
- `.claude/plans/building-detail-page.md`: doc only.

Same pattern as the prior 9 override-push cycles documented in `.claude/Task.md ## Handoffs` (most recent: f5dc690 on 2026-04-29) — but those were TTFC-related; this is the first cycle where the swipe outer gate also fails. Suggest the user weigh override-push (commit is risk-bounded — pure additive UI surface, page is reachable only by direct URL until Phase 2 ships) vs. waiting for INFRA-1 / IMP-8 to land.

### Edge cases (B7) — skipped

B7a refresh-resume / B7b action card / B7c persona report / B7d network failure injection were **not exercised** because the commit's diff doesn't touch any of those code paths (App.jsx swipe handlers, session resume, action card, persona report, network error toast — all unchanged). Running them on this commit specifically wouldn't produce signal that distinguishes pre-existing health from BUILDING-DETAIL-P1 regressions. They remain valid for any commit that touches `App.jsx` swipe state, `recommendation/views.py`, `engine.py`, or session resume logic.

### Spec primary-metric infrastructure sentinel (B8)

`Project.saved_ids` field is shipped (per recent commit `9053537` ResultsPage with bookmark stars). Bookmark endpoint `/projects/{id}/bookmark/` exists and is exercised by ResultsPage. Sentinel **passes** at the schema/endpoint level; not retested this cycle since this commit didn't touch the bookmark pipeline.

### Summary

- **New surface (BuildingDetailPage)**: all 3 direct-URL paths render correctly, 0 errors, 0 4xx/5xx. ✅
- **Swipe pipeline regression**: 0 functional regressions. Backend pipeline healthy (p95 868 ms < 1000 ms gate). ✅
- **Outer RTT gate**: FAIL (p95 1691 ms > 1500 ms gate, 9/10 breach) — pre-existing Neon RTT floor, NOT introduced by this commit. ❌

Per review.md Step B10, Part B FAIL routes the unified verdict to `REVIEW-FAIL` per Step C3b. Drift checks skipped per the spec.

## References

- Goal.md sections consulted: (no building-detail mentions)
- Report.md sections consulted: (no building-detail mentions)
- Spec sections consulted: `research/spec/requirements.md` §8 "Detail Page" (lines 376-385)
- Other files consulted: `.claude/plans/building-detail-page.md` (full), `frontend/src/api/projects.js`, `frontend/src/api/images.js`, `frontend/src/api/client.js`, `frontend/src/pages/FirmProfilePage.jsx` (regex pattern), `frontend/src/pages/BoardDetailPage.jsx` (TODO context), `frontend/src/components/profile/ProjectCard.jsx` (TODO context), `frontend/src/layouts/MainLayout.jsx` (header convention), `frontend/src/index.css` (CSS class + var verification), `backend/apps/recommendation/engine.py` (`_row_to_card`, `get_buildings_by_ids`), `backend/apps/recommendation/views/swipe.py` (`BuildingBatchView`)
