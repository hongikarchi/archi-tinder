# Cold-Start Seed Strategies: Hard-Filter + Farthest-Point vs Popularity / Cluster / Onboarding

## Status
Ready for Implementation

## Question

archi-tinder's cold start is a hard-filter-weighted pool (tier-scored `CASE WHEN`) followed by tier-ordered farthest-point sampling for the first `initial_explore_rounds=10` swipes. Is this optimal for a new user's first session, or should the seed strategy change — popularity-seeded, cluster-stratified, curated onboarding, random+diversity? What do short-horizon recommender systems do for first-session cold start, and how should our strategy coordinate with topics 01 (hybrid retrieval), 03 (HyDE `V_initial`), and 07 (popularity prior)?

## TL;DR

- **Keep hard-filter + tier-ordered farthest-point as the default.** It is already a credible short-horizon cold-start design: filter weighting handles query-informativeness, farthest-point is the canonical diversity seeder (Gonzalez 1985, 2-approximation on the k-center objective), and tier ordering is a weak form of stratified sampling. The 89.5% completion rate is a strong empirical floor — nothing here is broken enough to justify a rewrite. Popularity-seeding is already owned by topic 07. Cluster-stratified seeding duplicates what tier-ordering already does at ~3,465 rows. Curated onboarding is **out of scope** for a search-engine series; it is a product intervention.
- **Ship one targeted upgrade**: a **query-informativeness branch** at `SessionCreateView.post()`. Classify the parsed query as `rich` (≥2 filter_priority keys **or** ≥1 seed_id **or** a non-empty `raw_query` once topic 03 lands) vs `bare` (empty filters / only a generic `program`). On `bare` queries, widen the pool: raise `bounded_pool_target` (150 → 250) and replace tier-ordered farthest-point with pool-wide farthest-point. On `rich` queries, the current pipeline is already correct and stays as-is. This is one new helper (`_classify_query_informativeness`) and a `if`-branch at two call sites; no schema, no offline batch, no new dependency.
- **Coordinate with upstream topics rather than add a second cold-start track**: once topic 03 (HyDE `V_initial`) ships, the seed cosine-rank replaces the `CASE WHEN` as the primary ranker on rich queries, and the `bare`-branch's widened pool becomes a pure-popularity + farthest-point seed (topic 07 flag-on). The three reports compose cleanly; do not invent a fourth axis.

## Context (Current State)

archi-tinder experiences a **session** cold-start every time `SessionCreateView.post()` runs — distinct from the user cold-start of classical literature. Every session is independent: there is no carry-over of prior-session likes into the current pool. The pipeline is:

- `backend/apps/recommendation/views.py:155-181` — `SessionCreateView.post()` parses the NL query to `{filters, filter_priority, seed_ids}`, then runs `engine.create_bounded_pool(filters, filter_priority, seed_ids)` with a 3-tier relaxation fallback: full → drop geo/numeric → `_random_pool(target)`.
- `backend/apps/recommendation/engine.py:327-367` `create_bounded_pool()` — weighted `CASE WHEN` SQL on the eight parsed-filter fields produces `(pool_ids, pool_scores)` of size `RC['bounded_pool_target']=150`. `seed_ids` (LLM-derived from the NL query, up to 50) are force-inserted at highest `relevance_score = n+1`.
- `backend/apps/recommendation/views.py:186-203` — `initial_batch` (first 10 cards) is built by grouping `pool_ids` by `relevance_score` tier and running farthest-point within each tier, highest-tier first; when a tier exhausts, move to the next.
- `backend/apps/recommendation/engine.py:410-448` `farthest_point_from_pool()` — Gonzalez-style: pick candidate that maximises `1 − max cos(candidate, exposed)`. First call (empty `exposed_ids`) is a pure random pick.

Two structural facts matter here: (a) there is no user onboarding screen — the user lands directly on the LLM search input and types an NL query (per UI note in the brief); (b) the 3,465-row corpus (per topic 09) is small enough that every seeding strategy is online and brute-force-feasible. 89.5% completion rate (per `.claude/Report.md`) indicates the current seeding does not obviously block users in the first 10 swipes; the drop-off is mid-session, not entry.

## Findings

