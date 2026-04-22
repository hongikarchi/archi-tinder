# Collaborative Signals Across Users: PinSage / LightGCN / MF / Item-Item / Co-Like

## Status
Ready for Implementation

## Question
Given archi-tinder's scale (tens-to-low-hundreds of daily active users, ~few thousand buildings, binary like/dislike, no explicit ratings), does adding any collaborative-filtering (CF) signal — item-item co-like, matrix factorization, PinSage / LightGCN — improve recommendations enough to justify the complexity, or should CF be deferred until a concrete user-count threshold is met?

## TL;DR
- **Defer true CF (MF, LightGCN, PinSage) until `N_projects ≥ 500` AND `median likes/project ≥ 20`** (per-project is the right CF unit for our data model — see Finding §6); at our current scale every project is effectively cold-start, binary implicit signal is sparser-than-sparse, and content embeddings already encode item similarity far more efficiently. LightGCN/PinSage are ruled out on density grounds; iALS/BPR are ruled out on project-count grounds.
- **Ship one lightweight precursor now**: a **global-popularity prior** blended into `_build_score_cases()` pool scoring. Item-level like/dislike rates are (a) cheap to maintain, (b) non-personalized so they work at any scale, (c) compatible with the per-project like-history model, (d) measurable via algo-tester. This is *not* collaborative filtering in the MF/GNN sense but it's the one "cross-user signal" that converges at tens of users.
- **Per-project is the right CF unit, not per-user.** Users can have multiple projects with distinct tastes (`Project.liked_ids`, `models.py:6-21`); aggregating across projects would mix tastes and defeat personalization. When CF eventually lands, the user-item matrix must be `(project_id × building_id)`.

## Context (Current State)

archi-tinder has zero cross-session signal. Every `AnalysisSession` is independent:

- `backend/apps/recommendation/models.py:23-52` — `AnalysisSession` holds `preference_vector`, `like_vectors`, `exposed_ids`, `pool_ids` all **session-local**. There is no read path that surfaces another user's likes (or even the same user's prior project likes) into the current pool.
- `backend/apps/recommendation/models.py:6-21` — `Project.liked_ids` / `disliked_ids` are persisted indefinitely as `JSONField(default=list)`. A user can own many `Project` rows. This is the only raw CF material in the database.
- `backend/apps/recommendation/views.py:525-533` — swipes mutate `project.liked_ids` / `disliked_ids` on every like/dislike. Pool creation at session start reads **only** from the current session's own pool fetch, filters, and the user's exposure history; no cross-user fold-in.
- `backend/apps/recommendation/engine.py:289-367` — `_build_score_cases()` and `create_bounded_pool()` score candidates by filter match + embedding distance only. There is no slot for any global signal like "item X is liked 3× more often than the mean."
- `architecture_vectors` (Make DB, read-only per `CLAUDE.md`) contains ~few thousand rows and is schema-frozen. Any CF-derived data (co-occurrence counts, latent factors, node embeddings) must live in **Make Web's own schema** and must not require a migration on `architecture_vectors`.
- Pool is capped at 150 buildings per session (`settings.py:132`). Re-rank is bounded; brute-force cosine scales trivially — CF would be a **seed / cold-start / re-rank prior**, not a retrieval replacement.

Consequence of the current design: at session N+1, the system cannot learn from session N. If 10,000 users swipe through cards and a particular brutalist housing block is liked by 70% of those who see it, the 10,001st user's first session has zero awareness of that fact.

## Findings

### 1. Classical CF needs user-count and interaction-count far above ours

Matrix factorization for explicit feedback (Koren, Bell, Volinsky 2009 "Matrix Factorization Techniques for Recommender Systems" — the canonical SVD++ reference) and its implicit-feedback variant (Hu, Koren, Volinsky 2008 "Collaborative Filtering for Implicit Feedback Datasets", ICDM, later awarded 2017 10-Year Highest-Impact) both presume a sufficiently dense user-item matrix to factorize. The canonical benchmark used in both papers is the Netflix Prize (~480K users × 17K items, ~100M ratings) — density ~1.2%. Follow-up literature on implicit CF (Rendle 2009 BPR, and the survey by Andreas Bloch linked below) consistently uses MovieLens 1M (6K users × 4K movies, 1M interactions → ~4.2% density), MovieLens 20M, or Amazon product graphs (10⁵–10⁶ users). Implicit-feedback collaborative filtering suffers severely from data sparsity and cold-start; these are explicitly called out as the algorithm's primary failure modes [Hu/Koren/Volinsky, 2008; Bloch survey]. No citation we found supports convergence at `N_users < 100` with binary-only signal.

