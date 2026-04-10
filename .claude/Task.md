# Task Board

> Auto-updated by orchestrator. When you request work, orchestrator reads Goal.md
> + current code, then adds/updates tasks here before executing.
> Categories: Algorithm, Frontend, Backend, Auth, UX/Design, Infrastructure

---

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

---

## Open

#### B3v2. Exploring phase pool exhaustion returns null (LOW PRIORITY -- deferred)
`views.py:436-437` farthest_point_from_pool returns None when pool exhausted.
analyzing phase has action card fallback but exploring phase does not.
- [ ] exploring phase pool exhaustion -> action card or converged transition

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

### Phase 11: Frontend Bug Fix -- 2026-04-05

#### B7. Keyboard swiping blocked in gallery mode -- 2026-04-05
`SwipePage.jsx` line 426: `galleryOpen` guard blocked all keyboard events during gallery view.
Users expected ArrowLeft/ArrowRight to still trigger like/dislike even when viewing gallery photos.
- [x] Remove `galleryOpen` from keyboard handler guard
- [x] Close gallery before triggering swipe on ArrowLeft/ArrowRight
- [x] Keep drag swipe prevention in gallery mode (TinderCard preventSwipe stays as-is)
- Commit: f3afb26

#### B8. Card disappears after swipe, requires F5 reload -- 2026-04-05
`App.jsx` handleSwipeCard: race condition when non-instant path gets null next_image from API,
and catch block reverts to wrong card when canInstantSwap was true.
- [x] Non-instant path: never set currentCard to null from API response
- [x] Catch block: only revert to swipedCard when canInstantSwap was false
- [x] Catch block: when canInstantSwap was true, preserve current card (user is already looking at different card)
- Commit: f3afb26

### Phase 10: Swipe API Latency Fix -- 2026-04-05

#### PERF1. Non-algorithm swipe API latency optimizations -- 2026-04-05
Web testing revealed ~2-5% of swipes take 5-10s (vs normal 2-3s). Root causes were non-algorithm overhead.
engine.py was OFF-LIMITS (no algorithm changes).
- [x] views.py: Cache pool_embeddings once per request (eliminate redundant get_pool_embeddings call in prefetch section)
- [x] views.py: Batch dislike embedding fetch (replace N individual get_building_embedding calls with single get_pool_embeddings)
- [x] settings.py: Add CONN_MAX_AGE=600 for DB connection reuse (10 minutes)
- [x] App.jsx: Add 1.5s timeout to preloadImage() so UI does not block on slow CDN
- Commit: 607e143

### Phase 9: E2E Runner Fix -- 2026-04-07

#### TEST3. Fix screenshots, card visibility, timing breakdown -- 2026-04-07
Three E2E runner fixes validated across 57 personas (20 loops x 3 personas).
- [x] Issue 1: Screenshots on all swipe steps (was skipping 20/30 via modulo conditional)
- [x] Issue 2: Card image visibility check after screenshot (detects blank card renders)
- [x] Issue 3: Timing breakdown (gesture/api/card/image) in step metadata and dashboard
- [x] Bonus: 3-strategy swipe gesture (locator 3s timeout -> viewport-center drag -> keyboard)
- [x] Dashboard: timing display in step cards + performance table columns
- [x] Fixed undefined _wait_for_swipe_response call in action card handler
- Results: 89.5% completion rate (51/57), 0 gesture failures, 1.43% error rate per swipe
- Commit: db3f768

#### TEST2. Rewrite runner.py to match actual frontend UI flow -- 2026-04-06
Runner rewritten to match actual frontend after Gemini UX4 overhaul.
- [x] Follow actual flow: Home ("Create new folder") -> /new (project name) -> /search (LLM chat) -> /swipe (mouse drag) -> /library (results + report)
- [x] Use text selectors and aria-labels instead of CSS class guessing
- [x] Mouse drag swipe gesture (not keyboard -- bypasses swipedCardId guards)
- [x] No silent except:pass -- all errors logged and recorded
- [x] Proper timeouts for LLM (30s) and Gemini report (20s) calls
- [x] Extract card metadata from visible h2/span text
- [x] Dismiss tutorial popup via localStorage on dev-login

