# Recommendation hyperparameters — production values

<!-- GENERATED FILE — DO NOT EDIT. Source: backend/config/settings.py RECOMMENDATION dict. -->
<!-- Regenerate: python tools/gen-hyperparams.py   (CI fails if this file is stale) -->

Generated from `backend/config/settings.py` `RECOMMENDATION` — **77 parameters**.
Values here are what production runs with (environment overrides are marked `env`).
The *meaning* column is the inline comment on each key in `settings.py`; to document a
parameter, comment it there. Design intent and phase semantics: `docs/algorithm.md`.

## Core swipe loop (Phases 0–3)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `bounded_pool_target` | 150 | int | N: session card pool = top-N by cosine sim to V_initial after hard filters (Phase 0) |
| `min_likes_for_clustering` | 4 | int | Spec v1.8 Topic 06 N>=4 activation-cliff mitigation per Investigation 21 §closure -- defer K-Means until N>=4 to avoid the Investigation 09 worst-case window (1 Love + 2 Likes, k=2 forces centroid collapse onto Love) |
| `decay_rate` | 0.05 | float | gamma -- recency weight decay |
| `mmr_penalty` | 0.3 | float | lambda -- diversity penalty |
| `convergence_threshold` | 0.13 | float | epsilon -- tuned for convergence inside the 10-swipe target window |
| `convergence_window` | 3 | int | consecutive pref-vector deltas below epsilon required to declare convergence |
| `target_swipes` | 10 | int | product goal: taste should be captured within ~10 swipes |
| `convergence_min_recent_likes` | 2 | int | recent positive evidence required before backend declares convergence |
| `k_clusters` | 2 | int | K-Means clusters in the multi-modal phase (Phase 2) |
| `min_likes_for_multimodal` | 11 | int | keep the <=10-swipe loop single-centroid; KMeans only after the target window |
| `max_consecutive_dislikes` | 5 | int | dislike streak that triggers the escape fallback (farthest from dislike centroid) |
| `top_k_results` | 20 | int | buildings returned at session end (Completed: Top-K) |
| `like_weight` | 0.5 | float | kept for pref vector update |
| `dislike_weight` | -1.0 | float | pref-vector update weight for a dislike (like_weight is the positive counterpart) |
| `initial_explore_rounds` | 10 | int | kept for initial batch size |

## Promote-to-taste pool (Discovery → Taste)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `taste_pool_overfetch` | 3 | int | promote-to-taste pool: HNSW neighbours fetched = overfetch * pool target, MMR-downsampled to target |
| `taste_pool_mmr_penalty` | 1.0 | float | promote-to-taste pool: diversity penalty in the MMR down-sample (measured: 0.3 barely moved pairwise similarity) |
| `taste_pool_random_fraction` | 0.2 | float | promote-to-taste pool: share of uniformly random buildings kept for swipe-phase exploration |

## Adaptive clustering (Topic 06)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `adaptive_k_clustering_enabled` | False | bool | Topic 06: silhouette-based k selection {1, 2} |
| `soft_relevance_enabled` | False | bool | Topic 06: softmax over centroid distances vs max |

## Gemini rerank (Topic 02)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `gemini_rerank_enabled` | False | bool | Topic 02: Gemini setwise rerank at session end |

## MMR λ ramp (Topic 04a)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `mmr_lambda_ramp_enabled` | False | bool | Topic 04 (a): per-swipe λ ramp |
| `mmr_lambda_ramp_n_ref` | 10 | int | N_ref for ramp denominator |

## DPP top-K diversity (Topic 04b)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `dpp_topk_enabled` | False | bool | Topic 04 (b): DPP greedy MAP at session-final top-K |
| `dpp_overfetch_multiplier` | 3 | int | Topic 04 (b): candidate window multiplier when DPP ON (n=k*mult so DPP can MAP-narrow) |
| `dpp_alpha` | 1.0 | float | Wilhelm-form diversity strength; Optuna search [0.5, 1.0] |
| `dpp_singularity_eps` | 1e-09 | float | Cholesky residual threshold for singularity |