### 2. LightGCN and PinSage require graph densities we do not possess

LightGCN (He et al. 2020, SIGIR) benchmarks on Gowalla (30K users × 41K items, ~1M interactions), Yelp2018 (31K × 38K, ~1.6M), and Amazon-Book (52K × 92K, ~3M). Its performance gains come from multi-hop neighborhood aggregation on the bipartite user-item graph; with tens of users and binary signal, nearly every user node would have degree < 10 and two-hop neighborhoods would be trivially small or disconnected. PinSage (Ying, He, Chen, Eksombatchai, Hamilton, Leskovec 2018, KDD) operates at *Pinterest scale* — explicitly reported in the paper's abstract as 3 billion nodes × 18 billion edges, trained on 7.5 billion examples ([arXiv 1806.01973](https://arxiv.org/abs/1806.01973)). The paper's own framing is "web-scale recommender systems" — its value proposition is engineering a GCN that can *handle* billions of edges, not that it works on small graphs. Deploying PinSage at our scale is category error. LightGCN is closer to possible but still assumes graph connectivity orders of magnitude beyond us.

### 3. Content-based baselines outperform CF under sparsity

Cremonesi, Koren, Turrin 2010 ("Performance of Recommender Algorithms on Top-N Recommendation Tasks", RecSys) is the standard citation for the finding that **a naive non-personalized algorithm (Most-Popular) can match or outperform sophisticated CF methods** on top-N recommendation, particularly when sparsity is high. They also show that RMSE-optimized methods (classic MF) do not necessarily perform well on the top-N task that actually matters for swipe-style UIs. The Wikipedia cold-start article and multiple practitioner surveys (freeCodeCamp, ScienceDirect) converge on the same switching-strategy advice: **lean on content-based recommendations for cold users, switch to CF as interaction data accumulates** [Wikipedia "Cold start (recommender systems)"; freeCodeCamp cold-start; ScienceDirect topic page]. We already have a very strong content channel (384-dim pgvector embeddings + K-Means centroids) — the literature's pragmatic advice for small-N is exactly what we're already doing.

### 4. Item-item co-like (Amazon-style) needs catalog-wide density, not user-count density

Linden, Smith, York 2003 "Amazon.com Recommendations: Item-to-Item Collaborative Filtering" (IEEE Internet Computing) showed item-item CF was tractable and performant at Amazon's scale by computing similarities **between items** rather than users — so the method scales with item count × avg-co-purchases rather than user count. A Jaccard / cosine co-like matrix over items works at moderate user count **if average item receives enough like events to estimate its co-occurrence distribution reliably**. With 150 cards per session × ~15 likes per session × 100 active users = ~1,500 like events distributed across ~few thousand buildings, the average building has well under 1 like total. This is not enough to estimate co-occurrence reliably. Item-item CF becomes interesting somewhere north of ~50 likes/building on average, which at our session-yield rate requires several thousand users before most items in the catalog are "warm." Additionally, item-item CF would duplicate signal: our pgvector embeddings already encode item-item similarity via visual/semantic features, and the content similarity is dense whereas co-like similarity would be sparse and noisy.

### 5. Popularity prior is the one "cross-user signal" that converges at tens of users