### Gemini UI/UX Polish -- 2026-04-06

#### UX4. Gemini UX Overhaul (Chat, Swipe, Tutorial) -- 2026-04-06
Executed flawlessly by Gemini Antigravity Agent.
- [x] LLMSearchPage: Constrained message bubbles to 100vw to prevent ResultStrip horizontal scroll from stretching the whole page.
- [x] SwipePage: Added `keydown` event listener for PC ArrowLeft/ArrowRight swiping.
- [x] SwipePage: Removed bulky Like/Dislike action buttons to maximize elegant layout.
- [x] TutorialPopup: Replaced solid dark background with a semi-transparent blur overlay.
- [x] TutorialPopup: Responsive hints (`matchMedia`) shown based on touch vs cursor (Swipe gestures vs Arrow keys).
- [x] TutorialPopup: Removed awkward 'Don't show again' checkbox in UI; taps dismiss immediately.

### Phase 8: E2E Testing Infrastructure -- 2026-04-05

#### TEST1. E2E visual test runner module -- 2026-04-05
New `web-testing/` module for Playwright-based E2E testing with persona-driven scenarios.
- [x] `research/persona.py` -- PersonaProfile dataclass, template + LLM generation modes
- [x] `research/scenarios.py` -- TestScenario dataclass, keyword-overlap swipe decisions
- [x] `runner/runner.py` -- Playwright E2E orchestration (dev-login, search, swipe, results, report)
- [x] `runner/collector.py` -- StepRecord, ApiCallRecord, ErrorRecord, Collector class
- [x] `runner/reporter.py` -- report.json generation with bottleneck classification
- [x] `runner/feedback.py` -- feedback.json with endpoint-to-source-file mapping
- [x] `run.py` -- CLI entry point (--personas, --mode, --auto-fix, --loop, --dashboard-only)
- [x] `dashboard/` -- Static HTML/JS/CSS SPA (persona panel, step viewer, error panel, perf table)
- [x] `.gitignore` updated for web-testing/reports/ and web-testing/dashboard/data/
- [x] `CLAUDE.md` updated with web-testing documentation
- Commit: 20337da

### Phase 7: Codebase Audit Fixes -- 2026-04-04

#### AUDIT1. Remove unused deps, dead code, consolidate tests, fix deprecations -- 2026-04-04
Full codebase audit cleanup covering 9 items.
- [x] Removed unused frontend deps: @react-spring/web, react-masonry-css, @playwright/test
- [x] Removed dead CSS: .masonry-grid, .masonry-grid-col, .swipe-card, .swipe-card:active
- [x] Removed VITE_GEMINI_API_KEY from frontend/.env.example
- [x] Consolidated backend tests: migrated 8 tests (ProjectCRUD + BuildingBatch) from apps/recommendation/tests.py to backend/tests/test_projects.py (pytest style)
- [x] Deleted backend/tools/__init__.py (empty, unused)
- [x] Moved optuna to backend/requirements-dev.txt (not needed in production)
- [x] Added .pytest_cache/ and node_modules/ to .gitignore
- [x] Replaced deprecated STATICFILES_STORAGE with STORAGES dict (Django 4.2+ format)
- [x] Removed dead fallback `|| result.predicted_like_images` from client.js getResult()
- [x] All 23 backend tests pass, frontend build succeeds

### Phase 6: Cleanup -- 2026-04-04

#### INFRA1. Backend integration tests -- 2026-04-04
Set up pytest-django with SQLite in-memory test database.
- [x] pytest.ini + conftest.py with SQLite override and JWT fixtures
- [x] test_auth.py: 7 tests (Google login mock, token refresh valid/invalid, logout blacklist, dev-login correct/wrong secret)
- [x] test_sessions.py: 8 tests (session creation, swipe like/dislike, idempotent swipe, invalid action, exploring->analyzing, analyzing->converged)
- [x] All engine.py raw SQL calls mocked (architecture_vectors is external)
- [x] pytest + pytest-django added to requirements.txt
- Commit: 324ab91

