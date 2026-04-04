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

### Phase 4.5: Swipe Bug Fix (URGENT)
13. **B5** -- Fast swipe race condition (no swipe lock, concurrent requests)
14. **B6** -- Card suddenly changes (prefetch response overwrites current card)
15. **B2v2** -- Same cards still repeating (prefetch uses stale exposed_ids)
16. **B3v2** -- Pool exhaustion during exploring phase returns null

### Phase 5: New Features
17. **UX2** -- Persona Report AI image generation
18. **AUTH1** -- Kakao / Naver OAuth (deferred — future)
19. **F3** -- Mobile optimization

### Phase 6: Cleanup
20. **INFRA1** -- Backend integration tests
21. **INFRA2~4** -- Idempotency, total_rounds, console.error
22. **BE2** -- Gemini error handling improvement

---

## Open

### Bug Fix
#### B5. 빠른 스와이프 시 레이스 컨디션 ⚡ Priority 1
`handleSwipeCard` 진입 시 `isSwipeLoading` 체크 없음 → 연속 스와이프가 동시에 실행됨.
`SwipePage.jsx onCardLeftScreen`도 loading 체크 없이 `onSwipe` 호출.
두 번의 `recordSwipe`가 동시 발생 → prefetch 큐 오염, 상태 불일치.
- [ ] `handleSwipeCard` 시작 시 `if (isSwipeLoading) return` 가드 추가
- [ ] `onCardLeftScreen`에 loading 체크 추가
- [ ] `isSwipeLoading`을 useRef로 변경 (setState 비동기 문제 방지)

#### B6. 카드가 갑자기 바뀜 (prefetch 응답 충돌) ⚡ Priority 1
optimistic swap 후 backend 응답이 도착하면 `result.next_image.image_id !== savedPrefetch.image_id`
체크에서 currentCard를 덮어씀 (App.jsx:277-295).
사용자가 보고 있는 카드가 갑자기 다른 카드로 바뀌는 현상.
- [ ] backend 응답이 현재 표시 중인 카드와 다를 때 덮어쓰지 않기
- [ ] prefetch 큐만 업데이트하고 currentCard는 유지
- [ ] stale response 방지용 swipe sequence number 도입 검토

#### B2v2. 같은 카드 여전히 반복 (prefetch stale exposed_ids) ⚡ Priority 1
`views.py:465-498`에서 prefetch 계산 시 `session.exposed_ids`가 아직 DB에 저장 안 됨.
동시 요청 시 두 번째 요청이 DB에서 옛날 exposed_ids를 로드 → 같은 카드 prefetch.
- [ ] exposed_ids 업데이트를 prefetch 계산 전에 session.save() 호출
- [ ] 또는 select_for_update()로 세션 동시 접근 방지

#### B3v2. Exploring 단계에서 풀 소진 시 null 반환
`views.py:436-437`에서 `farthest_point_from_pool`이 None 반환 시 next_card=None으로 전달.
analyzing 단계는 action card fallback이 있지만 exploring 단계는 없음.
- [ ] exploring 단계에서도 풀 소진 시 action card 또는 converged 전환 추가

### Algorithm

#### A2. Hyperparameter optimization -- validated, full run pending
Smoke test (3 personas x 5 trials) passed. No code changes needed.
- [x] Smoke test passed (--personas 3 --trials 5)
- [ ] Run algo-tester: 100 personas x 200 trials
- [ ] Evaluate results vs baseline
- [ ] Apply optimized params if improvement found

### Frontend
#### F3. Mobile layout unoptimized
375px viewport touch targets, card gestures untested.
- [ ] SwipePage touch target audit
- [ ] Mobile Safari card flip test
- [ ] TabBar spacing adjustment

### Backend
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
#### UX2. Persona Report AI image generation (nano banana)
Generate architecture images based on user taste in final report.
- [ ] Image generation API selection
- [ ] Persona report generated image display component
- [ ] Backend image generation endpoint

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
- [x] `n_init=10` → `n_init=3` (3x faster clustering)
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
