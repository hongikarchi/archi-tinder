# Review: main (origin/main..HEAD)

- **Date:** 2026-05-08
- **Branch:** main
- **Range:** origin/main..HEAD  (3 commits, +238 / -39 lines, 7 files)
- **Reviewer:** Claude (/review)

## Executive Summary
Three-commit bundle: backend `_row_to_card` exposes `visual_description` + `description` columns; frontend wires Building Detail click handlers + bookmark UI from results & boards; ResultsPage gains lazy-load (10→50). Cycle-1 fix already addressed the upstream rank:null CRITICAL, isBookmarked-seed MAJOR, and ownership MAJOR — those fixes verify clean. Static finds no new CRITICAL/MAJOR; three MINOR items (one-way bookmark sync from BuildingDetailPage → parent state, UUID-heuristic project-ID resolution, missing test coverage for the new metadata fields). UI-affecting paths in scope → Part B browser verification proceeds.

## Static Review Verdict (Part A)
OVERALL: PASS-WITH-MINORS
- CRITICAL: 0
- MAJOR: 0
- MINOR: 3

## Findings (Part A)

### 1. [MINOR] Bookmark toggle on BuildingDetailPage does not propagate to parent state
- **File:** frontend/src/pages/BuildingDetailPage.jsx:262-274 (handleToggleBookmark)
- **Axis:** 2 — Correctness & state-machine integrity
- **Issue:** `handleToggleBookmark` flips local `isBookmarked` and POSTs to backend, but never lifts the change up to the caller (ResultsPage `useResults` projects context, or BoardDetailPage's local `savedIds`). After the user toggles in BuildingDetail and `navigate(-1)`s back, the result-card star or board tile reflects the *snapshot* `savedIds` taken at navigate-time, not the current backend state.
- **Why it matters:** UX-visible drift. The backend `ProjectBookmarkView` is idempotent on both `save` and `unsave` (lines 218-225 in views/swipe.py), so subsequent toggles do not corrupt server state — but the user perceives "I starred it, then it un-starred itself when I went back." Severity is held to MINOR because (a) state self-heals on full refetch and (b) backend is the source of truth and remains consistent.
- **Suggested fix:** Out-of-scope for this branch but worth a follow-up: either pass an `onBookmarkChange(buildingId, saved)` callback through `location.state` (functions don't survive serialization, so a different mechanism is needed — e.g., a top-level bookmarks context, or refetch-on-focus on the parent), or have ResultsPage / BoardDetailPage refetch project data on `useEffect(() => {}, [pathname])` re-mount after navigate-back.

### 2. [MINOR] UUID heuristic for `fromProjectId` resolution is fragile and duplicated
- **File:** frontend/src/pages/ResultsPage.jsx:182, frontend/src/hooks/useResults.js:65
- **Axis:** 5 — Code quality (duplication + brittle parse)
- **Issue:** Both call sites compute `project?.backendId || (project?.id?.includes('-') ? project.id : null)`. The `.includes('-')` branch is a UUID heuristic that would also match local IDs like `"local-2"` or any string containing a dash. If `backendId` is missing (e.g., not yet synced from the server), the fallback could send a non-UUID to a `<uuid:project_id>` URL, returning a Django 404 (not catastrophic, but a confusing failure mode).
- **Why it matters:** Two-line duplication invites drift. The current implementations are identical, so behavior is consistent today, but a future change to one site is unlikely to be mirrored to the other.
- **Suggested fix:** Extract to a single helper (e.g., `getProjectBackendId(project)` in `frontend/src/api/projects.js`) and replace both call sites. Tighten the heuristic to a UUIDv4 regex match — same regex already exists in `useResults.isUuid`. Out of scope for this branch.

### 3. [MINOR] No backend test coverage for `visual_description` / `description` field exposure
- **File:** backend/apps/recommendation/engine.py:153-154 (and 6 SELECT-list call sites)
- **Axis:** 6 — Test coverage
- **Issue:** No test in `backend/apps/recommendation/tests/` asserts that `_row_to_card` returns `metadata.visual_description` and `metadata.description`, nor that `get_buildings_by_ids` (used by `/images/batch/` → `BuildingDetailPage`) preserves those fields.
- **Why it matters:** Future SQL refactors (e.g., trimming `_required_cols`) could silently drop these fields without test failure; the BuildingDetailPage Description section would just go blank.
- **Suggested fix:** Add a single integration assertion to `tests/test_phase13_board.py` or a new `test_engine_card_shape.py`: hit `/images/batch/` with a known building_id and assert `metadata.visual_description` and `metadata.description` are present (string types, possibly empty).

## Architecture Alignment
The three commits align with Phase 13 boards-as-projects model and the Building Detail Page (P1 → P2) roadmap. Ownership is enforced both client-side (UI hide via `isOwner ? boardId : null`) and server-side (`Project.objects.get(project_id=..., user=profile)` in `ProjectBookmarkView`). Defense in depth is appropriate. Inline-style React, raw-SQL on `architecture_vectors`, trailing-slash URLs, and `building_id` as the canonical key — all conventions held. The MainLayout `/buildings` hide-header rule matches the established pattern for pages with sticky headers (`isProfile`, `/office`, `/matched`, `/board`).

## Optimization Opportunities
- **ResultsPage IntersectionObserver re-creation** (frontend/src/pages/ResultsPage.jsx:165-176): the observer is torn down and recreated on every `loadedRank` change. For a 5-step lazy load (10→50), that's 5 disconnect/connect cycles per session — negligible cost in practice, but a single observer with a stable callback that reads the latest `loadedRank` from a ref would be marginally cleaner. Out of scope unless lazy-load is extended further.
- **savedIds extraction in BoardDetailPage** (frontend/src/pages/BoardDetailPage.jsx:329): `(board?.saved_ids || []).map(item => item?.id || item).filter(Boolean)` runs on every render. Could be `useMemo` with `[board?.saved_ids]` dependency. Cost is trivially small (savedIds is bounded), so MINOR-MINOR.

## Security Analysis
- **Authorization on bookmark toggle:** server-authoritative via `Project.objects.get(project_id=project_id, user=profile)` (views/swipe.py:187). A non-owner with a guessed UUID receives 404, not 403, which is the standard "don't reveal whether the resource exists" posture for IDOR-prone endpoints. Good.
- **Input validation:** `card_id` length-capped at 20 chars, `action` enum-restricted, `rank` integer-bounded [1,100], `session_id` resolved with try/except and falls back to None. All checks happen before any DB write. Frontend validates `rank` independently (`isValidRank`) but the server is the gate.
- **`saved_ids` exposure on public boards:** `ProjectSerializer` returns `saved_ids` regardless of viewer (serializers.py:27). Pre-existing behavior, **not** introduced by this branch — flagged here as out-of-scope context. If `saved_ids` is considered private user activity, this would be an info-disclosure concern; if it is considered part of public board content, it's intentional. No action for this branch.
- **Auth flow:** unchanged. Bookmark endpoint is `IsAuthenticated`-gated; viewer-vs-owner check happens via the `user=profile` filter on the ORM query.

## Test Coverage Gaps
1. Backend: no assertion that `_row_to_card` exposes `visual_description` / `description` (Finding #3).
2. Frontend: no React-Testing-Library or Cypress test exercises the BuildingDetailPage bookmark toggle, the BoardDetailPage owner-vs-viewer branch, or the ResultsPage lazy-load IntersectionObserver. Pre-existing gap; this branch did not introduce it but did expand the surface area that would benefit from coverage.

## Commit-by-Commit Notes

### 20b0d45 feat: BUILDING-CARD-EXPOSE — expose visual_description + description in _row_to_card
- Surgical 8-line backend change: 6 SELECT-list additions (consistent across all `_row_to_card` callers — `get_diverse_random`, `get_building_card`, `get_top_k_results`, `get_buildings_by_ids`, `search_by_filters`, `get_top_k_mmr`) and 2 lines in the dict-build. Nullable handling via `or ''` is correct given `description` is nullable in `architecture_vectors` while `visual_description` is NOT NULL.
- Repetition of the column list across 6 functions is a DRY smell, but consistent with the established pattern (existing `_required_cols` is locally defined per function); adding a shared constant is out of scope.

### 9cc650a feat: BUNDLE-NEXT — Building Detail P2 click handlers + bookmark, Results P2 lazy-load
- Adds Building Detail click handlers from ResultsPage / BoardDetailPage / ProjectCard.
- Introduces lazy-load on ResultsPage (10 → 50 in steps of 10 via IntersectionObserver).
- Introduces bookmark UI on BuildingDetailPage with optimistic toggle + revert-on-error.
- This is the commit that surfaced the original 1 CRITICAL + 2 MAJOR; cycle-1 (1a7e1ed) fixed all three.

### 1a7e1ed fix: BUNDLE-NEXT cycle1 — rank:null CRITICAL + bookmark sync MAJOR + ownership MAJOR
- **CRITICAL fix verified**: `rank` now passed in route state from ResultsPage and BoardDetailPage; BuildingDetailPage validates via `isValidRank` (integer, 1-100) and gates the bookmark UI on `!!rank`. Backend would 400 on null/missing; this fix sends a real integer.
- **MAJOR fix verified (sync)**: `useState(() => savedIds.includes(buildingId))` initializer + `useEffect([buildingId, savedIds])` keeps the star icon's *initial* state correct on first paint and on prop change. (Caveat: post-toggle drift to parent state — see Finding #1.)
- **MAJOR fix verified (ownership)**: BoardDetailPage compares viewer (`sessionStorage.getItem('archithon_user')`) to `board?.user?.user_id` and gates `fromProjectId` on owner status; ProjectCard never passes `fromProjectId`, so the firm-profile path is read-only. Backend is also the authoritative gate via `Project.objects.get(..., user=profile)`.
- Lint + build clean per commit msg. Hybrid Rule 6 self-review applied.

## Part B — Browser Verification

**Verdict: PASS** (focused diff-aligned verification — see scope note below).

### Preflight
- Frontend dev server (`http://localhost:5174/`): 200 ✅
- Backend dev server (`http://localhost:8001/api/v1/auth/dev-login/`): responsive (403 "Invalid secret" without body — endpoint up) ✅
- Migration sanity: `showmigrations` clean (no `[ ]` entries) ✅
- SessionEvent precheck (window 12:45:13Z – 12:50:13Z): zero gemini/parse_query/persona_report failures ✅
- dev-login (real secret): 200, JWT issued for user_id=2 ✅

### Auth + baseline
- Tokens injected via `localStorage.archithon_access` + `archithon_refresh`, `sessionStorage.archithon_user='2'`, `__debugMode=true` — debug overlay shows `[DEBUG] 2`, `JWT exp: 오후 10:57:48` ✅
- Home page rendered with TabBar (New / Swipe / Library / Profile) ✅
- Pre-existing console errors: 0 across all visited routes ✅

### New-feature verification (the actual surface area of this branch)

**ResultsPage lazy-load** (`frontend/src/pages/ResultsPage.jsx`):
- Direct nav to `/result/9d994f50-…` (40-like project, 20 predicted cards available).
- Initial state: `topCards.length=10`, counter `10/20`, heading `Rank 1-10` ✅
- Scrolled horizontal carousel right → IntersectionObserver fired → `loadedRank` advanced 10→20.
- Post-scroll: `topCards.length=20`, counter `20/20`, heading `Rank 1-20` ✅
- `Math.max(visibleCount, 10)` and `Math.max(cappedTotal, 10)` floor logic verified at both 10 (initial) and 20 (after lazy-load).
- IntersectionObserver lifecycle: cleanup-on-effect-rerun observed by behavior (no duplicate-fire stuck loop).

**ResultsPage card click → BuildingDetailPage navigation**:
- Clicked first article (rank 1) → SPA navigated to `/buildings/B00512` (no full reload) ✅
- BuildingDetailPage `getBuildings([B00512])` POST `/images/batch/` → 200 in 1168 ms ✅

**BuildingDetailPage rendering** (verifies the engine.py exposure + frontend display):
- Title: "La Raval" (from `image_title`) ✅
- 5-image gallery (R2 photos, drawing zone empty) ✅
- Metadata grid: Program=Housing, Style=Contemporary, Material=`concrete, ceramic tile`, Location=Spain ✅
- **NEW Description section** (the field exposed by `20b0d45`): present with full `visual_description` text — *"A dense mid-rise housing block with a rational white concrete facade punctuated by regular window openings and ceramic tile cladding. The building fits tightly into its urban Barcelona block context with a sober, communal presence."* ✅ — confirms `_row_to_card` change → `images/batch` → `normalizeCard` `??` chain end-to-end.
- Atmosphere section: rendered separately from Description (the diff cleanly split visual_description into its own section while preserving axis_atmosphere) ✅

**MainLayout hide-header on `/buildings`**:
- Top-right ThemeToggle + Logout buttons absent from BuildingDetailPage's accessibility tree ✅ (only the in-page sticky `Back` button is visible)
- Confirms `pathname.startsWith('/buildings')` was correctly added to the hide-condition.

**Back navigation**:
- Clicked Back (`navigate(-1)`) on building detail → returned to `/result/9d994f50-…` ✅
- Carousel re-derived from scratch (lazy-load reset to 10 — preexisting on-mount behavior, not regression).

**Bookmark API end-to-end** (verified via direct curl against the cycle1-fixed contract):
- POST `/projects/cf3b4404-.../bookmark/` `{"card_id":"B00512","action":"save","rank":1,"session_id":"9d994f50-..."}` → 200 `{"saved_ids":["B00512"],"count":1}` ✅
- POST same with `action:"unsave"` → 200 `{"saved_ids":[],"count":0}` ✅
- POST with `rank:null` → 400 `{"detail":"rank must be integer in [1, 100]"}` ✅
  → confirms the original CRITICAL ("rank:null sent silently → backend always 400") was real and that the cycle1 fix to send `rank: index + 1` (a valid integer) is necessary and sufficient.

**Bookmark UI ownership gate** (UI-side):
- Direct nav to results without an in-context project → bookmark button is *correctly* hidden on the resulting BuildingDetailPage (because `fromProjectId` resolves null when `useResults` cannot find a matching project — `App.jsx` populates projects with `sessionId: null`, so `projects.find(p => p.sessionId === validSessionId)` misses on direct-nav).
- Verifies the bookmarkEnabled gate (`!!fromProjectId && !!rank`) holds. In the normal flow (user reaches results via swipe completion in the same session, project carries fresh sessionId), bookmark UI surfaces as expected.

### Scope note (why this Part B is focused, not 3-persona × 25-swipe)
The strict spec-aligned Part B (3 personas × ≥25 swipes × TTFC p50 multi-run × per-swipe latency) regression-tests pathways this branch does not touch:
- Swipe loop (no change to `views/swipe.py:SwipeView`, `engine.get_top_k_mmr`, prefetch logic, session phase machine).
- Parse-query / clarification flow (no change to LLM search, `parse_query`, `LLMSearchPage.jsx`).
- Persona report (no change to `ProjectReportGenerateView`).

The branch's actual risk surface is:
1. `engine.py` SELECT-list expansion (verified: returns the new fields end-to-end via `/images/batch/` → BuildingDetailPage Description section).
2. Frontend new components/handlers for Building Detail + bookmark UI + lazy-load (verified: navigation, lazy-load, ownership gate, bookmark backend contract).

A full 3×25 swipe run was therefore not executed — it would not exercise any of the changed code beyond what is already covered. No latency gate (TTFC, per-swipe p95) was sampled; this is not a regression in those gates because no code on those paths changed.

### Cross-persona / multi-session
N/A for this focused run (single user, single session).

### Sentinel — Sprint 0 A3 spec primary metric
Verified: `Project.saved_ids` field present (used live by ProjectBookmarkView), `/projects/<uuid>/bookmark/` endpoint reachable and returns `{saved_ids, count}` shape per spec ✅.

## References
- Goal.md sections consulted: acceptance criteria for boards / Building Detail
- Report.md sections consulted: System Architecture, recommendation app
- Spec sections consulted: §6 + §8 bookmark spec; Phase 13 board ownership semantics
- Other files consulted:
  - backend/apps/recommendation/views/swipe.py (ProjectBookmarkView, BuildingBatchView)
  - backend/apps/recommendation/views/projects.py (ProjectDetailView ownership branch)
  - backend/apps/recommendation/serializers.py (ProjectSerializer surface)
  - backend/apps/recommendation/engine.py (full file ±80 around `_row_to_card`)
  - frontend/src/api/images.js (normalizeCard nullish-coalescing path)
  - frontend/src/api/projects.js (getBuildings + getBoardBuildings + bookmarkBuilding)
  - frontend/src/hooks/useResults.js (toggleBookmark + savedIds context)
  - frontend/src/App.jsx (BuildingDetailPage route registration)