#### INFRA2~4. Idempotency + total_rounds + console.error -- 2026-04-04
Combined three small cleanups into one commit.
- [x] INFRA2: Idempotency check scoped to session + idempotency_key (was global). SwipeEvent unique_together constraint added.
- [x] INFRA3: Removed unused total_rounds field from AnalysisSession model + migration 0006. Removed from _progress, session creation, and response.
- [x] INFRA4: Removed console.error from 8 locations in production UI code (App.jsx, LoginPage, LLMSearchPage, FavoritesPage). Kept 4 in api/client.js graceful catch blocks.
- Commit: 55c7249

#### BE2. Gemini error handling improvement -- 2026-04-04
Improved Gemini API error handling with retry, logging, and structured errors.
- [x] _retry_gemini_call helper: 1 retry with 1s delay, logs error type and message per attempt
- [x] parse_query: uses retry wrapper, logs specific error on failure
- [x] generate_persona_report: raises ValueError/RuntimeError with descriptive messages instead of returning None
- [x] ProjectReportGenerateView: returns 502 with {detail, error_type} on Gemini failure
- [x] Frontend: FavoritesPage shows specific error text below Generate button
- [x] Frontend: handleGenerateReport propagates errors to caller (was silently swallowed)
- Commit: 5e23479

### Phase 5: New Features -- 2026-04-04

#### UX2. Persona Report AI image generation -- 2026-04-04
Generate architecture images based on user taste profile using Google Imagen 3.
- [x] Research: google-genai SDK v1.47.0 includes `client.models.generate_images()` (Imagen 3)
- [x] Backend: `generate_persona_image()` in services.py constructs architecture prompt from report attributes
- [x] Backend: `ProjectReportImageView` endpoint `POST /projects/{id}/report/generate-image/`
- [x] Backend: `report_image` TextField on Project model (base64 storage)
- [x] Frontend: `generateReportImage()` API function in client.js
- [x] Frontend: "Generate AI Architecture Image" button in PersonaReport section
- [x] Frontend: Image display with base64 data URI, error/loading states
- [x] Frontend: Image state propagated to App.jsx (persists across navigation)
- [x] Frontend: Image synced from backend on login via `report_image` field
- Commit: 797e619

#### F3. Mobile optimization (375px viewport) -- 2026-04-04
iPhone safe area support and touch target compliance.
- [x] `viewport-fit=cover` in meta tag for safe area support
- [x] `env(safe-area-inset-bottom)` on all page heights: calc(100vh - 64px - env(...))
- [x] TabBar: `content-box` sizing with safe area bottom padding
- [x] Fixed-bottom elements adjusted (LLM input bar, start swiping panel, ProjectSetup action bar)
- [x] All back buttons meet 44px minimum touch target (Apple HIG)
- [x] SwipePage top padding reduced 32px -> 20px for small screens
- [x] Card title 2-line clamp (`-webkit-line-clamp: 2`) prevents text overflow
- [x] CSS variable `--safe-area-bottom` added for future use
- [x] Desktop unaffected (env() fallback = 0px)
- Commit: 3a0b305

### Phase 4.5: Swipe Bug Fix -- 2026-04-04

#### B5. Fast swipe race condition -- 2026-04-04
Concurrent swipe requests corrupted prefetch queue state.
- [x] `swipeLock` useRef guard added to `handleSwipeCard` entry point
- [x] `onCardLeftScreen` checks swipeLock before calling `onSwipe`
- [x] useRef (not useState) to avoid async setState race
- Commit: 7a5a8e1

#### B6. Card suddenly changes (prefetch response overwrites currentCard) -- 2026-04-04
canInstantSwap path overwrote `currentCard` when backend response diverged from saved prefetch.
- [x] Removed `currentCard` overwrite in canInstantSwap path
- [x] Only prefetch queue updated when backend response differs; currentCard preserved
- Commit: 7a5a8e1