### 1. The literature's "cold start" is mostly user-cold-start; our problem is session-cold-start

The canonical Schein et al. / Wikipedia taxonomy splits the cold-start problem into **new user**, **new item**, and **new community/system** ([Wikipedia — Cold start (recommender systems)](https://en.wikipedia.org/wiki/Cold_start_(recommender_systems))). Nearly all surveyed remedies — onboarding quizzes (Pinterest's "Follow 5 topics", Netflix's "pick 3 shows"), preference elicitation (Elahi, Ricci, Rubens 2016 survey), demographic fallbacks — target the **new-user** case, where the goal is to bootstrap a persistent profile that will be refined across many sessions ([Elahi, Ricci, Rubens 2016 "A survey of active learning in collaborative filtering recommender systems", Computer Science Review](https://www.sciencedirect.com/science/article/abs/pii/S1574013715300150); [Rubens, Elahi, Sugiyama, Kaplan 2015 "Active Learning in Recommender Systems" in Recommender Systems Handbook](https://link.springer.com/chapter/10.1007/978-1-4899-7637-6_24)). Our setup is different: each session is fresh by design, the user has already typed a NL query before the first card is drawn, and we do not carry taste across sessions (per-project model, topic 07 Finding §6). The literature closer to our regime is **session-based recommendation**, which the NVIDIA Merlin group frames as "essentially a cold-start problem, where the recommender has access to neither long-term preferences nor situational context" ([NVIDIA Merlin — Session-Based Recommenders](https://developer.nvidia.com/merlin/session-based-recommenders); [Ludewig et al. 2019 "Evaluation of Session-based Recommendation Algorithms", arXiv:1803.09587](https://arxiv.org/pdf/1803.09587)). Most session-based benchmark systems use **recent-item embeddings** to seed — which is exactly what our `filters`+`seed_ids`+(future) `V_initial` do, aggregated from the NL query rather than a click trail.

### 2. Onboarding quizzes improve activation by 5–10% but are a UX intervention, not a search engine change

Pinterest's "Follow 5 topics" pre-home-feed is the canonical example; Casey Winters reports the experiment **improved activation rate abroad by 5–10%** depending on country and demographic ([Appcues interview — How Pinterest perfected user onboarding](https://www.appcues.com/blog/casey-winters-pinterest-user-onboarding)). Netflix's 3-step signup ending with "choose 3 shows you like" ([useronboard.com — Netflix](https://www.useronboard.com/how-netflix-onboards-new-users/)) and Spotify's cyclic artist/genre selection that feeds straight into the embedding pipeline ([Spotify Research — Generalized user representations for large-scale recommendations](https://research.atspotify.com/2025/9/generalized-user-representations-for-large-scale-recommendations)) share the same pattern: **a dedicated onboarding screen whose output is a user-level vector used across every subsequent session**. Three reasons to **reject onboarding for Topic 11**:
  1. We already have preference elicitation *inside* the NL query — the query itself is the user's answer to "tell us what you want." Asking again creates friction with no new signal.
  2. Onboarding persistence assumes cross-session identity of taste; our per-project data model says users have genuinely different taste per project (topic 07 Finding §6). A once-per-user quiz cannot express that.
  3. Topic 11 is in a *search-engine* research series. A new onboarding screen is a product-design task touching frontend routes, UX, and profile schema — outside this terminal's scope by invocation context.

### 3. Farthest-point sampling has a provable 2-approximation bound on the k-center objective

Gonzalez's 1985 algorithm on the k-center problem — pick the point maximising distance to the nearest selected centre — yields a **2-approximation to the min-max-radius optimum, and this bound is tight** (a polynomial-time heuristic with ratio < 2 would imply P = NP) ([Gonzalez 1985, covered at Wikipedia — Farthest-first traversal](https://en.wikipedia.org/wiki/Farthest-first_traversal); [Wikipedia — Metric k-center](https://en.wikipedia.org/wiki/Metric_k-center)). This is the strongest approximation guarantee of any method discussed in this series for set-selection under a max-spread objective. In our context, "spread" is the right primary objective for the first 10 swipes — before any likes have arrived, the system's goal is to *inform the user model*, which means exposing cards that differ from each other. Our `farthest_point_from_pool()` at `engine.py:410-448` is literally Gonzalez's heuristic on the cosine metric. Treating the current design as "a heuristic that might be improved" understates its theoretical status; it is the proven-optimal poly-time approach for this objective.

### 4. Tier-ordered farthest-point is a weak stratified-sampling scheme

Stratified sampling partitions the population by a categorical variable and samples within strata ([Amplitude — Stratified Sampling guide](https://amplitude.com/explore/experiment/stratified-sampling)). Our tier ordering partitions the 150-pool by `relevance_score` (each `CASE WHEN` contributes 0 or `n−i`, so scores form a small discrete set), then farthest-point within the top tier first. This is **not** per-cluster stratified sampling in the K-Means-on-embeddings sense, but it **is** stratified by the filter-relevance axis — which is the axis the user cares about, since they typed those filters explicitly. Adding a second stratification on unsupervised K-Means clusters of the *embedding* space would:
  - Add an offline compute path (K-Means on 3,465 × 384-dim vectors, nightly or on-corpus-change).
  - Double-count diversity — farthest-point already selects across the embedding geometry; forcing "one seed per cluster" is a coarser version of the same signal.
  - At 3,465 items with e.g. k=15 clusters, each cluster has ~230 items; a "guarantee one per cluster" constraint would *reduce* diversity relative to farthest-point within the 150-pool, not increase it, because clusters blur fine-grained embedding distance.

There is no literature showing cluster-stratified seeding outperforms farthest-point at small-corpus, small-N cold start. The general Gonzalez bound dominates.

### 5. Query-informativeness adaptivity is the real gap — and no upstream topic owns it

Query performance prediction (QPP) is the IR subfield that asks "given only the query, predict the retrieval quality" ([Carmel & Yom-Tov 2010 "Estimating the query difficulty for information retrieval", SIGIR](https://dl.acm.org/doi/10.1145/1835449.1835683); [Datta et al. 2024 "Query Performance Prediction using Relevance Judgments", arXiv:2404.01012](https://arxiv.org/pdf/2404.01012)). A core QPP use-case, explicitly called out in the SIGIR tutorial: *"The search engine can invoke alternative retrieval strategies for different queries according to their estimated difficulty… heavy procedures that are not feasible for all queries may be invoked selectively only for difficult queries"* ([SIGIR 2012 Predicting Query Performance tutorial](http://www.sigir.org/sigir2012/tutorial/PredictingQueryPerformance.php)). For archi-tinder, the rich/bare split is a crude but well-founded QPP-at-retrieval: when the parsed filter set is empty or carries only a generic program, the hard-filter + tier-ordered farthest-point reduces to a random pool + farthest-point, because the `CASE WHEN` score is degenerate. Users who type "something cool" or "housing" (bare) and users who type "minimalist concrete courtyard housing in Korea, 1990s" (rich) get the same pool target and the same tier ordering. That is a miss. The rich query deserves a tight 150-pool because the user has already narrowed the space; the bare query deserves a wider 200–300-pool because the user *wants* us to explore.

### 6. Topic 03 (HyDE V_initial) is the single biggest lever on cold-start quality, not seed-strategy swaps

Topic 03 documents that `research/algorithm.md:13-16` specifies HyDE-style V_initial (Gao et al. 2023) — an LLM-generated visual-description paragraph embedded into the 384-dim space and used to cosine-rank the pool. The live code never implements this step; pool creation is pure `CASE WHEN`. **Once topic 03 ships, the cold-start semantic quality improves by an order of magnitude more than any seed-strategy swap could**, because the pool ranker stops being "count of filter hits" and becomes "cosine similarity to the LLM's hallucinated ideal." Topic 11's recommendation must *not* presume to replace the `CASE WHEN` ranker — that is topic 03's domain — and must *not* presume V_initial is already shipped. The right framing: topic 11's query-informativeness branch sits at the seeding layer above the ranker, orthogonal to whether the ranker is `CASE WHEN` or V_initial cosine.

### 7. Active-learning / bandit-based cold-start is the wrong tool at our scale

The Rubens et al. 2015 chapter and Elahi et al. 2016 survey frame active learning as the principled answer to "which items should we ask the user to rate to learn fastest?" ([Elahi, Ricci, Rubens 2016](https://dl.acm.org/doi/10.1016/j.cosrev.2016.05.002)). LinUCB-style bandits (topic 05's deferred tech) provide exploration under uncertainty. Both would replace farthest-point with a more theoretically sophisticated strategy. Two reasons to reject for cold-start:
  - Active learning methods are designed for explicit ratings (Likert), not binary swipes, and their informativeness scores (entropy, variance-reduction) rely on a likelihood model that our engine does not maintain.
  - Per topic 05, we lack the telemetry and session-count (~1K+) to fit and validate bandit exploration. Deploying LinUCB only in the first 10 swipes would still require the same infrastructure and would be tested on zero live sessions' worth of data at our current scale.

Farthest-point is the *non-parametric* analog of "maximise informativeness under no model" — which is our regime. It wins on simplicity, ships without telemetry, and has the 2-approximation guarantee in §3.

### 8. Empirical evidence from the current system is the binding constraint

`.claude/Report.md` records an 89.5% completion rate and notes that drop-offs cluster **after** the first 10 swipes, not during them. The first-10-swipe regime is the exploring phase, powered by exactly the seeding pipeline under discussion. Any change to the seeder must at minimum hold that 89.5% — regressions in first-impression would show as early drop-offs within 10 swipes. This argues for flag-gated, small-delta interventions (Option B below) over wholesale rewrites. It also argues that the cost of *not* changing the seed strategy is low: the system is not bleeding out at the entry funnel.

## Options

### Option A — Status quo (documented, no change)
Keep hard-filter + tier-ordered farthest-point as the sole cold-start strategy. Add a code-comment explaining the Gonzalez guarantee and the tier-ordered stratification so future maintainers understand the design is intentional.
- **Pros**: Zero risk. 89.5% completion rate is the empirical floor; any change risks regression. Keeps the surface area minimal for upstream topics (03, 07) to compose with.
- **Cons**: Bare-query users (NL query with no or single filter) get a degenerate pool — `CASE WHEN` is all zeros or all ones, tier ordering collapses, the 150-pool is effectively random. Users have no way to know their query was "bare" vs "rich," and the UI does not explain the degraded-pool case.
- **Complexity**: Zero.
- **Expected impact**: Zero, by design.

### Option B — Query-informativeness branch (RECOMMENDED)
Add `_classify_query_informativeness(filters, filter_priority, seed_ids, raw_query)` returning one of `{'rich', 'bare'}` based on: `len(filter_priority) >= 2` **or** `len(seed_ids) >= 1` **or** (once topic 03 lands) `raw_query` present. On `'rich'`: current pipeline unchanged. On `'bare'`: widen the pool (`bounded_pool_target=250` instead of 150), skip tier ordering (a bare pool has only one or two score tiers anyway), and run farthest-point over the whole widened pool for the first 10 swipes.
- **Pros**: Targets the one real gap (degenerate pools on bare queries). Zero impact on rich-query sessions (which are the majority given the NL-query prompt — `parse_query` is prompted to extract filters aggressively). Composes with topic 07 (popularity prior) trivially: popularity contributes more to the bare-branch score since the `CASE WHEN` term is near-zero. Composes with topic 03 (V_initial): once `raw_query` is non-empty, `_classify_query_informativeness` flips most queries to `rich` and cosine-to-V_initial becomes the ranker; the bare branch becomes the fallback for truly empty queries.
- **Cons**: One more code path to maintain. The threshold (`len(filter_priority) >= 2`) is a heuristic, not a calibrated QPP model — future work (logged session telemetry) may reveal a better threshold.
- **Complexity**: **Low** (~half day: one classifier helper, an optional `target` override on `create_bounded_pool` already present, one conditional in `SessionCreateView`).
- **Expected impact**: Small-to-medium on bare-query session like-rate and first-10-swipe like-rate; neutral on rich-query sessions. Rich queries are already well-served by the existing pipeline.

### Option C — Offline K-Means cluster-stratified seed
Run K-Means (k=15–25) nightly on the full `architecture_vectors.embedding` corpus; persist `cluster_id` per building. Rewrite the seeder to force at least one building from each of the top-k clusters (by centroid similarity to the query's `V_initial` or the most-matched filter program).
- **Pros**: Guarantees coverage of semantic clusters even when the filter pool is small or skewed.
- **Cons**: Duplicates what farthest-point already provides (Finding §4). Adds offline plumbing (nightly job, cluster-id column on `architecture_vectors` — which is Make DB-owned and migration-restricted per `CLAUDE.md`). At 3,465 rows, tier-ordered farthest-point and K-Means-stratified both produce visually diverse first-10s; no empirical reason to prefer one over the other.
- **Complexity**: **Medium** (corpus clustering job + Make DB negotiation for the cluster-id column or app-side join table + engine rewrite).
- **Expected impact**: Near-zero incremental over Option B; negative expected-value once offline maintenance cost is priced in.

### Option D — Curated onboarding quiz (REJECTED on scope)
Build a one-time onboarding screen: "Pick 5 buildings you like from this grid" → compute a user-level preference vector → persist → use as the cosine seed on session 1.
- **Pros**: Matches Netflix/Pinterest/Spotify industry pattern; known to improve activation ~5–10% on other platforms.
- **Cons**: Out of scope for a search-engine research series — requires frontend routes, UX copy, profile schema. Duplicates the NL-query step (the user already states preferences in the query). Conflicts with the per-project data model (one cross-session taste vector doesn't fit per-project taste, topic 07 Finding §6).
- **Complexity**: **High** (full UX workstream + backend schema + recommendation wiring).
- **Expected impact**: Unknown without A/B; theoretically positive on new-user activation but negligible on session cold-start (which is our actual problem).

## Recommendation

**Ship Option B.** Keep the current cold-start pipeline as the default, add a `_classify_query_informativeness` branch, and widen the pool + pool-wide farthest-point when the query is bare. Reject Option C as redundant, defer Option D permanently as scope-mismatch, and leave Option A documented as the "no-change" baseline to measure B against.

Concretely:

1. `engine.py` gains a one-line helper `_classify_query_informativeness(filters, filter_priority, seed_ids, raw_query=None) -> Literal['rich', 'bare']`. A query is `'rich'` if any of: `len([k for k,v in filters.items() if v not in (None, '', [])]) >= 2`, `seed_ids and len(seed_ids) >= 1`, `raw_query and raw_query.strip()`. Otherwise `'bare'`.
2. `views.py:SessionCreateView.post()` calls the classifier right after `parse_query()` returns. When `'bare'`, passes `target=RC['bare_pool_target']` (default 250, new settings entry) to `create_bounded_pool()` and sets a local `skip_tier_ordering=True` flag.
3. In the `initial_batch` builder, when `skip_tier_ordering=True`, run farthest-point over the full `pool_ids` in one pass rather than iterating tiers (reduces to plain Gonzalez traversal on the unstratified pool).
4. Add a `RECOMMENDATION` dict entry `'BARE_POOL_WIDEN_ENABLED': False` (default off) and `'bare_pool_target': 250`. Flag-gated so algo-tester can A/B it before production rollout.
5. Algo-tester compares completion rate, first-10-swipe like rate, and time-to-convergence across 50+ personas with the flag toggled. Ship if non-negative on all three.

This Option B composes cleanly with the upstream pipeline:
- When topic 03 (HyDE `V_initial`) lands, `raw_query` is populated; `_classify_query_informativeness` flips to `'rich'` for almost every real user query, and the bare branch becomes the fallback for genuinely empty input (rare but non-zero — users who open a session from the favourites page with no NL query).
- When topic 07 (popularity prior) lands, its `POPULARITY_PRIOR_ENABLED` flag contributes an additive `CASE WHEN` term. In the bare branch, that term is the dominant non-random signal — topic 07's prior becomes most useful exactly where our filter signal is weakest.
- When topic 01 (hybrid retrieval) lands, the tsvector channel kicks in on `raw_query`; again, `_classify_query_informativeness` flips to `'rich'` and the RRF-blended pool replaces the `CASE WHEN` pool.

Option B is therefore not a competing cold-start strategy — it is the *branch point* that makes the three upstream improvements hang together coherently.

## Open Questions

- **Calibrating the richness threshold.** `len(filter_priority) >= 2` is a heuristic. A proper QPP-style calibration would train on (query, completion_rate) pairs — infeasible at current telemetry volume. After 6 months of logging, we should revisit with a simple logistic-regression classifier on query features (filter count, filter rarity, raw-query length).
- **Bare-pool widening vs bare-pool different-ranker.** Option B widens the target. An alternative is to *keep* the 150-pool size but flip the ranker to pure-random for bare queries (already the 3rd-tier fallback at `views.py:175-179`). Widening has the advantage that topic 07's popularity prior, once on, has more surface area to act on. To be measured.
- **Bare-query rate in production.** We have no telemetry yet on what fraction of live queries parse to an empty filter set. If the answer is <5%, Option B is a cheap guard rather than a large lever. If 20%+, Option B is actively addressing a meaningful population. Proposed: add a `bare_vs_rich` counter to the session-create log and revisit the impact prediction in 30 days.
- **Interaction with filter relaxation.** When `create_bounded_pool` returns empty and `views.py:162-173` relaxes filters (drops geo/numeric), is the relaxed query still `'rich'` or has it become `'bare'`? Current code evaluates richness before relaxation. If all relaxations leave only `program`, the session is effectively bare. Option B should probably re-classify after relaxation — cheap to fix, flag-gated behind the same setting.
- **First-card psychology.** The very first card shown is `initial_batch[0]`, picked by farthest-point from an empty exposed set — i.e., random within the top tier (by `random.choice`). This is a known cold-start psychology lever: the first card shapes the user's impression of "what this app is." A future extension could force the first card to be the top-`relevance_score` building (most-matched to the query) rather than a random top-tier one — small UX-grade change, out of scope for Option B but worth noting.
- **Session vs persona telemetry.** Our algo-tester runs synthetic personas; their "cold start" is not the real cold start because personas are deterministic once seeded. Any measured delta from B on personas may not transfer to real users. Recommend flag-off in production initially, on for algo-tester, then shadow-log on production before flipping the production flag.

## Proposed Tasks for Main Terminal

All backend; no frontend changes. Scope is `backend/apps/recommendation/*.py` + one settings entry.

1. **BACK-CS-1** — `engine.py`: add module-level helper `_classify_query_informativeness(filters: dict, filter_priority: list, seed_ids: list, raw_query: str|None = None) -> str` returning `'rich'` or `'bare'`. Pure function, fully unit-testable.

2. **BACK-CS-2** — `config/settings.py`: add `'BARE_POOL_WIDEN_ENABLED': False` and `'bare_pool_target': 250` to the `RECOMMENDATION` dict (near the other cold-start params, line ~131-144). Default off so the setting has zero production effect until flipped by algo-tester.

3. **BACK-CS-3** — `views.py:SessionCreateView.post()`: after `parse_query()` returns, call `richness = engine._classify_query_informativeness(filters, filter_priority, seed_ids, raw_query=parsed.get('raw_query'))`. When `settings.RECOMMENDATION.get('BARE_POOL_WIDEN_ENABLED', False)` and `richness == 'bare'`, pass `target=RC['bare_pool_target']` to `create_bounded_pool` and set a local `skip_tier_ordering = True`.

4. **BACK-CS-4** — `views.py:SessionCreateView.post()` (initial_batch builder, lines 186-203): when `skip_tier_ordering=True`, replace the tier loop with a single pass:
   ```
   initial_batch, exposed_temp = [], []
   while len(initial_batch) < RC['initial_explore_rounds']:
       next_bid = engine.farthest_point_from_pool(pool_ids, exposed_temp, pool_embeddings)
       if not next_bid: break
       initial_batch.append(next_bid); exposed_temp.append(next_bid)
   ```

5. **BACK-CS-5** — Logging: emit `richness` (`'rich'` or `'bare'`) in the `Session created` log line (line 228) so we can later tally production bare-rate.

6. **TEST-CS-1** — `backend/tests/test_sessions.py`: parametrised tests for `_classify_query_informativeness` covering: empty filters → bare; one filter → bare; two filters → rich; seed_ids present → rich regardless; raw_query present → rich regardless. Integration test that when `BARE_POOL_WIDEN_ENABLED=True` and a bare query is parsed, `create_bounded_pool` is called with `target=250` and tier ordering is skipped.

7. **ALGO-CS-1** — Once BACK-CS-1..5 ship, run algo-tester across 50+ personas (half with rich queries, half with bare queries) comparing completion rate, first-10-swipe like rate, and time-to-convergence with `BARE_POOL_WIDEN_ENABLED={False, True}` and `bare_pool_target ∈ {200, 250, 300}`. Apply only if non-negative on all three metrics. If algo-tester detects regression in rich-query runs (which should be impossible by design since the rich path is unchanged), investigate a logic error in the classifier.

8. **DOCS-CS-1** — Update `research/search/README.md` row 11 to reflect this report. (Not this terminal's write responsibility per the research-terminal folder isolation rule; noted here so the main orchestrator picks it up.)

## Sources

- [Gonzalez 1985 — Farthest-first traversal (k-center 2-approximation), Wikipedia](https://en.wikipedia.org/wiki/Farthest-first_traversal) — classic clustering algorithm behind our `farthest_point_from_pool`; establishes the 2-approximation bound for cold-start diversity seeding.
- [Metric k-center — Wikipedia](https://en.wikipedia.org/wiki/Metric_k-center) — companion reference for tightness of the 2-approximation (P=NP barrier).
- [Wikipedia — Cold start (recommender systems)](https://en.wikipedia.org/wiki/Cold_start_(recommender_systems)) — standard new-user / new-item / new-community taxonomy.
- [NVIDIA Merlin — Session-Based Recommenders](https://developer.nvidia.com/merlin/session-based-recommenders) — frames session-based recommendation as "essentially cold-start"; supports our session-cold-start framing.
- [Ludewig et al. 2019 — Evaluation of Session-based Recommendation Algorithms, arXiv:1803.09587](https://arxiv.org/pdf/1803.09587) — benchmark survey of session-based methods.
- [Wang et al. 2021 — A Survey on Session-based Recommender Systems, arXiv:1902.04864](https://arxiv.org/pdf/1902.04864) — taxonomy of session-based methods; cold-start treatment.
- [Elahi, Ricci, Rubens 2016 — A survey of active learning in collaborative filtering recommender systems, Computer Science Review](https://www.sciencedirect.com/science/article/abs/pii/S1574013715300150) — canonical active-learning-for-cold-start survey; motivates why we reject active learning at our scale.
- [Rubens, Elahi, Sugiyama, Kaplan 2015 — Active Learning in Recommender Systems (chapter in Recommender Systems Handbook)](https://link.springer.com/chapter/10.1007/978-1-4899-7637-6_24) — foundational chapter on preference elicitation strategies.
- [Casey Winters via Appcues — How Pinterest perfected user onboarding](https://www.appcues.com/blog/casey-winters-pinterest-user-onboarding) — "Follow 5 topics" activation lift of 5–10%.
- [useronboard.com — How Netflix Onboards New Users](https://www.useronboard.com/how-netflix-onboards-new-users/) — "pick 3 shows" pattern.
- [Spotify Research 2025 — Generalized user representations for large-scale recommendations](https://research.atspotify.com/2025/9/generalized-user-representations-for-large-scale-recommendations) — onboarding signals encoded through same embedding pipeline as established users.
- [Carmel & Yom-Tov 2010 — Estimating the query difficulty for information retrieval, SIGIR](https://dl.acm.org/doi/10.1145/1835449.1835683) — foundational query performance prediction reference.
- [SIGIR 2012 tutorial — Predicting Query Performance for IR](http://www.sigir.org/sigir2012/tutorial/PredictingQueryPerformance.php) — motivates selective retrieval strategies by query difficulty (the Option B branch).
- [Datta et al. 2024 — Query Performance Prediction using Relevance Judgments, arXiv:2404.01012](https://arxiv.org/pdf/2404.01012) — current state of QPP.
- [Amplitude — Stratified Sampling guide](https://amplitude.com/explore/experiment/stratified-sampling) — general stratified-sampling primer supporting our tier-ordered-is-weak-stratified framing.
- [Gao et al. 2023 — Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE), ACL](https://aclanthology.org/2023.acl-long.99/) — foundation of Topic 03; the upstream that changes "seeding" once shipped.
