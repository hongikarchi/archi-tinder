# Buildings-DB Index Handoff — for the Make DB owner (2026-07-07)

**From:** Make Web (backend speed/accuracy analysis, `.claude/plans/algo-speed-accuracy-analysis.md`)
**To:** Make DB owner (owner of `canonical_v2_buildings` — Make Web cannot and must not run DDL on it)
**Why:** Make Web's recommendation hot paths (session-create pool build, swipe next-card selection, LLM search, discovery) run raw SQL against `canonical_v2_buildings` (~39.5k rows, ~93% publishable). No index is documented in `docs/database-schema.md`, and Make Web's own code comments *assume* a pgvector HNSW index exists without any confirmation. If those assumptions are wrong, every similarity query is a full-corpus scan on the user-facing hot path.

## Step 1 — Check what already exists (read-only, one query)

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'canonical_v2_buildings';
```

Please paste the output back to Make Web — we will update `docs/database-schema.md` so the documented schema matches operational reality (right now the doc has zero `CREATE INDEX` statements).

## Step 2 — Recommended indexes (priority order, all additive + `CONCURRENTLY` = no downtime)

| # | Index | Purpose (Make Web call sites) |
|---|---|---|
| 1 | `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cvb_embedding_hnsw ON canonical_v2_buildings USING hnsw (embedding vector_cosine_ops);` | **Most important.** Every similarity query uses `ORDER BY embedding <=> %s::vector LIMIT k` — top-K results, MMR next-card, taste-ranked pages, discovery candidate hydration. Without HNSW each call computes distance over the full corpus. Make Web code comments (discovery_feed.py) already assume this index exists. |
| 2 | `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cvb_fts ON canonical_v2_buildings USING gin (to_tsvector('simple', coalesce(name,'') || ' ' || coalesce(visual_description,'')));` | BM25/hybrid text-search path. Make Web engine.py:918 carries a TODO admitting this index is missing. **Match the exact tsvector expression used in engine.py's hybrid query before creating** — an expression index only serves queries with the identical expression. |
| 3 | `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cvb_material_visual ON canonical_v2_buildings USING gin (material_visual);` | Filter pool creation runs `EXISTS (SELECT 1 FROM unnest(material_visual) ...)` per candidate row. |
| 4 | `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cvb_program_pub ON canonical_v2_buildings (program) WHERE is_publishable = true;` | Session-create pool filters gate on `is_publishable = true AND program = %s`. Partial index keeps it small (~37k rows today; matters more as the corpus grows). |

Notes:
- At today's ~39.5k rows, plain b-tree filters are survivable without indexes; **#1 (HNSW) is the one with immediate hot-path impact** because vector distance is expensive per row, not just I/O.
- HNSW build takes memory/time on 384-dim × 39.5k rows — fine at this scale; `CONCURRENTLY` avoids locking crawler writes.
- If an ivfflat index already exists instead of HNSW, that also works for `ORDER BY <=> LIMIT`; just tell us which so the docs can say so.

## Step 3 — Two stale cost assumptions to be aware of (Make Web side, FYI)

- `engine.py:574-576` comment claims the tag-score CTE scan costs "~10-50ms on 2.6k publishable rows" — the publishable corpus is ~37k now (~14x the comment's basis). We flagged this internally; fresh `EXPLAIN ANALYZE` after Step 1/2 would let us re-pin the number.
- `swipe` p95 and session-create p95 are being re-measured on the Make Web side; index results here directly move those numbers.

## Contact / follow-up

After Step 1 output lands, Make Web will update `docs/database-schema.md` (schema source of truth) with the confirmed index list in the same PR that records your reply.
