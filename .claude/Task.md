# Task Board

> Auto-updated by orchestrator. When you request work, orchestrator reads Goal.md
> + current code, then adds/updates tasks here before executing.
> Categories: Algorithm, Frontend, Backend, Auth, UX/Design, Infrastructure

---

## Handoffs

> Short-lived cross-terminal signals for the **review / push** and **antigravity / main**
> cycles. Each terminal (main / review / antigravity) reads this section at session start.
> Oldest entries expire naturally — keep ~10 most recent.
>
> **Research handoff placement**:
> - `[SPEC-READY]` marker (persistent "spec exists at this path") goes in `## Research Ready` below.
> - **Spec version bumps** (`SPEC-UPDATED`) go here in Handoffs — time-sensitive signals that
>   main terminal picks up at session start. Do not duplicate `[SPEC-READY]` here;
>   it belongs in `## Research Ready`.
>
> Signal types for this section:
> - `REVIEW-REQUESTED: <sha>` — reporter (main pipeline) → review terminal; run `/review` next (or just say "리뷰해줘" / "review please" — natural language triggers the unified workflow per CLAUDE.md "Natural language review trigger").
> - `REVIEW-PASSED: <sha>` — review terminal → user; review passed (Part A static + Part B browser when applicable + Part C drift checks). Run `git push` manually from the review terminal itself (no context-switch to main needed). On `PASS-WITH-MINORS` verdict the signal inlines `<K> MINOR noted (see .claude/reviews/latest.md)` so the count is visible at a glance; MINORs are non-blocking for push.
> - `REVIEW-ABORTED: <sha> — <reason>` — review terminal → main; review verdict was PASS but drift was detected during the review. `HEAD advanced …` → re-run `/review` on the new HEAD. `origin/main moved …` → `git pull --rebase` then re-review.
> - `REVIEW-FAIL: <sha> — <summary>` — review terminal → main; run fix loop via orchestrator (max 2 cycles).
> - `MOCKUP-READY: <page>` — antigravity → main; page is ready for API integration pass.
> - `SPEC-UPDATED: vX.Y → vX.Z — <sections> — <summary>` — research terminal → main; spec at `research/spec/requirements.md` bumped to new version. Main reads only the affected sections, not the whole spec. If the change invalidates in-progress work, main's orchestrator stops and asks user.

<!-- Append new handoff entries here. Format: `- [YYYY-MM-DD] <SIGNAL>` -->

