# Algorithm Research

> Phase logic, mathematical formulas, and hyperparameter theory.
> Research agent updates this file. Orchestrator references it for algorithm tasks.

**Last Synced (Reporter):** 2026-04-28 7348593

---

## Recommendation Pipeline Theory

### Phase 0: Initialization & Bounded Pool Generation (Warm Start)
Translates the user's initial chat prompt into a semantic vector space.

1. **Hard Filter Extraction:** An LLM extracts explicit metadata constraints from the user's prompt (e.g., `program`, `location_country`) to be used as `WHERE` clauses in the DB query.
2. **Visual Description Generation:** The LLM generates a rich, paragraph-length visual description of the ideal architecture based on the prompt.
3. **Initial Embedding:** This text is embedded using the `paraphrase-multilingual-MiniLM-L12-v2` model to create the initial vector: V_initial.
4. **Bounded Pool Creation:** Fetch the top N items (e.g., 150) that pass the hard filters and have the highest cosine similarity to V_initial. This becomes the session's exclusive card pool.

   _(Updated 2026-04-25 8bf73b8: `_build_score_cases` returns `(cases, params, total_weight)`; `create_bounded_pool` SQL output normalized to [0, 1] via `((sum)::float / total_weight)`; seed boost `1.1`. Fixes weight-scale drift across queries with different filter counts. See spec Section 11 Topic 12.)_

_(Updated 2026-04-25 e290287: Sprint 1 §3 chat phase rewrite (Investigation 06) — `services.parse_query(conversation_history)` now supports 0-2 turn probe per spec §3, output schema gains `visual_description` (English HyDE seed) + `filter_priority` + `raw_query` (first user turn verbatim). LLM-autonomous probe axis selection per Investigation 06 9 few-shot examples. Spec v1.3 §11.1 IMP-4 push-gate-blocker fix shipped: `thinking_config=ThinkingConfig(thinking_budget=0)` on parse_query + generate_persona_report — root cause of monotonic 3437→5496→6706 ms latency drift was Gemini 2.5-flash default dynamic thinking; expected post-fix p50 ~1000-1500ms. Mandatory companion `parse_query_timing` SessionEvent emitted for measurement.)_

_(Updated 2026-04-26 6f4b76f: HyDE V_initial scaffolding — flag-gated default OFF; activates HF Inference API embed of visual_description and pgvector cosine sim blending in pool creation when enabled)_

_(Updated 2026-04-26 305e213: Topic 01 Hybrid RRF scaffolding — flag-gated default OFF; activates RRF blend of BM25 + v_initial-cosine + filter channels in pool creation when enabled. v_initial reused from Topic 03 — no extra HF call.)_

_(Updated 2026-04-26 06c6c5a: IMP-7 per-building-id immutable cache + companion §6 swipe.timing_breakdown observability — fixes A4 escalation cache invalidation; expected select_ms 300ms → ~50ms.)_

_(Updated 2026-04-26 c133787: IMP-5 Gemini explicit context caching for _CHAT_PHASE_SYSTEM_PROMPT — flag-gated default OFF; lazy-init via _ensure_chat_cache with 80% Django TTL invariant; once flipped on, expected per-Gemini-call ~3246→~1400-1800ms drop. Companion to IMP-8 — both share LocMemCache→Redis swap requirement for multi-worker prod.)_

_(Updated 2026-04-27 6604296: IMP-5 staging validation — 100% cache_hit + 5919 cached tokens verified (mechanism works), but only 5.5% latency drop (161ms) on same-session A/B (Phase A uncached median 2904ms vs Phase B cached median 2743ms); spec §11.1 IMP-5 predicted ≥50% / 1400-1800ms target. Prediction invalidated: Gemini 2.5-flash baseline dropped ~3200→~2900ms since spec written; output-generation dominates floor, cached input tokens do not reduce wall time at 5919-token scale. See research/investigations/16-gemini-context-caching.md for revisit.)_

_(Updated 2026-04-28 834d36e: M4 clarification telemetry shipped — parse_query_timing payload now has additive clarification_fired + query_complexity_class fields. Investigation 22 Phase 1 passive data accumulation can begin (was permanently blocked). Source for clarification_fired = probe_needed Gemini response field, authoritative not heuristic.)_

