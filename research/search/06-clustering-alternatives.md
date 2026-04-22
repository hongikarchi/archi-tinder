# Preference-space Clustering: K-Means k=2 vs GMM / DBSCAN / Spectral / Adaptive

## Status
Ready for Implementation

## Question
archi-tinder clusters liked-building embeddings via K-Means (k=2, recency-weighted, n_init=3) to produce "taste centroids" for MMR relevance scoring. Does a fixed k=2 under-capture multi-modal taste? Should we migrate to Gaussian Mixture Models, DBSCAN, spectral clustering, fuzzy/soft assignment, or an adaptive-k method?

## TL;DR
- **The dominant constraint is N=3-15 in D=384.** Typical liked-building counts during a session are smaller than 1/25th of the embedding dimension. Every clustering technique in the prompt other than K-Means and single-mean degenerates in that regime — GMM cannot estimate covariance, DBSCAN cannot pick `eps`, spectral/agglomerative need more points to build a meaningful affinity graph.
- **The honest null isn't k=2, it's k=1.** On 3-5 likes, fixed k=2 produces centroids of 1-2 points each — noise masquerading as multi-modal taste. The first-order fix is **adaptive k ∈ {1, 2}** selected at runtime by silhouette score (Rousseeuw 1987), falling back to k=1 whenever the data doesn't clearly separate.
- **Recommended**: ship **adaptive-k K-Means with silhouette-based selection** plus an optional **soft-assignment relevance upgrade** (weighted cosine over centroids instead of `max`), both flag-gated as `ADAPTIVE_K_CLUSTERING_ENABLED`. This is a ~30-line change in `engine.py:451-489`, zero new dependencies (sklearn already present).
- **Defer / reject**: GMM (cannot fit covariance at N<<D), DBSCAN (eps untunable at N≤15), spectral/agglomerative (no quality win at this scale), contextual bandits / full bayesian priors (warranted only after we log enough sessions to be data-driven).
- This report is the direct answer to the open question in `research/search/02-reranking-layer.md` about whether feeding all likes as one summary washes out multi-modal taste.

## Context (Current State)

- `backend/apps/recommendation/engine.py:451-489` `compute_taste_centroids()`:
  - Input: `like_vectors` = list of `{embedding: 384-float, round: int}`, current `round_num`.
  - Applies exponential recency weights: `w_i = exp(-gamma * (round_num - round_i))`, `gamma=0.05` (`config/settings.py:131-144` RECOMMENDATION dict).
  - `KMeans(n_clusters=min(RC['k_clusters'], len(weighted_likes)), random_state=42, n_init=3)` with `sample_weight=w_i`.
  - Returns `(centroids_list, global_centroid)`; global_centroid is the recency-weighted L2-normalized mean (`engine.py:549-573`).
- Cache key = `(sparse-fingerprint of like_vectors, round_num)` — skipped entirely on dislikes, so centroids are stable through dislike streaks.
- Consumed by:
  - `engine.py:492-532` `compute_mmr_next()` — per-swipe MMR, `relevance = max(np.dot(candidate, c) for c in centroids)`.
  - `engine.py:661-755` `get_top_k_mmr()` — final top-K at session completion; fetches `3*k` nearest neighbours of the global centroid, then MMR-reranks over the cluster centroids list.
  - `engine.py:576-599` `compute_convergence()` — delta-V on centroid drift.
- `RC['k_clusters'] = 2` (`config/settings.py:138`), listed in `research/algorithm.md:90` as an Optuna-tunable hyperparameter in range 1-3.
- `RC['min_likes_for_clustering'] = 3`; below that threshold the pipeline uses the raw preference vector (not clustering at all).
- Realistic session footprint: **3-15 like_vectors**, **D=384 embedding**, running inside a Django view hit per-swipe.

Two structural facts upstream matter: (a) embeddings are pre-computed multilingual MiniLM, so distance-metric surprises are baked in (cosine is the right metric); (b) `CLAUDE.md` forbids SentenceTransformers but explicitly permits scipy/sklearn.

## Findings

### 1. N=3-15 in D=384 is the core problem, not k selection