Popularity bias is usually discussed as a *problem* for long-tail items ([MDPI 2025 survey on popularity bias](https://www.mdpi.com/2078-2489/16/2/151); [Abdollahpouri 2019 arXiv 1907.13286]), but the same literature notes that **for new / cold-start users, recommending popular items improves engagement and trust**. For a swipe-style app where every user is effectively cold in every session (we already personalize within-session via phase pipeline), a global item-popularity term blended in at pool-scoring time is a well-understood, cheap, convergent signal: item-level like-rate is estimable with tight confidence intervals after only a few dozen likes per item, not thousands.

### 6. Per-project, not per-user, is the right CF entity

Our data model lets one user own multiple `Project` rows, each with independent `liked_ids` / `disliked_ids`. A user running a "housing" project and a "museum" project has genuinely different taste in each; aggregating to per-user likes would mix tastes and distort any learned user factor. If and when CF lands, the correct matrix is `(project_id × building_id)` — projects are treated as lightweight pseudo-users. This shrinks *average* likes per entity (since each user produces multiple projects, each with fewer likes) but preserves taste coherence within each row, which is what CF actually needs to learn. Same density barrier applies — just with `project_id` on the row axis.

## Options

### Option A — Do nothing, defer CF entirely with documented trigger
Add no CF, add no popularity blend. Document scale threshold in code comment + `research/algorithm.md` addendum.
- **Pros**: Zero implementation cost, zero risk, zero maintenance surface. Content pipeline is already well-tuned.
- **Cons**: Misses the one genuinely cheap cross-user signal (global popularity). Does not set up the telemetry plumbing that later CF work will need.
- **Complexity**: Zero.
- **Expected impact**: Zero on recommendations; low but nonzero on strategic clarity (the trigger is written down).

### Option B — Global popularity prior blended into pool scoring (recommended)
Maintain a materialized view or cached dict `{building_id: (n_likes, n_dislikes, n_exposures)}` aggregated across *all completed sessions* repository-wide. Add a new additive term inside `_build_score_cases()`:
```
weight_popularity * (n_likes / max(n_exposures, 1) - global_mean_like_rate)
```
Flag-gated `POPULARITY_PRIOR_ENABLED` (default off); `popularity_weight` ships with a starting value of `0.0` so that turning the flag on has no effect until algo-tester explicitly raises it. Apply the prior only to items with `n_exposures ≥ 5` (fall back to neutral 0 otherwise) — avoids punishing items that have been exposed once and unluckily not liked, and avoids locking out newly-added buildings. Runs only during pool creation (150 rows), not per-swipe.
- **Pros**: Converges at tens of users (item-level rate, not user-level). Trivial to compute (a single `GROUP BY building_id` over `SwipeEvent`). Orthogonal to K-Means centroids and MMR — does not touch the analyzing-phase logic. Compatible with per-project likes (we aggregate across all projects globally for item-level rate). Sets up the interaction-logging plumbing that future MF/LightGCN would need.
- **Cons**: Not "true" CF — no per-user / per-project personalization in the signal. Popularity bias can compound if unchecked (early-liked items get shown more, get liked more, etc.); mitigated by centering on `global_mean_like_rate` and bounding the weight small.
- **Complexity**: **Low** (~1 day: materialized view migration, engine hook, settings flag, algo-tester weight).
- **Expected impact**: Small-to-medium. Shifts pool composition toward items that the community validates, and away from items that most users reject. Works as a soft prior — does not override strong content match.

### Option C — Item-item co-like Jaccard / cosine sparse matrix
Build a `(building_id × building_id)` sparse matrix of co-like counts. At pool creation, for each seed building in the user's current project-like history, look up top-k co-liked items and promote them in the scoring.
- **Pros**: Closest thing to "real CF" that's still implementable at our scale. Works per-item rather than per-user, so user-count is less of a bottleneck.
- **Cons**: As shown in Findings §4, most items have <1 like total at our current scale — the co-like matrix would be nearly all zeros. Redundant with content embedding similarity, which already captures item-item similarity much more densely. Not safe to ship until per-item like count ≥ ~20 on median, which is 2-3× our target scale.
- **Complexity**: Medium (needs sparse matrix maintenance, nightly recompute job, engine integration).
- **Expected impact**: Near-zero until density reaches ~20 likes/item median.

### Option D — Implicit-feedback MF (iALS via `implicit` library) on `(project_id × building_id)`
Train a factorization model on the full swipe log. Project latent vectors feed into either pool seeding (user "warm vector" from MF) or pool re-ranking.
- **Pros**: Canonical technique for binary implicit signal. Pure Python via `benfred/implicit`. Produces latent vectors per project that generalize across items.
- **Cons**: Convergence requires the density floor that neither Hu/Koren/Volinsky nor follow-up literature establishes below ~100 users × 20+ interactions. At our scale every project has <20 likes; iALS will overfit or fail to converge meaningfully. Adds a training job, a cache, serving logic, a new Django model for latent vectors, and re-training cadence. Content embeddings already provide a dense latent vector *per item* for free.
- **Complexity**: **Medium-High** (model training plumbing + latent vector storage + serving).
- **Expected impact**: Negative expected until scale triggers are met.

### Option E — LightGCN / PinSage graph-neural-network
Build a bipartite graph of `(project, building)` edges, train a GNN.
- **Pros**: State-of-the-art on benchmark graphs with millions of edges.
- **Cons**: See Findings §2 — our graph has ~orders of magnitude fewer edges than the smallest benchmark LightGCN was validated on. PinSage is categorically out of scope (Pinterest scale). Requires GPU training, PyTorch Geometric / DGL dependencies, model-serving infrastructure. `CLAUDE.md` explicitly forbids adding sentence-transformers; adding a GNN stack would be a far larger footprint addition.
- **Complexity**: **Very High**.
- **Expected impact**: Near-zero to negative; sophisticated methods on tiny graphs typically underperform simple baselines.

## Recommendation

**Ship Option B now. Defer Options C/D/E to explicit scale triggers. Reject Option E as permanent category mismatch.**

Concretely:

1. **Now (Option B)**: Implement the global-popularity prior behind a `POPULARITY_PRIOR_ENABLED` flag, default off. Maintain item-level like-rate in a materialized view or periodically-refreshed cache over `SwipeEvent`. Wire into `_build_score_cases()` as one additional additive term. Weight starts at 0, tuned by algo-tester once we have ≥30 completed sessions.

2. **Revisit Option C (item-item co-like)** when `median likes per building ≥ 20` across all projects. At that density the co-occurrence matrix has enough non-zero cells to be a useful prior, still much cheaper than MF.

3. **Revisit Option D (iALS on `(project, building)`)** when `N_projects ≥ 500` AND `median likes per project ≥ 20`. These are a conservative fraction of the smallest implicit-feedback CF benchmarks in the literature (Hu/Koren/Volinsky's smallest experiment used MovieLens 1M — ~6K users × ~200 interactions/user — roughly 10× our target trigger). At these triggers, iALS becomes one of several reasonable options and a proper bake-off can be run.

4. **Permanently reject Option E (LightGCN/PinSage)** unless archi-tinder grows beyond ~50K projects × ~100K buildings (adding many-building catalogs or user-generated buildings). These methods are web-scale tooling; even at 500 users we'd be two-three orders of magnitude below their validated regime.

Option B is the bridge: it exploits the one cross-user signal that converges at our scale (item-level popularity), it installs the swipe-aggregation plumbing that any future CF work will want, and it is orthogonal to the phase pipeline so it can be A/B tested without risk of session-behavior regression. If Option B shows measurable like-rate or time-to-convergence improvement via algo-tester, we have empirical proof that cross-user signal helps; if not, we have empirical proof that content personalization dominates and we can defer all CF indefinitely.

## Open Questions

- **Popularity prior as pool gate vs re-rank**: Apply in pool scoring (`CASE WHEN` additive) or as a post-MMR re-rank? Pool scoring is cheaper and affects retrieval; re-rank is more surgical. Recommend pool-scoring first, evaluate, move to re-rank only if popularity bias in final top-K becomes visible.
- **Centering choice**: Center per-program? Globally? Different programs (Housing, Museum, Religion) have different absolute like-rates because they're different sample sizes — per-program centering may be fairer. Needs empirical check once we have session telemetry.
- **Decay of old popularity**: Should popularity counts age out (EWMA with λ ≈ 0.01/day) so recent trends dominate? Probably yes at scale; not worth the code at current volume.
- **Denial-of-service by power users**: A single user submitting 100 sessions shouldn't dominate the popularity signal. Mitigation: aggregate at project-level (each project contributes at most its own like set once, not once per session), or dedupe by user_id.
- **Filter interaction**: Does popularity help or hurt when filters are narrow? If `program=Religion` narrows the pool to 40 buildings, popularity-centered prior may be dominated by noise. Mitigation: scale popularity weight inversely with candidate-set size.
- **Benchmarking under tiny N**: We don't yet have >10 real users. Algo-tester synthetic personas produce deterministic swipes; popularity signal on synthetic runs only measures synthetic consensus, not real users. Open question: how to validate Option B before we have real traffic? One proposal — bootstrap-sample from the synthetic personas as if they were independent users and measure stability.

## Proposed Tasks for Main Terminal

All backend; no frontend changes. Scope is `backend/apps/recommendation/*.py` + one migration and one settings entry. Option B only; Options C/D are explicitly out of scope until triggers are met.

1. **BACK-CF-1** — New Django migration `recommendation/migrations/00XX_popularity_view.py` creating a materialized view:
   ```sql
   CREATE MATERIALIZED VIEW mv_building_popularity AS
   SELECT building_id,
          SUM(CASE WHEN action='like' THEN 1 ELSE 0 END)::float AS n_likes,
          SUM(CASE WHEN action='dislike' THEN 1 ELSE 0 END)::float AS n_dislikes,
          COUNT(*)::float AS n_exposures
   FROM recommendation_swipeevent
   GROUP BY building_id;
   CREATE UNIQUE INDEX idx_mv_bldg_pop_id ON mv_building_popularity(building_id);
   ```
   Reverse = `DROP MATERIALIZED VIEW`. Does not touch `architecture_vectors`; fully in Make Web's schema.

2. **BACK-CF-2** — `engine.py`: new module-level helper `_get_popularity_prior() -> dict[str, float]` returning `{building_id: centered_like_rate}`, computed once per pool creation via `SELECT building_id, (n_likes - global_mean)/sqrt(n_exposures+1) FROM mv_building_popularity`. Cache the dict on the service layer for the lifetime of the request.

3. **BACK-CF-3** — `engine.py:_build_score_cases()`: when `settings.RECOMMENDATION.get('POPULARITY_PRIOR_ENABLED', False)` is true, add one additive `CASE WHEN building_id IN (...) THEN priors[building_id]*weight ELSE 0` term parameterized by `popularity_weight` (default 0.5, tunable via algo-tester).

4. **BACK-CF-4** — `config/settings.py`: add `'POPULARITY_PRIOR_ENABLED': False`, `'popularity_weight': 0.0`, and `'popularity_min_exposures': 5` to the `RECOMMENDATION` dict (line ~131-144). Defaults are "dormant": the flag is off, and even if turned on the weight of 0.0 means zero effect until algo-tester picks a value. Leave off in production until Task ALGO-CF-1 greenlights a specific weight.

5. **BACK-CF-5** — Add a Django management command `refresh_popularity` that runs `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_building_popularity`. Schedule via cron (daily) once the flag flips on; not needed before.

6. **BACK-CF-6** — Add a Django management command `report_cf_readiness` that prints:
   - `N_projects_with_likes` (trigger for Option C: ≥ 500 projects)
   - `median_likes_per_project` (trigger for Option D: ≥ 20)
   - `median_likes_per_building` (trigger for Option C: ≥ 20)
   - `N_unique_swipers` (raw scale)
   This is the "have we met the threshold" dashboard; running it monthly tells us when to revisit Options C/D. Output goes to stdout only (no DB write, no Task.md write).

7. **TEST-CF-1** — `backend/tests/test_engine.py`: parametrized tests for both flag states. With flag off, score vector matches current master. With flag on and seeded `SwipeEvent` rows, popular buildings score higher in the CASE output; unseen buildings score at `0` (neutral prior).

8. **ALGO-CF-1** — Once Task BACK-CF-1..5 ship, run algo-tester across 50+ personas comparing completion rate, like rate, time-to-convergence with `POPULARITY_PRIOR_ENABLED={False, True}` and `popularity_weight ∈ {0.25, 0.5, 1.0}`. Apply only if non-negative on all three metrics. If algo-tester detects regression, leave flag off and document in `.claude/Report.md`.

9. **DOCS-CF-1** — Update `research/search/README.md` to add the row for this report. (Not this terminal's write responsibility per the research-terminal folder isolation rule; noted here so the main orchestrator picks it up.)

## Sources

- [Hu, Koren, Volinsky 2008 — Collaborative Filtering for Implicit Feedback Datasets (ICDM)](http://yifanhu.net/PUB/cf.pdf) — canonical implicit-feedback MF (iALS) reference; benchmarks density assumptions.
- [Koren, Bell, Volinsky 2009 — Matrix Factorization Techniques for Recommender Systems (IEEE Computer)](https://datajobs.com/data-science-repo/Recommender-Systems-%5BNetflix%5D.pdf) — classic MF exposition.
- [He, Deng, Wang, Li, Zhang, Wang 2020 — LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation (SIGIR)](https://arxiv.org/abs/2002.02126) — benchmarks on Gowalla/Yelp2018/Amazon-Book establish the graph-density regime LightGCN targets.
- [Ying, He, Chen, Eksombatchai, Hamilton, Leskovec 2018 — Graph Convolutional Neural Networks for Web-Scale Recommender Systems (PinSage, KDD)](https://arxiv.org/abs/1806.01973) — 3B-node / 18B-edge graph; establishes PinSage is explicitly web-scale.
- [Cremonesi, Koren, Turrin 2010 — Performance of Recommender Algorithms on Top-N Recommendation Tasks (RecSys)](https://dl.acm.org/doi/10.1145/1864708.1864721) — shows naive Most-Popular baselines can match or outperform sophisticated CF for top-N tasks; RMSE-optimized methods don't win top-N.
- [Linden, Smith, York 2003 — Amazon.com Recommendations: Item-to-Item Collaborative Filtering (IEEE Internet Computing)](https://www.cs.umd.edu/~samir/498/Amazon-Recommendations.pdf) — foundational item-item CF; confirms method scales with item count, not user count.
- [Sarwar, Karypis, Konstan, Riedl 2001 — Item-Based Collaborative Filtering Recommendation Algorithms (WWW)](https://dl.acm.org/doi/10.1145/371920.372071) — item-based CF formalization; co-cited with Linden et al.
- [Rendle, Freudenthaler, Gantner, Schmidt-Thieme 2009 — BPR: Bayesian Personalized Ranking from Implicit Feedback (UAI)](https://arxiv.org/abs/1205.2618) — pairwise-ranking implicit MF; the other canonical implicit-CF method alongside iALS.
- [Bloch — An Overview of Collaborative Filtering Algorithms for Implicit Feedback Data](https://andbloch.github.io/An-Overview-of-Collaborative-Filtering-Algorithms/) — practitioner survey covering iALS, BPR, density assumptions, sparsity impact.
- [Wikipedia — Cold start (recommender systems)](https://en.wikipedia.org/wiki/Cold_start_(recommender_systems)) — switching-strategy advice: content-based for cold users, CF as interactions accumulate.
- [freeCodeCamp — What is the Cold Start Problem in Recommender Systems?](https://www.freecodecamp.org/news/cold-start-problem-in-recommender-systems/) — practitioner cold-start framing.
- [ScienceDirect topic — Cold Start Problem](https://www.sciencedirect.com/topics/computer-science/cold-start-problem) — effect of cold-start on CF specifically vs content-based.
- [MDPI 2025 — Popularity Bias in Recommender Systems: The Search for Fairness in the Long Tail](https://www.mdpi.com/2078-2489/16/2/151) — popularity bias discussion and the specific finding that popularity-based recs improve engagement during cold start.
- [Abdollahpouri 2019 — The Unfairness of Popularity Bias in Recommendation (arXiv 1907.13286)](https://arxiv.org/pdf/1907.13286) — popularity bias survey; informs Option B's centering design.
- [benfred/implicit — Fast Python Collaborative Filtering for Implicit Feedback Datasets (GitHub)](https://github.com/benfred/implicit) — reference implementation for iALS/BPR that Option D would use once triggers are met.
