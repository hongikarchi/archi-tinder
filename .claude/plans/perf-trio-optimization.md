# PERF Trio Optimization — BACK-PERFORMANCE-1/2/3

## Context

User directive 2026-05-26: address 3 backend latency items in a single
auto-driven session via `/goal`-style retry-unlimited execution. PR per item,
all base=`develop`. **`develop → main` deploy is explicitly out of scope** for
this plan.

Source items (from `Task.md ## Next`):

- **BACK-PERFORMANCE-1** — `GET /api/v1/projects/` p50 = 600 ms, target ≤ 300 ms.
- **BACK-PERFORMANCE-2** — `GET /api/v1/discovery/` cache-hit p50 = 450 ms, target < 200 ms.
- **BACK-PERFORMANCE-3** — `POST /api/v1/sessions/` (Search → first card) p50 = 5–8 s, target ≤ 2 s.

## Goal Conditions (the `/goal` predicates)

| Slice | Endpoint | Predicate (3-run p50 unless noted) |
|---|---|---|
| PERF-1 | `GET /api/v1/projects/` | p50 ≤ 300 ms (1 cold + 2 warm, local dev DB) |
| PERF-3 | `POST /api/v1/sessions/` | p50 ≤ 2000 ms (3 fresh sessions, different query) |
| PERF-2 | `GET /api/v1/discovery/` | cache-hit p50 < 200 ms (5 consecutive hits) |

### Measurement scope (user decision 2026-05-26)

Local dev DB (Neon `local-dev-2` branch) p50 = **development proxy**, NOT the
final acceptance gate. Task.md acceptance cites Singapore Railway deploy
numbers; meeting local p50 ships a candidate, not a guarantee. Each PR body
must contain a `## Measurement scope` block stating:

> Measured locally against Neon `local-dev-2` (development proxy). Production
> Singapore-deploy p50 will be confirmed by post-deploy Codex retest, which
> the admin runs separately. Local goal-met does not equate to acceptance-met.

PERF-1/3/2 each surface their local before/after numbers in the PR. Codex
retest cycle is out of scope for this auto-driven session.

### Retry policy

Unlimited iterations on the optimization hypothesis. Each iteration = (form
hypothesis IN MAIN SESSION → implement via back-maker with that exact spec →
measure → compare). Main session owns hypothesis formation; back-maker does
not improvise. No 3-strike abort. Stop only on the hard STOP conditions below.

### Algorithm-territory authorization (user decision 2026-05-26)

PERF-3 likely touches `backend/apps/recommendation/engine.py`,
`backend/apps/recommendation/services/_caches.py`, and possibly
`services/embeddings.py`. CLAUDE.md `## Rules` places these in
algorithm-owner territory. User has **explicitly authorized this session to
touch them for PERF-3**, with the standing invariant that **swipe-loop
determinism + pool ordering + initial_batch shape MUST be preserved**. If a
hypothesis cannot be implemented without breaking that invariant, STOP #9
fires. Algorithm theory (`docs/algorithm.md` non-sync sections) remains
read-only.

## Execution Order

1. **PERF-1 first** — smallest blast radius (serializer + query shape), builds
   the per-stage timing-log infrastructure that PERF-3 / PERF-2 reuse.
2. **PERF-3 next** — largest single absolute saving (~3–6 s), engine internals,
   highest regression risk; do after the timing infra is battle-tested.
3. **PERF-2 last** — smallest absolute saving (~250 ms), cache shape work.

## Step 0 — Baseline Capture (before any optimization commit)

Before PERF-1 optimization, capture before-numbers for **all 3 endpoints**
using the same measurement script that will verify goal-met. Without
baselines, before/after deltas are anecdotal. Baseline output is logged in
PERF-1's PR body as a `## Baseline (local proxy, 2026-05-26)` block and
referenced by PERF-3 / PERF-2.

Baseline capture procedure:
1. `backend/tools/perf_measure.py` created + committed (see below).
2. Run `python tools/perf_measure.py --endpoint projects --runs 3`,
   `--endpoint sessions --runs 3`, `--endpoint discovery --runs 5`.
3. Output JSON: `{ endpoint, runs: [...], p50_ms, p95_ms }` per endpoint.
4. Save under `backend/test-artifacts/perf-baseline-2026-05-26.json`
   (not committed; report-only artifact).

## Measurement Infrastructure (created in PERF-1, reused in PERF-3 / PERF-2)

### Timing instrumentation
- `backend/apps/common/perf_timing.py` — context manager
  `with stage("v_initial"): ...` that logs per-stage ms when
  `settings.PERF_TIMING_ENABLED = True`.
- Cross-app location (`common`) so PERF-3 doesn't reach into another app's
  namespace.
- Logging route: standard `logging` to `perf_timing` logger; opt-in via env
  or setting; no production noise by default.

### Measurement script (committed in PERF-1)
- `backend/tools/perf_measure.py` — Python CLI:
  - `--endpoint projects|sessions|discovery` — selects which endpoint to hit.
  - `--runs N` — repetition count.
  - `--auth-token <token>` — JWT for auth (env fallback).
  - Output: JSON summary `{ endpoint, runs[ms], p50_ms, p95_ms,
    timing_breakdown: {stage: p50_ms, ...} }`.
