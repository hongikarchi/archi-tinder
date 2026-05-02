# 1b2bd21 Improvements (for main + research terminals)

**Source:** `/review` cycle on range `1491c5d..1b2bd21` (6 commits: c133787 IMP-5, 6604296 validate_imp5, db87827 design pipeline UI, 80e37f3 v1.9 boundary, 834d36e M4 telemetry, 1b2bd21 M1 cap).

**Static review verdict:** PASS (0 CRITICAL / 0 MAJOR / 0 MINOR). All 6 commits surgical, well-grounded, governance-clean. 328 tests pass + 1 skipped. **Headline empirical finding**: validate_imp5 disproved spec v1.5 IMP-5 predicted 50% latency drop (actual 5.5%). M1 mitigation showed first cycle of empirical evidence (Brutalist clarification rate 3/3 → 0/3).

**Browser verification (Part B):** Brutalist B4 PASS for the **first time in 9 cycles** (sys p50 3964 ms < 4000 budget); Korean + BareQuery FAIL on harness measurement artifacts (not code regressions). B5 incomplete (harness chromium resource exhaustion).

---

## Tier 1 (research-terminal, URGENT) — Spec §11.1 IMP-5 latency hypothesis revision

### What broke (predictively)

Spec v1.5 §11.1 IMP-5 predicted: "TTFC drops 50%+ per spec" / "1400-1800 ms target".

`validate_imp5` empirical data:
- **Phase A (uncached, flag OFF)**: 10/10 succeeded, median gemini_total_ms = 2904 ms
- **Phase B (cached, flag ON, 100% cache_hit, 5919 tokens cached)**: 10/10 succeeded, median gemini_total_ms = 2743 ms
- **Delta: 161 ms / 5.5% drop**

Predicted 50% drop. Got 5.5% drop. The implementation is mechanically correct (100% cache_hit, full 5919 cached tokens). The latency hypothesis underlying the prediction is empirically wrong.

### Why the prediction was wrong (per validate_imp5 commit body)

1. **Gemini 2.5-flash baseline drifted ~3200 → ~2900 ms** between the time the spec was written and now. Output-generation latency now dominates the wall-time floor.
2. **Cached input tokens reduce billing cost but don't measurably reduce wall time at this prompt scale** — TTFT savings are minimal because the bottleneck is output generation, not input ingestion.
3. The 9% delta seen in the prior `--mode=cached` ad-hoc run was an artifact of comparing against a stale ~3200 ms baseline; same-session A/B shows true 5.5%.

### Spec changes needed

`research/spec/requirements.md` v1.9 → v2.0+ candidate:

- **§11.1 IMP-5 expected savings** — revise from "~50% drop / 1400-1800 ms" to empirically-grounded "~5-10% drop / 2700-2900 ms" (or remove the latency claim entirely; keep only cost savings).
- **§4 TTFC re-tightening pathway** — "via IMP-5" path is invalidated. IMP-6 (2-stage decouple) becomes the primary structural fix.
- **§11.1 IMP-5 status annotation** — note the empirical disproof + validate_imp5 commit reference.

### Production decision implication

- **Do NOT flip IMP-5 production flag for latency reasons** — savings don't justify rollout risk.
- **Cost-flip decision is separate**: token billing reduction (5919 cached tokens × Gemini billing rates) is real and may justify rollout for cost reasons alone. Out of scope for review terminal — research/ops decision.

---

## Tier 2 (carryover, escalating) — IMP-6 (2-stage decouple) structural fix candidate

With IMP-5 alone unable to break the ~2900 ms Gemini RTT floor, IMP-6 becomes the next implementation candidate per spec v1.5 §11.1 stacking pathway:

- **Stage 1 (sync)**: parse_query returns `{filters, filter_priority, raw_query, probe_*}` immediately → first card visible
- **Stage 2 (async)**: `visual_description` computed in background → V_initial → unseen pool re-rank

Expected Stage 1 latency: ~1500-2000 ms (filters-only response, smaller output token count). Expected Stage 2 latency: invisible to user (post-render).

This is the structural fix that can break the 4000 ms TTFC budget. IMP-5 stays in the codebase as cost-saving infrastructure; IMP-6 becomes the latency story.

Investigation 17 has the full design + safety analysis (Stage 2 cache scope, race handling, V_initial late-bind allowance per Topic 03 / 01).

---

## Tier 3 (research task) — M4 vocabulary reconciliation

Per `834d36e` reviewer MINOR 6: three vocabulary mismatches:
- (a) M4 implementation: `'brutalist' / 'narrow' / 'barequery' / 'unknown'`
- (b) Investigation 20 row 22 SQL: `'narrow'` (should query `'brutalist'` to capture high-specificity cohort — currently the analytics row is wrong)
- (c) Investigation 22 §6: `'narrow' / 'medium' / 'bare'`

