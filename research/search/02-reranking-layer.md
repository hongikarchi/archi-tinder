# Re-ranking Layer: Do We Add One, and Where?

## Status
Ready for Implementation

## Question
After the 150-pool vector retrieval, should archi-tinder add an explicit re-ranking stage (cross-encoder, LLM-based, or learned-to-rank) to pick the final top-K, and if so, at which pipeline phase does the cost/benefit actually pay off?

## TL;DR
- **We already have a re-ranker** — `get_top_k_mmr()` at `backend/apps/recommendation/engine.py:661-755` fetches 3×k (=60) cosine neighbours of the K-Means centroid and re-orders by MMR. The real question is whether to add a *scoring-based* stage **on top of MMR at session completion**, not to invent re-ranking from nothing.
- **Recommended**: ship a **Gemini-2.5-flash setwise re-ranker** over the 60-candidate shortlist at session completion (one call per completed session), flag-gated as `GEMINI_RERANK_ENABLED`, fused with MMR's diversity via `final_score = α·rerank_rank + (1-α)·mmr_rank` RRF. Zero new dependencies (Gemini is already integrated at `services.py:93-199`), latency parked off the swipe hot path.
- **Explicitly defer** per-swipe LLM re-rank (busts the 2-s swipe budget), local cross-encoders (the `no sentence-transformers` rule gates them), and learning-to-rank (we have no labelled session logs yet). Re-visit after logging 1K+ completed sessions.

## Context (Current State)

archi-tinder's recommendation pipeline has *three* distinct insertion points where a re-ranker could live, each with a different latency envelope:

1. **Pool creation** (once per session, `backend/apps/recommendation/engine.py:327-367` + `views.py:155-180`): a weighted `CASE WHEN` filter score produces 150 building IDs. Off the swipe hot path; runs on session start.
2. **Per-swipe next-card** (`engine.py:410-448` `farthest_point_from_pool`, `engine.py:492-532` `compute_mmr_next`): each swipe triggers `compute_mmr_next(...)` which picks the next building by relevance-to-centroid minus redundancy-to-shown. Runs inside the 2-s swipe budget (p95 ~5 s per `CLAUDE.md`). Already diversity-re-ranked but not relevance-re-scored.
3. **Final top-K at session completion** (`engine.py:661-755` `get_top_k_mmr`): fetches 3×k (=60) candidates `ORDER BY embedding <=> centroid`, then greedy MMR with `λ=mmr_penalty=0.3` (`config/settings.py` RECOMMENDATION dict). One-shot; user sees a "Your Taste is Found!" action card first (`engine.py:637-658`), so there is a natural UX moment that absorbs 500-1500 ms of latency gracefully.

Critically, MMR **is a re-ranker** — it is second-stage re-ordering of first-stage cosine hits. What the current pipeline *does not* do is re-score candidates against any signal richer than the 384-dim embedding (no text match, no cross-encoder interaction features, no LLM-judged relevance). Every text field the embedding can't capture — `visual_description` phrasing, `tags` enumerations, `atmosphere` prose, `architect` proper nouns — is invisible to both retrieval and ranking.

Gemini 2.5-flash is already wired into the stack for NL query parsing (`services.py:93-134`) and persona report generation (`services.py:137-199`), with a `_retry_gemini_call` helper and structured-JSON response mode. No new SDK/infra is required to add an LLM-based re-ranker.

## Findings

### 1. Cross-encoder latency numbers make sense only in context

