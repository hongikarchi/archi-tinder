# Pool-Construction Ranking: Weighted CASE WHEN vs RRF vs Borda Count vs Learning-to-Rank

## Status
Ready for Decision — Normalize-Now, Defer-Rest (recommended)

## Question
archi-tinder's 150-building bounded pool is built via weighted `CASE WHEN` SQL additive scoring with priority-derived integer weights. Is this the right aggregation, or should it be replaced with Reciprocal Rank Fusion (RRF), Borda Count, Condorcet voting, or a learned ranker (LambdaMART, LightGBM)? What happens when each filter's "rank" is essentially binary match/no-match?

## TL;DR
- **Keep weighted `CASE WHEN` as the default pool-construction method.** The alternatives surveyed all degrade, match, or are blocked for our filter shape: each filter emits a binary `{0, weight}` signal rather than a true ranked list, which is the regime where rank-fusion methods have the weakest mathematical justification.
- **RRF is the right answer for *heterogeneous-scale* channels (cosine vs BM25 vs filter), not for the *homogeneous-binary* filter channel we have today.** When Topic 01's hybrid retrieval lands, RRF will fuse the vector branch and text branch at pool creation — that is where RRF earns its keep. It does not replace the filter-side aggregation; Topic 01 explicitly preserves the CASE WHEN path when `raw_query` is empty (`research/search/01-hybrid-retrieval.md:75-87`). Topic 12's question is therefore *moot in the hybrid path* and only has bite for filter-only queries.
- **The one concrete defect in the current method is weight-scale drift with active-filter count.** Weights are `n - i` where `n = |filter_priority|`, so a 3-filter query produces scores in `[0, 6]` while a 5-filter query produces `[0, 15]`. The `seed_ids` boost (`n + 1`) drifts in lock-step. A one-line normalization (divide the score expression by `sum(weights)`) fixes this with no change to ordering semantics and makes the score interpretable as "fraction of weighted filters satisfied."
- **Impact ceiling is small by construction.** `pool_scores` is used in exactly one place post-creation: tier-grouping the first 10 rounds' exploration batch with a `RANDOM()` within-tier tiebreaker (`views.py:186-203`, `views.py:218`). After round 10 the score is never read again — MMR uses cosine + diversity in numpy (`engine.py:492-532`). Any ranking method below "which score bucket a building lands in" is washed out by round 11.
- **Defer Borda, LambdaMART, and LTR** for the same reason as Topic 05: no session logs yet, no labelled training data, and (for Borda) no secondary ordering within match/no-match that would provide information the binary CASE WHEN discards.

## Context (Current State)

The pool-construction ranking is one function with three consumers:

- `backend/apps/recommendation/engine.py:289-324` — `_build_score_cases()` emits one `CASE WHEN <predicate> THEN <weight> ELSE 0 END` term per active filter across eight fields: `program` (exact match), `location_country` `style` `material` (ILIKE), `min_area` `max_area` (numeric ≥/≤), `year_min` `year_max` (numeric ≥/≤).
- `backend/apps/recommendation/engine.py:327-367` — `create_bounded_pool()` derives `weights[key] = n - i` from `filter_priority` (LLM-generated ordering), sums the CASE terms, filters `WHERE score > 0`, `ORDER BY relevance_score DESC, RANDOM()`, `LIMIT 150`. `seed_ids` (LLM-extracted specific building_ids) are force-inserted at score `n + 1` (one higher than any filter-derived score).
- `backend/apps/recommendation/services.py:93-134` — `parse_query()` emits `filter_priority` as an ordered list. No empirical signal about priority correctness; Gemini 2.5-flash produces it from the NL query.

**Where the score is consumed downstream.** Verified by grep across `backend/apps/recommendation/*.py`:
- `views.py:186-203` — `tiers[pool_scores.get(bid, 0)].append(bid)` groups pool IDs by their integer score, then iterates tiers highest-first; inside each tier, `farthest_point_from_pool` picks greedy-diverse cards. Only the first 10 (= `initial_explore_rounds`) cards come out of this pipeline.
- `views.py:218` / `models.py:44` — `pool_scores` is persisted on `AnalysisSession` but **never re-read** in the codebase. It is dead state after round 10.
- After round 10, the algorithm transitions to the analyzing phase (`engine.py:451-532`), where `compute_mmr_next` operates on K-Means centroids of `like_vectors` with cosine similarity and MMR diversity — `pool_scores` does not enter.

