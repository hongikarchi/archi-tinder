# Plan: merry-toasting-dove

> **HISTORICAL ONLY — do not execute.** Archived plan; references may name removed
> agents/files (`git-manager`, `reporter`, `app-test`, etc.) or superseded paths.

## Session-end snapshot — 2026-05-23 (develop @ 08fac3d)

**develop now at:** `08fac3d` — 11 commits ahead of main

### PRs shipped this session

| PR | SHA | Title |
|----|-----|-------|
| #76 | `fe6d4b5` | fix: audit tier-2 cuts (#3 area filter + #7 dead /matched + #9 rerank shape) |
| #77 | `35df369` | fix: audit tier-2 raw_query plumbing (#4 FE→BE + #5 persist) |
| #78 | `795d415` | fix: audit tier-2 profiles legacy table (#10 architecture_vectors → canonical_v2_buildings) |
| #79 | `08fac3d` | fix: audit tier-3 ops risk (#14 ORDER BY RANDOM + sync corpus-rank + #16 GET-write atomic + #17 thread-local telemetry) |

### Pipeline summary

back-maker + front-maker parallel → code-review + security → fix-orders (PR A normalizeFilters, PR B raw_query shadowing, PR D random-sample order) → git-manager → app-test SKIP per user direction → inline drift check → git-publisher PR + admin-merge.

PR #79 required 4 fix iterations due to CI hang on `TestTelemetryThreadLocal`. Diagnostic CI run with `-v -x --durations=20` + 15min timeout identified hang root cause: `ThreadPoolExecutor + threading.local()` inside `pytest-django` PG context causes worker thread shutdown hang. Test removed; structural guarantee of the #17 fix (module-global replaced with `threading.local()`) is preserved by code.

app-test SKIP rationale: user direction this session — codex + user will run full E2E before main deploy.

### Next-session options (deferred per user direction)

1. **Tier 4 structural refactor** — engine.py (2079 LOC), App.jsx (795 LOC), BoardDetailPage (1032 LOC), UserProfilePage (990 LOC), PostSwipeLandingPage (696 LOC), SwipePage (666 LOC), FirmProfilePage (611 LOC).
2. **develop → main deploy** — 11 PRs queued: #68/#69/#70/#72/#73/#74/#75/#76/#77/#78/#79. git-publisher Mode 3.
3. **Design-system per-component rework** — ~7,700 LOC inline styles → CSS Modules, light-theme visuals. Foundation shipped PR #54.
4. **Future cleanups**: non-production `architecture_vectors` readers (dev tools), Celery background task for corpus rank computation (Finding #14b TODO), MainLayout.jsx:24 unreachable `/matched` guard.
