# Perf Baseline — 2026-09-30

Reference point for before/after comparison of the speed experiments
(Python pin, gthread, buildings `CONN_MAX_AGE`, psycopg3, filter-first / streaming,
Jev PoC, swipe round-trip reduction). Pre-launch: prod has ~0 real traffic
(`session_metrics_report --days 30`: 0 swipes, 0 sessions, 2 image loads), so the
server-side baseline is synthetic.

Code measured: local `develop` @ `2551611` (#338, pre-#339 release code).

## 1. Network — Korea → prod (curl, median of 10)

Script: `tools/perf/probe.sh`.

| Target | cold connect / TLS / TTFB (ms) | warm (reused conn) |
|---|---|---|
| Frontend — Vercel (Seoul edge) | 11 / 34 / 54 | **11** |
| Backend — Railway (edge `hnd1` Tokyo → Singapore origin) | 44 / 89 / 202 | **110** |
| Ref: AWS Seoul | 15 / 29 / 38 | 8 |
| Ref: AWS Tokyo | 45 / 91 / 132 | 41 |
| Ref: AWS Singapore (direct) | 79 / 159 / 231 | 71 |

Every API call pays ~110 ms of network + Django floor. Only a full-stack Seoul move
(API + both DBs + Redis) removes it (~100 ms/call). Moving compute alone makes a swipe
~7x slower (see §5).

## 2. Prod facts (read-only, 2026-09-30)

- `canonical_v2_buildings` **has** `idx_canonical_v2_buildings_embedding_hnsw`
  (`hnsw (embedding vector_cosine_ops)`), plus GIN on `architect_canonical_ids`,
  `typology_tags`, `architectural_elements`, `source_refs`, `source_categories`, and
  b-tree on `is_publishable`, `style`, `program`, `location_country`, `location_city`,
  `project_year`, etc. → `docs/db-index-handoff.md` Step 1 answered: HNSW exists.
- pgvector `0.8.0` (iterative index scan available). `max_connections` = 901.
- Prod `IMAGE_BASE_URL` = `https://pub-….r2.dev` (rate-limited dev URL — move to an R2
  custom domain before launch).
- Prod Python version: **not yet read** (needs `railway ssh`; host key must be accepted
  once interactively).

## 3. Server — local in-process harness

Script: `tools/perf/bench.py` (DRF `APIClient` in-process against local `.env` DBs,
user `perf_bench_user`, 3 fixed Korean queries → session create → 20 swipes
(seeded 12 like / 8 dislike) → result, cold + warm pass).

```
cd backend && PYTHONIOENCODING=utf-8 python ../tools/perf/bench.py [--seed 1234] [--swipes 20] [--out DIR] [--label X]
```

Requires the local DB migrated to the checked-out code (`make migrate-local`); on
`origin/develop` after #339 an unmigrated local DB fails with
`null value in column "question_cooldown"`.

Local RTT to Neon (Korea → Singapore) is ~73 ms vs ~1-2 ms in prod, so **query counts
are the reliable signal**; wall times are inflated.

| Endpoint | Local wall p50 (cold / warm) | DB round trips / request (verified) | Cache ops | Est. prod |
|---|---|---|---|---|
| parse-query | 3476 ms (1 of 3 = 12 s) | 1 + 1 | 5 | LLM-bound, ~3.3 s |
| session create | 1232 / 750 ms | 7-8 default + 1-3 buildings | 14-17 | ~200-450 ms |
| swipe (like/dislike) | 1117 / 1038 ms | **12 default + 2 buildings = 14** (13 on card-cache hit) | ~16-17 | **~70-110 ms** (65-185) |
| swipe (extend) | 446 / 374 ms | 4 + 0-1 | 2-3 | ~90 ms |
| session result | 1372 / 933 ms | 5 + 1 | 12 | **~50-70 ms** |

Verified corrections (independent re-run):
- Round trips include psycopg2's separate `BEGIN` (+1 per transaction); the raw
  harness column undercounts by 1.
- Swipe CPU is ~10 ms. The rest is round trips + result transfer.
- `session_result` time is ~99% transfer: one buildings query returns ~458 KB because it
  selects `embedding::text` (server exec 1.5 ms).
- The 12 s parse was mostly a cold vocab/corpus-stats load (14 buildings queries,
  `SELECT DISTINCT style` 2.9 s), cached 24 h in shared Redis in prod.

Per-request costs the in-process harness does **not** include (measured separately
with a real Bearer token + real connection handling):
- Buildings DB reconnect every request (`CONN_MAX_AGE` 0): 517-552 ms locally,
  est. 10-40 ms in-region (repo record: 37 ms).
- `CONN_HEALTH_CHECKS` `SELECT 1` on default: +1 round trip.
- JWT auth: +1 `accounts_userprofile` query, +1 cache get.

Swipe round-trip sequence (like): load session → idempotency check → buildings
existence check → `BEGIN` → reload session `FOR UPDATE` → project `FOR UPDATE` →
savepoint → insert swipe event → release → update project → recent actions →
update session → `COMMIT` → buildings card fetch.

## 4. Side finding — HNSW candidate shortfall

A top-k query with `LIMIT 60` returned only **32 rows**: pgvector's default
`hnsw.ef_search` = 40 and the `NOT IN (exposed)` filter is applied after the index
scan. With pgvector 0.8 the fix is `SET hnsw.iterative_scan = relaxed_order` (or a
higher `ef_search`) for that query. Correctness issue (fewer candidates than asked),
not only speed — check which call sites hit it.

## 4b. PERF-SWIPE-1 before/after (local harness, same session, back to back)

before = `origin/develop` `dbfe598`, after = `78932f0`. Local RTT ~73 ms, so the
per-request counts are the signal.

| Endpoint (warm) | wall p50 before → after | buildings queries | cache ops |
|---|---|---|---|
| swipe (like+dislike) | 1011 → 904 ms | 1 → 0 (cold 2 → 1) | 15 → 7 |
| session create | 734 → 747 ms | unchanged | 14 → 11 |
| session result | 907 → 902 ms | unchanged | unchanged |

Prod estimate: swipe gains ~15-25 ms (1 buildings round trip + ~8 Redis ops), and
cache eviction now runs after COMMIT, outside the row locks. HNSW fix: filtered
`LIMIT 60` returns 60 rows instead of 8 (iterative scan off vs on, same query).

## 5. Railway replacement review (summary)

| Option | Per API call | Per swipe | Monthly | Effort |
|---|---|---|---|---|
| Stay on Railway SG (+ hardening) | 110 ms | ~125-135 ms | ~$10-20 | hours |
| Other SG host (Render / DO) | 0 to −39 ms (upper bound, unverified) | same | ~$50-135 | 1-2 days |
| Full Seoul (API + DB + Redis) | ~−100 ms | ~30 ms | ~$50-120 | 1-3 weeks + Make DB |
| Compute-only to Seoul/Tokyo | −70 to −100 ms | **+800-900 ms** | ~$25-60 | — (regression) |

Recommendation: stay on Railway now; hardening = `healthcheckPath` +
`restartPolicyType` in `railway.toml`, a portable Dockerfile, a "all services in SEA"
runbook check. Revisit full-Seoul only if post-launch data shows the ~100 ms network
floor hurts retention.
