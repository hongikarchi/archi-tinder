# Hybrid Retrieval: BM25/lexical + pgvector Cosine

## Status
Ready for Implementation

## Question
Should archi-tinder's search engine add BM25/lexical retrieval blended with pgvector cosine, and if so, what blend strategy and which fields?

## TL;DR
- **Yes** — production-standard hybrid search (BM25 ⊕ vector via Reciprocal Rank Fusion) is now the retrieval norm (Elastic, Vespa, Azure AI Search, Google Vertex AI). Our pure-cosine pipeline leaves lexical precision on the table.
- **Recommended blend**: Katz-style RRF hybrid using PostgreSQL built-in `tsvector` + `ts_rank_cd` on the text side and existing pgvector cosine on the semantic side. **No extensions required** — stays compatible with Neon.
- **Recommended text fields**: `visual_description`, `tags`, `atmosphere`, `material_visual`, `name_en`, `project_name` concatenated into a single `tsvector` expression using the `'simple'` dictionary (multilingual-safe; our embeddings already handle semantic multilingual).
- **Expected impact**: better precision for queries with specific terms ("concrete", "courtyard", "louvre") that current filter parsing discards and pure-cosine compresses.

## Context (Current State)

Pure cosine, with no lexical channel and no use of the raw NL query:

- `backend/apps/recommendation/engine.py:200-237` — `get_top_k_results()`: runs `ORDER BY embedding <=> %s::vector` on the preference vector. No text matching at all.
- `backend/apps/recommendation/engine.py:289-367` — `create_bounded_pool()` + `_build_score_cases()`: builds pool via weighted `CASE WHEN` on the eight parsed-filter fields only (`program`, `location_country`, `style`, `material`, `min_area`, `max_area`, `year_min`, `year_max`). No matching on the rich text fields.
- `backend/apps/recommendation/services.py:93-134` — `parse_query()`: Gemini parses NL → structured filters + `filter_priority`; the **raw query text is discarded** after extraction (return value contains `reply`, `filters`, `filter_priority` — no `raw_query`).
- `architecture_vectors` schema contains several high-signal text fields currently unused for retrieval: `visual_description` (long free text), `tags` (array), `atmosphere` (free form), `material_visual` (array), `name_en`, `project_name`, `architect`.

Consequence: A query like "minimalist concrete housing with courtyard" gets reduced to `{program: Housing, style: minimalist?, material: concrete?}`. The word "courtyard" — likely present in many `visual_description` and `tags` fields — never influences retrieval.

## Findings