**Concrete structural observation.** Each CASE WHEN emits exactly two values per row: `0` (no match) or `weight` (match). The final score is `sum(weight_i · 1[match_i])`. This is a **weighted match count**, not a rank — the entire score distribution for an N-filter query has at most `2^N` distinct values. With typical N = 3-5 active filters, pool rows concentrate on at most 32 score values.

**Filter shape audit**: of eight filters, only `min_area/max_area` and `year_min/year_max` wrap a continuous column. In principle these could emit a graded score ("how close to the range center"); in the current SQL they emit binary. Everything else is categorical where "graded" is undefined.

## Findings

### 1. RRF degenerates on homogeneous-binary channels

Reciprocal Rank Fusion's formal definition is `RRF(d) = Σ_i 1 / (k + rank_i(d))` where `rank_i(d)` is document `d`'s position in ranked list `L_i`, and `k` is a smoothing constant (typically 60). Cormack, Clarke, and Buettcher's original paper proves RRF's robustness claim ([*Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods*, SIGIR 2009](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)) against baselines where each input list is a *genuine ranking* of candidates — the TREC queries in their evaluation are retrievals from BM25, MRF, language models, etc., each of which produces a dense ordering.

Our filter channels do not. Each `CASE WHEN` produces only two ranks:
- **rank 1** for every matched row (they all tie), or
- **rank ∞** (i.e., not in the list) for non-matched rows.

Plugging this into RRF: for each filter `i`, a matched row contributes `1/(60 + 1) = 1/61 ≈ 0.0164`; a non-matched row contributes 0. Summing over N filters, `RRF(d) = 0.0164 · (number of filters matched by d)`. This is identical to the unweighted match-count, up to a scalar — **losing the priority information the current system encodes**.

You could tie-break each filter by secondary ordering (e.g., within year_min matches, sort by year descending), but then you're doing Borda Count per filter, not RRF — see Finding 3. The fundamental issue: RRF is designed for heterogeneous-scale channels where a single numeric comparison is unreliable; it is not a method for combining binary satisfaction signals.

Elastic's and Azure's production RRF implementations are explicit about this: RRF's listed use case is "combining lexical (BM25) with vector (cosine) retrievers" — both of which produce dense rankings on the same candidate set ([Elastic Hybrid Search](https://www.elastic.co/what-is/hybrid-search); [Azure AI Search RRF](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)). No RRF deployment we can find uses it for boolean attribute filters; the standard practice there is weighted sum or a function-score query.

### 2. Weighted sum is the recognized norm for boolean attribute aggregation