_(Updated 2026-04-28 1b2bd21: M1 refined clarification cap shipped — prompt + Python 3-layer enforcement caps user clarification turns at max 2 per session. Cap fires at user_turn_count >= 3 (preserves Investigation 06 BareQuery 2-turn flow). m1_cap_forced_terminal telemetry surfaces override events. UX trade-off: cap-forced terminal has short ack reply + None visual_description + partial filters; HyDE V_initial skips cleanly.)_

_(Updated 2026-04-28 7348593: IMP-6 2-stage decouple shipped (flag-gated default OFF) — Phase 0 Gemini call split into Stage 1 sync (parse_query_stage1, ~150-220 output tokens, user-blocking, returns filters+reply via _STAGE1_RESPONSE_SCHEMA that structurally excludes visual_description) + Stage 2 async daemon thread (generate_visual_description, ~140-180 output tokens, fire-and-forget, stores V_initial in Django cache key v_initial:{user_id}:{sha256(raw_query)[:16]}). Stage 1 alone expected ~45-55% Gemini wall drop when stage_decouple_enabled flipped ON; total TTFC ~2400-2700ms restoring spec v1.0 aspirational <3-4s outer budget.)_

### Phase 1: Bounded Exploration
Gathers initial user feedback within the bounded pool while ensuring visual diversity.

- Execute **Greedy Farthest-point Sampling** within the pool to serve cards that are as visually distinct from one another as possible.
- **Transition:** Phase 1 -> Phase 2 when Like count reaches `min_likes_for_clustering` (e.g., 4).

_(Updated 2026-04-26 da547cb: min_likes_for_clustering 3→4 per Spec v1.8 Topic 06 N≥4 cliff mitigation — defers K-Means until N≥4 to avoid Investigation 09 worst-case 1 Love + 2 Likes pathology.)_

_(Updated 2026-04-26 1491c5d: IMP-8 async prefetch background thread — flag-gated default OFF; activates daemon thread spawn for prefetch_card+_2 computation when enabled, primary swipe response returns immediately with prefetch=None. Combined with IMP-7 cache fix (06c6c5a): total_ms ~600ms→~300ms per spec v1.6 §4 re-tightening pathway.)_

_(Updated 2026-04-25 a9305e4: `farthest_point_from_pool()` (engine.py:421-455) corrected from inverted max-max accumulator to true Gonzalez max-min sampling per Spec v1.1 §11.1 IMP-1. Pre-fix code silently picked near-duplicates of exposed items. Bundled with NumPy batch matmul vectorization (~22ms → ~1ms per call, 20-50× speedup). Topic 11's 2-approximation bound and Section 4 C-3 Better layer 3's "first 3-5 diverse seeds" now actually deliver diverse selection.)_

### Phase 2: Multi-modal Formulation & Exploitation (MMR)
The core engine. Tracks recent moods, analyzes multi-faceted tastes, and applies diversity penalties.

### Phase 3: Graceful Exit (Action Card)
Once convergence detected, backend injects an Action Card. User swipes right to view results.

### Completed: Top-K Results
Top-K results fetched based on final multi-modal centroids, with MMR for diverse layout.

_(Updated 2026-04-25 03c697b: Sprint 4 Topic 02 Gemini session-end setwise rerank — when `gemini_rerank_enabled` (default OFF) AND len(predicted_cards) >= 2 at session-result time, services.rerank_candidates calls Gemini 2.5-flash with system prompt + 5 few-shot examples (Investigation 12) and reorders predicted_cards by taste alignment. Output is full ordering (sets up Topic 02 ∩ 04 RRF fusion in upcoming Option α composition). Off swipe hot path. thinking_budget=0 + temp=0 + JSON mime for deterministic structured extraction. Validation: set + length equality with input ids. Silent graceful degradation to cosine ordering on any failure (parse/partial/extra/duplicate/exception) per spec §5.4. Cost ~$0.002-0.0028/session.)_

_(Updated 2026-04-25 de9bfa3: Sprint 4 Topic 04(b) DPP greedy MAP at session-final top-K — when `dpp_topk_enabled` (default OFF) AND len(predicted_cards) >= 2 AND session.like_vectors, services-side compute_dpp_topk applies Wilhelm 2018 kernel L_ii=q², L_ij=α·q_i·q_j·⟨v_i,v_j⟩ via Chen 2018 Cholesky-incremental greedy MAP O(N·k²). Standalone q = max centroid cosine (RRF rescale ships in Topic 02 ∩ 04 composition). α clamped [0,1] (α>1 breaks PSD). Singularity (residual<eps=1e-9) → pad q-ordered. SessionResultView runs DPP AFTER Topic 02 rerank, preserving cosine→rerank→DPP composition order.)_