#### B2v2. Same cards still repeating (prefetch stale exposed_ids) -- 2026-04-04
`session.exposed_ids` not yet saved to DB when prefetch was computed, causing stale reads on concurrent requests.
- [x] `session.save()` called before prefetch calculation in views.py
- [x] `select_for_update()` on session query to prevent concurrent stale reads
- Commit: 7a5a8e1

### Phase 4: UX Enhancement -- 2026-04-03

#### UX1. Tutorial popup -- 2026-04-03
First-time swipe page usage guide with "don't show again" checkbox.
- [x] TutorialPopup component (4 steps: swipe right/left, tap card, AI learns)
- [x] Semi-transparent overlay, close (X) button, "Don't show again" checkbox
- [x] localStorage key `archithon_tutorial_dismissed` persists dismissal
- [x] Only shows on main swipe view (not completed/empty states)
- [x] Inline styles matching existing dark gradient theme
- Commit: eb9dc74

#### UX3. Action card message improvement -- 2026-04-03
Current message was ambiguous about analysis vs completion stage.
- [x] Backend: `build_action_card()` now returns `action_card_message` + `action_card_subtitle`
- [x] Title changed from "Analysis Complete" to "Your Taste is Found!"
- [x] Message: clear explanation of what happened; subtitle: explains swipe directions
- [x] Frontend: ActionCard renders subtitle, "View results" hint highlighted in accent color
- [x] `normalizeCard()` passes `action_card_subtitle` through
- Commit: 1cb814d

#### F2. Image load failure handling -- 2026-04-03
`SwipePage.jsx`: no retry, no fallback on 404/500 image errors.
- [x] On first `onError`: retry with `?retry=1` cache-busting param
- [x] On second failure: show styled fallback (gradient bg + building icon + "Image unavailable")
- [x] Uses `imgRetried` ref (not state) to avoid re-render loops
- [x] Inline styles consistent with existing card design
- Commit: b660453

### Phase 3: Performance -- 2026-04-03

#### A1. Swipe performance optimization -- 2026-04-03
Repeated pool embedding fetch + KMeans re-clustering on every swipe caused latency spikes.
- [x] Pool embedding session-level caching (frozenset key, max 50 entries)
- [x] KMeans centroid caching (like-vector fingerprint + round_num key, max 20 entries; recompute only on new like)
- [x] `n_init=10` -> `n_init=3` (3x faster clustering)
- [x] Double prefetch: backend returns `prefetch_image_2`, frontend buffers 2 cards with queue shifting
- Commit: 1eedcda

### Phase 2: Stability -- 2026-04-03

#### F1. Swipe error handling + state sync -- 2026-04-03
`App.jsx:211-262`: `api.recordSwipe()` had no try-catch. Network failure = UI state out of sync with backend.
- [x] Add try-catch + error toast to `handleSwipeCard`
- [x] Move local state update (swipedIds, likedBuildings) after backend response
- [x] Add 1 retry on network error, revert card on failure
- [x] Auto-dismissing error toast (3s) with inline styles
- Commit: 1341036

#### A3. Recency weight math protection -- 2026-04-03
`engine.py:502-513`: `round_num < entry_round` caused weight > 1 (exponential amplification).
- [x] `max(0, round_num - entry_round)` guard in `_apply_recency_weights`
- Commit: dc38d41

#### BE1. API timeout/retry logic -- 2026-04-03
`client.js:28-58`: fetch had no timeout (infinite by default), only retried on 401.
- [x] 10s AbortController timeout on all fetch calls
- [x] Network error retry with exponential backoff (2 retries, 300ms/900ms)
- [x] Timeout on token refresh and dev-login paths
- [x] Existing 401 refresh logic preserved unchanged
- Commit: ddad1ae

### Phase 1: Critical Bug Fix -- 2026-04-03

