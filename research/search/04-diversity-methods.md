# Diversity Methods: MMR λ Tuning vs DPP vs Submodular

## Status
Ready for Implementation

## Question
Is MMR with `mmr_penalty = 0.3` still the right relevance-diversity trade-off method for archi-tinder, or should the two insertion points (per-swipe `compute_mmr_next` and session-final `get_top_k_mmr`) migrate to Determinantal Point Processes (DPPs), submodular facility-location objectives, or cluster-based diversification? Given our specific 150-pool / 60-candidate / 20-output setup, what does the evidence actually support?

## TL;DR
- **Keep MMR at the per-swipe insertion point.** It is naturally online/greedy, runs inside the 2-s swipe budget, and the "relevance target" (K-Means centroid) is already the right first-term. The immediate win here is **making `mmr_penalty` session-aware**, not switching methods: early-session `|exposed|` is tiny so redundancy is weak; late-session it dominates. Introduce `λ(t) = λ_base · clamp(|exposed|/N_ref, 0, 1)` — simple ramp, no new dependencies.
- **Replace MMR with DPP greedy MAP at `get_top_k_mmr` (session-final top-K).** Our bounded k=20 output from a 60-candidate shortlist is the *textbook* DPP sweet spot: Chen et al. 2018's fast greedy MAP runs at ~O(M³) total where M is candidate count — ~216 K ops for M=60, literally milliseconds, so the historical "DPP is too expensive" argument is moot here. Two independent sources (Chen et al. NeurIPS 2018 and Wilhelm et al. CIKM 2018 at YouTube) show DPP wins against MMR on live A/B with the same relevance input.
- **Explicitly do not adopt** facility-location submodular (Lin & Bilmes 2011) as a separate track — it is *the same greedy family* as MMR with a similar 1−1/e guarantee and a cleaner theoretical framing, but no meaningful empirical edge over MMR at our scale and no adoption energy in the recommender community. Cluster-based diversification is already implicit via K-Means `k_clusters=2` on the *relevance* side; duplicating that in the diversity term is redundant.

## Context (Current State)

There are **two insertion points** with different latency envelopes and different redundancy semantics, and the right diversity method differs between them:

1. **Per-swipe online** — `backend/apps/recommendation/engine.py:492-532` `compute_mmr_next()`:
   - Relevance term: `max(cos(candidate, centroid))` across K-Means centroids (multi-modal).
   - Redundancy term: `max(cos(candidate, exposed))` across **all exposed cards** (likes, dislikes, skips) per `backend/apps/recommendation/views.py:221,276` where `exposed_ids` accumulates every shown building.
   - Budget: must return in ~2 s (part of swipe loop).
   - k = 1 (one card at a time); `|exposed|` grows 1 per swipe from 1 → ~25.

2. **Session-final batch** — `backend/apps/recommendation/engine.py:661-755` `get_top_k_mmr()`:
   - Fetches top 3k=60 candidates by `ORDER BY embedding <=> centroid` from Postgres.
   - Greedy MMR picks k=20 from those 60. Redundancy term is `max(cos(candidate, already_selected))` — **only the output set**, not `exposed_ids`.
   - Budget: user sees an action card first (`engine.py:637-658`), so 500–1500 ms is UX-invisible.

`λ = mmr_penalty = 0.3` is defined in `backend/config/settings.py:135` (RECOMMENDATION dict). It is identical at both insertion points. `algorithm.md:55` lists its tunable range as 0.1–0.4.

The exploring phase uses **farthest-point sampling** (`engine.py:410-448`), a separate diversity mechanism; it is out of scope here.

## Findings

### MMR's greedy structure is a submodular approximation, with the same 1−1/e guarantee