## HyDE V_initial (Topic 03)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `hyde_vinitial_enabled` | False | bool | Topic 03: HyDE V_initial embedding rerank |
| `hyde_hf_model` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | str | HF Inference API model that embeds the HyDE visual description (same model as the corpus) |
| `hyde_hf_timeout_seconds` | 5 | int | HF embed call timeout; on timeout V_initial falls back to filters-only |
| `hyde_score_weight` | 50.0 | float | HyDE similarity score additive weight |

## Hybrid retrieval RRF (Topic 01)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `hybrid_retrieval_enabled` | False | bool | CRITICAL: default OFF for backward compat |
| `hybrid_rrf_k` | 60 | int | Cormack 2009 default; uniform fusion 1/(k+rank) |
| `hybrid_bm25_dict` | `simple` | str | tsvector dictionary; 'simple' = multilingual-safe (no stemming) |
| `hybrid_filter_channel_enabled` | True | bool | True: filter is a 3rd RRF rank channel; False: filter is a predicate gate |

## Embedding cache (IMP-7)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `pool_precompute_enabled` | False | bool | Currently gates a no-op: cache is warmed naturally via |
| `pool_embedding_cache_max_size` | 5000 | int | IMP-7 FIFO eviction bound; ~5MB max. Bump for larger corpora. |

## Async prefetch (IMP-8)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `async_prefetch_enabled` | True | bool | Re-enabled after PERF-PREFETCH-CHAIN (PR 4 of 4 perf sweep): thread write off-by-one fixed + cache.get consumer wired + Redis backend (INFRA-REDIS-1) provides multi-worker cache coherence. |
| `async_prefetch_cache_timeout_seconds` | 60 | int | Django cache TTL for prefetch entries (seconds) |

