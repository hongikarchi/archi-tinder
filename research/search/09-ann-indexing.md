# ANN Indexing on pgvector: HNSW vs IVFFlat vs Brute Force

## Status
Deferred — Document Trigger, Do Not Ship

## Question
archi-tinder currently does brute-force cosine on `architecture_vectors.embedding VECTOR(384)` with no ANN index. At what corpus size does adding HNSW or IVFFlat on pgvector become worth the operational cost? What are the recall/latency/memory/build-time trade-offs, and what thresholds should trigger migration?

## TL;DR
- **Do nothing now.** At our current "few-thousand" corpus size, brute-force `ORDER BY embedding <=> %s::vector LIMIT %s` on 384-d vectors runs in a few milliseconds — 0.1–0.3% of our 2 s swipe budget and far below measurement noise on our 5 s p95. Vendor benchmarks ([Neon](https://neon.com/docs/ai/ai-vector-search-optimization), [Microsoft Azure](https://learn.microsoft.com/en-us/azure/cosmos-db/postgresql/howto-optimize-performance-pgvector)) put the "seq-scan becomes costly" threshold around **50K rows**; we would need a >10× corpus explosion to approach the knee.
- **The critical reframe**: the concern baked into the task ("filtered ANN after WHERE") doesn't apply to our stack. Our metadata filter (`_build_filter_sql`, `_build_score_cases`) and the vector ANN are **in separate stages** — the WHERE-clause path at `create_bounded_pool` never touches the `embedding` column; the two `embedding <=> %s::vector` sites (`engine.py:232`, `engine.py:700`) run with only a `building_id NOT IN (exposed_ids)` exclusion over the **full corpus**. The pgvector-0.8.0 `iterative_scan` feature is interesting but not a current blocker. (§ Context)
- **When the trigger fires, prefer HNSW.** Our workload is low QPS, accuracy-sensitive, and the Make-DB-owned refresh cadence removes IVFFlat's main advantage (faster rebuild). HNSW's 30× QPS / ~100× p99-latency win over IVFFlat at 0.99 recall ([Katz 150× speedup post](https://jkatz05.com/post/postgres/pgvector-performance-150x-speedup/)) matches our profile.
- **Trigger metric**: brute-force p95 of the `embedding <=>` queries exceeds **150 ms** (≈7.5% of the 2 s swipe budget), which per Neon/Azure numbers occurs around **50K–100K rows**. Log query timings now so we detect this cleanly, and pre-negotiate the index addition with Make DB since `architecture_vectors` is read-only from Make Web.

## Context (Current State)

**Only two sites run pgvector ANN. Both are full-corpus scans.**

- `backend/apps/recommendation/engine.py:200-237` `get_top_k_results()`: `SELECT ... FROM architecture_vectors WHERE building_id NOT IN (exposed_ids) ORDER BY embedding <=> %s::vector LIMIT %s`. Runs once per session (session-complete top-K fallback). `k = RC['top_k_results'] = 20`.
- `backend/apps/recommendation/engine.py:661-755` `get_top_k_mmr()`: same shape, `LIMIT k*3 = 60`. Runs once per session on session completion to fetch the MMR shortlist. MMR itself then runs in numpy over the fetched rows (`engine.py:713-752`).

**Metadata filtering is upstream and does NOT use the embedding column.**

- `engine.py:289-367` `create_bounded_pool()` and `_build_score_cases()` build a `CASE WHEN program = %s THEN w ELSE 0 END + ... > 0` scoring predicate against scalar columns only. Result: 150 `building_id`s. No vector operator.
- Per-swipe ranking uses `get_pool_embeddings()` (`engine.py:370-402`) which fetches the pool's embeddings once and caches them in a process-local dict keyed by `frozenset(pool_ids)`. All subsequent MMR / farthest-point math (`engine.py:410-450`, `engine.py:492-532`) runs in numpy on this 150-element cache — zero pgvector ANN per swipe.

**Implication.** The task-prompt framing ("ANN operates after filter; index lookup size depends on filter selectivity") describes a pattern we don't currently execute. The pgvector indexing decision only affects two once-per-session full-corpus `ORDER BY embedding <=> centroid` queries. We therefore discuss filtered-ANN mechanics (iterative_scan, pre-/post-filter trade-offs) only as future-proofing; they are not today's bottleneck.

**Ownership constraint.** `CLAUDE.md` marks `architecture_vectors` as read-only: Make Web cannot migrate or `CREATE INDEX` on this table. Any index addition requires Make DB coordination.

**Latency budget.** Swipe API target <2 s end-to-end; current p95 ≈5 s. ANN query time is not measured today; on a few-thousand-row table, brute-force 384-d cosine with `LIMIT 20–60` is consistently single-digit ms across vendor benchmarks. It is safely <1% of budget.

## Findings

### 1. Brute force stays competitive well past our current scale

Vendor and blog benchmarks converge on a "~50K rows" knee for pgvector sequential scan on a single-threaded single-user workload:

- Neon's own optimisation doc says a sequential scan "performed reasonably well for tables with 10k rows (~36 ms)" but "start[s] to become costly at 50k rows" ([Neon — Optimize pgvector search](https://neon.com/docs/ai/ai-vector-search-optimization)). Azure Cosmos DB for PostgreSQL mirrors this guidance ([Azure — How to optimize performance when using pgvector](https://learn.microsoft.com/en-us/azure/cosmos-db/postgresql/howto-optimize-performance-pgvector)).
- Google Cloud's AlloyDB benchmark shows a dramatic ratio even on tiny data — sequential scan 12.4 ms vs HNSW 0.5 ms on 800 rows — but the **absolute** 12.4 ms is itself nowhere near our latency concern ([Google Cloud — Faster similarity search with pgvector indexes](https://cloud.google.com/blog/products/databases/faster-similarity-search-performance-with-pgvector-indexes/)). At 30K rows sequential scan is 226 ms (HNSW 0.98 ms) — this is where a user-facing single query starts to sting.
- At 1M rows the gap is existential — Katz reports IVFFlat 0.4.1 at 8 QPS / 150 ms p99 vs HNSW 0.7.0 at 253 QPS / 5.5 ms p99 at 99% recall on 1536-d OpenAI embeddings; sequential scan at this scale is unusable ([Katz — The 150× pgvector speedup](https://jkatz05.com/post/postgres/pgvector-performance-150x-speedup/)).

For our 384-d vectors in a few-thousand-row table, brute force is unambiguously the right choice — `embedding <=> v` is a single SIMD-friendly distance calc per row; a few thousand dot products complete faster than the query's planning and row-materialisation overhead.

### 2. HNSW dominates IVFFlat on our profile when the time comes

The IVFFlat build-time / memory advantage is real but situational:

- **Recall/latency curve**: HNSW wins everywhere in the standard benchmarks — ~30× QPS and ~30× p99 latency improvement over IVFFlat at matched 0.998 recall, per Katz's Aurora tests. This matches AWS's guidance ([AWS — Optimize generative AI applications with pgvector indexing](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/)): "HNSW is well-suited for high-recall, low-latency applications."
- **Build time**: IVFFlat wins — 128 s vs HNSW's 4065 s for 1M vectors at 0.998-recall parameters in Katz's tests (pgvector 0.7 cut HNSW build ~30× further; still slower than IVFFlat). For Make DB's refresh cadence (infrequent bulk recrawls of architecture sources), a one-time HNSW build measured in hours is acceptable; the refresh is not hourly.
- **Memory**: HNSW uses 2–5× more memory than IVFFlat. At <100K × 384-d vectors that's megabytes of delta — irrelevant on any Neon plan.
- **Parameters**: HNSW has `m` (default 16), `ef_construction` (default 64), `ef_search` (default 40). IVFFlat has `lists` (pgvector docs recommend `rows/1000` up to 1 M, else `sqrt(rows)`) and `probes` (`lists/10`, then `sqrt(lists)`). HNSW is less parameter-sensitive to corpus size; IVFFlat's recall drops sharply if `lists` drifts from its corpus-size-appropriate value, which means IVFFlat requires more maintenance attention as the corpus grows ([pgvector GitHub README](https://github.com/pgvector/pgvector)).

Our workload — a handful of full-corpus ANN queries per user session on a largely static corpus — is exactly the accuracy-sensitive / low-QPS profile where HNSW's build-time cost amortises cleanly and its query-time advantages dominate.

### 3. Filtered-ANN mechanics: not our current gotcha

The well-known pgvector failure mode is post-filtering under an approximate index: with `hnsw.ef_search = 40` and a WHERE-clause that matches 10% of rows, you get ~4 usable rows on average, starving high-LIMIT queries ([pgvector GitHub — Understanding HNSW + filtering](https://github.com/pgvector/pgvector/issues/259); [DEV — No pre-filtering in pgvector means reduced ANN recall](https://dev.to/franckpachot/no-pre-filtering-in-pgvector-means-reduced-ann-recall-1aa1)). pgvector 0.8.0 introduced `hnsw.iterative_scan` (`strict_order` / `relaxed_order`) plus better planner cost estimation to mitigate this ([AWS — pgvector 0.8.0](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/), [PostgreSQL — pgvector 0.8.0 release](https://www.postgresql.org/about/news/pgvector-080-released-2952/)).

We do not hit this mode today because our two `embedding <=>` queries only exclude `exposed_ids` (a small list); there is no selective WHERE on metadata at the ANN stage. **If** we ever move the filter-scored pool creation into a combined WHERE + ANN query (Option C in `research/search/01-hybrid-retrieval.md` sketches a related hybrid shape), the iterative_scan work becomes required reading — but that is a design choice, not a forced migration.

### 4. Neon-specific considerations

- Both HNSW and IVFFlat are production-ready on Neon and tuning docs explicitly cover both ([Neon — The pgvector extension](https://neon.com/docs/extensions/pgvector), [Neon — Optimize pgvector search](https://neon.com/docs/ai/ai-vector-search-optimization)). Neon shipped a 30× build-time improvement for pgvector HNSW in 2024 ([Neon — pgvector 30x Faster Index Build](https://neon.com/blog/pgvector-30x-faster-index-build-for-your-vector-embeddings)), so the "slow HNSW build" objection is much smaller on Neon than on self-hosted Postgres.
- `maintenance_work_mem` matters: both indexes build faster when the graph/lists fit in memory. Neon's compute tiers with sufficient memory are available on paid plans; a free-tier compute unit may OOM during an HNSW build on a large corpus. Make DB's Neon plan should be verified before triggering the index build.
- `CREATE INDEX CONCURRENTLY` is supported and **must** be used in production to avoid write blocking ([pgvector README](https://github.com/pgvector/pgvector)). For HNSW a concurrent build can be parallelised via `SET max_parallel_maintenance_workers = N` at session scope.

### 5. The realistic trigger

Combining the two queries' once-per-session frequency, the 2 s swipe budget, and the typical >5 s session length, the honest threshold is:

- **Below ~20K rows**: do nothing. Brute force is <50 ms and sits in background relative to Gemini parsing, network RTT, and front-end animation.
- **20K–50K rows**: measure. Per-query brute-force cost rises into the 50–250 ms range. Monitor user-perceived session-completion latency (final top-K fetch) and `get_top_k_mmr` p95 in the Django log.
- **≥50K rows, or ≥150 ms p95 on the `embedding <=>` queries, or any move to multi-query-per-swipe SQL-side ranking**: propose HNSW with `m=16, ef_construction=64` (defaults) plus `SET hnsw.ef_search = 100` at session scope for ≥0.95 recall on a 20/60-element LIMIT.
- **At 1M+ rows** (aspirational): revisit and re-benchmark; by then pgvector's own defaults and Neon's build machinery may have moved.

## Options

### Option A — Do nothing now; document the trigger (RECOMMENDED)
Leave brute-force in place. Land lightweight timing logs on the two `embedding <=>` sites. Pre-negotiate the index migration with Make DB as a standing playbook, to be executed when the trigger fires.
- **Pros**: Zero code change today. No dependency on Make DB cooperation. Matches the scale we actually have.
- **Cons**: Risk of surprise if corpus grows faster than logging cadence (mitigated by the log).
- **Complexity**: **Minimal** — 10-line logger wrap.
- **Expected impact**: None now; enables sub-day response when trigger fires.

### Option B — Add HNSW index now (pre-emptive)
`CREATE INDEX CONCURRENTLY ix_arch_vec_hnsw ON architecture_vectors USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);`
- **Pros**: Future-proofs against unannounced corpus growth. Cheap to maintain at our scale.
- **Cons**: Violates Make-DB read-only ownership — requires Make DB team coordination for what is currently zero observable win. Build time on a "few thousand" rows is <1 minute but the governance cost is the expensive part. Slightly raises recall floor below 1.0 (negligible at this scale since candidate graph visits all reachable nodes).
- **Complexity**: **Low** code / **Medium** ops (cross-team).
- **Expected impact**: Net zero today; prevents a future handoff.

### Option C — Add IVFFlat index now
`CREATE INDEX CONCURRENTLY ix_arch_vec_ivf ON architecture_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = sqrt(rows));`
- **Pros**: Faster build than HNSW.
- **Cons**: Strictly worse recall/latency curve than HNSW; still requires Make DB coordination; `lists` must be retuned as corpus grows (operational tax). No win over B except build time — which doesn't matter at a few-thousand rows or for Make DB's infrequent bulk refresh.
- **Complexity**: Same as B.
- **Expected impact**: Strictly dominated by B if we were shipping an index today.

### Option D — Hybrid: do nothing on the index, but migrate per-swipe ranking into SQL
Push `compute_mmr_next` and `farthest_point_from_pool` into a SQL `ORDER BY embedding <=> centroid` over the pool (currently numpy-in-cache).
- **Pros**: Offloads CPU from Python; simpler in-memory state.
- **Cons**: Trades a cache hit for a round-trip per swipe, regressing the happy path. MMR's redundancy term (`max_similarity(b, recent_shown)`) is awkward in one SQL statement. This is a refactor argued elsewhere (see `research/search/01-hybrid-retrieval.md`), not an ANN-indexing question.
- **Complexity**: **Medium-High**.
- **Expected impact**: Likely worse p95 today. Only revisit if the pool-embeddings cache breaks down (e.g., under high user concurrency with distinct pools).

## Recommendation

**Ship Option A.** Concretely:

1. Add a `logger.info("pgvector.ann", extra={"fn": "get_top_k_mmr", "rows": k*3, "duration_ms": ms})` around both `cur.execute(...)` calls at `engine.py:232` and `engine.py:700`, and around the raw fetch in `get_pool_embeddings` (`engine.py:382-388`). Cost: one log line per session.
2. Add a threshold check / alert rule on ingestion: when observed p95 of `get_top_k_mmr` SQL exceeds 150 ms, fire the index-migration playbook.
3. Pre-negotiate with Make DB: the playbook is a single SQL — `CREATE INDEX CONCURRENTLY ix_arch_vec_hnsw ON architecture_vectors USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);` — executed by Make DB during an off-hours window, followed by an `ANALYZE architecture_vectors;`. Make Web changes at that point are limited to a `SET LOCAL hnsw.ef_search = 100` on the two ANN SQL sites to keep recall high on the short LIMITs.
4. The IVFFlat branch is documented but not recommended; the trigger-time migration goes straight to HNSW for the reasons in Finding 2.

This is the rare "the best engineering decision is to not engineer" outcome. Every pgvector benchmark we can find agrees that below ~10K–50K rows the seq-scan path is already faster than the index setup cost and the recall is 100%. Ours is in that regime with an order of magnitude of runway. Adding the index today would be a pure operational cost with no user-visible benefit; waiting until the trigger fires is cheaper and produces a better-calibrated choice (we will know our actual p95 distribution then).

## Open Questions

- **What is our actual brute-force p95 today?** We lack telemetry. The trigger rule is calibrated against vendor-reported numbers — first week of logging will validate or correct our baseline.
- **Make DB refresh cadence and coordination ceremony.** We assume bulk, infrequent corpus rebuilds — which favours HNSW over IVFFlat. Confirm with Make DB team: is there ever a high-frequency drip of new buildings that would make HNSW's slower build painful? If yes, revisit option ranking.
- **Neon compute tier memory ceiling for HNSW build.** HNSW build scales with `maintenance_work_mem`; on a small Neon compute, a large corpus may force fallback to disk-spilling builds. Not an issue for 2026-scale corpus; check before 2027.
- **Interaction with future hybrid retrieval.** If we ship the RRF hybrid from `research/search/01-hybrid-retrieval.md`, the vector branch becomes a per-query full-corpus ANN (currently only per-session). That raises the ANN query frequency from O(1/session) to O(1/search) and likely pulls the trigger forward by an order of magnitude. The correct sequence is: ship hybrid first, re-measure, then decide index.
- **Iterative scan applicability.** If future work moves the metadata filter into the same SQL as the `ORDER BY embedding <=>`, `hnsw.iterative_scan = relaxed_order` becomes required alongside the HNSW index. Document alongside the hybrid-retrieval rollout.
- **Why `vector_cosine_ops` over `vector_l2_ops`?** Our embeddings are L2-normalised (`engine.py:394-396`) so cosine and Euclidean are monotone-equivalent, and `<=>` is cosine distance. Indexing with `vector_cosine_ops` matches the query operator; double-check that pgvector's planner uses the index for `<=>` queries under this opclass (it does, per the pgvector README).

## Proposed Tasks for Main Terminal

Scope: `backend/apps/recommendation/engine.py`, `backend/config/settings.py`, one playbook doc in `.claude/`. **No index migrations from Make Web** — those live with Make DB.

1. **BACK-ANN-1** — `engine.py`: wrap `cur.execute` at lines 232 (`get_top_k_results`), 700 (`get_top_k_mmr`), and 385 (`get_pool_embeddings` — note this is a metadata-only fetch but useful for end-to-end timing) with `time.perf_counter()` measurement and emit `logger.info("pgvector.query", ...)` containing `fn`, `sql_shape`, `row_count`, `duration_ms`. Logger name `apps.recommendation.pgvector`.
2. **BACK-ANN-2** — `config/settings.py`: add `RECOMMENDATION['ANN_LATENCY_WARN_MS'] = 150` and `RECOMMENDATION['ANN_LATENCY_CRIT_MS'] = 500`. BACK-ANN-1 log line should include a `warn`/`crit` flag when thresholds are exceeded.
3. **DOC-ANN-1** — New `.claude/playbooks/ann-index-migration.md` with: the `CREATE INDEX CONCURRENTLY` HNSW statement; Make DB coordination checklist; the one Make Web change (`SET LOCAL hnsw.ef_search = 100` wrapped around the two `embedding <=>` SQL sites); rollback (drop index). Not a code change; pre-written so the migration is low-risk when triggered.
4. **OBS-ANN-1** — After BACK-ANN-1 lands, add a 7-day sampled p95/p99 dashboard (or a one-shot `psql` query on the Django `api_requestlog` if we log there) for the two query-shape labels. This produces the first real baseline for the trigger metric.
5. **ALGO-ANN-1** — Re-run this analysis whenever (a) the `architecture_vectors` row count crosses 20K, (b) `get_top_k_mmr` p95 crosses 150 ms, or (c) the hybrid-retrieval report (`research/search/01-hybrid-retrieval.md`) ships and moves ANN frequency from per-session to per-query.
6. **RESEARCH-ANN-1** — Coordinate with Make DB to confirm their planned corpus growth trajectory and the governance for adding an index on `architecture_vectors`. Output: a one-paragraph "owner", "trigger signal", "response SLA" entry added to this report's Status section.

## Sources

- [pgvector — GitHub README](https://github.com/pgvector/pgvector) — canonical reference for index types, parameters, `CREATE INDEX CONCURRENTLY`, filtered search behavior, iterative_scan.
- [Neon — The pgvector extension](https://neon.com/docs/extensions/pgvector) — HNSW and IVFFlat are both production-ready on Neon.
- [Neon — Optimize pgvector search](https://neon.com/docs/ai/ai-vector-search-optimization) — "10K rows ≈ 36 ms, costly at 50K" threshold; `lists`/`probes` guidance for IVFFlat.
- [Neon — pgvector: 30x Faster Index Build](https://neon.com/blog/pgvector-30x-faster-index-build-for-your-vector-embeddings) — HNSW build-time improvements on Neon infra, relevant to build-cost objection.
- [Jonathan Katz — The 150x pgvector speedup: a year-in-review](https://jkatz05.com/post/postgres/pgvector-performance-150x-speedup/) — dbpedia-openai-1M benchmarks; 253 QPS HNSW vs 8 QPS IVFFlat at 0.998 recall; build-time numbers.
- [Google Cloud — Faster similarity search with pgvector indexes](https://cloud.google.com/blog/products/databases/faster-similarity-search-performance-with-pgvector-indexes/) — 800-row (12.4 ms seq vs 0.5 ms HNSW) and 30K-row (226 ms vs 0.98 ms) latency numbers.
- [AWS — pgvector 0.8.0 on Aurora PostgreSQL](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/) — iterative_scan `strict_order` / `relaxed_order` mechanics; planner cost-estimation improvements.
- [AWS — Optimize generative AI applications with pgvector indexing (IVFFlat vs HNSW)](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/) — "HNSW well-suited for high-recall low-latency" framing.
- [PostgreSQL — pgvector 0.8.0 release announcement](https://www.postgresql.org/about/news/pgvector-080-released-2952/) — official 0.8.0 features incl. iterative_scan.
- [Azure — How to optimize performance when using pgvector](https://learn.microsoft.com/en-us/azure/cosmos-db/postgresql/howto-optimize-performance-pgvector) — independent confirmation of the ~50K-row threshold guidance.
- [pgvector issue #259 — Understanding HNSW + filtering](https://github.com/pgvector/pgvector/issues/259) — canonical discussion of post-filter degenerate recall with selective WHERE clauses.
- [DEV — No pre-filtering in pgvector means reduced ANN recall (Pachot)](https://dev.to/franckpachot/no-pre-filtering-in-pgvector-means-reduced-ann-recall-1aa1) — detailed worked example of the post-filter pitfall, clarifying why we only care about this mode if we later combine filter + ANN in one SQL.