MMR's score `score(b) = rel(b) − λ·max_{s∈S} sim(b,s)` is the greedy-step objective of a monotone submodular set function (coverage minus redundancy). The greedy algorithm on any monotone submodular function achieves a (1 − 1/e) ≈ 0.632 approximation of the optimum ([Nemhauser et al. 1978 result, summarized at Jeremy Kun's blog](https://www.jeremykun.com/2014/07/07/when-greedy-algorithms-are-good-enough-submodularity-and-the-1-1e-approximation/); [MIT 6.854 lecture on submodular maximization](https://courses.csail.mit.edu/6.854/20/sample-projects/A/submodular%20optimization.pdf)). Lin & Bilmes' 2011 facility-location formulation for document summarization is an explicitly submodular sibling of MMR, combining representativeness and a diversity reward; it inherits the same 1−1/e bound ([Lin & Bilmes 2011, ACL](https://aclanthology.org/P11-1052/)). **Practical implication**: MMR is not a naïve heuristic — it is the greedy instance of a well-understood submodular family. This is the reason "switch MMR to submodular" is largely a re-branding, not a capability upgrade, for our use case.

### DPPs are fundamentally different: they score *sets*, not candidates

A Determinantal Point Process defines a probability `P(Y) ∝ det(L_Y)` where `L_Y` is the submatrix of a positive semi-definite kernel indexed by the chosen subset ([Kulesza & Taskar 2012 "Determinantal Point Processes for Machine Learning", arXiv 1207.6083](https://arxiv.org/abs/1207.6083)). The canonical quality-similarity factorization is `L_ij = q_i · S_ij · q_j` where `q_i` is a per-item quality score and `S_ij` is pairwise similarity ([Kulesza & Taskar 2012, §3.1 L-ensembles](http://www.alexkulesza.com/pubs/dpps_fnt12.pdf)). The MAP set `argmax_Y det(L_Y)` is NP-hard, but the greedy algorithm — pick the item maximizing the determinant-increase at each step — runs efficiently and is the de-facto serving recipe.

The *critical* property for our use case: unlike MMR, which compares a candidate to each selected item pairwise, the DPP determinant evaluates the *entire set geometry* at once. Wilhelm et al. illustrate this concretely: three redundant Action videos together achieve roughly 10 000× lower determinant probability than an Action + Comedy + Documentary triple of equivalent quality ([Medium write-up of Wilhelm 2018 DPP](https://medium.com/data-science-collective/diversity-in-recommendations-determinantal-point-processes-dpp-2427bf1b6324)). MMR would require a carefully tuned λ to reproduce this and still can only do pairwise myopic comparisons.

### DPP complexity: trivial at our scale

Classical greedy DPP MAP is O(M⁴) (recomputing the determinant each step); Chen et al.'s Cholesky-incremental variant is O(M³) total for selecting up to M items from a candidate pool of M ([Chen, Zhang, Zhou 2018 "Fast Greedy MAP Inference for DPP", arXiv 1709.05135](https://arxiv.org/abs/1709.05135); [Han et al. 2017 "Faster Greedy MAP Inference for DPPs"](https://proceedings.mlr.press/v70/han17a/han17a.pdf)). For our session-final stage where M=60, 60³ = 216 000 elementary operations — sub-millisecond on any CPU. The "DPP is too expensive" argument, which still shapes many recommender blog posts, evaporates entirely at our scale.

### DPP beats MMR empirically on production recommender systems

- **Chen et al. 2018** directly compare DPP vs MMR on Netflix Prize and Million Song Dataset with candidate pools of ~735 and 811 items and k=20/100. They report DPP "performs the best with respect to the relevance–diversity trade-off" on both datasets. Online A/B on a mobile news feed shows DPP yielded 1.33 % increase in engagement vs MMR's 0.84 % lift ([arXiv:1709.05135 §5](https://ar5iv.labs.arxiv.org/html/1709.05135)).
- **Wilhelm et al. 2018** at YouTube deploy a windowed DPP on the live homepage and report significant short- and long-term engagement gains against the MMR-family baseline ([Wilhelm et al. CIKM 2018](https://dl.acm.org/doi/10.1145/3269206.3272018)). Their L-ensemble: `L_ii = q_i²` and `L_ij = α · q_i · q_j · exp(−D_ij / 2σ²)` with `α ∈ [0,1]` controlling diversity strength. Quality `q_i` is the retrieval score (analogous to our `cos(candidate, centroid)`).

**Scale caveat.** Both benchmarks above use candidate pools an order of magnitude larger than ours (735–811 items, 100s-of-genres at YouTube). Our session-final 60-candidate shortlist is already the top cosine neighbours of a single centroid, so semantic density is high and "set geometry" has less room to disagree with pairwise MMR. The cited wins likely *attenuate* in our regime; the A/B is the honest answer, which is why Option B is flag-gated rather than replace-in-place.

### Session-aware λ: the cheapest win we are missing

The per-swipe redundancy term takes a `max` over `|exposed_ids|` at swipe *t*. At t=1 there is essentially no history to de-duplicate against, so the penalty encodes little ranking information and can override relevance arbitrarily. As `|exposed|` grows, the `max` draws from more inputs and the term carries real signal; by t=20 it saturates — tiny relevance differences are dwarfed by the diversity term and the selection reduces to "least-similar-to-history" with almost no relevance input. **The fixed λ=0.3 is effectively different policies at early vs late session.** An adaptive schedule — `λ(t) = λ_base · clamp(|exposed|/N_ref, 0, 1)` with `λ_base=0.3` and `N_ref=10` — gives relevance full weight for the first few swipes (where we have no history to de-duplicate against anyway) and phases diversity in as the exposure set grows ([Adaptive Quality-Diversity Trade-offs arXiv:2602.02024](https://arxiv.org/abs/2602.02024) gestures at the same idea). This is a one-line code change and an Optuna-tunable hyperparameter — no new libraries.

### Qdrant's MMR benchmark already cited in 02-reranking-layer.md

Per [Qdrant's MMR blog](https://qdrant.tech/blog/mmr-diversity-aware-reranking/) (reused from `research/search/02-reranking-layer.md`): MMR reranking on expert queries buys 23.8–24.5 % intra-list diversity at a 20.4–25.4 % nDCG@10 cost. In our single-user archi-tinder context, the nDCG cost is less directly applicable (there is no ground-truth relevance — only the user's own centroid), but the *magnitude of the trade-off* tells us λ choice matters a lot, and a better method should Pareto-improve that trade-off.

## Options

### Option A — Session-aware λ ramp for `compute_mmr_next` (RECOMMENDED, cheap)
Replace constant `RC['mmr_penalty']` in `compute_mmr_next` with `lambda_t = mmr_penalty_base · min(1.0, len(exposed_ids) / mmr_lambda_ramp)`. Add `mmr_lambda_ramp = 10` to `RECOMMENDATION` dict. Exit criterion unchanged.
- **Pros**: One-line code change; Optuna-tunable; keeps the online path pure-numpy and inside the 2-s budget; no new dependencies (per CLAUDE.md: `sentence-transformers` forbidden, numpy already present).
- **Cons**: Pure tuning — not a methodological upgrade. Doesn't address MMR's myopic nature.
- **Complexity**: **Very Low** (~2 hours incl. test + hyperparam entry).
- **Expected impact**: Medium on early-session feel (more relevance, less forced diversity); small on late-session. Measurable via median-swipe-to-convergence and like-rate per round.

### Option B — DPP greedy MAP at `get_top_k_mmr` (RECOMMENDED, methodological upgrade)
Replace the greedy MMR loop at `engine.py:713-752` with Chen et al.'s Cholesky-incremental greedy DPP MAP. L-ensemble: `L_ii = q_i²`, `L_ij = q_i · q_j · ⟨v_i, v_j⟩` where `q_i = max(cos(v_i, centroid_c))` (the same multi-modal relevance already used) and `⟨v_i, v_j⟩` is the cosine between candidate embeddings (already available in `row['_vec']`). Selection picks k=20 from the 60-candidate shortlist by maximizing incremental log-det. Tunable diversity strength via `α` in `L_ij = α · q_i · q_j · ⟨v_i, v_j⟩` (mirrors `mmr_penalty`).
- **Pros**: Published wins over MMR on comparable setups; determinant natively scores *set geometry*, not myopic pairwise; O(60³) = trivial; no new libraries (pure numpy Cholesky). Single-point-of-change (session-final only).
- **Cons**: New code path; needs a correctness test (verify the selected set is subset-monotone for a toy L). Tuning `α` means a second hyperparam in the Optuna search.
- **Complexity**: **Low-Medium** — ~1 day incl. unit tests. Reference: Chen et al. Algorithm 1 (~30 LOC pure numpy).
- **Expected impact**: Uncertain at our scale (60 candidates → 20) — the published gains come from pools an order of magnitude larger where set geometry matters more. Flag-gated A/B is the honest answer. Bias is toward a small positive lift on top-K *spread* (mean-pairwise-cosine, program/style Shannon entropy) with neutral-to-positive relevance proxy.

### Option C — Facility-location submodular (Lin & Bilmes 2011 style)
Replace MMR with `F(S) = Σ_j max_{i∈S} sim(candidate_j, centroid) + λ · Σ_{c ∈ clusters} √Σ_{i∈S ∩ c} r_i`, a representativeness + sqrt-of-coverage reward.
- **Pros**: Monotone submodular → 1−1/e guarantee; cleaner theoretical framing than MMR.
- **Cons**: Empirically indistinguishable from MMR at k=20 and M=60 — same greedy family, same approximation ratio; the sqrt-of-coverage needs an external cluster assignment which is extra machinery without a clear payoff (our 2-cluster K-Means is on the *relevance* side, not for diversity coverage). No adoption momentum in the recsys literature at this scale.
- **Complexity**: **Medium** — requires cluster-assignment logic for the coverage term.
- **Expected impact**: Near-zero incremental gain over MMR; adoption adds maintenance burden.

### Option D — Cluster-based diversification (round-robin across `program`/`style`)
Enforce quota-based diversity: within the 60-candidate shortlist, bucket by `program` / `style` and round-robin.
- **Pros**: Trivial to implement; interpretable ("at least one of each program").
- **Cons**: Hard buckets discard semantic-embedding nuance (a modernist concrete library is closer to a modernist concrete office than to a baroque museum, but bucketing forces the latter pairing). Our `program` vocab has 14 values — round-robin would oversample rare programs relative to centroid relevance. Incompatible with the embedding-centric design per `algorithm.md`.
- **Complexity**: **Low**.
- **Expected impact**: Unpredictable; likely a regression on relevance proxy.

## Recommendation

**Ship A and B together.** They are complementary and address different insertion points:

1. **Option A** (session-aware λ ramp, per-swipe) — cheap, no new methodology, tunable via existing Optuna harness. Gate behind nothing; make it the default.
2. **Option B** (DPP greedy MAP, session-final) — flag-gated `DPP_TOPK_ENABLED` in `RECOMMENDATION` dict; when off, current MMR path runs unchanged. Enables safe A/B rollout.

The two combined target the system's two distinct diversity roles: **A** keeps the swipe loop feeling curated (not forced-random in the first few swipes when there's nothing yet to de-duplicate from); **B** ensures the "Your Taste is Found!" results screen (the product moment that earns the brand) uses a method empirically proven to beat MMR on engagement in analogous settings.

Explicitly **reject C and D**. C is re-branding without lift; D breaks the embedding-first design. Do **not** migrate the per-swipe path to DPP — the online k=1 streaming use-case is where MMR's greedy structure is a feature, not a bug.

## Open Questions

- **α and σ choice for the DPP L-ensemble.** Wilhelm et al. use a Gaussian kernel `exp(−D_ij / 2σ²)` where D is some distance; ours could use `⟨v_i, v_j⟩` directly (cosine) with α as the single lever. Need Optuna sweep over α ∈ [0.2, 1.0] at k=20, M=60. Is there an information-theoretic prior from the embedding-norm distribution that points to a good σ?
- **Does session-final DPP interact with the proposed Gemini rerank (`research/search/02-reranking-layer.md` Option B)?** Option 02-B proposes an LLM re-rank fused via RRF on the 60-candidate shortlist. If DPP is added too, the RRF input should be (cosine-rank, LLM-rank), and *then* DPP runs on the RRF-ordered relevance scores as the `q_i` input. Order matters — document it.
- **Liked vs exposed as the redundancy anchor.** Per-swipe redundancy currently uses `exposed_ids` (includes dislikes). Late-session this means a candidate similar to a dislike is penalized for diversity, which is *arguably wrong* — we want diversity *from what the user has already seen*, separate from the dislike-driven relevance penalty. An alternative anchor is `liked_ids`, but that makes redundancy light at session start. Empirical comparison required. (This is a per-swipe concern that applies regardless of Option A.)
- **What metric do we optimize `α` against?** Suggest composite = (median cosine-to-centroid of top-K) + β · (1 − mean pairwise cosine among top-K). β is a policy choice; β=1 gives equal weight to relevance and spread.
- **Does the 3k=60 shortlist need to grow for DPP?** MMR under-utilizes the tail of the shortlist because each step re-evaluates just the incremental penalty; DPP cares more about geometry, so a fatter shortlist (say 5k=100) may help. Cheap to sweep.

## Proposed Tasks for Main Terminal

All backend; no frontend changes. Scope is `backend/apps/recommendation/engine.py`, `config/settings.py`, tests.

1. **BACK-DIV-1** — `engine.py:compute_mmr_next`: add session-aware λ. After `candidates = [...]`, compute `ramp = min(1.0, len(exposed_ids) / RC.get('mmr_lambda_ramp', 10))` and replace `RC['mmr_penalty']` in line 526 with `RC['mmr_penalty'] * ramp`. Log `lambda_t` at DEBUG level once per swipe.
2. **BACK-DIV-2** — `config/settings.py`: add `'mmr_lambda_ramp': 10` to `RECOMMENDATION` dict (line ~131-144). Add to `algorithm.md`'s hyperparam table with range 5–20.
3. **BACK-DIV-3** — `engine.py`: add module-level helper `dpp_greedy_map(candidate_vectors: list[np.ndarray], quality_scores: list[float], k: int, alpha: float) -> list[int]` implementing Chen et al.'s Cholesky-incremental greedy MAP. Pure-numpy, <60 LOC. Input: list of (already L2-normalized) 384-dim vectors and matching list of q_i. Output: list of *indices* in selection order. Reference: `arXiv:1709.05135` Algorithm 1.
4. **BACK-DIV-4** — `engine.py:get_top_k_mmr` (line 661-755): after `rows` is fetched (line 703) and `_vec` populated (line 711), branch on `settings.RECOMMENDATION.get('DPP_TOPK_ENABLED', False)`. When true: compute `q_i = max(np.dot(row['_vec'], c) for c in centroids)` for each row, call `dpp_greedy_map(vectors, q_list, k, RC['dpp_alpha'])`, and convert index list → selected rows. When false: current MMR loop unchanged.
5. **BACK-DIV-5** — `config/settings.py`: add `'DPP_TOPK_ENABLED': False` and `'dpp_alpha': 0.5` to `RECOMMENDATION` dict. Add `dpp_alpha` to `algorithm.md` hyperparam table with range 0.2–1.0.
6. **BACK-DIV-6** — `engine.py:dpp_greedy_map`: include a fallback branch — if numeric issues in the Cholesky update (negative incremental variance under epsilon), terminate selection early and pad from remaining by pure quality. Log at WARNING.
7. **TEST-DIV-1** — `backend/tests/test_diversity.py` (new file): (a) golden test — `compute_mmr_next` with `exposed_ids = []` uses λ=0 (pure relevance), `exposed_ids` length ≥ `mmr_lambda_ramp` uses full `mmr_penalty`; (b) parametrized test — identical output when `DPP_TOPK_ENABLED=False` (regression guard for `get_top_k_mmr`); (c) DPP correctness — on a toy 5-item, 2-cluster L-ensemble with known optimum, `dpp_greedy_map` returns the expected subset; (d) DPP does not select duplicates.
8. **ALGO-DIV-1** — After shipping Options A and B flag-off (DPP) / on (λ-ramp) in production, run `backend/tools/algorithm_tester.py` Optuna sweep over `mmr_lambda_ramp` ∈ [5, 20] and `dpp_alpha` ∈ [0.2, 1.0]. Metric: composite of (median convergence round) + (top-K mean pairwise 1−cosine). Apply tuned values only if both components non-negative versus production baseline at 500-persona validation.
9. **OBS-DIV-1** — Add a structured debug log in `get_top_k_mmr` recording `(candidate_count, dpp_enabled, mean_pairwise_cosine_top_k, mean_cosine_to_centroid_top_k, wall_ms)`. Unlocks empirical validation of the Open Questions without code changes.

## Sources

- [Kulesza & Taskar 2012, "Determinantal Point Processes for Machine Learning" (arXiv 1207.6083)](https://arxiv.org/abs/1207.6083) — foundational DPP treatment; L-ensemble factorization.
- [Alex Kulesza — full DPP monograph PDF](http://www.alexkulesza.com/pubs/dpps_fnt12.pdf) — detailed §3.1 on quality-similarity decomposition.
- [Wilhelm et al. 2018, "Practical Diversified Recommendations on YouTube with DPP", CIKM 2018](https://dl.acm.org/doi/10.1145/3269206.3272018) — YouTube-scale DPP deployment; the recipe to adapt.
- [Chen, Zhang, Zhou 2018, "Fast Greedy MAP Inference for DPP" (arXiv 1709.05135)](https://ar5iv.labs.arxiv.org/html/1709.05135) — Cholesky-incremental greedy MAP, O(M³); direct benchmarks vs MMR.
- [Han et al. 2017, "Faster Greedy MAP Inference for DPPs" (PMLR)](https://proceedings.mlr.press/v70/han17a/han17a.pdf) — complementary fast-DPP result.
- [Lin & Bilmes 2011, "A Class of Submodular Functions for Document Summarization", ACL](https://aclanthology.org/P11-1052/) — facility-location diversity objective; submodular family kin to MMR.
- [Carbonell & Goldstein 1998, "The Use of MMR" (CMU)](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf) — original MMR paper.
- [Qdrant — MMR diversity-aware reranking (diversity vs nDCG trade-off benchmark)](https://qdrant.tech/blog/mmr-diversity-aware-reranking/) — expert-query numbers reused from `02-reranking-layer.md`.
- [Medium — Aayush Agrawal, Diversity in Recommendations: DPP](https://medium.com/data-science-collective/diversity-in-recommendations-determinantal-point-processes-dpp-2427bf1b6324) — pedagogical walk-through of DPP greedy MAP and L = diag(q)·S·diag(q).
- [NeurIPS 2018 proceedings — Fast Greedy MAP Inference for DPP](http://papers.neurips.cc/paper/7805-fast-greedy-map-inference-for-determinantal-point-process-to-improve-recommendation-diversity.pdf) — published version of Chen et al.
- [Adaptive Quality-Diversity Trade-offs for Large-Scale Batch Recommendation (arXiv 2602.02024)](https://arxiv.org/abs/2602.02024) — adaptive-λ framing supporting Option A.
- [Jeremy Kun — When Greedy Algorithms are Good Enough: Submodularity and (1−1/e)](https://www.jeremykun.com/2014/07/07/when-greedy-algorithms-are-good-enough-submodularity-and-the-1-1e-approximation/) — pedagogical treatment of the MMR ↔ submodular connection.
- [MIT 6.854 — Greedy Maximization of Submodular Functions (Rolnick & Weed)](https://courses.csail.mit.edu/6.854/20/sample-projects/A/submodular%20optimization.pdf) — proof of the 1−1/e bound.