Implementation shipped per task spec contract; reconciliation routed to research vocab unification (R-vocab-reconciliation candidate). Not blocking — analytics queries can be amended without code changes.

---

## Tier 4 (carryover, escalating) — Harness reliability

This cycle's B5 hung again on Brutalist swipe session — same chromium resource exhaustion pattern as prior cycles after 9 prior browser launches in B4.

Cumulative impact across cycles: B5 has not completed in any cycle since `06c6c5a`. The swipe-loop p50/p95 measurements (the actual gate Investigation 18 cares about) have never been captured under live load. Workarounds:

1. **Chromium pool reuse** — instead of `chromium.launch()` per run, share a single browser instance across all B4 + B5 runs with `browser.newContext()` per run. Reduces resource pressure 10× (1 browser process vs ~10).
2. **Shorter B5 timeout** — current 120s deadline is too generous for a hung-state. 60s is enough to either succeed (~40s for 25 swipes at ~1.5s each) or fast-fail.
3. **Restart-browser-per-persona** — between B5 personas, explicitly close and re-launch chromium. Avoids accumulated state.
4. **Headless Chrome flags** — `--disable-dev-shm-usage`, `--no-sandbox`, `--single-process` may stabilize.

This is review-terminal infrastructure work, not main-pipeline. Could be tackled by adding a script under `web-testing/` that the harness can invoke.

---

## Tier 5 (Investigation 22 Phase 1 follow-up) — empirical M1 / clarification-rate validation

This cycle's data point (Brutalist clarification 3/3 → 0/3) is a single observation. Investigation 22 Phase 1 needs n≥30 trials to confirm M1 mitigation isn't single-cycle variance.

Now that M4 telemetry (`clarification_fired`, `query_complexity_class`, `m1_cap_forced_terminal`) is shipped, this query is trivial:

```python
from apps.recommendation.models import SessionEvent
from datetime import datetime, timedelta, timezone

# Last 30 days of parse_query_timing events
since = datetime.now(timezone.utc) - timedelta(days=30)
events = SessionEvent.objects.filter(
    event_type='parse_query_timing',
    created_at__gte=since,
).values('payload')

# Stratify by query_complexity_class + clarification_fired
import collections
by_class = collections.defaultdict(lambda: {'fired': 0, 'not_fired': 0, 'cap_forced': 0})
for e in events:
    p = e['payload']
    cls = p.get('query_complexity_class', 'unknown')
    if p.get('clarification_fired') is True:
        by_class[cls]['fired'] += 1
    elif p.get('clarification_fired') is False:
        by_class[cls]['not_fired'] += 1
    if p.get('m1_cap_forced_terminal') is True:
        by_class[cls]['cap_forced'] += 1

for cls, stats in by_class.items():
    total = stats['fired'] + stats['not_fired']
    rate = stats['fired'] / total if total else 0
    print(f'{cls}: {stats["fired"]}/{total} = {rate:.1%} clarification rate; cap forced {stats["cap_forced"]}x')
```

Expected pattern:
- `brutalist` class: <20% clarification rate (M1 working)
- `narrow` class: 20-50% clarification rate (1-turn legitimate)
- `barequery` class: >50% clarification rate (BareQuery 2-turn legitimate)
- `m1_cap_forced_terminal` count: should be near zero in steady state (cap is defensive, not regular)

Schedule: query weekly. Tier 5 is observational, not a code task.

---

## What does NOT need fixing in this batch

The static review found 0 issues. All 6 commits are clean:

- **c133787 IMP-5**: already reviewed clean prior cycle. Implementation exemplary.
- **6604296 validate_imp5**: 883-line management command implementing Tier 2 staging validation directive. Empirical result captured; spec prediction disproved (good science).
- **db87827 design pipeline**: governance-clean (designer pipeline territory; design-ui-maker spawn; ESLint clean; Vite build passes). Pragmatic Report.md bundling exception with documented precedent.
- **80e37f3 v1.9 boundary fix**: workflow doc + harness runner consistent; spec v1.9 numeric budgets unchanged from v1.4.
- **834d36e M4 telemetry**: probe_needed-sourced (authoritative) clarification_fired field + 4-tier query_complexity_class. 14 tests covering classification matrix.
- **1b2bd21 M1 refined cap**: three-layer enforcement (prompt + Python + telemetry); preserves Investigation 06 BareQuery 2-turn design intent (threshold ≥3, not ≥2). 13 tests covering cap activation matrix.

**This file is purely about systemic gaps (spec prediction failure on IMP-5, harness reliability) — not about the commits being reviewed.**