On **GPU** the MS MARCO MiniLM-L12-v2 cross-encoder runs ~2–5 ms/pair; on **CPU**, benchmarks on the same model show roughly `12 ms` for a batch of 1, `58 ms` for 10 pairs, `740 ms` for 100 pairs ([Metarank cross-encoder guide](https://docs.metarank.ai/guides/index/cross-encoders), [sbert.net MS MARCO CE docs](https://www.sbert.net/docs/pretrained-models/ce-msmarco.html)). For our 60-candidate shortlist that's ~400 ms on a modest CPU. Reranking adds about 100–200 ms of latency per query when dealing with ~30 candidates in production RAG systems, and cross-encoders cost roughly 10–100 ms for re-scoring the top 100 candidates ([Milvus: cross-encoder overhead](https://milvus.io/ai-quick-reference/what-is-the-overhead-of-using-a-crossencoder-for-reranking-results-compared-to-just-using-biencoder-embeddings-and-how-can-you-minimize-that-extra-cost-in-a-system)).

**But**: CLAUDE.md states `"SentenceTransformers is NOT a dependency here — embeddings are pre-computed"`. Running a cross-encoder locally would violate that rule, so the interesting comparison is vs *hosted* cross-encoder APIs, not vs local inference.

### 2. Hosted rerank API latencies cluster around 400–700 ms regardless of provider

Public benchmarks place Cohere Rerank 3.5 and Voyage Rerank 2.5 at ~595–603 ms average p50 latency ([Agentset rerankers leaderboard](https://agentset.ai/rerankers)). Cohere's own guidance: "Sending over 100 documents per request significantly increases latency and token consumption without proportional gains in nDCG" and "this model is most effective when used as a second-stage ranker to filter the top 20 to 100 results from a high-recall vector search" ([Cohere Rerank docs](https://docs.cohere.com/docs/rerank)). API latency generally adds 100–400 ms to the pipeline p50 and can spike under load. For our 60-candidate scale the provider-hosted option fits, but it introduces a new vendor relationship and a new API key.

### 3. LLM zero-shot rerankers have converged on *setwise* prompting

Pointwise prompting (score each doc independently) is efficient but weak. Listwise (the full RankGPT pattern) is strong but expensive: O(n) LLM calls via sliding-window sort. **Setwise** — "select the most relevant from a set of k" — splits the difference: it needs materially fewer LLM inferences than listwise and offers comparable quality when logits or structured output are available ([Zhuang et al. 2023, "A Setwise Approach for Effective and Highly Efficient Zero-shot Ranking with Large Language Models"](https://arxiv.org/html/2310.09497v2); [ACM SIGIR 2024](https://dl.acm.org/doi/10.1145/3626772.3657813)). The `rank_llm` and `llm-rankers` toolkits support Gemini-family models directly for listwise/setwise rerank ([RankLLM GitHub](https://github.com/castorini/rank_llm), [ielab/llm-rankers](https://github.com/ielab/llm-rankers)). Pointwise approaches score high on efficiency but suffer from poor effectiveness; pairwise demonstrate superior effectiveness but incur high computational overhead — setwise is the Pareto point.

For a 60-document candidate set with a 1 M-token context window (Gemini 2.5-flash supports 1 M context, [ai.google.dev pricing](https://ai.google.dev/gemini-api/docs/pricing)), a *single* setwise call can re-rank the entire shortlist with no sliding-window bookkeeping. Cost estimate: if each candidate is ~150 tokens of `visual_description`+metadata, 60 × 150 ≈ 9 K input tokens + ~300 output tokens. At Gemini 2.5-flash pricing ($0.30 / M input, $2.50 / M output), that's ~$0.003 per session completion. Negligible.

### 4. MMR + cross-encoder is a deliberate relevance-diversity trade-off, not a free upgrade

On expert queries, MMR re-ranking increases intra-list diversity by 23.8–24.5 % at a 20.4–25.4 % nDCG@10 cost ([Qdrant: Balancing Relevance and Diversity with MMR](https://qdrant.tech/blog/mmr-diversity-aware-reranking/); [Carbonell & Goldstein 1998, "The Use of MMR"](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf)). If we add a relevance-only re-ranker and let it *replace* MMR, we'd get nDCG back but collapse diversity — fatal on a "Your Taste is Found!" results screen where the five-to-twenty cards should feel like a curated variety. **Fuse**, don't replace: the rerank score should *join* MMR, e.g. via RRF over both rank lists.

### 5. Personalized re-ranking using session signal beats generic cross-encoders on session tasks

Reranking rearranges items from the previous ranking stage to better meet users' demands; post-processing adjusts the final list based on alternative weighting criteria, which ensures the recommendations better reflect a wider range of factors ([ACM TKDD 2024, "Utility-Oriented Reranking with Counterfactual Context"](https://dl.acm.org/doi/10.1145/3671004)). For our setup, the relevant personalization signal is already aggregated in the like-vector list and the 2-cluster K-Means centroids (`engine.py:451-489`). A re-ranker that can see `(liked_building_metadata, candidate_metadata)` simultaneously — something a cross-encoder *cannot* do without explicit prompt engineering, but an LLM can — has a direct quality ceiling advantage. This argues again for an LLM-style prompt feeding the liked set and the candidate pool in one shot.

### 6. Learned-to-rank (LambdaMART/LightGBM) is powerful but label-gated

LightGBM's `lambdarank` objective implements LambdaMART and is the standard learning-to-rank workhorse ([LightGBM LGBMRanker docs](https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMRanker.html); [Shaped: LambdaMART Explained](https://www.shaped.ai/blog/lambdamart-explained-the-workhorse-of-learning-to-rank)). It thrives on query-group data with (TF-IDF, BM25, click rate, dwell-time, prior engagement) features. **We don't have labelled session logs yet** — not even dwell-time, since the swipe gesture is a single binary bit. Training LambdaMART today means either synthetic labels (dubious) or logging-gated deployment (correct but months away). Defer.

## Options

### Option A — Do nothing; rely on MMR + centroid cosine
Keep the existing pipeline.
- **Pros**: Zero risk, zero cost, zero latency budget hit. MMR already handles diversity, and with pre-computed 384-dim multilingual embeddings, cosine-to-centroid is a reasonable relevance prior.
- **Cons**: Leaves rich text signal (`visual_description`, `tags`, `atmosphere`, `architect`) unused at ranking time. Semantic near-ties in embedding space (buildings 0.01 cosine apart in the 60-candidate shortlist) are resolved by MMR's diversity term only — no *relevance* tiebreaker beyond centroid similarity.
- **Complexity**: None.
- **Expected impact**: Baseline.

### Option B — Gemini 2.5-flash setwise re-rank at session completion (RECOMMENDED)
Add a single call to `services.generate_rerank(candidates, liked_buildings)` inside `get_top_k_mmr` **after** MMR but before the top-K cut. Pass 60 candidates' `(building_id, name_en, visual_description, tags, atmosphere, material, architect)` and a summary of liked buildings. Ask the LLM for a JSON list of building IDs in relevance order. Fuse with MMR's implicit rank via RRF (`k=60` constant, à la `01-hybrid-retrieval.md`). Flag-gate behind `GEMINI_RERANK_ENABLED`.
- **Pros**: No new dependencies (Gemini already integrated). Setwise prompt = 1 LLM call per completed session, negligible cost (~$0.003). Off the swipe hot path — user sees an action card first, so 500-1500 ms latency is invisible. Can read text fields MMR can't. Personalization is free — just include liked-building summary in the prompt.
- **Cons**: Needs careful prompt design to avoid hallucinated IDs (mitigate with post-hoc ID-set validation and fallback to MMR order). Non-deterministic output (mitigate with `temperature=0.0`). Vendor-lock on Gemini (but we're already locked for query parsing).
- **Complexity**: **Low-Medium** — ~1 day for prompt + fusion code + flag + tests.
- **Expected impact**: Medium-High on top-K quality; zero impact on swipe-loop feel.

### Option C — Cohere / Jina / Voyage Rerank API on the 60-candidate shortlist
Same insertion point as Option B, but use a dedicated rerank API.
- **Pros**: Industry-grade cross-encoder models, designed exactly for this size. Deterministic, well-benchmarked latency (~600 ms p50).
- **Cons**: New vendor, new API key, new failure mode. Cannot natively consume the liked-building personalization context (rerank APIs take `(query, documents)` — we'd need to synthesize a pseudo-query from likes). Added operational cost ~$1/1K reranks typical.
- **Complexity**: **Medium** — vendor onboarding + new service module + fallback path.
- **Expected impact**: High on generic relevance, medium on personalization (pseudo-query is lossy).

### Option D — Learning-to-rank (LambdaMART via LightGBM)
Train an LGBMRanker on offline-logged session data once we have enough labels. Features: cosine-to-centroid, BM25 score (from Option 01), tag-overlap with likes, program match, architect match, position in initial MMR order.
- **Pros**: Pure Python, fast inference (~ms per candidate), no vendor dependency, tunable. Dominant in production LTR historically.
- **Cons**: Requires labelled training data we don't have. Synthetic-label experiments are risky. Only defensible after we log 1K+ completed sessions with like/final-save outcomes.
- **Complexity**: **High** (labels + feature pipeline + training infra + A/B harness).
- **Expected impact**: Unknown until we have labels. Probably large once the data arrives.

## Recommendation

**Ship Option B.** Concrete design:

1. **`services.py`** — add `rerank_candidates(candidates: list[dict], liked_summary: str, target_k: int) -> list[str]`. Uses the `_retry_gemini_call` helper already present. System instruction: "You are an architectural taste re-ranker. Given a user's liked buildings and a candidate shortlist, return the building_ids ordered by relevance to the user's taste. Return ONLY a JSON array of building_id strings. Do not invent IDs not in the input." Temperature = 0.0, response_mime_type='application/json'. Validate the returned IDs are a subset of input IDs; on drift, fall back to the input order.
2. **`engine.py:get_top_k_mmr`** — after MMR selection produces the ordered `selected` list (line 752), call the re-ranker when `settings.RECOMMENDATION.get('GEMINI_RERANK_ENABLED', False)` is true. Fuse via RRF: `fused_score[bid] = 1/(60 + mmr_rank) + 1/(60 + rerank_rank)`. Sort by fused score desc, take top `k`. When the flag is off, behaviour is unchanged.
3. **`config/settings.py`** — add `'GEMINI_RERANK_ENABLED': False` to the `RECOMMENDATION` dict (line ~131-144).
4. **Latency defence** — the rerank call is wrapped in a `try/except` that falls back to pure MMR order on any Gemini failure, preserving current behaviour as the robust default.
5. **Scope** — apply only in `get_top_k_mmr` (final top-K at session completion). Do **not** apply in `compute_mmr_next` (per-swipe hot path). Do **not** apply in `create_bounded_pool` (pool creation is filter-driven, not LLM-judged).

Why B beats C: Option B reuses existing tooling zero-dependency, can natively express personalization via liked-building context, and fits the session-completion timing perfectly. C is a stronger generic reranker but loses the personalization edge and adds vendor surface area for marginal gain at our 60-candidate scale.

Why defer D: learning-to-rank is the right terminal state, but only after we've logged enough `(session_id, candidate, final_save_yes/no)` tuples to train on. Phase it after 1K+ completed sessions are logged.

## Open Questions

- **Does re-ranking 60 centroid-neighbours (all already highly similar) actually surface meaningful differentiation, or does MMR's diversity penalty already dominate?** Measure via A/B: post-session save rate, "go back" rate, and persona-report satisfaction proxy across equal-N sessions with flag on/off.
- **Does the personalization prompt signal (liked buildings summary) mislead the LLM when the user's taste is multi-modal?** Our K-Means k=2 setup assumes 2 taste clusters. Feeding all likes as one summary may wash out the modes. Possible refinement: re-rank each cluster's candidates independently then interleave.
- **What's the user-facing latency tolerance on "show my results"?** UX currently inserts an action card as a cover; if the results screen loads in ≤1.5 s after the action swipe, users will not perceive delay. Need an empirical measurement of current time-to-results; if already ~800 ms, adding a 500 ms rerank keeps us under threshold.
- **Cost envelope at scale.** At ~10 K completed sessions/month, ~$30/month in Gemini rerank calls. Cheap. At 1 M/month, ~$3 K/month — re-evaluate vs self-hosted alternatives at that scale.
- **Prompt-cache leverage.** Gemini supports implicit/explicit prompt caching. Can the system instruction be cached across sessions for meaningful cost reduction?

## Proposed Tasks for Main Terminal

All backend; no frontend changes. Scope is `backend/apps/recommendation/services.py`, `engine.py`, `config/settings.py`, plus tests.

1. **BACK-RNK-1** — `services.py`: add `rerank_candidates(candidates: list[dict], liked_summary: str) -> list[str]`. Contract: (i) build a prompt including each candidate's `building_id, name_en, visual_description, tags (joined), atmosphere, material, architect`; (ii) system instruction from the `_RERANK_PROMPT` constant (define alongside `_PARSE_QUERY_PROMPT` at `services.py:32-53`); (iii) `temperature=0.0`, `response_mime_type='application/json'`; (iv) wrap in `_retry_gemini_call`; (v) validate returned IDs ⊆ input IDs, fallback to input order on mismatch.
2. **BACK-RNK-2** — `engine.py:get_top_k_mmr` (lines 661-755): insert the rerank call **between** the candidate fetch (line 703, after the `cur.execute(... LIMIT %s ...)` that produces the 60 rows) **and** the MMR greedy loop (line 714, `while len(selected) < k`). The rerank operates on the full 60-row candidate set; it produces an ordered list of building_ids that is then fused with the initial cosine ordering via RRF (`fused_relevance[bid] = 1/(60 + cosine_rank) + 1/(60 + rerank_rank)`). MMR then runs *with `fused_relevance` replacing the pure cosine-to-centroid score* as the relevance term (the `relevance = max(np.dot(candidate_emb, c) for c in centroids)` line). The MMR diversity penalty (`- RC['mmr_penalty'] * redundancy`) is unchanged. Gate the rerank call on `settings.RECOMMENDATION.get('GEMINI_RERANK_ENABLED', False)`; when flag is off, `fused_relevance` is untouched and behaviour is identical to current code. On any Gemini exception, log and fall back to cosine-only relevance (current behaviour). Liked-building summary comes from a helper `_liked_summary_for_rerank(like_vectors)` (see BACK-RNK-3).
3. **BACK-RNK-3** — `engine.py`: add helper `_liked_summary_for_rerank(like_vectors) -> str` returning a compact summary string used as the personalization context for the rerank prompt (e.g., `"User liked {n} buildings: {name1} ({style1}, {atmosphere1}); ..."`, truncated at ~1 K tokens).
4. **BACK-RNK-4** — `config/settings.py`: add `'GEMINI_RERANK_ENABLED': False` to the `RECOMMENDATION` dict (line ~131-144). No other config changes.
5. **BACK-RNK-5** — `services.py`: define `_RERANK_PROMPT` module-level constant: "You are an architectural taste re-ranker. Given the buildings a user liked and a shortlist of candidate buildings, return the candidate building_ids ordered from most to least aligned with the user's taste. Return ONLY a JSON array of strings, all of which must appear in the input list. Do not invent or omit IDs."
6. **BACK-RNK-6** — `services.py`: sanitize the rerank response: parse JSON array, coerce to list of strings, `set()`-compare vs input candidate IDs; on mismatch (extra or missing IDs), log at WARNING and return the input order.
7. **TEST-RNK-1** — `backend/tests/test_rerank.py` (new file): parametrized tests for (i) flag off → identical to MMR output (golden test), (ii) flag on, happy path → reordered list matches mocked Gemini output, (iii) flag on, Gemini returns invalid IDs → falls back to MMR order, (iv) flag on, Gemini raises → falls back to MMR order. Mock `services.rerank_candidates` directly; no live Gemini calls in unit tests.
8. **TEST-RNK-2** — `backend/tests/test_rerank.py`: add a timing harness test that asserts `get_top_k_mmr` with flag-on completes in <2 s p99 on mocked data (guards against the RRF fusion adding unexpected cost).
9. **ALGO-RNK-1** — After shipping flag-off in production, run the web-testing E2E harness (`web-testing/run.py --personas 10`) with flag toggled; compare final-results satisfaction proxy (e.g., average pairwise cosine in final top-K and spread across `program`/`style`) and median latency on the results-screen. Apply only if median quality strictly improves and latency is within 1.5 s p95.
10. **OBS-RNK-1** — Add a DEBUG-level log line in `get_top_k_mmr` that records `(len(candidates), len(liked_summary_tokens), gemini_latency_ms, fused_changes)` — how many positions changed between MMR order and post-fusion order. This unlocks empirical answers to the Open Questions.

## Sources

- [A Setwise Approach for Effective and Highly Efficient Zero-shot Ranking with Large Language Models — Zhuang et al., SIGIR 2024 (arxiv 2310.09497)](https://arxiv.org/html/2310.09497v2)
- [ACM SIGIR 2024 — Setwise Approach DOI](https://dl.acm.org/doi/10.1145/3626772.3657813)
- [RankLLM: A Python Package for Reranking with LLMs (supports Gemini family)](https://github.com/castorini/rank_llm)
- [llm-rankers (ielab) — listwise/setwise/pairwise toolkits](https://github.com/ielab/llm-rankers)
- [Cohere Rerank v2 API docs — "most effective on top 20-100 results"](https://docs.cohere.com/docs/rerank)
- [Rerank leaderboard — Agentset (Voyage 2.5, Cohere 3.5 ~600 ms p50)](https://agentset.ai/rerankers)
- [Metarank cross-encoder reranking guide — CPU benchmarks per batch size](https://docs.metarank.ai/guides/index/cross-encoders)
- [Sentence-Transformers MS MARCO cross-encoders reference](https://www.sbert.net/docs/pretrained-models/ce-msmarco.html)
- [Milvus — overhead of cross-encoder reranking](https://milvus.io/ai-quick-reference/what-is-the-overhead-of-using-a-crossencoder-for-reranking-results-compared-to-just-using-biencoder-embeddings-and-how-can-you-minimize-that-extra-cost-in-a-system)
- [Qdrant — MMR diversity trade-off (23–25% diversity vs 20–25% nDCG cost)](https://qdrant.tech/blog/mmr-diversity-aware-reranking/)
- [Carbonell & Goldstein 1998 — The Use of MMR, Diversity-Based Reranking (original paper)](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf)
- [Gemini Developer API pricing — Gemini 2.5-flash $0.30 / $2.50 per M tokens](https://ai.google.dev/gemini-api/docs/pricing)
- [LightGBM `LGBMRanker` docs — `lambdarank` objective](https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMRanker.html)
- [Shaped.ai — LambdaMART Explained](https://www.shaped.ai/blog/lambdamart-explained-the-workhorse-of-learning-to-rank)
- [ACM TKDD 2024 — Utility-Oriented Reranking with Counterfactual Context](https://dl.acm.org/doi/10.1145/3671004)
- [Weaviate — Using Cross-Encoders as reranker in multistage vector search](https://weaviate.io/blog/cross-encoders-as-reranker)