_(Updated 2026-04-25 ebbafd2: Sprint 4 Topic 02 ∩ 04 Option α composition (Investigation 07) — when BOTH `gemini_rerank_enabled` AND `dpp_topk_enabled`, SessionResultView composes the two flags via RRF fusion of cosine_rank + rerank_rank, then min-max rescale to [0.01, 1.0] (per Investigation 14 q-scale fix), then DPP with q_override. Single integration point: q_i in L-ensemble reads from RRF-fused score (Topic 02 output) instead of pure cosine. Standalone behaviors of either flag preserved when only one is on. Failure cascade: rerank returning input order = sentinel None = DPP falls back to cosine q. Sprint 4 algorithm batch (Topic 06 + 02 + 04 + composition) milestone reached.)_

---

## Mathematical Formulas

### Recency Weighting
```
w_i = exp(-gamma * (current_round - round_i))
```

Exponential decay gives recent likes more influence on cluster centroids.
gamma (decay_rate) range: 0.01-0.1. Current production value: 0.05.

### K-Means Clustering (Multi-modal)
Group the weighted Like vectors into K clusters (e.g., 2). The centroids represent the user's multi-modal preference (V_pref).
Uses `sample_weight` parameter with recency weights.

_(Updated 2026-04-25 96b91a6: Sprint 4 Topic 06 adaptive k — when `adaptive_k_clustering_enabled` (default OFF), N>=4 likes triggers silhouette-weighted k {1,2} selection (threshold 0.15). Weak cluster signal degrades to k=1 (single global weighted centroid). Implementation uses silhouette_samples + np.average(weights=like_weights) for sklearn 1.6.1 API compat.)_

### MMR Scoring
```
score(b) = similarity(b, centroids) - lambda * max_similarity(b, recent_shown)
```

Balances relevance (first term) against diversity (second term).
lambda (mmr_penalty) range: 0.1-0.4. Current production value: 0.3.

_(Updated 2026-04-25 96b91a6: Sprint 4 Topic 06 soft-assignment relevance — when `soft_relevance_enabled` (default OFF) AND len(centroids) > 1, relevance becomes softmax-weighted average of cosine similarities across centroids (vs hard max). Numerically-stable (sims − sims.max()).)_

_(Updated 2026-04-25 de9bfa3: Sprint 4 Topic 04(a) MMR λ ramp — when `mmr_lambda_ramp_enabled` (default OFF), λ(t) = λ_base · min(1, |exposed|/N_ref) ramps diversity penalty as session progresses. Encourages relevance-heavy at start (sparse signal), diversity-heavy as exposure accumulates. λ computation hoisted outside candidate loop.)_

### Convergence Detection
```
delta_V = ||centroid_now - centroid_prev|| / ||centroid_prev||
```

Moving average over `convergence_window` rounds. Converged when delta_V < epsilon.
epsilon (convergence_threshold) range: 0.05-0.15. Current production value: 0.08.

_(Updated 2026-04-25 f3b8381: Sprint 3 C-1 confidence bar shipped — engine.compute_confidence(history, threshold, window=3) returns user-facing confidence in [0,1] (or None for hide-bar) per spec formula `1 − min(1, avg(last 3 Δv) / ε_threshold)`. SwipeView response includes 'confidence' field in all 3 paths (normal-swipe / action-card reset / complete). confidence_update SessionEvent emitted with `action` field for Spec v1.2 dislike-bias telemetry. Bar visible threshold = phase transition threshold = 0.08 (settings.py); informational vs decisional signals at the same numeric threshold but different semantic targets per Investigation 13.)_

### Preference Vector Updates
- Like: +like_weight (0.5) added to preference vector, L2-normalized
- Dislike: +dislike_weight (-1.0) added to preference vector, L2-normalized

_(Updated 2026-04-25 190c830: Like writes now carry an `intensity` field (default 1.0; future Sprint 3 A-1 Love sets 1.8). Backend stores `liked_ids` as list[{id, intensity}]; intensity is clamped [0, 2] at write time. The recency-weighted preference vector update is unchanged in formula; intensity will modulate `like_weight` once Sprint 3 A-1 wires the up-swipe gesture.)_

---

## Edge Cases & Fallbacks

- **Extreme Dislike Bias:** If consecutive dislikes >= `max_consecutive_dislikes`, pick building farthest from dislike centroid (escape dead-end). K-Means cannot run without likes.

  _(Updated 2026-04-25 f04646f: `max_consecutive_dislikes` reduced 10 → 5 per spec Section 5.1; silent dislike fallback now fires sooner.)_