## Card cache

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `card_cache_ttl` | 3600 | int | Per-card LRU TTL (PR #22 absorb): cache.get/set under 'bcard:<id>' keys. 3600s default keeps building-card payloads warm across requests without going stale relative to Make DB updates. |

## Gemini context caching (IMP-5)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `context_caching_enabled` | False | bool | default OFF; flip True only after Redis cache backend is wired |
| `context_caching_ttl_seconds` | 3600 | int | Gemini cache TTL; also used as Django cache TTL for resource name |

## Parse 2-stage decouple (IMP-6)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `stage_decouple_enabled` | `os.getenv('STAGE_DECOUPLE_ENABLED', 'false').lower() == 'true'` | env | default OFF; set STAGE_DECOUPLE_ENABLED=true in env to flip |

## Discovery feed (v3.x)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `discovery_chunk_size` | 10 | int | Discovery tab v3.1 hyperparameters (10-card chunk + 3-Tier + Draft Board) |
| `discovery_tier2_min_likes` | 10 | int | tier 2 unlocks once the user has this many Discovery likes |
| `discovery_tier3_min_projects` | 4 | int | tier 3 unlock: boards (projects) required ... |
| `discovery_tier3_min_likes` | 50 | int | ... and total likes required |
| `discovery_tier2_local` | 2 | int | tier 2 chunk mix: cards near the user's taste centroid (local) ... |
| `discovery_tier2_global` | 8 | int | ... vs corpus-wide exploration cards (global), per 10-card chunk |
| `discovery_tier3_local` | 4 | int | tier 3 chunk mix: local ... |
| `discovery_tier3_global` | 6 | int | ... vs global, per 10-card chunk |
| `discovery_dislike_history_window` | 30 | int | most recent dislikes used to build the dislike centroid |
| `discovery_dislike_zone_threshold` | 0.15 | float | pgvector cosine DISTANCE; candidates farther than this from dislike centroid pass |
| `discovery_local_sim_radius` | 0.55 | float | cosine SIM to nearest centroid to count as local/취향 |
| `discovery_centroid_cache_ttl` | 21600 | int | 6h — app-session fixed |
| `discovery_promote_threshold` | 10 | int | Discovery likes that unlock the promote-to-taste (analysis) CTA |
| `discovery_like_hard_cap` | 50 | int | Discovery draft hard stop: block likes beyond 50; client redirects to Taste |
| `discovery_recent_boards_cap` | 10 | int | DISCOVERY-PERF-1: scope tier/exclude/dislike/centroid to most-recent N boards (tunable). Older boards' liked/disliked/saved buildings may re-appear in Discovery — intended behaviour. |
| `discovery_tablesample_pct` | 2.0 | float | DISCOVERY candidate fetch: TABLESAMPLE SYSTEM percentage — block-level random sample that avoids a full seq scan of the large canonical_v2_buildings table (VECTOR(384) + JSONB rows). ~2% of ~39k ≈ 780 sampled, ample for the 120-cap FPS. |

## LLM search ranking (LLM-SEARCH-RANK-1)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `corpus_df_cache_ttl_seconds` | 86400 | int | LLM search (get_corpus_tag_df / engine.llm_search_by_filters) TF-IDF corpus DF cache TTL (24h) |
| `llm_search_topk` | 200 | int | K: tag-score candidate set before BM25 rerank |
| `llm_search_w_bm25` | 8.0 | float | w_bm25: BM25 contribution weight in final score |
| `llm_search_priority_boost` | 0.25 | float | boost factor for filter_priority ordering |
| `llm_search_top_priority_multiplier` | 4.0 | float | D2: rank-0 axis extra dominance multiplier |
| `llm_search_idf_ceiling` | 3.0 | float | IDF ceiling clamp (rare tags capped at 3x) |
| `llm_search_base_weights` | `{program: 10.0, typology_primary: 6.0, location_country: 5.0, location_city: 5.0, material: 4.0, style: 4.0, atmosphere: 3.0, color_tone: 2.0, architectural_elements: 4.0, year_min: 1.0, year_max: 1.0}` | dict | per-axis base scoring weights (soft, no hard gate) |

## Persona report grounding (BACK-LLM-5)

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `report_fact_min_shown` | 3 | int | min cards shown with a feature before it can become a fact |
| `report_fact_min_liked` | 2 | int | min liked cards with a feature before it can become a LIKE fact |
| `report_fact_min_ratio` | 1.5 | float | min smoothed like-rate ratio (feature vs not) for a LIKE fact |
| `report_fact_tie_ratio` | 0.3 | float | ratio candidates within this margin are tie-broken by support (Q37) |
| `report_fact_max_likes` | 3 | int | cap on selected LIKE facts per report |
| `report_fact_max_dislikes` | 1 | int | cap on selected DISLIKE facts per report |
| `report_dislike_often` | 0.4 | float | min disliked/shown rate for a feature to qualify as a DISLIKE fact |
| `report_dislike_mostly` | 0.8 | float | disliked/shown rate at/above which the dislike_word is "mostly" (else "often") |
| `report_fact_overlap_max` | 0.8 | float | drop a candidate fact whose supporting buildings overlap an already-selected fact's by >= this (Q38) |
| `report_fact_smoothing` | 1 | int | Laplace smoothing constant `s` in r=(liked+s)/(shown+2s) -- guards against small-sample flukes (Q36) |

## Persona axis scores

| Key | Value | Type | Meaning (from code comment) |
|---|---|---|---|
| `axis_confidence_full_n` | 5 | int | FULL-PERSONA-SPECTRUM (2026-09-27): axis_scores.py confidence formula -- confidence = min(n / axis_confidence_full_n, 1) * max(0, 1 - iqr). n=5 liked buildings is treated as "full" confidence (before the iqr penalty). |

## Undocumented keys

None — every key carries a comment in `settings.py`.