- [2026-04-22] REVIEW-FAIL: d320166 — 0 CRITICAL, 3 MAJOR; see .claude/reviews/latest.md
- [2026-04-22] REVIEW-PASSED: b5931ab — safe to push; fix-loop resolves all findings from d320166 (one was my misread, correctly dismissed)
- [2026-04-22] REVIEW-PASSED: d12b2d4 — drift checks passed; run `git push` manually from this terminal
- [2026-04-25] SPEC-UPDATED: initial → v1.0 — search flow requirements spec v1.0 published at research/spec/requirements.md. Section 11 consolidates actionable directives from all 12 research reports (previous per-topic RESEARCH-READY markers removed — see `research/search/**` files directly for reasoning archive if needed). Main terminal: read the spec and plan implementation independently.
- [2026-04-25] REVIEW-REQUESTED: 3ee9c77 — convergence detection signal-integrity fixes (Topic 10 Option A); run `/deep-review` next.
- [2026-04-25] REVIEW-PASSED: ded38be — drift checks passed, 1 MINOR noted (see .claude/reviews/latest.md); run `git push` manually from this terminal
- [2026-04-25] REVIEW-REQUESTED: 8bf73b8 — pool-score normalization (Topic 12 A1); run `/deep-review` next.
- [2026-04-25] REVIEW-REQUESTED: f04646f — max_consecutive_dislikes 10 -> 5 (Section 5.1 A2); run `/deep-review` next.
- [2026-04-25] REVIEW-REQUESTED: 190c830 — Project schema migration (A3): liked_ids intensity shape + saved_ids field; run `/deep-review` next (UI-affecting paths in scope — recommend `/deep-web-test` after).
- [2026-04-25] REVIEW-PASSED: 88f0532 — drift checks passed, 1 MINOR noted (see .claude/reviews/latest.md); run `git push` manually from this terminal
- [2026-04-25] REVIEW-FAIL: 88f0532 — **stale: PASSED above is Part A (static) only.** `/deep-web-test` (Part B) ran AFTER and FAILed: migration 0007 not applied to running dev DB → POST /api/v1/analysis/sessions/ returns 500 ("column saved_ids does not exist"). **Two fixes needed** — see `.claude/reviews/latest.md` "Post-test Addendum" section: (1) immediate: `cd backend && python3 manage.py migrate` + restart runserver; (2) systemic: orchestrator pipeline gap — back-maker writes migration FILES but no agent runs `manage.py migrate` against the dev DB, so subsequent agents work on stale schema. Recommended Tier 1 fix: add migrate-after-migration rule to `.claude/agents/back-maker.md`. Note: HEAD has since advanced to 6984993 (unification commit) — after fixes, re-run unified `/review` on origin/main..HEAD (9 commits), not on the stale 88f0532 range.
- [2026-04-25] REVIEW-FAIL: 5d85b90 — static review PASS but browser test FAIL (Persona Brutalist time-to-first-card 5496 ms > 4000 ms hard ceiling; LLM produced "trouble understanding" + diverse_random fallback for query "concrete brutalist museum"); see .claude/reviews/latest.md. **No source bug** — Part A clean (1 MINOR: orchestrator.md Step 2.5 hardcodes `recommendation` app filter, should match review.md Step B1bb's app-agnostic check). Likely cause: upstream Gemini API latency / quality jitter. The migration-gap fix (`5d85b90` 3-tier guard) itself works correctly: B1bb backstop PASSED (no unapplied migrations detected). Decision needed: (a) re-run /review later (transient), (b) investigate parse-query latency, or (c) loosen spec budget if 5s is the new normal.
- [2026-04-25] SPEC-UPDATED: v1.0 → v1.1 — Sections 3, 4, 6, 10, 11 + new 11.1. Incorporates findings from 10 post-spec investigations (`research/investigations/01-10`; index at `research/investigations/README.md`). Highlights for main: (a) **NEW Section 11.1 IMP-1**: `engine.py:410-448 farthest_point_from_pool()` correctness bug (max-max → max-min, one-line fix; bundle with NumPy vectorization for 20-50× speedup). (b) **Section 11 Topic 01 corrected**: injection point `get_top_k_mmr()` → `create_bounded_pool() q_text` parameter; Topic 01 needs Topic 03 v_initial as RRF vector probe (ship Topic 03 first, Topic 01 second). (c) **Section 6 logging**: new events `pool_creation` / `cohort_assignment` / `probe_turn` + `swipe.timing_breakdown` (lock_ms / embed_ms / select_ms / prefetch_ms / total_ms) + `bookmark.rank_corpus`. (d) **Section 4**: per-swipe latency 측정 정의 명확화 (backend RTT vs user-visible) + V_initial bit hypothesis 가 corpus-wide narrowing 임을 명시 (pool-internal 만으로는 ~2.9 bits 부족) + A-1 row 에 γ retune Optuna search space + B-1 row 에 Option F selection mechanism. (e) **Section 11 Topic 02 ∩ Topic 04**: rerank-then-diversify (Option α) — single `q_i` swap composition. (f) **Section 11 Topic 11**: Gonzalez bound 은 IMP-1 fix 의존. (g) **Section 10**: open #5/#7 resolved (cross-ref investigation 06), 신규 #15 (conversation history persistence). Non-breaking — main 의 진행 중 작업 (Topic 10/12, Section 5.1 trigger, A-1 schema migration) 과 무관. 5d85b90 의 latency FAIL 관련해서는 `research/investigations/01-swipe-latency-feasibility.md` 의 4-step 최적화 경로 참조.
- [2026-04-25] REVIEW-REQUESTED: 2f8a943 — orchestrator Step 2.5 showmigrations app-agnostic (Part A MINOR fix from /review on 5d85b90); run `/review` next.
- [2026-04-25] REVIEW-REQUESTED: a9305e4 — IMP-1 farthest_point max-min correctness + NumPy vectorization; run `/review` (or "리뷰해줘") next (UI-affecting paths in scope — Part B will trigger).
- [2026-04-25] SPEC-UPDATED: v1.1 → v1.2 — Sections 4, 6, 10, 11. Incorporates findings from `research/investigations/11-14`. Highlights for main: (a) **Section 4 C-1**: `ε_init` → `ε_threshold` rename + 3 under-specified behaviors documented (n<3 hide bar, phase-gating, dislike-bias semantic gap from Topic 10 fix → log `confidence_update.action`). (b) **Section 6**: `confidence_update.action` field + optional `bookmark.provenance` booleans `(in_cosine_top10, in_gemini_top10, in_dpp_top10)` for Topic 02 / 04 uplift attribution. (c) **Section 11 Topic 02**: rerank output is **full 60-id ordering** (RRF math 가 모든 후보 rerank_rank 필요 — top-20 truncate 아님); ~$0.0028/session 정정; prompt design (English-only, 5 few-shot) cross-ref `research/investigations/12`. (d) **Section 11 Topic 04**: default **α=1.0** + Optuna search space `α∈[0.5, 1.0]` post-launch + q transform (linear RRF + min-max rescale to `[0.01, 1.0]`) + Cholesky singularity threshold; full pseudocode at `research/investigations/14`. (e) **Section 10 #3**: Multi-session signal transfer 6-option 분석 ready (`research/investigations/11`), 사용자 결정 대기. Non-breaking — main 의 v1.1 흡수 작업 (a9305e4 farthest-point fix 등) 과 무관.
- [2026-04-25] SPEC-UPDATED: v1.2 → v1.3 — **🚨 URGENT push-gate-blocker fix.** Sections 4, 6, 11.1. Incorporates `research/investigations/15-parse-query-latency.md`. **Root cause of monotonic 3437→5496→6706 ms parse-query latency (FAIL on f607e73 / 5d85b90)**: Gemini 2.5-flash's default **dynamic thinking mode** generates hidden reasoning tokens for our structured-extraction task. `services.py:106-110` `GenerateContentConfig` 에 `thinking_config` 미설정 → 5× generation overhead. 150 output tokens × 200 tok/sec = ~0.75s pure generation; thinking tokens fill the 5× gap. Monotonic increase across runs = server-side throttling drift on top of the thinking-tax floor. **🔧 NEW Section 11.1 IMP-4 (one-line fix)**: add `thinking_config=types.ThinkingConfig(thinking_budget=0)` to `GenerateContentConfig` in both `parse_query` (line 106-110) and `generate_persona_report` (line 188). **Mandatory companion**: Section 6 신규 `parse_query.timing` event with `gemini_total_ms / ttft_ms / gen_ms / input_tokens / output_tokens / thinking_tokens` (`response.usage_metadata.thoughts_token_count`). Without instrumentation, IMP-4 effect unobservable. Section 4 time-to-first-card row 에 sub-budget 추가 (per-Gemini-call p95 ≤ 2.5s). **Expected outcome post-fix**: parse-query 1000-1500 ms (p50), total time-to-first-card ~2.0-2.5s, push gate clears with 1.5s margin. **Sprint 1 chat phase (investigation 06 의 더 큰 prompt) 는 IMP-4 에 latency-blocked** — Sprint 1 ship 전 IMP-4 + instrumentation 필수. Recommend Sprint 0/0.5 immediate.
- [2026-04-25] REVIEW-FAIL: f607e73 — **Part A: PASS (0 findings, genuinely clean — IMP-1 fix exemplary).** Part B FAIL: Persona Brutalist time-to-first-card **6706 ms > 4000 ms hard ceiling** (parse-query latency alone). **Second consecutive Part B FAIL on same gate; latency monotonically increasing (3437 → 5496 → 6706 ms across 88f0532 / 5d85b90 / f607e73 runs)** — no longer plausibly Gemini jitter, looks structural. IMP-1 (`a9305e4`) targets `select_ms` (swipe hot path), unrelated to parse-query latency. **Workflow-level decision needed before next UI-affecting batch can pass push gate**: (1) ship `services.parse_query` optimization per `research/investigations/01-swipe-latency-feasibility.md` 4-step path, (2) loosen spec §4 budget from <4s to <8s until #1 lands, OR (3) make Part B latency gate tier-aware (fail on swipe-loop p95, warn-only on parse-query). Recommendation: option 3 (lowest-friction, highest-fidelity — tracks the actual hot path that the user's IMP-1 fix targets). See `.claude/reviews/latest.md` Part B "Decision needed" section. B1bb migration backstop PASSED again; no source code regression; no governance violations.
- [2026-04-25] REVIEW-REQUESTED: f17cb5e — A4 pool exhaustion guard (§5.6 + §6); migration 0008 applied; run `/review` (or "리뷰해줘") next (UI-affecting paths in scope — Part B will trigger).
- [2026-04-25] REVIEW-REQUESTED: 2c7be51 — A5 §6 session logging infrastructure (SessionEvent model + emit_event + initial wire-up); migration 0009 applied; run `/review` (or "리뷰해줘") next (UI-affecting paths in scope — Part B will trigger).
- [2026-04-25] REVIEW-REQUESTED: e290287 — Sprint 1 chat phase rewrite + Spec v1.3 §11.1 IMP-4 push-gate-blocker fix; migration 0010 applied; run `/review` (or "리뷰해줘") next (UI-affecting paths in scope — Part B will trigger; expect ~1000-1500ms parse-query p50 vs prior 5496ms FAIL).
- [2026-04-25] REVIEW-FAIL: 57b3244 — **Part A: PASS (0 findings).** Part B FAIL on retry-after-billing-restoration: parse_query 4166 ms vs 4000 ms ceiling (overshoots by 166 ms / 4.15%). **First real measurement of IMP-4 fix**: A5 `parse_query_timing` SessionEvent payload `{thinking_tokens: None, input_tokens: 5924, output_tokens: 309, gemini_total_ms: 3246}` confirms IMP-4 `thinking_budget=0` works empirically (no thinking-tokens). But IMP-4's predicted 1000-1500 ms p50 underestimated — the new Sprint 1 chat phase prompt (Investigation 06: 9 bilingual few-shot examples) is **5924 input tokens**, ~10× larger than the prior `_PARSE_QUERY_PROMPT`. Gemini 3246 ms + Django/serialization 920 ms = 4166 ms. **Note: prior 4 Part B FAILs (88f0532/5d85b90/f607e73/57b3244-first-run) were ALL Gemini 403 PERMISSION_DENIED — the "monotonic latency drift" in `f607e73.md` was a misdiagnosis; A5 logging surfaced the true cause on its first real run.** **Decision options for user**: (1) accept and push (spec target "3-4s", 4166 ms is at 4.166 — single-run variance), (2) loosen spec §4 budget to <5000 ms, (3) trim chat prompt (Sprint of work, risks bilingual regression), (4) explicit-override single retry. No code change; branch is functionally healthy. See `.claude/reviews/latest.md` Part B "Re-run after Gemini billing restoration" + "Decision options".
- [2026-04-25] USER-OVERRIDE-PUSH: 57b3244 — User accepted the 4.15% margin over spec §4 budget per /review's decision option 1 and pushed manually. Branch deployed to `origin/main` (`ded38be..57b3244`, 19 commits). Audit trail: Part B verification produced real diagnostic data (parse_query_timing SessionEvent), IMP-4 fix empirically verified (thinking_tokens=None), 4166 ms latency is the empirical floor for the current chat-phase prompt size. No code regression. **Improvement recommendations for main's next sprint** at `.claude/reviews/57b3244-improvements.md` — Tier 1 fixes (~1.5h total): (1.1) loosen spec §4 budget to <5000ms, (1.2) multi-run aggregation in /review Part B Step B4, (1.3) /review Step B0 SessionEvent.failure pre-check. Tier 2 (Sprint scale): chat prompt optimization, tier-aware Part B gates. Main: read 57b3244-improvements.md, decide which to action this Sprint.
- [2026-04-25] REVIEW-REQUESTED: f3b8381 — Sprint 3 C-1 confidence bar (Investigation 13 + Spec v1.2 dislike-bias telemetry); UI-affecting paths in scope (SwipePage + App.jsx changes). run `/review` (or "리뷰해줘") next.
- [2026-04-25] REVIEW-REQUESTED: 96b91a6 — Sprint 4 Topic 06 adaptive k + soft-assignment relevance (both flags default OFF backward-compat); run `/review` (or "리뷰해줘") next (UI-affecting paths NOT in scope — Part B optional).
- [2026-04-25] REVIEW-REQUESTED: 03c697b — Sprint 4 Topic 02 Gemini setwise rerank (default OFF backward-compat); UI-affecting paths in scope (SessionResultView). run `/review` (or "리뷰해줘") next.
- [2026-04-25] REVIEW-REQUESTED: de9bfa3 — Sprint 4 Topic 04 DPP + MMR λ ramp (both flags default OFF backward-compat); UI-affecting paths in scope (SessionResultView). run `/review` (or "리뷰해줘") next.
- [2026-04-25] REVIEW-REQUESTED: ebbafd2 — Sprint 4 Topic 02 ∩ 04 Option α composition (RRF fusion + DPP integration); Sprint 4 algorithm batch complete; UI-affecting paths in scope. run `/review` (or "리뷰해줘") next.

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

### Phase 12: Critical Swipe Bug Fixes -- COMPLETED 2026-04-05
30. **B9** -- Cards stop loading after ~N swipes (never set currentCard null) -- COMPLETED 2026-04-05
31. **B10** -- Refresh creates new session instead of resuming (SessionStateView + currentHint) -- COMPLETED 2026-04-05
32. **B11** -- Same card appears twice (client_buffer_ids in exposed_ids) -- COMPLETED 2026-04-05

### Phase 13: Profile System -- PENDING
33. **PROF1** -- OfficeProfile model + Make DB integration (blue-mark, project list, external links, basic info)
34. **PROF2** -- UserProfile extension (MBTI, avatar, bio, external DM links)
35. **PROF3** -- Firm profile page UI (project card grid + website/email links)
36. **PROF4** -- User profile page UI (feed style, board list)

### Phase 14: Board System -- PENDING
37. **BOARD1** -- Board model (public/private visibility, owner FK)
38. **BOARD2** -- Project creation: visibility selection UI
39. **BOARD3** -- Profile page: board browse/manage UI

### Phase 15: Social Foundation -- PENDING
40. **SOC1** -- Follow model + API (follow/unfollow, follower list)
41. **SOC2** -- "Love this!" reaction model + API
42. **SOC3** -- Profile/board: follow button + reaction button UI

### Phase 16: Recommendation Expansion -- PENDING
43. **REC1** -- Post-swipe "MATCHED!" screen redesign
44. **REC2** -- Firm recommendation logic (user taste vector ↔ firm project vector matching)
45. **REC3** -- User recommendation logic (taste vector similarity)
46. **REC4** -- Landing tab UI (Related Projects / Offices / Users)

### Phase 17: LLM Reverse-Questioning -- PENDING
47. **LLM1** -- Chat reverse-question prompt design (identify user needs)
48. **LLM2** -- Persona classification logic (P1-P4 differentiation)
49. **LLM3** -- Per-persona UI branching (recommendation card type switching)

### Phase 18: External Connections -- PENDING
50. **EXT1** -- Firm article crawler (Space, ArchDaily, news — keyword-based)
51. **EXT2** -- Article list UI (inside firm profile)
52. **EXT3** -- External DM link UI (Instagram, email — on profile)

---

## Research Ready

> Written by research terminal. Since spec v1.0 (2026-04-25), this section holds a single persistent `[SPEC-READY]` pointer (updated in place on version bumps). Research handoff is **spec-centric**:
> - `[SPEC-READY]` marker below points to `research/spec/requirements.md`.
> - `research/search/**` (12 topic deep-dives) is reasoning archive — accessed directly via filesystem only when deep-justification is needed. No Task.md pointers.
> - `SPEC-UPDATED` entries in `## Handoffs` (above) carry incremental change signals.

- [SPEC-READY 2026-04-25] requirements-spec-v1.3 — consolidated search flow requirements + Section 11 actionable directives per topic + **Section 11.1 implementation issues IMP-1..IMP-4** (correctness bug + plumbing gaps + corpus label gate + **Gemini thinking-mode push-gate fix**). 15 post-spec investigations absorbed. **Entry**: `research/spec/requirements.md` (binding). Reference: `research/investigations/README.md` (post-spec investigations index — implementation guidance per topic), `research/spec/research-priority-rebaselined.md` (roadmap recommendation, non-binding), `research/search/**` (reasoning archive). Main terminal: read spec, scan latest SPEC-UPDATED in Handoffs for incremental changes (esp. v1.3 IMP-4 push-gate-blocker), plan independently, implement via orchestrator pipeline.

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

### Sprint 4 Topic 02 ∩ 04: Option α Composition -- 2026-04-25

#### COMP1. RRF + DPP composition (Investigation 07 + 14) -- 2026-04-25
Per research/investigations/07-topk-shaping-composition.md (Option α rerank-then-diversify) + Investigation 14 §"q derivation" (RRF rescale to [0.01, 1.0]).
- [x] engine.compute_dpp_topk: q_override=None kwarg added (when supplied, uses values directly without [0.4, 0.95] clip — preserves RRF rescale at both tails).
- [x] views.SessionResultView: candidate_ids_cosine_order captured BEFORE any reorder; rerank_rank_by_id sentinel initialized None.
- [x] Topic 02 block: sentinel set ONLY when rerank produced real reorder (new_order != candidate_ids_cosine_order). Rerank returning input order = no-op = sentinel stays None.
- [x] Topic 04 block: branches on sentinel — RRF rescale path when set, existing cosine-q path when None.
- [x] RRF formula (Investigation 07 line 84): K_RRF=60 hardcoded; fused[bid] = 1/(60+cosine_rank) + 1/(60+rerank_rank).
- [x] Min-max rescale (Investigation 14): q_i = 0.01 + 0.99 * (fused[bid] - fmin) / (fmax - fmin). Edge case fmax==fmin → all q=0.5.
- [x] Architectural deviation flagged: composition operates on post-MMR top-K (typically k=20) not raw cosine-60 — established integration point for Topics 02/04 individually; composition follows. Bigger refactor out of scope.
- [x] Failure cascade per Investigation 07: rerank fail (returns input order) → sentinel stays None → DPP falls back to cosine q.
- [x] 5 new tests in test_topic_composition.py. 124 total pass + 1 skipped. Existing 119 unchanged.
- [x] Reviewer: PASS. Security: PASS.
- Commit: ebbafd2

**Sprint 4 algorithm batch milestone**: Topic 06 (96b91a6) + Topic 02 (03c697b) + Topic 04 (de9bfa3) + Composition (ebbafd2) — all 4 features flag-gated, default OFF, ready for joint Optuna tuning post §6 logging accumulation.

### Sprint 4 Topic 04: DPP Greedy MAP + MMR Lambda Ramp -- 2026-04-25

#### TOPIC04. DPP greedy MAP + MMR lambda ramp (Spec §11 + Investigation 14) -- 2026-04-25
Per research/spec/requirements.md v1.3 §11 Topic 04 + research/investigations/14-topic04-dpp-kernel-design.md + Spec v1.2 SPEC-UPDATED additions (default α=1.0, q transform, Cholesky singularity threshold).
- [x] settings.py RECOMMENDATION: 5 new flags/values (mmr_lambda_ramp_enabled F, mmr_lambda_ramp_n_ref 10, dpp_topk_enabled F, dpp_alpha 1.0, dpp_singularity_eps 1e-9). All defaults preserve current behavior.
- [x] (a) MMR λ ramp: 1-line change in compute_mmr_next; λ(t) = λ_base · min(1, |exposed|/N_ref). λ hoisted outside per-candidate loop (micro-optimization). When flag off, λ_base used as-is.
- [x] (b) compute_dpp_topk(candidates, embeddings, q_values, k, alpha): Wilhelm kernel L_ii=q², L_ij=α·q_i·q_j·⟨v_i,v_j⟩ via Chen 2018 Cholesky-incremental greedy MAP. O(N·k²) total.
- [x] α clamped [0, 1] (α>1 breaks PSD per Investigation 14).
- [x] Singularity (residual<eps=1e-9) → terminate selection + pad q-ordered remaining (no double-selection via valid_mask).
- [x] 2-phase fallback: phase-1 embedding/q failure → ids[:k]; phase-2 Cholesky exception → q-sorted top-k.
- [x] Embedding fetch via get_pool_embeddings(ids), NOT from card dicts (which lack embedding field; would crash). Critical correctness flag from back-maker.
- [x] Standalone Topic 04 q derivation: q = max centroid cosine (range [0.4, 0.95] typical, no rescale needed). RRF fusion + min-max rescale = upcoming Option α composition task.
- [x] views.py SessionResultView DPP block AFTER Topic 02 rerank block (preserves cosine→rerank→DPP composition order). Gated on dpp_topk_enabled + len>=2 + session.like_vectors.
- [x] 15 new tests in test_topic04.py (4 ramp + 7 DPP + 3 integration + 1 early-return). 119 total pass + 1 skipped. Existing 104 unchanged.
- [x] Reviewer: PASS. Security: PASS.
- Commit: de9bfa3

### Sprint 4 Topic 02: Gemini Session-End Setwise Rerank -- 2026-04-25

#### TOPIC02. Gemini setwise rerank at session-end (Spec §11 + Investigation 12 + Spec v1.2 full 60-id ordering) -- 2026-04-25
Per research/spec/requirements.md v1.3 §11 Topic 02 + research/investigations/12-topic02-rerank-prompt-design.md (full prompt + 5 few-shot examples) + Spec v1.2 SPEC-UPDATED. Flag-gated (default OFF) Gemini rerank at session result time, off swipe hot path.
- [x] settings.py RECOMMENDATION dict: gemini_rerank_enabled (default False).
- [x] services.rerank_candidates(candidates, liked_summary) → list of building_ids in rerank order. Full input length (no truncate).
- [x] services._liked_summary_for_rerank(session): pulls metadata from architecture_vectors via parameterized SQL; intensity tagging [Love]>=1.5 / [Like]<1.5; recency truncation [-MAX_ENTRIES:].
- [x] _RERANK_SYSTEM_PROMPT + 5 few-shot examples lifted verbatim from Investigation 12 (English-only — no Korean reaches this call).
- [x] IMP-4 applied: thinking_config=ThinkingConfig(thinking_budget=0).
- [x] temperature=0.0, response_mime_type='application/json' (deterministic structured extraction).
- [x] Validation: set(ranking)==set(input_ids) AND len equality (catches missing, extra, duplicate ids).
- [x] Failure cascade per spec §5.4: parse fail / timeout / partial / extra / duplicate / exception → logger.warning + emit failure event (failure_type='gemini_rerank', recovery_path='cosine_fallback') + return input order.
- [x] views.py SessionResultView: flag-gated reorder via card_by_id dict reconstruction + foreign-id guard (defense in depth).
- [x] Cross-session liked_summary scope: like_vectors lacks building_id (only embedding+round) → workaround uses project.liked_ids ({id, intensity}). Tied to §10 #3 multi-session signal transfer (user decision pending).
- [x] 16 new tests in test_topic02.py (14 unit + 2 DB integration). 104 total pass + 1 skipped. Existing 88 unchanged.
- [x] Reviewer: PASS-WITH-MINORS (1 fix-loop iteration: slice [:N] → [-N:] for recency). Security: PASS.
- Commit: 03c697b

### Sprint 4 Topic 06: Adaptive K + Soft-Assignment Relevance -- 2026-04-25

#### TOPIC06. Adaptive k {1,2} + softmax relevance (Spec §11 Topic 06) -- 2026-04-25
Per research/spec/requirements.md v1.3 §11 Topic 06. Two orthogonal flag-gated improvements; both default OFF for backward-compat.
- [x] settings.py RECOMMENDATION dict: adaptive_k_clustering_enabled + soft_relevance_enabled (both default False, opt-in per spec).
- [x] engine.compute_taste_centroids: adaptive-k branch (silhouette via silhouette_samples + np.average weighted; threshold 0.15; degrades to k=1 on weak signal). N>=4 gate.
- [x] engine.compute_mmr_next: soft-relevance branch (numerically-stable softmax over centroid similarities). len(centroids)>1 gate.
- [x] sklearn 1.6.1 API compat: silhouette_score doesn't accept sample_weight kwarg → manual weighted aggregation via silhouette_samples preserves spec intent.
- [x] Degenerate KMeans (single cluster despite k=2 request): outer guard + try/except ValueError → sil2=-1.0 → k=1 fallback.
- [x] 9 new tests in TestTopic06AdaptiveK; 88 total pass + 1 skipped. Existing 79 unchanged.
- [x] Reviewer: PASS (after fix-loop Option b sklearn compat). Security: PASS.
- Commit: 96b91a6

### Sprint 3 C-1: Confidence Bar -- 2026-04-25

#### CONF1. Confidence bar (Spec §4 + Investigation 13) -- 2026-04-25
Per research/spec/requirements.md v1.3 §4 C-1 row (통합안 1) + research/investigations/13-c1-confidence-formula-validation.md + Spec v1.2 SPEC-UPDATED additions (ε_init→ε_threshold rename, 3 underspecified behaviors, dislike-bias semantic gap → confidence_update.action).
- [x] engine.compute_confidence(history, threshold, window=3) returns float [0,1] or None when n<window. Anchor values verified per Investigation 13 (avg=0→1.0, avg=0.02→0.75, avg=0.04→0.5, avg=threshold→0). threshold=0 div-by-zero guarded via max(threshold, 1e-6).
- [x] SwipeView response 'confidence' field across all 3 paths (normal-swipe computed, action-card reset null, action-card complete null per fix-loop fix).
- [x] confidence_update SessionEvent emitted with payload {confidence, dominant_attrs (top-3 dim indices), action} per Spec v1.2 dislike-bias telemetry. Only emitted when non-null.
- [x] Frontend ConfidenceBar component in SwipePage with inline styles + DESIGN.md accent (#ec4899). Phase label REMOVED per spec. Fallback counter when bar hidden (exploring + non-analyzing).
- [x] App.jsx propagates confidence in applySessionResponse + handleSwipeCard; backward-compat via result.confidence ?? null.
- [x] 1-line interpretation text deferred to Sprint 4 (attribute-name mapping layer not yet wired; backend emits dimension indices only).
- [x] 12 new tests in TestConfidenceBar (3 commit cycles: backend pipeline cycle 1 with 11 unit + 4 integration; fix-loop cycle 2 added 1 test for action-card complete path). 79 tests pass + 1 skipped.
- [x] Reviewer: PASS (after fix-loop cycle 2 added missing 'confidence' key to action-card complete path). Security: PASS.
- Commit: f3b8381

### Sprint 1: Chat Phase Rewrite + IMP-4 Push-Gate Fix -- 2026-04-25

#### CHAT1. Chat phase 0-2 turn probe + IMP-4 push-gate-blocker (Spec v1.3 §3 + §11.1 IMP-4) -- 2026-04-25
Per research/spec/requirements.md v1.3 §3 + §11.1 IMP-4 + research/investigations/06-chat-phase-prompt-design-3c.md (full prompt design + 9 few-shot examples). Bundles Sprint 1 chat phase rewrite + IMP-4 URGENT push-gate-blocker (root cause: Gemini 2.5-flash dynamic thinking mode, 5× generation overhead).
- [x] services._CHAT_PHASE_SYSTEM_PROMPT replaces _PARSE_QUERY_PROMPT (Investigation 06 full system prompt with 9 few-shot examples).
- [x] services.parse_query(conversation_history) multi-turn signature with backward-compat shim for legacy string.
- [x] Multi-turn Gemini call: contents=[Content(role,parts)] history + system_instruction.
- [x] Output schema: terminal {filters, filter_priority, raw_query, visual_description, reply} OR probe {probe_needed=true, probe_question, reply}.
- [x] raw_query = first user message verbatim (BM25 stability); visual_description always English (HyDE compatibility).
- [x] §11.1 IMP-4: thinking_config=ThinkingConfig(thinking_budget=0) on BOTH parse_query AND generate_persona_report. Expected p50 1000-1500ms (vs prior 5496ms Part B FAIL).
- [x] §6 + IMP-4 mandatory companion: parse_query_timing SessionEvent (gemini_total_ms, gen_ms, input_tokens, output_tokens, thinking_tokens). Migration 0010 AlterField for choices change.
- [x] ParseQueryView input validation: history > 10 / text > 2000 / non-dict / role ∉ {user,model} → 400.
- [x] Frontend (LLMSearchPage + client.js): parseQuery accepts string OR list; probe path renders probe_question + accumulates conversationHistory; terminal path resets to []. Backward-compat for undefined probe_needed.
- [x] Resolves §10 #5 (bare query "random" — Investigation 06 Example 7 0-turn skip with diverse_random fallback), §10 #7 (Korean — bilingual prompt design).
- [x] §10 #15 conversation history persistence: chosen frontend-ephemeral (Investigation 06 default; backend stateless). Future: add backend storage if needed.
- [x] Pre-deploy gate: _CHAT_PHASE_FEW_SHOT_STYLE_LABELS frozenset asserted against architecture_vectors corpus via pytest test (skips on SQLite).
- [x] 10 new tests in test_chat_phase.py (5 classes: TestChatPhaseParseQuery, TestPreDeployStyleLabelGate, TestGeneratePersonaReportThinkingBudget, TestParseQueryTimingEvent, TestParseQueryInputValidation). 63 total tests pass + 1 skipped. Zero regressions.
- [x] Reviewer: PASS (after migration 0010 added in fix-loop cycle 2). Security: PASS.
- Commit: e290287

### Sprint 0 A5: §6 Session Logging Infrastructure -- 2026-04-25

#### LOG1. SessionEvent model + emit helpers + initial endpoint wire-up (§6) -- 2026-04-25
Per research/spec/requirements.md v1.1 §6 (binding) + v1.1 SPEC-UPDATED additions. Foundation for measurement-dependent v1.0/v1.1 work — V_initial bit hypothesis (Topic 03), latency budget validation (Investigation 01 O1), bandit/CF training (Topic 05/07), Topic 09 ANN trigger detection.
- [x] SessionEvent model: 13 event types (10 v1.0 + 3 v1.1: pool_creation, cohort_assignment, probe_turn), JSON payload, db_index on (session, created_at) + (event_type, created_at). Migration 0009 pure CreateModel.
- [x] event_log.py: emit_event(event_type, session=None, user=None, **payload) never raises; emit_swipe_event() convenience wrapper.
- [x] §6 implementation requirements: #1 Pool exhaustion ✅ (A4 prior); #2 Monotonic timestamps (auto_now_add microsecond + sequence_no tie-break); #3 Anonymized aggregation (user FK SET_NULL preserves history; both FKs nullable for pre-session events); #4 Bookmark rank_zone deferred to Sprint 4 bookmark endpoint.
- [x] Wired NOW: session_start + pool_creation (SessionCreateView); swipe with timing_breakdown lock_ms/embed_ms/select_ms/prefetch_ms/total_ms via _mark closure (SwipeView normal path); session_end with end_reason='user_confirm' on action-card accept; failure events in services.py parse_query + generate_persona_report exception handlers (4 call sites; error_message truncated 200 chars).
- [x] Wired LATER: tag_answer (Sprint 3 B-1), confidence_update (Sprint 3 C-1), bookmark/detail_view/external_url_click/session_extend (Sprint 4 result page), probe_turn (Sprint 1 chat phase), cohort_assignment (A/B testing wire-up).
- [x] TestSessionEventLogging: 5 tests (create + never-raise + sequence_no per session + integration session_create + integration swipe with timing). 54 total tests pass.
- [x] Reviewer: PASS. Security: PASS (error_message truncation verified at all 4 services.py call sites; no credential leakage; ORM-only SQL).
- Commit: 2c7be51

### Sprint 0 A4: Pool Exhaustion Guard -- 2026-04-25

#### POOLEX1. Pool exhaustion 3-tier auto-relaxation guard (§5.6 + §6) -- 2026-04-25
Per research/spec/requirements.md v1.1 §5.6 + §6 Implementation Requirements item 1. When remaining pool drops below 5 buildings during swiping, auto-escalate to next filter relaxation tier and merge new candidates so swipe never hits a "no card" dead end.
- [x] AnalysisSession + 4 new fields (original_filters, original_filter_priority, original_seed_ids, current_pool_tier) — migration 0008 (pure AddField, no data migration)
- [x] engine.create_pool_with_relaxation() — factored out 3-tier logic from SessionCreateView for reuse; supports start_tier param so caller can escalate
- [x] engine.refresh_pool_if_low(session, threshold=5) — mutates session in-place when remaining < threshold AND tier < 3; exclude_ids excludes both existing pool AND already-exposed for guaranteed-disjoint merge
- [x] SessionCreateView refactored: inline 3-tier (lines 169-194) → single helper call. Identical behavior. filter_relaxed flag derived from current_pool_tier > 1.
- [x] SwipeView: refresh_pool_if_low() called in normal swipe path AND action-card "Reset and keep going" branch (§5.6 "더 swipe" path); update_fields extended with pool_ids, pool_scores, current_pool_tier
- [x] TestPoolExhaustionGuard: 5 tests (no-op above threshold, tier 1→2 escalate, tier 3 no-op, exclude exposed, fall-through to tier 3). 49 total tests pass.
- [x] Reviewer: PASS. Security: PASS. Reviewer flagged pre-existing race (action-card branch lacks select_for_update; A4 widens existing race to new pool fields) — defer.
- Commit: f17cb5e

### Sprint 0 IMP-1: Farthest-point Correctness + Vectorization -- 2026-04-25

#### IMP1. Farthest_point max-min correctness fix + NumPy vectorization (Spec v1.1 §11.1) -- 2026-04-25
Per research/spec/requirements.md v1.1 §11.1 IMP-1 + research/investigations/02-farthest-point-correctness-and-vectorization.md. Bundles correctness bug fix and 20-50× speedup vectorization in one commit per investigation 02's recommendation.
- [x] Bug: max-max → max-min accumulator. Function name implies Gonzalez farthest-point sampling (max distance to NEAREST exposed); pre-fix code computed max distance to FARTHEST exposed, silently picking near-duplicates of exposed items.
- [x] NumPy vectorization: nested Python loop (~7500 individual np.dot calls) → single BLAS matmul (C @ E.T + max(axis=1) + argmin). pgvector rejected (CROSS JOIN anti-pattern, network RTT 50-100× the local NumPy cost).
- [x] Signature + return contract preserved across all 12 production callers (views.py × 10, algorithm_tester.py × 2).
- [x] All fallbacks preserved (None on no candidates, random.choice on no anchor, defensive skip on missing-from-embeddings).
- [x] New TestFarthestPointFromPool class (5 tests). Counterexample fixture corrected from spec text geometric error (3D orthogonal A⊥B, X near A, Y equidistant cos=0.5). Pre-fix picks X (score 0.8590); post-fix picks Y (score 0.5000). 44 total tests pass (39 prior + 5 new).
- [x] Reviewer: PASS. Security: PASS.
- Commit: a9305e4

### Sprint 0 A3: Project Schema Migration -- 2026-04-25

#### SCHEMA1. Project.liked_ids intensity shape + saved_ids field (Section 7) -- 2026-04-25
Per research/spec/requirements.md Section 7 + 11. Lays the data layer foundation for Sprint 3 A-1 (Love intensity 1.8) and Sprint 4 top-K bookmark UI (primary success metric).
- [x] Migration 0007: AddField saved_ids + RunPython backfill of liked_ids shape (idempotent)
- [x] Project.liked_ids: list[str] -> list[{id, intensity}]; existing entries default intensity=1.0
- [x] Project.saved_ids NEW: list[{id, saved_at}], read-only on serializer
- [x] Project.disliked_ids UNCHANGED per spec (no intensity)
- [x] views.py _liked_id_only helper for legacy/new shape transparency; persona report extracts plain IDs
- [x] views.py SwipeView like-write: clamp intensity from request body (default 1.0, range [0,2])
- [x] frontend App.jsx extractLikedIds helper applied at 3 sites in handleLogin
- [x] 6 new TestProjectSchemaA3 tests; 39 total pass
- [x] Reviewer: PASS. Security: PASS (1 pre-existing Warning on Project read-modify-write race; deferred).
- Commit: 190c830

### Sprint 0 A2: Dislike Threshold Reduction -- 2026-04-25

#### DISLIKE1. max_consecutive_dislikes reduced 10 -> 5 (Section 5.1) -- 2026-04-25
Per research/spec/requirements.md Section 5.1 (binding). Silent dislike fallback now fires after 5 consecutive dislikes. Three locations aligned for coherence:
- [x] settings.py RECOMMENDATION['max_consecutive_dislikes']: 10 -> 5 (canonical)
- [x] views.py line 618 + 626 RC.get() fallback defaults: 10 -> 5
- [x] tools/algorithm_tester.py PRODUCTION_PARAMS baseline: 10 -> 5 (Optuna search range (5,20) unchanged)
- [x] No new tests needed (grep -rn max_consecutive_dislikes backend/tests -> empty; pure constant change)
- [x] Reviewer: PASS. Security: PASS.
- Commit: f04646f

### Sprint 0 A1: Pool-Score Normalization -- 2026-04-25

#### POOL1. Pool-score normalization (Topic 12) -- 2026-04-25
Per research/spec/requirements.md Section 11 Topic 12. Fixes weight-scale drift (3-filter raw max 6 vs 8-filter raw max 36) by normalizing pool_scores to [0,1].
- [x] `_build_score_cases` returns (cases, params, total_weight) — accumulates branch weights
- [x] `create_bounded_pool` wraps SQL score as `((sum)::float / total_weight)` → normalized [0,1]
- [x] Seed boost changed from `n+1` to clean `1.1`
- [x] New `TestPoolScoreNormalization` class with 2 unit tests (build_score_cases empty + populated paths). 33 tests total pass.
- [x] Reviewer: PASS. Security: PASS.
- Commit: 8bf73b8

### Sprint 0 Topic 10: Convergence Detection Signal-Integrity -- 2026-04-25

#### CONV1. Convergence detection signal-integrity fixes (Topic 10 Option A) -- 2026-04-25
Per research/spec/requirements.md Section 11 Tier A Critical + research/search/10-convergence-detection.md Option A. Two structural bugs in the analyzing-phase Delta-V pipeline were producing meaningless convergence signals. Both fixes land unconditionally (no flag).
- [x] Bug 1 fix: on exploring -> analyzing transition in views.py SwipeView, clear session.convergence_history and session.previous_pref_vector. Previously the first analyzing Delta-V computed a cross-metric ||centroid - pref_vector|| (apples to oranges).
- [x] Bug 2 fix: remove `action == 'like'` gate from the analyzing Delta-V append in views.py. Now every analyzing swipe appends a Delta-V entry (guarded only by `like_vectors` non-empty). convergence_window=3 now counts rounds, not likes.
- [x] Tests: new TestConvergenceSignalIntegrity class in backend/tests/test_sessions.py with 2 tests (phase transition reset + dislike Delta-V append). All 31 backend tests pass.
- [x] Known side effect documented in commit + code comment: dislike Delta-V < like Delta-V biases the moving average downward on dislike-heavy sequences. Acceptable per spec; revisit with data.
- Commit: 3ee9c77

### Phase 12: Critical Swipe Bug Fixes -- 2026-04-05

#### B9. Cards stop loading after several swipes -- 2026-04-05
Root cause: `canInstantSwap` path in `App.jsx:handleSwipeCard` sets `currentCard=null` when canInstantSwap=false.
The null guard at line 282 then returns early on subsequent interactions, permanently blocking the swipe flow.
- [x] Frontend: Never set currentCard to null in non-instant path (keep visible with loading overlay)
- [x] Frontend: Non-instant path handles null next_image gracefully (edge case: pool temporarily exhausted)
- [x] Backend: `SwipeView.post()` accepts `client_buffer_ids`, merges into `exposed_ids` via `_merge_buffer_into_exposed`
- [x] Frontend: `handleSwipeCard` sends `client_buffer_ids` from `[prefetchCard, prefetchCard2]`
- [x] Frontend: canInstantSwap path uses `result.next_image` as tail-fill only (ignores backend prefetch/prefetch_2)
- [x] Frontend: Action cards treated as always instant-swappable via `isActionCard()` helper
- Commit: fbd8486

#### B10. Refresh during swiping returns to beginning -- 2026-04-05
Root cause: On refresh, `initSession` always created a new session. `SessionStateView` also rejected current_hint
if it wasn't in exposed_ids (but after instant-swap, the displayed card might only be in the frontend buffer).
- [x] Backend: `SessionStateView` at `GET /analysis/sessions/<uuid>/state/` with `?current=` hint param
- [x] Backend: Accept current_hint from pool_ids (not just exposed_ids); append to exposed_ids for prefetch exclusion
- [x] Backend: Prefetch scans initial_batch forward from current_round+1 (not fixed index)
- [x] Frontend: `getSessionState(sessionId, currentHint)` in client.js
- [x] Frontend: `initSession` tries `getSessionState` first, falls back to new session on 404
- [x] Frontend: swipeRestored useEffect and handleResumeProject pass `project.sessionId`
- [x] Frontend: currentCard persisted to localStorage per project for seamless refresh hint
- Commit: fbd8486

#### B11. Same card appears twice -- 2026-04-05
Root cause: Frontend's prefetch buffer cards not tracked in backend's exposed_ids.
When canInstantSwap was false and currentCard became null, subsequent swipes couldn't send client_buffer_ids.
- [x] Fixed by B9 (currentCard never null -> client_buffer_ids always sent)
- [x] Backend merges client_buffer_ids into exposed_ids before card selection
- [x] Backend tests verify merge behavior
- Commit: fbd8486

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