- **Pool Exhaustion:** If all pool buildings shown and delta_V still above epsilon (erratic swiping), force exit to results. UI indicates best-effort results.

  _(Updated 2026-04-25 f17cb5e: §5.6 + §6 implementation requirement A4 — engine.refresh_pool_if_low(threshold=5) called from SwipeView in normal + action-card paths; auto-escalates to next 3-tier filter relaxation level (full → drop geo/numeric → random) and merges new candidates with exclude_ids = pool_ids ∪ exposed_ids. Migration 0008 adds session-level relaxation state (original_filters, original_filter_priority, original_seed_ids, current_pool_tier).)_

---

## Hyperparameter Space (12 params)

| Param | Type | Range | Production Value |
|-------|------|-------|-----------------|
| decay_rate | float | 0.01-0.1 | 0.05 |
| mmr_penalty | float | 0.1-0.4 | 0.3 |
| convergence_threshold | float | 0.05-0.15 | 0.08 |
| like_weight | float | 0.1-1.0 | 0.5 |
| dislike_weight | float | -2.0 to -0.1 | -1.0 |
| bounded_pool_target | int | 50-300 | 150 |
| min_likes_for_clustering | int | 2-5 | 4 |
| convergence_window | int | 2-5 | 3 |
| k_clusters | int | 1-3 | 2 |
| max_consecutive_dislikes | int | 5-20 | 5 |
| initial_explore_rounds | int | 5-20 | 10 |
| top_k_results | int | 10-30 | 20 |
| `adaptive_k_clustering_enabled` | bool | True/False | False |
| `soft_relevance_enabled` | bool | True/False | False |
| `gemini_rerank_enabled` | bool | True/False | False |
| `mmr_lambda_ramp_enabled` | bool | True/False | False |
| `mmr_lambda_ramp_n_ref` | int | 5-20 | 10 |
| `dpp_topk_enabled` | bool | True/False | False |
| `dpp_alpha` | float | 0.0-1.0 | 1.0 |
| `dpp_singularity_eps` | float | 1e-12 to 1e-6 | 1e-9 |
| `hyde_vinitial_enabled` | bool | True/False | False |
| `hyde_hf_model` | string | — | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `hyde_hf_timeout_seconds` | int | 1-30 | 5 |
| `hyde_score_weight` | float | 0-100 | 50.0 |
| `hybrid_retrieval_enabled` | bool | True/False | False |
| `hybrid_rrf_k` | int | 10-100 | 60 |
| `hybrid_bm25_dict` | string | — | `simple` |
| `hybrid_filter_channel_enabled` | bool | True/False | True |
| `pool_precompute_enabled` | bool | True/False | False |
| `pool_embedding_cache_max_size` | int | 1000-10000 | 5000 |
| `async_prefetch_enabled` | bool | True/False | False |
| `async_prefetch_cache_timeout_seconds` | int | 10-300 | 60 |
| `context_caching_enabled` | bool | True/False | False |
| `context_caching_ttl_seconds` | int | 60-7200 | 3600 |
| `stage_decouple_enabled` | bool | True/False | False |

Source: `backend/config/settings.py` RECOMMENDATION dict.

---

## Optimization Methodology

Originally specified as Grid Search, now implemented as **Optuna Bayesian optimization** (`backend/tools/algorithm_tester.py`).

- Phase 1: N personas x T trials (e.g., 100 x 200) — broad search
- Phase 2: Top combos validated with larger persona set (e.g., 500)
- Scoring: composite of precision and average swipe count
- Production baseline seeded as first Optuna trial for fair comparison

Target: convergence in 15-25 swipes with high precision in Top-K results.

_(Updated 2026-04-25 2c7be51: §6 session logging infrastructure (Sprint 0 A5) shipped — SessionEvent model + emit_event helper. Wired session_start, pool_creation, swipe (with timing_breakdown), session_end, failure events. Foundation for V_initial bit hypothesis measurement (Topic 03), per-swipe latency budget validation (Investigation 01 O1), Topic 09 ANN trigger detection, and bandit/CF training data accumulation (Topic 05/07). Other events (tag_answer, confidence_update, bookmark, detail_view, external_url_click, session_extend, probe_turn, cohort_assignment) wired when their feature endpoints ship.)_

---

## Open Questions

(Research agent adds questions here as they arise)