The Euclidean contrast — the ratio of max distance to min distance — decays toward 1 as D grows; in very-high-dim regimes the concept of "nearest neighbour" becomes unstable ([Aggarwal, Hinneburg & Keim 2001, "On the Surprising Behavior of Distance Metrics in High Dimensional Space"](https://bib.dbvis.de/uploadedFiles/155.pdf)). With N < D (here by a factor of 25-100×), the sample points span a subspace of rank N-1; every clustering algorithm is effectively partitioning a 2-14-dimensional affine shell embedded in 384d. On a pre-L2-normalized, semantically dense manifold (as produced by our MiniLM encoder) cosine distances compress further. Translation: fancy clustering geometry (elongated clusters, density-variable clusters, nonconvex clusters) is unobservable at our N. Any method that *requires* seeing that geometry to pay off will underperform K-Means until our preference sample size grows by at least an order of magnitude.

### 2. GMM is a killer, not a tradeoff

Gaussian Mixture Models give soft assignment and probabilistic centroids — attractive on paper. In practice, a GMM fit requires estimating a covariance matrix per cluster. At N=5-15 in D=384:

- **Full covariance** per cluster: needs `D(D+1)/2 = 73,920` parameters per component; rank-deficient by four orders of magnitude.
- **Diagonal covariance**: needs `D = 384` parameters per component; still rank-deficient by >25×.
- **Spherical covariance** (one variance per cluster): 1 parameter per component — fittable, but mathematically reduces to weighted K-Means with a per-cluster radius. No new information.
- **Tied covariance** across all clusters: common regularizer, but still requires `>D` total samples to avoid a singular covariance.

sklearn's own docs note that GMM with few samples is effectively uninformed, and for N<D users should "consider using a simpler model" ([sklearn GaussianMixture notes](https://scikit-learn.org/stable/modules/mixture.html)). There is no covariance regularizer that rescues full GMM at N<D/2 — the posterior collapses to the prior. **GMM is ruled out, not deferred.**

### 3. DBSCAN cannot be tuned at N ≤ 15

DBSCAN is parameter-light in reputation, parameter-heavy in practice: the `eps` neighbourhood radius is typically chosen by inspecting the k-distance plot and finding the "elbow" ([Schubert et al. 2017, "DBSCAN Revisited, Revisited"](https://dl.acm.org/doi/10.1145/3068335)). With 5 points you do not have a meaningful k-distance plot — any elbow is an artefact of a single sample. Worse, DBSCAN will label everything as noise if `min_pts` > typical cluster size; at `min_pts=2` (the minimum viable) it degenerates to single-linkage clustering. The "mark outliers as likely mis-swipes" idea has appeal, but the statistical power to distinguish a mis-swipe from legitimate preference heterogeneity is zero at N=5. **DBSCAN is a dead end at this scale.**

### 4. Spectral and agglomerative clustering: no pay-off here

Spectral clustering shines on nonconvex / manifold-structured clusters by operating on the Laplacian of an affinity graph ([von Luxburg 2007, "A Tutorial on Spectral Clustering"](https://arxiv.org/abs/0711.0189)). It requires enough points to construct a stable nearest-neighbour graph (typically N >> 20 for the affinity matrix to reflect anything but noise). Agglomerative / hierarchical clustering is a reasonable K-Means alternative when N is small, but without ground-truth labels there's no reliable linkage-rule choice (single vs complete vs Ward), and on L2-normalized vectors in 384d all linkage rules converge to similar partitions for N<20. Neither buys anything meaningful over K-Means at our scale.

### 5. The honest null hypothesis: k=1

The prompt frames this as *"does k=2 under-capture multi-modal taste?"* — but with 3-5 likes the more likely failure is that **k=2 over-fits** unimodal preference. Two-cluster K-Means on 3 points produces centroids of 2 points and 1 point (or 1+2). The 1-point "cluster" centroid *is* that single embedding — extreme variance estimate from a single draw. MMR relevance then scores candidates against the noise. On 4 likes you get 3+1 or 2+2. Only at N≥6 with measurable within-cluster cohesion does k=2 become meaningfully informative.

Milligan & Cooper's survey of 30+ k-selection procedures on synthetic clustered data gives silhouette among the top performers and broadly usable at small N ([Milligan & Cooper 1985, "An examination of procedures for determining the number of clusters in a data set", *Psychometrika*](https://link.springer.com/article/10.1007/BF02294245)). The gap statistic (Tibshirani, Walther & Hastie 2001) is the other standard, but requires reference-distribution bootstrap which is expensive and flaky at N=5. **Silhouette score is the right k-selector at our scale**: for each candidate k, compute `s(k) = (b - a) / max(a, b)` averaged over points; pick `argmax_k s(k)` if `s > threshold` (0.1-0.25 is typical), else fall back to k=1. At N=3-5 silhouette naturally defaults to k=1 because the 2-cluster fit produces within-cluster cohesion no better than between-cluster separation on normalized sparse data.

### 6. Soft assignment ≠ GMM

Soft / probabilistic assignment is usually framed as a GMM feature, but you can get it cheaply from K-Means centroids without fitting covariance. Fuzzy c-means (Bezdek 1981) uses `u_ij = 1 / Σ_k (||x_i - c_j|| / ||x_i - c_k||)^(2/(m-1))` as membership weights; a simpler variant is the **softmax over negative distances**: `w_i = softmax(-||x - c_i||² / τ)` with temperature τ. Applied to our MMR relevance term:

```
relevance_hard = max_i cos(x, c_i)      # current
relevance_soft = Σ_i w_i · cos(x, c_i)  # proposed
```

The hard-max form is brittle when the user's taste is *between* two modes — a candidate that's 0.72 to centroid A and 0.71 to centroid B gets the same relevance as one that's 0.73 to A and 0.30 to B. The soft form rewards the "between" candidate more. This is a relevance-scoring change, not a clustering change; it's orthogonal to (and compatible with) adaptive k. Cost: negligible (4 ops per centroid per candidate).

### 7. Session-based recsys at small N: dominant practice is no clustering at all

Modern session-based recommenders (GRU4Rec [Hidasi et al. 2016], SASRec [Kang & McAuley 2018]) model the session as a single evolving hidden state, not as multi-modal cluster centroids ([Hidasi et al. 2016, "Session-based Recommendations with Recurrent Neural Networks"](https://arxiv.org/abs/1511.06939); [Kang & McAuley 2018, "Self-Attentive Sequential Recommendation"](https://arxiv.org/abs/1808.09781)). They attend over past interactions rather than cluster them. The implicit assumption: at tiny session horizons, an aggregated representation dominates any attempt to partition. Our preference-vector direct update (`engine.py:188-189`, `+like_weight` on likes, L2-normalize) is already exactly this kind of single-state model. The K-Means layer was added as an "exploitation" step assuming bimodal taste ("warm vs cool", "classical vs modern"), but we have no empirical evidence that bimodality is the norm rather than the exception.

### 8. Stability via bootstrap is expensive at our latency budget

Ben-Hur, Elisseeff & Guyon (2002) propose cluster stability via repeated subsampling as a model-selection criterion ([Ben-Hur et al. 2002, "A Stability Based Method for Discovering Structure in Clustered Data"](https://doi.org/10.1142/9789812799623_0002)). Beautiful in principle; requires dozens of resampled K-Means fits per session turn. At our 2-s swipe budget with centroid recomputation already inside the cache-miss path, bootstrap-stability is too expensive. **Silhouette at runtime is the right compromise**: single extra K-Means fit per turn (k=1 trivially closed-form, k=2 is what we already compute), silhouette on the single result, all O(N·k·D) with N≤15 and D=384 — microseconds.

## Options

### Option A — Keep K-Means k=2 (do nothing)
Current behaviour.
- **Pros**: Zero risk, zero cost, behaviour already understood.
- **Cons**: At N=3-5 the 1-point cluster is pure noise; at any N where user taste is truly unimodal, MMR is mis-scored against a spurious second centroid. The `max` over centroids rewards high similarity to *either* centroid including the noise one.
- **Complexity**: None.
- **Expected impact**: Baseline.

### Option B — Adaptive k ∈ {1, 2} via silhouette (RECOMMENDED)
Compute K-Means at k=1 (trivially = weighted mean) and at k=2; pick k=2 iff `silhouette_score(embeddings, k=2_labels, sample_weight=w) > threshold` (default 0.15), else k=1.
- **Pros**: Defaults to robust unimodal behaviour at small N and on genuinely unimodal tastes. Catches true bimodal structure when it's strong enough to show in silhouette. Single sklearn call for silhouette; negligible cost. No new dependencies. Preserves cache key shape.
- **Cons**: Silhouette threshold becomes a new hyperparameter (Optuna-tunable). One extra K-Means fit and one silhouette computation per cache miss — both O(N=10, D=384) so <1 ms.
- **Complexity**: **Low** — ~30-line change in `compute_taste_centroids` plus one settings entry plus one Optuna range.
- **Expected impact**: Medium — eliminates spurious k=2 at small N, preserves k=2 at larger N with clear bimodal structure.

### Option C — Soft-assignment MMR relevance (orthogonal to A/B)
Replace `relevance = max_i cos(x, c_i)` with `relevance = Σ_i softmax(-||x - c_i||²/τ) · cos(x, c_i)` in `compute_mmr_next` and `get_top_k_mmr`.
- **Pros**: Smoother scoring surface; rewards "between modes" candidates; cheap (4 ops per centroid). Works with any clustering. Probabilistic without GMM.
- **Cons**: New temperature hyperparameter τ. At k=1 the soft-max collapses to the hard-max, so benefit is only at k≥2.
- **Complexity**: **Low** — ~10-line change to two relevance lines in engine.py.
- **Expected impact**: Small-to-medium; largest when user genuinely has bimodal taste and candidates sit in the gap.

### Option D — GMM with shared spherical covariance
Fit sklearn `GaussianMixture(covariance_type='spherical')`.
- **Pros**: In principle gives probabilistic centroids.
- **Cons**: Mathematically collapses to weighted K-Means with extra per-cluster scalar (the spherical variance). Doesn't buy probabilistic relevance beyond Option C. Slower fit. GMM with diagonal/full covariance is non-fittable at N<D.
- **Complexity**: **Low** (sklearn drop-in) but scientifically empty.
- **Expected impact**: Indistinguishable from B+C. **Reject.**

### Option E — DBSCAN / spectral / agglomerative
See Findings §3 and §4.
- **Reject for this N**: `eps` untunable, affinity graph sample-starved, no pay-off.

## Recommendation

**Ship Option B + Option C together**, flag-gated as `ADAPTIVE_K_CLUSTERING_ENABLED`. Concretely:

1. `engine.py:compute_taste_centroids`: when `settings.RECOMMENDATION.get('ADAPTIVE_K_CLUSTERING_ENABLED', False)` is True and `len(weighted_likes) ≥ 4`:
   - Fit `KMeans(n_clusters=2, ...)` as today.
   - Compute `silhouette_score(like_embeddings, labels_, sample_weight=weights, metric='cosine')` via `sklearn.metrics.silhouette_score`.
   - If `silhouette ≥ RC['silhouette_threshold']` (default 0.15), return both centroids. Else collapse to k=1 and return `[global_centroid]`.
   - At `len(weighted_likes) < 4`, short-circuit to k=1 unconditionally.
2. `compute_mmr_next` and `get_top_k_mmr` (`engine.py:516, 722, 737`): when `settings.RECOMMENDATION.get('SOFT_RELEVANCE_ENABLED', False)` is True, replace the three `max(np.dot(x, c) for c in centroids)` sites with `_soft_relevance(x, centroids, tau=RC['soft_relevance_tau'])` where `_soft_relevance` computes `softmax(-||x - c||² / τ) · cos(x, c)` summed. When k=1 the function degenerates to the single cosine anyway, so the flag is defensive.
3. `config/settings.py` `RECOMMENDATION`: add `'ADAPTIVE_K_CLUSTERING_ENABLED': False`, `'silhouette_threshold': 0.15`, `'SOFT_RELEVANCE_ENABLED': False`, `'soft_relevance_tau': 0.1`.
4. `research/algorithm.md`: add `silhouette_threshold` (0.05-0.30) and `soft_relevance_tau` (0.05-0.5) to the hyperparameter table.
5. Cache key (`engine.py:457-463`) unchanged — the new behaviour is a pure function of existing inputs plus config.

Both flags are independent. Start with Option B alone (ADAPTIVE_K on, SOFT_RELEVANCE off); add C after B ships cleanly.

**Why this beats all other options.** GMM/DBSCAN/spectral are ruled out by N<<D. Contextual bandits and bayesian priors are right for the post-1K-sessions regime (see Open Questions). Within feasible methods, adaptive k is the *correct* default because it admits that most users don't have two distinct taste modes and that forcing k=2 on 3 points is statistical cargo-culting. Soft-assignment relevance is a cheap upgrade whenever k=2 does fire, addressing the specific failure mode flagged in `02-reranking-layer.md` ("feeding all likes as one summary may wash out the modes").

## Open Questions

- **What fraction of real sessions are genuinely bimodal at convergence?** We don't know. Recommend logging `(session_id, final_like_count, silhouette_score_at_2, k_selected)` once Option B ships flag-off, sampling 200 sessions, and looking at the distribution. If >60% of sessions with ≥6 likes hit silhouette > 0.15, bimodal is common and k=2 default is justified; if <30%, k=1 should be the structural default.
- **Is cosine the right silhouette metric for our L2-normalized embeddings?** `silhouette_score(metric='cosine')` is supported in sklearn but slower than Euclidean. On L2-normalized vectors cosine and Euclidean distances are monotone-equivalent (`||x - y||² = 2 - 2·cos(x, y)`), so `metric='euclidean'` should give identical rankings at a fraction of the cost. Verify empirically.
- **Interaction with recency weighting.** Our `sample_weight=w_i` biases K-Means toward recent likes. Does silhouette computed with the same weights give a defensible k-selection, or does the time-decay confound the cohesion/separation calculation? Worth a unit test with synthetic "taste shift mid-session" data.
- **Should k=3 be on the table?** At N≥9 it's defensible. Empirical: try k ∈ {1, 2, 3}, take argmax silhouette. Probably over-engineering given most sessions converge in <25 swipes, but a Phase-2 consideration.
- **Soft-relevance τ tuning.** The right τ depends on the typical inter-centroid cosine distance in the dataset; too small collapses to hard-max, too large flattens. Optuna will find it, but also consider setting τ adaptively as `τ = median_pairwise_centroid_cosine / 2`.
- **Convergence-detection interaction.** `compute_convergence` measures `||centroid_now - centroid_prev||`. If k changes mid-session (was k=1, becomes k=2 when a 4th like arrives), how do we define centroid drift? Recommended: track `delta_v` against the *global_centroid* (already returned as the second tuple element), which is unaffected by k selection. The current code already uses `centroid` (global), so this is already robust — verify no regressions.

## Proposed Tasks for Main Terminal

All backend; no frontend changes. Scope: `backend/apps/recommendation/engine.py`, `backend/config/settings.py`, `research/algorithm.md`, tests.

1. **BACK-CLU-1** — `engine.py:compute_taste_centroids` (lines 451-489): add adaptive-k logic behind `settings.RECOMMENDATION.get('ADAPTIVE_K_CLUSTERING_ENABLED', False)`. When flag is off, behaviour is identical to current. When flag is on and `len(weighted_likes) >= 4`, fit KMeans(k=2), compute `sklearn.metrics.silhouette_score(embeddings, labels_, sample_weight=weights, metric='euclidean')` (Euclidean is monotone-equivalent to cosine on L2-normalized vectors), collapse to `([global_centroid], global_centroid)` when silhouette < `RC['silhouette_threshold']`. For `len(weighted_likes) < 4`, always use k=1 regardless of `RC['k_clusters']`. Cache key unchanged.
2. **BACK-CLU-2** — `engine.py`: add module-level helper `_soft_relevance(candidate_emb, centroids, tau) -> float` computing `Σ softmax(-||candidate - c||² / τ) · np.dot(candidate, c)`. Numerical stability via max-subtract in softmax.
3. **BACK-CLU-3** — `engine.py:compute_mmr_next` (line 516) and `engine.py:get_top_k_mmr` (lines 722, 737): replace `max(np.dot(...) for c in centroids)` with `_soft_relevance(candidate_emb, centroids, RC['soft_relevance_tau'])` when `settings.RECOMMENDATION.get('SOFT_RELEVANCE_ENABLED', False)`. Behaviour unchanged when flag off; behaviour identical to hard-max when `len(centroids) == 1`.
4. **BACK-CLU-4** — `config/settings.py` RECOMMENDATION dict (lines 131-144): add `'ADAPTIVE_K_CLUSTERING_ENABLED': False`, `'silhouette_threshold': 0.15`, `'SOFT_RELEVANCE_ENABLED': False`, `'soft_relevance_tau': 0.1`.
5. **BACK-CLU-5** — `research/algorithm.md` hyperparameter table (lines 79-95): add rows `silhouette_threshold | float | 0.05-0.30 | 0.15` and `soft_relevance_tau | float | 0.05-0.5 | 0.1`.
6. **TEST-CLU-1** — `backend/tests/test_engine_clustering.py` (new file): unit tests for (i) flag off → identical output to current (golden fingerprint on fixed seed), (ii) flag on, N=3 → always k=1, (iii) flag on, N=8 with two clearly separated centroid clusters → k=2 selected, (iv) flag on, N=8 drawn from a single spherical blob → k=1 selected, (v) silhouette threshold parametrized.
7. **TEST-CLU-2** — `backend/tests/test_engine_clustering.py`: unit tests for `_soft_relevance`: (i) with 1 centroid identical to hard-max, (ii) with 2 centroids and candidate exactly on centroid A, τ→0 equals cos(A), (iii) at τ→∞ equals arithmetic mean of cosines, (iv) NaN/inf stability (large `||x - c||²` handled via max-subtract).
8. **OBS-CLU-1** — `engine.py:compute_taste_centroids`: add DEBUG log with `(len(weighted_likes), silhouette, k_selected)` once per cache miss. Enables answering Open Question 1 without a schema change. Logger name `apps.recommendation.clustering`.
9. **ALGO-CLU-1** — After shipping flag-off, run `backend/tools/algorithm_tester.py` with toggle of `ADAPTIVE_K_CLUSTERING_ENABLED` and `SOFT_RELEVANCE_ENABLED` (4 combinations × baseline persona set). Apply only if convergence swipe count and precision@K are non-regressed on the joint metric.
10. **ALGO-CLU-2** — Extend the Optuna search space in `algorithm_tester.py` to include `silhouette_threshold` and `soft_relevance_tau` when the corresponding flags are active; rerun the broad Phase-1 search.

## Sources

- [Aggarwal, Hinneburg & Keim 2001 — "On the Surprising Behavior of Distance Metrics in High Dimensional Space"](https://bib.dbvis.de/uploadedFiles/155.pdf) — classic result on the instability of Euclidean / cosine contrast in high-D; the foundational reason small-N clustering in D=384 is hard.
- [Rousseeuw 1987 — "Silhouettes: a graphical aid to the interpretation and validation of cluster analysis"](https://doi.org/10.1016/0377-0427(87)90125-7) — silhouette score definition, still the most widely used k-selector.
- [Milligan & Cooper 1985 — "An examination of procedures for determining the number of clusters in a data set"](https://link.springer.com/article/10.1007/BF02294245) — survey of 30+ stopping rules; silhouette / Calinski-Harabasz among the top performers at small N.
- [Tibshirani, Walther & Hastie 2001 — "Estimating the number of clusters in a data set via the gap statistic"](https://doi.org/10.1111/1467-9868.00293) — gap statistic, the other standard k-selector; expensive on small N.
- [Ben-Hur, Elisseeff & Guyon 2002 — "A Stability Based Method for Discovering Structure in Clustered Data"](https://doi.org/10.1142/9789812799623_0002) — cluster-stability via bootstrap; argued against here on latency grounds.
- [von Luxburg 2007 — "A Tutorial on Spectral Clustering"](https://arxiv.org/abs/0711.0189) — reference for why spectral needs N >> 20 to matter.
- [Schubert et al. 2017 — "DBSCAN Revisited, Revisited: Why and How You Should (Still) Use DBSCAN"](https://dl.acm.org/doi/10.1145/3068335) — eps selection via k-distance plot; the reason DBSCAN fails at N≤15.
- [scikit-learn — GaussianMixture documentation](https://scikit-learn.org/stable/modules/mixture.html) — covariance-type tradeoffs; the N<<D regime is unrecoverable.
- [scikit-learn — `silhouette_score` documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html) — sample_weight support, cosine metric option.
- [Hidasi et al. 2016 — "Session-based Recommendations with Recurrent Neural Networks" (GRU4Rec)](https://arxiv.org/abs/1511.06939) — session-based recsys state-of-the-practice uses aggregated state, not multi-cluster centroids.
- [Kang & McAuley 2018 — "Self-Attentive Sequential Recommendation" (SASRec)](https://arxiv.org/abs/1808.09781) — same: attention over history, not clustering of it.
- [Bezdek 1981 — "Pattern Recognition with Fuzzy Objective Function Algorithms"](https://link.springer.com/book/10.1007/978-1-4757-0450-1) — fuzzy c-means, origin of soft assignment; our softmax variant is the lightweight analogue.