- Reproducible across sessions, archives well in PR bodies.
- Hits the local Django dev server at `http://127.0.0.1:8001`.

### Per-slice measurement procedure
- Local dev DB (Neon `local-dev-2` branch — per `[[infra_env_1]]`).
- 3 (or 5 for cache-hit) requests via `perf_measure.py`.
- Compute p50 from the measured stage durations.
- Compare to goal predicate; iterate hypotheses if not yet met.

## Per-Slice Pipeline

Each slice runs through the `orchestrate` skill:

```
[plan inline]
  → back-maker (implement hypothesis + measurement script)
  → code-review + security-manager (parallel)
  → fix-loop if needed (max 2 cycles)
  → measure with `/goal` predicate
    ├── met → continue to commit
    └── not met → form next hypothesis → back-maker again (no cycle cap on
         hypothesis iteration, only on review fix-loop)
  → git-commit skill
  → app-test:
       PERF-1 → FEATURE-SCOPED (projects-list smoke + light swipe regression)
       PERF-3 → FULL (swipe path changed, recommendation determinism)
       PERF-2 → FEATURE-SCOPED (discovery hit-path smoke)
  → reporter-inline skill (audit on same branch as work)
  → git-publish skill (PR open base=develop + admin squash + delete branch)
  → develop sync local
```

## PR Plan (Step 8 publish-gate authorization)

This section opens `git-publish` Step 0 publish gate (b) — Active plan with
`## PR Plan` section explicitly authorizes the listed PRs.

| Slice | Feature branch | PR base | Merge strategy |
|---|---|---|---|
| PERF-1 | `feature/algo-perf-projects-list` | `develop` | admin squash + delete branch |
| PERF-3 | `feature/algo-perf-session-create` | `develop` | admin squash + delete branch |
| PERF-2 | `feature/algo-perf-discovery-cache` | `develop` | admin squash + delete branch |

**Excluded from authorization**:
- Any PR with `--base main`.
- Any `develop → main` deploy PR.
- Any `--force` / `--force-with-lease` push.
- Any `--no-verify` commit/push.

## Hard STOP Conditions (sub-agent or session halts, surfaces to user)

Stop and ping user **immediately** on any of:

1. **`app-test` FAIL** (browser test broken, not drift).
2. **`code-review` FAIL after 2 fix-loop cycles**.
3. **`security-manager` FAIL** at any cycle.
4. **Existing test suite regression** — `cd backend && pytest -x` red.
5. **`origin/develop` drift** — someone else pushed mid-work; rebase + re-run
   app-test, do not force-push.
6. **Pre-commit / pre-push hook failure** that back-maker cannot diagnose
   within 1 fix attempt.
7. **Hypothesis exhaustion** — back-maker reports it has tried all reasonable
   approaches (cache, query shape, batch fetch, vectorization, etc.) and
   cannot move the needle further; surface the measured floor + ask the user
   whether to accept the partial gain or rescope.
8. **Schema change required** — if hitting the goal needs a DB schema change
   on `default` or `buildings`, STOP. Schema changes need explicit user
   approval per CLAUDE.md `## Backend Conventions` (especially the read-only
   `buildings` connection).
9. **Algorithm semantics change** — if the goal cannot be met without
   altering swipe-loop determinism, pool ordering, or initial_batch shape,
   STOP. These are algorithm-owner territory per `## Algorithm work` rule.

On any STOP: report the slice's measured floor + the hypotheses tried + ask
user how to proceed. Do not auto-skip to next slice.

## Forbidden Operations (mirror CLAUDE.md HARD RULES)

- `git push origin develop` / `git push origin main` directly.
- `gh pr create --base main` for any slice.
- `gh pr merge` for a `develop → main` deploy PR.
- `--force`, `--force-with-lease`, `--no-verify`, `--amend on pushed`,
  `git rebase -i`, `git reset --hard` on shared branches.
- Modifying `canonical_v2_buildings` schema / migrations (Make-DB-owned).
- Editing files under `docs/algorithm.md` beyond reporter-inline's narrow
  sync permission.
- Direct edits to algorithm core (`engine.py`, `services/embeddings.py`,
  `services/rerank.py`, `services/_caches.py`) WITHOUT first surfacing the
  ownership boundary to the user. PERF-2/PERF-3 may need to touch these —
  surface the touch in the slice plan and confirm before back-maker dispatch.

## End-of-Plan Report (after PERF-2 squash + develop sync)

Report to user:

1. 3 PR links (URL + squash SHA on develop).
2. Per-slice before / after p50 measurements.
3. Goal met / partial / missed per slice.
4. New deferrals (if any) → which `## Next` bucket they landed in.
5. Whether `develop → main` deploy is now ripe (advisory only — user decides).

## Notes

- `/goal` predicate is met when the **measured** p50 satisfies the inequality,
  not when back-maker claims a fix works. Always measure before claiming
  `/goal` reached.
- Per-stage timing log itself MUST NOT impact production latency — it is
  opt-in (env or settings flag), default off in production.
- Codex retest cycle: not mandatory between slices, but the final report
  should reference whether any Codex retest was run. If user wants pre-PR
  Codex measurement, they will say so per slice.