### Hybrid search is the production norm, and RRF is the default fusion
- Elastic: "Hybrid search combines lexical and semantic results... RRF is built-in... k constant typically 60" ([Elastic hybrid search guide](https://www.elastic.co/what-is/hybrid-search)).
- Azure AI Search: "RRF is the default ranking for hybrid queries... score = Σ 1/(k + rank_i)" ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)).
- RRF requires no training, no per-corpus tuning, and handles the score-scale-mismatch problem between BM25 (unbounded) and cosine (bounded) cleanly ([Minimalist Innovation — RRF primer](https://www.minimalistinnovation.com/post/hybrid-search-reciprocal-rank-fusion-lexical-semantic)).

### On PostgreSQL specifically: three implementation tiers
1. **Built-in `tsvector` + `ts_rank_cd`** (no extensions). Jonathan Katz demonstrates a clean UNION-ALL + RRF pattern that runs in ~8.5 ms on 50K rows on vanilla pgvector + built-in FTS ([Hybrid search with PostgreSQL and pgvector](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)). This is not technically BM25 (it's TF-IDF with document-length normalization) but yields similar ranking behavior for short, keyword-dense corpora like ours.
2. **Real BM25 via extension**: `paradedb_pg_search` or TigerData's `pg_textsearch` add proper BM25 scoring ([ParadeDB hybrid guide](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual), [TigerData pg_textsearch](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres)). Quality is better on long documents and rare-term scoring; cost is operational (extension install, platform compatibility — **Neon support not guaranteed**).
3. **Dual-query with app-side RRF**: run two queries separately, fuse ranks in Python. Most flexible, worst performance (two round-trips).

### Multilingual tokenization
Katz's example hardcodes `'english'`. For archi-tinder, `visual_description` and `name_en` are English-dominant but `location_country`, `city`, and future Korean building descriptions will vary. Using the `'simple'` dictionary (no stemming, no stopword removal) avoids index-invalidation when languages mix, at the cost of slightly worse English-only recall. Our multilingual embedding already carries semantic Korean/English, so the tsvector channel only needs to catch exact/near-exact tokens.

### Query-embedding blend (a complementary axis)
Blending a raw-query embedding into the preference vector (`α·q + (1-α)·pref`) is popular in session-based search (e.g., Vespa rank profiles). **Not feasible in our stack today**: `CLAUDE.md` mandates "SentenceTransformers is NOT a dependency here — embeddings are pre-computed." Computing a query embedding would require a remote embedding call or loading the model. This is tracked as a follow-up (see Open Questions).

## Options

### Option A — tsvector CASE WHEN inside `_build_score_cases`
Add a weighted `ts_rank_cd` as another additive term in the existing `CASE WHEN` scoring.
- Pros: Minimal code change, stays within current pool-scoring paradigm, no new SQL shape.
- Cons: Additive scoring with unscaled `ts_rank_cd` mixes poorly with the integer filter-priority weights; no true rank fusion.
- Complexity: **Low** (~half day).
- Expected impact: Small-to-medium; text signal drowned by filter weights if the priority sum is large.

### Option B — BM25 extension (ParadeDB `pg_search` or TigerData `pg_textsearch`) + RRF
Install a real-BM25 extension; run vector + BM25 queries and fuse via RRF.
- Pros: True BM25 scoring; industry-grade; best quality on long text like `visual_description`.
- Cons: Extension install on Neon must be verified (ParadeDB bundles a custom Postgres distribution; TigerData's `pg_textsearch` targets Timescale). Adds ops surface.
- Complexity: **Medium-High** (extension install + migration + dual-query logic).
- Expected impact: Largest, but unknown until benchmarked.

### Option C — Query-embedding blend (α·q_embed + (1-α)·pref_vector)
Embed the raw NL query and blend into preference vector.
- Pros: Solves the "discarded raw query" problem on the semantic side; orthogonal to A/B.
- Cons: Violates "no SentenceTransformers here" rule; requires a remote embedding API call or architectural change.
- Complexity: **Medium** (new dependency/service).
- Expected impact: High for nuanced queries, zero for exact-term queries.

### Option D — Katz-style RRF hybrid (recommended)
Single SQL query with UNION ALL of two subqueries — pgvector ordering + tsvector ordering — fused by a custom `rrf_score(rank, k=60)` function. Gated by `HYBRID_RETRIEVAL_ENABLED` flag.
- Pros: Industry-standard RRF; no extensions (works on Neon); single round-trip; cleanly replaces current pool scoring when a raw query is present; leaves filter-priority weights in the non-hybrid path for backward compatibility.
- Cons: `ts_rank_cd` is not true BM25 (mild quality loss vs Option B); one new GIN index needed on the concatenated tsvector expression.
- Complexity: **Low-Medium** (1-2 days incl. flag + tests + index migration).
- Expected impact: Large on text-keyword queries; neutral on filter-only queries (path bypassed).

## Recommendation

**Ship Option D.** Flag-gated, replacing pool scoring **only when `raw_query` is non-empty**. Concretely:

1. `parse_query()` returns `raw_query` verbatim alongside existing fields.
2. `create_bounded_pool()` accepts an optional `q_text` argument; when present (and `HYBRID_RETRIEVAL_ENABLED=True`), uses the Katz RRF SQL pattern:
   - Vector branch: `ORDER BY embedding <=> preference_vector` (or centroid in analyzing phase), `LIMIT 3*pool_target`.
   - Text branch: `ORDER BY ts_rank_cd(to_tsvector('simple', visual_description || ' ' || array_to_string(tags, ' ') || ' ' || atmosphere || ' ' || array_to_string(material_visual, ' ') || ' ' || name_en || ' ' || project_name), plainto_tsquery('simple', q_text))`, `LIMIT 3*pool_target`, with the `@@` operator as WHERE filter.
   - Outer: `GROUP BY id, SUM(rrf_score(rank, 60))`, `LIMIT pool_target`.
3. If `HYBRID_RETRIEVAL_ENABLED=False` **or** `q_text` is empty, fall through to existing CASE WHEN scoring — zero behavior change.
4. Add a single GIN index on the concatenated tsvector expression (migration-as-raw-SQL, one-liner — no schema change to `architecture_vectors` required since indexes are usage-side).
5. Seed filter IDs still force-included at highest score (preserved from current behavior).

Defer Options B and C until Option D is measured. If D underperforms on long-text queries, graduate to B; if D misses nuanced paraphrases (e.g., "a space that feels protective"), graduate to C.

## Open Questions

- **Real user query distribution.** We have no telemetry on whether users type keyword-heavy ("concrete courtyard") vs. affective ("cozy and warm"). The expected impact of D is a direct function of this. Recommend landing D flag-off in production first, then sampling 100 live queries to decide rollout.
- **Neon compatibility for extensions.** If we later want real BM25 (Option B), need confirmation that Neon allows `pg_search` / `pg_textsearch` extension install. Current Neon extension allowlist needs a check.
- **Tsvector index ownership.** `architecture_vectors` is "owned by Make DB" per `CLAUDE.md`. Adding a GIN index on it may need a Make DB side change. If Make Web cannot write indexes, we need to negotiate the index migration with Make DB or fall back to an app-side join table.
- **Korean-query behavior.** `'simple'` handles any Unicode but won't tokenize CJK properly (whitespace-separated only). If we expect Korean queries, need separate indexing with `pg_trgm` or a CJK tokenizer. Non-blocking for English-dominant corpus.
- **Analyzing-phase integration.** During MMR ranking, "preference vector" is replaced by K-Means centroid. Does the raw query still apply post-convergence, or should its weight decay? Recommend: hybrid blend applies only during exploring phase and initial pool creation; analyzing phase stays pure-vector (preserves taste-driven convergence). To be validated empirically.

## Proposed Tasks for Main Terminal

All backend; no frontend changes. Scope is `backend/apps/recommendation/*.py` + one migration.

1. **BACK-HYB-1** — `services.py:parse_query()`: add `'raw_query': query_text` to the return dict on both success and fallback paths. Update `ParseQueryView` response schema accordingly. Update any call site that consumes the parsed result.
2. **BACK-HYB-2** — `engine.py`: add a `q_text: str | None = None` parameter to `create_bounded_pool()`. When `q_text` is non-empty **and** `settings.RECOMMENDATION.get('HYBRID_RETRIEVAL_ENABLED', False)` is true, execute the Katz RRF SQL pattern (UNION ALL + `rrf_score` CTE). Otherwise, existing behavior unchanged.
3. **BACK-HYB-3** — `engine.py`: add a module-level helper `_rrf_hybrid_pool(q_text, pref_vector, pool_target, rrf_k=60)` returning `(pool_ids, pool_scores)` matching the current return shape so the call site in `views.py` stays unchanged.
4. **BACK-HYB-4** — New migration `recommendation/migrations/00XX_hybrid_retrieval_index.py` with `RunSQL` creating `CREATE INDEX IF NOT EXISTS idx_architecture_vectors_fts ON architecture_vectors USING GIN (to_tsvector('simple', coalesce(visual_description,'') || ' ' || coalesce(array_to_string(tags,' '),'') || ' ' || coalesce(atmosphere,'') || ' ' || coalesce(array_to_string(material_visual,' '),'') || ' ' || coalesce(name_en,'') || ' ' || coalesce(project_name,'')))`. Reverse = DROP INDEX IF EXISTS. Note: verify with Make DB team that index addition on `architecture_vectors` is acceptable from Make Web side.
5. **BACK-HYB-5** — `config/settings.py`: add `HYBRID_RETRIEVAL_ENABLED: False` to the `RECOMMENDATION` dict (line ~131-144).
6. **BACK-HYB-6** — `views.py:SessionCreateView.post()`: pass the new `raw_query` (from parse_query output) into `create_bounded_pool(... q_text=raw_query)`.
7. **TEST-HYB-1** — `backend/tests/test_sessions.py`: add parametrized tests for both flag states. Mock `create_bounded_pool` differently based on flag; assert that when flag=True and raw_query present, the hybrid path is taken (verify via dependency-injected SQL capture).
8. **ALGO-HYB-1** — After shipping flag-off, run algo-tester comparing completion rate, like rate, and time-to-convergence across 50+ personas with flag toggled. Apply only if non-negative on all three metrics.

## Sources

- [Hybrid search with PostgreSQL and pgvector — Jonathan Katz](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/) — primary reference for the recommended SQL pattern.
- [A Comprehensive Hybrid Search Guide — Elastic](https://www.elastic.co/what-is/hybrid-search)
- [Hybrid Search Scoring (RRF) — Azure AI Search, Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)
- [About hybrid search — Vertex AI, Google Cloud](https://docs.cloud.google.com/vertex-ai/docs/vector-search/about-hybrid-search)
- [Hybrid Search in PostgreSQL: The Missing Manual — ParadeDB](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [Introducing pg_textsearch — TigerData](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres)
- [Hybrid Search & Reciprocal Rank Fusion — Minimalist Innovation](https://www.minimalistinnovation.com/post/hybrid-search-reciprocal-rank-fusion-lexical-semantic)
- [Integrating BM25 in Hybrid Search and Reranking Pipelines — DEV Community](https://dev.to/negitamaai/integrating-bm25-in-hybrid-search-and-reranking-pipelines-strategies-and-applications-4joi)