#### B4. Mobile Google login failure -- 2026-04-03
Google popup works, account selection succeeds, but `onSuccess` -> `api.socialLogin()` fails on mobile Safari.
Root cause: implicit flow access_token unreliable on mobile Safari.
- [x] Switch to `flow: 'auth-code'` in LoginPage.jsx (sends `code` not `access_token`)
- [x] Backend GoogleLoginView handles both `access_token` and `code` flows
- [x] Auth-code exchange via Google token endpoint with `redirect_uri: 'postmessage'`
- [x] Added `onNonOAuthError` callback for popup-blocked errors
- [x] Detailed error messages (backend error details shown to user instead of generic message)
- [x] Detailed backend logging for Google API failures
- [x] CORS: added `http://localhost:5173` to default origins, `CORS_ALLOW_CREDENTIALS = True`
- Commits: a3c92df

#### B1. "View Result" button appears too early -- 2026-04-03
`showExit` was true when `phase !== 'exploring'`, showing button during 'analyzing'.
- [x] Changed condition to `phase === 'converged' || phase === 'completed'`
- Commits: 0ff0843

#### B2. Same cards repeating -- 2026-04-03
Dislike fallback path didn't explicitly track `fallback_id` in `exposed_ids`.
- [x] Added `fallback_id` to `exposed_ids` immediately after selection
- [x] Added duplicate check before appending to `exposed_ids`
- Commits: d914caf

#### B3. "No buildings match your criteria" -- 2026-04-03
`SessionCreateView` returned 404 with no fallback when pool was empty.
- [x] Added 3-tier filter relaxation: original -> drop geo/numeric -> random pool
- [x] `filter_relaxed` flag in API response
- [x] Frontend shows subtle notice when filters are relaxed
- [x] Improved fallback message text
- Commits: 60a0103

### Algorithm
#### Embedding normalization bug -- 2026-04-01
Raw embeddings had L2 norm ~3.3, `farthest_point_from_pool` returned None.
- [x] Normalize in `get_pool_embeddings()`
- [x] Fix recency weighting -- KMeans uses `sample_weight`

#### Missing engine functions crash analyzing phase -- 2026-04-03
`views.py:317` called `compute_taste_centroids()` which didn't exist.
`views.py:461` passed `round_num` to `get_top_k_mmr()` which didn't accept it.
- [x] Create `compute_taste_centroids()` in engine.py
- [x] Add `round_num` to `get_top_k_mmr()`
- [x] Remove dead `select_next_image()`
- [x] Remove 5 ghost params from settings

#### Algorithm tester upgraded -- 2026-04-03
Replaced random search with Optuna Bayesian optimization.
- [x] Add 2 missing params (max_consecutive_dislikes, top_k_results)
- [x] Add dislike fallback simulation
- [x] Add exposed_ids exclusion from precision measurement
- [x] Seed production baseline as first Optuna trial

### Frontend
#### gallery_drawing_start dropped by normalizeCard -- 2026-04-01
Drawings rendered with wrong background-size on card back.
- [x] Add field to `normalizeCard()` mapping

### Infrastructure
#### Action card paths lack transaction safety -- 2026-04-01
- [x] Add `@transaction.atomic()` + `update_fields` to action card views

#### Documentation system created -- 2026-04-03
- [x] Created WORKFLOW.md (agent system overview)
- [x] Created algo-tester agent definition
- [x] Removed duplicate conventions from agent files
- [x] Added PRD.md references to orchestrator, reviewer, algo-tester

#### Documentation system redesign -- 2026-04-03
Consolidated 3 overlapping docs (PRD.md, PROJECT.md, REPORT.md) into purpose-specific files.
- [x] Created Goal.md (vision + acceptance criteria)
- [x] Created Task.md (problem board with history)
- [x] Created Report.md (live system reference with diagrams)
- [x] Created research/algorithm.md (math formulas + hyperparameters)
- [x] Created research agent definition
- [x] Updated all agent file references
- [x] Trimmed CLAUDE.md architecture sections (now in Report.md)
- [x] Deleted PRD.md, PROJECT.md, REPORT.md
