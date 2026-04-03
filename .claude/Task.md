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

### Phase 2: Stability
5. **F1** -- Swipe error handling + state sync
6. **A3** -- Recency weight math protection
7. **BE1** -- API timeout/retry

### Phase 3: Performance
8. **A1** -- Pool caching + KMeans caching + prefetch
9. **A2** -- Algo-tester 100 personas

### Phase 4: UX Enhancement
10. **UX1** -- Tutorial popup
11. **UX3** -- Action card message improvement
12. **F2** -- Image load failure handling

### Phase 5: New Features
13. **UX2** -- Persona Report AI image generation
14. **AUTH1** -- Kakao / Naver OAuth
15. **F3** -- Mobile optimization

### Phase 6: Cleanup
16. **INFRA1** -- Backend integration tests
17. **INFRA2~4** -- Idempotency, total_rounds, console.error
18. **BE2** -- Gemini error handling improvement

---

## Open

### Algorithm
#### A1. Swipe performance optimization -- Priority 2
Repeated pool embedding fetch + KMeans re-clustering every swipe.
- [ ] Pool embedding session-level caching
- [ ] KMeans centroid caching (recompute only on new like)
- [ ] `n_init=10` -> `n_init=3`
- [ ] Image preloading: 1 -> 2 cards

#### A2. Hyperparameter optimization unverified
Algo-tester built with Optuna but only 3-persona smoke-test done.
- [ ] Run algo-tester: 100 personas x 200 trials
- [ ] Evaluate results vs baseline
- [ ] Apply optimized params if improvement found

#### A3. Recency weight math protection missing
`engine.py:502-513`: `round_num < entry_round` causes weight > 1.
- [ ] `max(0, round_num - entry_round)` guard

### Frontend
#### F1. Swipe error handling absent -- Priority 2
`App.jsx:211-262`: `api.recordSwipe()` has no try-catch.
- [ ] Add try-catch + error toast to `handleSwipeCard`
- [ ] Move local state update after backend response
- [ ] Add retry logic on network failure

#### F2. Image load failure handling missing
`SwipePage.jsx:88-102`: no retry, no fallback on 404/500.
- [ ] Image load failure retry (1x)
- [ ] Fallback placeholder image

#### F3. Mobile layout unoptimized
375px viewport touch targets, card gestures untested.
- [ ] SwipePage touch target audit
- [ ] Mobile Safari card flip test
- [ ] TabBar spacing adjustment

### Backend
#### BE1. API timeout/retry logic missing
`client.js:28-58`: infinite fetch timeout, only 401 retry.
- [ ] 10s fetch timeout
- [ ] Retry with exponential backoff

#### BE2. Gemini API error feedback missing
`services.py:66-98`: generic error on Gemini failure.
- [ ] Gemini API error logging
- [ ] Retry logic (1x)
- [ ] Clear error message for persona report failure

### Auth
#### AUTH1. Kakao / Naver OAuth not implemented
Google OAuth only. Korean users need domestic login.
- [ ] Kakao social auth backend + frontend button
- [ ] Naver social auth backend + frontend button

### UX/Design
#### UX1. Tutorial popup
First-time swipe page usage guide with "don't show again" checkbox.
- [ ] Popup component (checkbox + localStorage)
- [ ] Conditional display on SwipePage entry
- [ ] Guide content (swipe directions, card flip, gestures)

#### UX2. Persona Report AI image generation (nano banana)
Generate architecture images based on user taste in final report.
- [ ] Image generation API selection
- [ ] Persona report generated image display component
- [ ] Backend image generation endpoint

#### UX3. Action card message improvement
Current message is ambiguous about analysis vs completion stage.
- [ ] Clearer action card wording
- [ ] Korean language support review

### Infrastructure
#### INFRA1. Backend integration tests missing
All testing is manual or web-tester dependent.
- [ ] pytest + test DB config
- [ ] Auth flow tests
- [ ] Swipe session lifecycle tests

#### INFRA2. Idempotency key not session-scoped
`SwipeEvent.objects.filter(idempotency_key=...)` is global.
- [ ] Scope idempotency to session + user
- [ ] Cross-session collision risk verification

#### INFRA3. total_rounds model field cleanup
`AnalysisSession.total_rounds` is unused (default 20, set to 999).
- [ ] Remove total_rounds field migration

#### INFRA4. console.error cleanup
Production code has multiple `console.error()` calls.
- [ ] Replace with proper error handling or remove

---

## In Progress

(none)

---

## Resolved

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