The Bradley & Smyth work on case-based recommender systems ([*Improving Recommendation Diversity*, AIRTC 2001 / follow-ups in 2003-2009, summarized in Felfernig & Burke, *Constraint-Based Recommender Systems*](https://link.springer.com/chapter/10.1007/978-3-319-90775-0_12)) treats attribute-match aggregation explicitly as a linear utility `U(d) = Σ w_i · sim_i(d)` where `sim_i ∈ [0,1]`. For boolean filters, `sim_i ∈ {0,1}` — exactly our shape. This is also the canonical form for Elasticsearch's `function_score` / `rank_feature` queries and for pgvector hybrid examples where boolean filters are added to a weighted sum alongside a vector score.

The weakness of the method is well-known and is the single pathology we actually exhibit: weights are unnormalized. Felfernig's constraint-based recommender survey (ibid.) and Ricci's *Recommender Systems Handbook* (Chapter 5, [Springer 2022](https://link.springer.com/book/10.1007/978-1-0716-2197-4)) both recommend normalizing `w_i` to sum to 1 precisely to keep the score on a comparable scale across queries with different active filter counts. Our current code does not.

### 3. Borda Count requires secondary ordering we don't have

Borda Count ([classical social-choice theory; applied to IR in Aslam & Montague, *Models for Metasearch*, SIGIR 2001](https://www.ccs.neu.edu/home/jaa/publications/drafts/models-metasearch.pdf)) assigns each candidate a position score from each voter (filter), then sums positions. Borda's information advantage over weighted sum requires that each "voter" provide a complete ordering of candidates — not a binary yes/no.

Where we could reclaim an ordering: `year_min ≤ year ≤ year_max` could be scored by "distance from range centroid," `min_area ≤ area ≤ max_area` similarly. A richer `architect` filter with a fame proxy, or `style` with a closeness-to-canonical-style score, could also provide ordering. None of that exists in the schema today. Until we enrich filter semantics, Borda on our channels collapses to the same "weighted match count" that RRF does.

Jonathan Katz's empirical comparison of rank-fusion methods over heterogeneous retrievers ([*Which hybrid search method should I use?*, 2024](https://jkatz05.com/post/postgres/hybrid-search-ranking-fusion/)) shows Borda and RRF producing near-identical orderings on TREC-DL when given dense rankings. The two methods' relative merit is about tail-shape (RRF is less sensitive to rank-1 dominance) and is only observable when the input channels contain gradation — which ours don't.

### 4. Condorcet / pairwise voting is overkill and produces cycles

Condorcet methods pick the candidate that beats every other candidate in pairwise filter-majority votes. Two practical blockers:
- **Cycles**: classical Condorcet paradoxes (the Arrow impossibility family — [Arrow 1950, *A Difficulty in the Concept of Social Welfare*](https://www.jstor.org/stable/1828886)) are provably unavoidable when voters (filters) disagree. Our filters are not independent — program and style are positively correlated, year and style are positively correlated — but they are not guaranteed transitive. On a 150-row candidate pool with N filters, pairwise evaluation is 150² · N comparisons vs 150 · N for weighted sum. No quality payoff to justify the complexity.
- **Binary-ballot degeneracy**: when each filter outputs only "yes/no," Condorcet's pairwise matrix entries are 0 or 1 with heavy ties — essentially the same degenerate case as RRF on binary channels. Cormack et al. (ibid.) showed RRF *beats* Condorcet on TREC precisely because Condorcet requires ordered ballots that our filters don't produce.

Condorcet is not a candidate for Topic 12. Included here only because the task brief listed it.

### 5. Learning-to-Rank (LambdaMART / LightGBM Ranker) is blocked by the same constraint as Topic 05

LambdaMART ([Burges 2010, *From RankNet to LambdaRank to LambdaMART: An Overview*, Microsoft TR](https://www.microsoft.com/en-us/research/publication/from-ranknet-to-lambdarank-to-lambdamart-an-overview/)) and LightGBM's `LGBMRanker` ([Ke et al. 2017, *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*, NeurIPS](https://proceedings.neurips.cc/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html)) require labelled click-through-style data: `(query, candidate_features, relevance_label)` tuples. We have zero. Topic 05 (`research/search/05-preference-weight-learning.md:95-103`) already argued this case for the preference-vector weights; the same block applies here with one twist — we can't even bootstrap via session completion because `pool_scores` never re-enters the algorithm after round 10, so "click ≡ liked" doesn't propagate backward cleanly to the pool-ranking decision.

Practical consequence: LTR for pool construction requires (a) session logging (deferred via Topic 05 Option D), (b) ≥1K sessions, (c) a decision about whether the label is "user accepted the action card" or "user liked ≥ some threshold in the session" or "building appeared in final top-K." Each label is defensible; none is obvious. This is a 2026-H2 conversation at earliest.

### 6. The "washed-out" constraint: `pool_scores` drives only 10 rounds

The advisor-flagged structural property: `pool_scores` is consumed exactly once post-creation, by the tier-grouping at `views.py:186-203`, to bias the first 10 exploration rounds toward higher-scoring tiers (with `farthest_point_from_pool` picking diverse picks *within* each tier). It is persisted on `AnalysisSession.pool_scores` (`models.py:44`) but a grep of `backend/` shows **no read site** — the field is write-only state.

This bounds the impact ceiling of every ranking-method comparison in this report. If the current weighted CASE WHEN and a perfect oracle pick the same ~150 rows (just in different orders), and within-tier picks are randomized-diverse, the ordering difference only manifests when the oracle *excludes* a row that CASE WHEN *includes* — i.e., when pool membership, not pool order, differs.

Pool membership only differs when >150 candidates match ≥1 filter; below that, everything with any match is included regardless of method. We have no telemetry on how often the 150 cutoff binds. With a few-thousand-row corpus and typical N = 3 active filters, rough theoretical estimate: if each filter has ~30% match rate independently, the expected ≥1-match count is `corpus · (1 − 0.7^3) ≈ 0.657 · corpus`. For a 5K corpus that's ~3300 candidates — the cutoff binds hard. For a 500-row corpus it's ~330 — cutoff still binds. So the method *does* drive pool membership in practice, and this argument does not render the question moot.

### 7. Weight-scale drift is the one real defect, and normalization fixes it

`n - i` weights depend on the number of active filters. A query with `priority = ['program', 'style', 'material']` produces weights `{3, 2, 1}`; a query with `priority = ['program', 'location_country', 'style', 'material', 'year_min']` produces `{5, 4, 3, 2, 1}`. The seed_ids boost is `n + 1`, so seeds in the first query score 4, in the second query score 6.

Two practical consequences:
- **Within-query**: the ratios are what matter for ordering, and those are preserved (`3:2:1` vs `5:4:3:2:1` both keep program > style). So query-internal behavior is unchanged by normalization.
- **Cross-query / interpretability / telemetry**: if we ever log the score for a dashboard, 3-filter queries will look "low-score" and 5-filter queries "high-score" in absolute terms, conflating the two.
- **Seed-boost consistency**: with raw weights, the seed boost `n + 1` is just-barely-above the max filter score, a property that holds by construction. With normalized weights `w_i / Σw`, summing to 1 for a perfect-match row, the seed boost becomes a cleaner `1 + ε` (e.g., 1.1) — interpretable as "10% above best possible filter score."

Ricci's textbook (ibid. ch. 5) and Felfernig/Burke's review both recommend normalization for exactly these interpretability and telemetry reasons. It is the only change in this report we'd ship with any urgency.

## Options

### Option A — Keep current weighted CASE WHEN as-is (STATUS QUO)
Leave `_build_score_cases` and `create_bounded_pool` unchanged.
- **Pros**: Zero code change. Ordering behavior is correct given the priority list is correct.
- **Cons**: Cross-query weight drift. Seed boost semantics coupled to N. No explicit handling when priority list is miscalibrated.
- **Complexity**: None.
- **Expected impact**: Baseline.

### Option B — Normalize weights by sum (RECOMMENDED)
Divide each CASE-WHEN weight by `Σ w_i` at SQL emission time, producing scores in `[0, 1]` regardless of filter count. Seed boost becomes `1 + ε` (e.g., 1.1).
- **Pros**: Fixes the one real defect. One-line SQL change (`w / sum_w` instead of `w`). No ordering change within a single query, so no risk of regression. Makes scores comparable across queries — prerequisite for any later telemetry-driven tuning.
- **Cons**: Tier-grouping at `views.py:188` currently buckets by integer score; after normalization, buckets become floats. Grouping requires either rounding to a fixed number of tiers (e.g., round to 2 decimals → ~100 tiers max) or using `n` natural buckets keyed by "number of priority-matched filters." Mild refactor in views.py.
- **Complexity**: **Low** (½ day: SQL change + tier-grouping refactor + test).
- **Expected impact**: Small user-facing; medium infrastructural (enables clean telemetry).

### Option C — Replace CASE WHEN with RRF of per-filter ranked lists
For each filter, produce a ranked list (e.g., year filter: sort by proximity to range center among matches), then RRF-fuse.
- **Pros**: Principled rank fusion method; smoothly handles future filter enrichment.
- **Cons**: **Today's filters have no secondary ordering** (Finding 3) — RRF collapses to unweighted match count and *loses* the priority information. Only becomes useful if we first enrich filter semantics (e.g., graded year-fit). Implementation complexity is medium (per-filter subquery with window function, outer RRF sum).
- **Complexity**: **Medium** (~2 days) — and the work pays off only after a separate filter-enrichment project.
- **Expected impact**: Zero-to-negative until filter semantics are enriched.

### Option D — Learning-to-Rank (LambdaMART / LGBMRanker) on logged sessions
Train a pairwise ranker once we have ≥1K labelled sessions (Topic 05 Option D logging). Features: filter-match booleans, pool score, building attributes, parsed-query metadata.
- **Pros**: Long-run correct answer if we want truly adaptive pool ordering.
- **Cons**: Blocked by session-logging (Topic 05) and label definition. Modest impact ceiling given `pool_scores` only drives 10 rounds of exploration (Finding 6). High infra cost (training pipeline, periodic retraining, model hosting).
- **Complexity**: **High** (~1-2 weeks once data is available).
- **Expected impact**: Uncertain; capped by Finding 6's "scores washed out after round 10."

## Recommendation

**Ship Option B.** Concretely:

1. Modify `_build_score_cases` to accept a `normalized` boolean (default `False` for backward compat, or `True` if we cut over). When normalized, emit `CAST(<weight> AS FLOAT) / <sum_of_weights>` as the coefficient in each CASE WHEN.
2. Replace the `n + 1` seed boost in `create_bounded_pool` with `1.1` (or make it a config: `RC['seed_score_boost'] = 1.1`).
3. Update the tier-grouping at `views.py:186-203` to bucket by `round(pool_scores.get(bid, 0), 2)` so that floating-point tiers remain groupable. Alternatively (cleaner): group by "number of highest-priority filters matched" derived from `pool_scores` by reverse-engineering which filters contributed, but this is a bigger refactor — start with rounding.
4. Add one integration test asserting that (a) a 3-filter query and a 5-filter query both produce scores in `[0, 1]`, (b) seed_ids score strictly > any filter-match score, (c) within a single query, normalization preserves the ordering produced by the un-normalized version.

**Defer Options C and D.** Option C requires filter-semantic enrichment that is not on any roadmap. Option D is blocked by the Topic 05 session-logging dependency.

**Explicit scope note for Topic 01 interaction.** When `research/search/01-hybrid-retrieval.md` ships and `raw_query` is non-empty, pool construction switches to the RRF hybrid (`vector_branch ⊕ text_branch`). The filter-based CASE WHEN path is *bypassed* in that branch — Topic 12's question does not apply there. The normalized weighted sum is the correct default only for the filter-only (empty raw_query, or flag-off) path, which will continue to serve filter-heavy catalog-style queries after Topic 01 ships.

## Open Questions

- **Does the 150 cutoff actually bind in production?** Finding 6 estimates it binds at any reasonable corpus size under typical filter match rates, but we have zero telemetry. Logging `len(candidate_set_before_limit)` for one week on the pool-creation SQL would answer this empirically and would calibrate how much the ranking method actually matters. Cheap to add.
- **Is `filter_priority` from Gemini actually correct?** The whole current aggregation rests on the LLM-produced priority list being meaningful. We have no evaluation of priority quality. A brittle but cheap test: sample 50 diverse queries, have a human produce a "ground-truth priority," measure Kendall-τ against Gemini's output.
- **Can the score survive past round 10?** Consider passing the (normalized) score as a secondary relevance signal into the MMR formula (`engine.py:492-532`), weighted at 10-20% against cosine-to-centroid. This would give the filter-match signal a life beyond the exploration phase. Counter-argument: it could compromise the "user's actual liking pattern" bias MMR currently respects. Needs persona-tester evaluation.
- **Are range-filter binary predicates worth upgrading to graded?** `year_min/year_max` could produce "how close to range center" rather than binary yes/no, and `area_sqm` similarly. This is the only code-local change that would make Borda/RRF informative beyond weighted sum. Evaluate only if Option B metrics stall.
- **Can we piggyback on the existing tier-grouping to get a "filter disagreement" diagnostic?** The tier distribution at pool creation is a signal of how well-aligned the filters are. Low-tier-variance (all pool rows match most filters) means filters are redundant; high-tier-variance means filters conflict. Could drive a UI warning (e.g., "your filters are in tension — here's why").

## Proposed Tasks for Main Terminal

All backend. No frontend changes. Scope is `backend/apps/recommendation/engine.py`, `backend/apps/recommendation/views.py`, and `backend/config/settings.py`.

1. **BACK-PR-1** — `engine.py:_build_score_cases`: add `normalized: bool = True` parameter. When `True`, divide each `w` by the sum of weights **over active filters only** (i.e., the filters that pass the `if filters.get(...)` guards in the function body, not the full `filter_priority` list). This makes a perfect-match score equal to exactly 1.0 regardless of how much of the priority list was populated. Cast divisor to float in SQL. Preserve legacy behavior under `normalized=False` for test comparison.
2. **BACK-PR-2** — `engine.py:create_bounded_pool`: replace `pool_scores[sid] = n + 1` with a configured constant `RC['seed_score_boost']` (default `1.1`). Ensure seed score is still strictly above any legitimate filter-match score after normalization (max 1.0).
3. **BACK-PR-3** — `config/settings.py` RECOMMENDATION dict: add `seed_score_boost: 1.1`.
4. **BACK-PR-4** — `views.py:186-203`: keep the raw float score as the tier dict key — since all tier keys within a single query come from the same arithmetic, Python float equality is exact and no rounding is required. Verify the seed tier (1.1) sorts above all filter tiers (max 1.0). Log `len(tiers)` in the existing info log to surface distribution.
5. **TEST-PR-1** — `backend/tests/test_bounded_pool.py`: new test cases asserting (a) active-filter score sums land on `[0, 1]`, (b) seed_ids score strictly > any filter-match score, (c) within-query ordering preserved between normalized and un-normalized paths (golden-file on 5 fixed queries — ordering is guaranteed by monotone scaling, so this is a regression guard), (d) tier-grouping in `views.py` still produces monotone-decreasing tier iteration under float keys.
6. **OBS-PR-1** — `engine.py:create_bounded_pool`: log `candidate_count_before_limit` (rows matching WHERE score > 0, pre-LIMIT) alongside the existing log. One-week sampling answers Open Question 1 and calibrates whether Option C is ever worth revisiting.
7. **ALGO-PR-1** — Run `algorithm_tester.py` with Option B vs baseline across ≥50 personas. **Note**: within-query normalization is pure monotone scaling and cannot change single-query ordering by construction; the only behavior that can differ is tier membership under the float-key grouping. Treat this as a "confirm no regression from tier-key dtype change" harness, not a ranking-quality test. Apply permanently only if non-regressive on completion rate and precision.
8. **DOC-PR-1** — Update `research/algorithm.md` §"Phase 0" to note that pool-score values are normalized to `[0, 1]` over active filters with seed boost `1.1`, and cross-reference this file for the rationale.
9. **BACK-PR-5** *(deferred; blocked on Topic 05 session logging)* — When logs exist, evaluate whether a learned ranker (Option D) over pool scores produces detectably better pool composition. Success metric: at least one of completion rate, precision, or swipe count improves ≥5% on held-out personas. If not, close out the LTR-for-pool-ranking thread permanently.

## Sources

- [Cormack, Clarke, Buettcher 2009 — *Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods* (SIGIR)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) — foundational RRF paper; formal definition with `k = 60`; Condorcet comparison.
- [Aslam & Montague 2001 — *Models for Metasearch* (SIGIR)](https://www.ccs.neu.edu/home/jaa/publications/drafts/models-metasearch.pdf) — Borda Count applied to IR rank fusion.
- [Burges 2010 — *From RankNet to LambdaRank to LambdaMART: An Overview* (Microsoft Research TR)](https://www.microsoft.com/en-us/research/publication/from-ranknet-to-lambdarank-to-lambdamart-an-overview/) — canonical LambdaMART reference.
- [Ke, Meng, Finley, Wang, Chen, Ma, Ye, Liu 2017 — *LightGBM: A Highly Efficient Gradient Boosting Decision Tree* (NeurIPS)](https://proceedings.neurips.cc/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html) — LightGBM including `LGBMRanker`.
- [Arrow 1950 — *A Difficulty in the Concept of Social Welfare* (JPE)](https://www.jstor.org/stable/1828886) — Arrow's impossibility, underpinning Condorcet cycle-inevitability.
- [Ricci, Rokach, Shapira (eds.) 2022 — *Recommender Systems Handbook*, 3rd ed. (Springer)](https://link.springer.com/book/10.1007/978-1-0716-2197-4) — Chapter 5 on hybrid and knowledge-based recommenders; weighted-sum normalization guidance.
- [Felfernig, Friedrich, Jannach, Zanker 2018 — *Constraint-Based Recommender Systems* chapter in *Recommender Systems Handbook* 2018](https://link.springer.com/chapter/10.1007/978-3-319-90775-0_12) — weighted linear utility form for attribute-matching recommenders.
- [Elastic — *A Comprehensive Hybrid Search Guide*](https://www.elastic.co/what-is/hybrid-search) — production documentation that RRF's use case is cosine+BM25 fusion, not attribute-filter aggregation.
- [Microsoft Azure — *Hybrid Search Scoring (RRF)*](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking) — same framing as Elastic; independent confirmation of scope.
- [Jonathan Katz 2024 — *Which hybrid search method should I use?*](https://jkatz05.com/post/postgres/hybrid-search-ranking-fusion/) — empirical comparison of RRF, Borda, and weighted-sum on TREC-DL.
- [pgvector GitHub README](https://github.com/pgvector/pgvector) — current Postgres vector search primitives in the archi-tinder stack.
- Sibling topics: `research/search/01-hybrid-retrieval.md` (RRF use case, preserves CASE WHEN in non-hybrid path), `research/search/05-preference-weight-learning.md` (session-logging dependency for any learned method).
