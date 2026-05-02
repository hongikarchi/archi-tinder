# 4d98793 Improvements (operator action + carryover)

**Source:** `/review` cycle on range `7348593..4d98793` (3 commits — `20df524` docs carryover, `31d5164` validate_imp6 + HF URL fix, `4d98793` STAGE_DECOUPLE_ENABLED env override).

**Static review verdict:** PASS (0 CRITICAL / 0 MAJOR / 0 MINOR). All 3 commits clean. 385 tests pass + 1 skipped. Governance-clean.

**Browser verification (Part B):** MIXED — Brutalist B4 PASS (3rd consecutive cycle, sys_p50 3762 ms < 4000 budget); Korean + BareQuery harness measurement failures (recurring). `stage_decouple_enabled=False` default in this measurement — IMP-6 dormant until operator flips Railway env var.

**Headline empirical finding** (from `31d5164` validate_imp6 run):
- Spec v1.10 predicted IMP-6 ~45-55% Gemini wall drop
- Empirical Stage 1 drop: **10.7%** (median 2389 → 2133 ms)
- Empirical user-facing TTFC drop: **~21% (~800 ms)** because Stage 2 (1705 ms) is OFF user-blocking critical path
- Same pattern as IMP-5 disproof (5.5% vs 50% predicted): spec assumes output-dominance, real Gemini cost is input-dominated at 6077-token system_instruction scale

---

## Tier 1 (operator action, READY) — Production canary flip

`4d98793` ships the mechanism (env var override). The flip itself is operator-controlled.

### Procedure

1. **Pre-flip baseline measurement** (optional, ~5 min):
   - Query `parse_query_timing` SessionEvents for the past hour as a "before" snapshot.
   - Specifically: median `gemini_total_ms` per `query_complexity_class`, plus `clarification_fired` rate.

2. **Flip env var on Railway dashboard**:
   - Railway → service → Variables → add `STAGE_DECOUPLE_ENABLED=true`
   - Railway auto-redeploys (~30-60 s)

3. **Post-flip observation window (1 hour minimum)**:
   - **Smoke test 1 — Stage 1 active**: query `parse_query_timing` for `stage='1'` field. Should appear on every parse_query call (was absent pre-flip). Expected count: ≥1 per session.
   - **Smoke test 2 — Stage 2 firing**: query `stage2_timing` events. Count should be > 0 (was 0 pre-flip). Stage 2 fires ONLY on terminal turns (probe_needed=False), so count ≈ session count × (1 - clarification_rate).
   - **Smoke test 3 — Stage 2 success rate**: `stage2_timing.outcome` distribution. Target: ≥95% `'success'`. If <95%, investigate `'gemini_failure'` / `'hf_failure'` / `'cache_failure'` distribution. HF cold-start can spike to 1500 ms first call; subsequent calls ~370 ms.
   - **Smoke test 4 — TTFC trend**: median `gemini_total_ms` for Stage 1 events should drop ~10-15% vs pre-flip baseline (per validate_imp6's 10.7% empirical). Brutalist sys_p50 in next /review cycle should land ~3300 ms (was 3762 ms in this cycle's pre-flip measurement).

4. **Decision point at 1-hour mark**:
   - All 4 smoke tests PASS → continue running with flag ON. Sprint D complete.
   - Any smoke test FAIL → instant rollback (unset env var or set to 'false'). No code redeploy needed.

5. **Rollback procedure** (if needed):
   - Railway → Variables → delete `STAGE_DECOUPLE_ENABLED` OR set to `false`
   - Railway auto-redeploys
   - Next process cycle reads `False` → byte-identical pre-Sprint-C behavior
   - V_initial cache entries stay in Django LocMemCache for `_V_INITIAL_CACHE_TTL_SECONDS` (1h) but are unreferenced — natural eviction. No data corruption.

### Why this is safe to flip

- **Default-OFF preserved**: env var unset → `False` → byte-identical pre-IMP-6 behavior. Production stays at current latency until operator deliberately flips.
- **Test coverage**: 385 passing tests including end-to-end SessionCreateView integration with flag ON.
- **Empirical pre-validation**: validate_imp6 ran in dev with flag ON; 100% Stage 2 success post-HF-URL-fix; ~800ms TTFC drop confirmed.
- **Instant rollback**: env var change → next process cycle reads new value. No migration to revert, no schema change to back out, no data corruption risk (Stage 1 + Stage 2 are additive paths; legacy single-call path remains intact).
- **Pre-launch traffic level**: per `4d98793` commit body, current Railway gunicorn is single-worker; LocMemCache works fine for V_initial cache. No multi-worker Redis swap needed yet.

### Cost framing (per spec v1.10 + 7348593-improvements.md Tier 1)

- Gemini billing: 2-call architecture costs ~2× per terminal turn vs 1-call. Stage 1 is smaller (~150-220 output tokens) + Stage 2 is smaller (~140-180 output tokens). Net token cost roughly 70-80% of pre-IMP-6 single-call (~290-400 output tokens).
- HF Inference API: free tier covers <30 RPM; if traffic exceeds, $0.06/M tokens (negligible at our scale).
- Net cost change: roughly neutral or marginally negative until ~250+ sessions/day. Acceptable trade for ~21% TTFC improvement.

---

## Tier 2 (research terminal, deferred non-blocking) — Spec v1.11 SPEC-UPDATED for IMP-6 expected savings revision

Per `31d5164` commit body explicit handoff: spec v1.10 §11.1 IMP-6 "expected ~45-55% Gemini wall drop" should be re-grounded with validate_imp6 empirical data:

- Stage 1 alone: empirical 10-25% drop (varies per sample)
- Stage 2 ranges: ~1100-1340 ms Gemini + ~370-1555 ms HF (cold-start dependent)
- Real user-facing TTFC drop: ~800 ms / ~21%
- Cost structure: input-dominated (~6077-token system_instruction dominates Gemini wall regardless of output schema)

**Important**: prediction-revision is NOT blocking the production canary. The 800 ms TTFC drop is real and meaningful for users; spec accuracy is documentation hygiene. Research can pick this up at their cadence.

This is the **second consecutive spec-prediction miss** (IMP-5: 5.5% vs 50% predicted; IMP-6: 10.7% vs 45-55% predicted). Pattern documented; future IMP predictions should explicitly account for input-token-domination at our prompt scale.

---

## Tier 3 (deferred, scope-bounded) — Session-level gradual canary

Currently the env var is binary (set → all-on, unset → all-off). At pre-launch scale (≪250 sessions/day), binary is appropriate. When traffic warrants gradual rollout (1% → 25% → 50% → 100%):

1. Add `canary_cohort` telemetry field to parse_query_timing + stage2_timing
2. Cohort assignment: `int(hashlib.sha256(session_id).hexdigest(), 16) % 100 < canary_pct`
3. Branch parse_query routing on cohort instead of flag

Estimated: ~0.5 d. Defer until traffic justifies the implementation cost.

---

## Tier 4 (carryover, escalating) — Harness chromium pool reuse + multi-turn measurement

This cycle's Korean B4 ALL 3 RUNS hit max-turns (worst Korean cycle observed). BareQuery had 1/3 runs hit max-turns. Documented Tier 4 issue: harness's MAX_TURNS=3 with canned-reply approach doesn't reliably yield cards on these query classes.

**Mitigations** (review-terminal infrastructure work, not main pipeline):
1. Increase MAX_TURNS to 4 — gives one more canned-reply attempt before giving up
2. Persona-specific richer canned replies (currently 2 per persona; add a 3rd that's more specific)
3. Detect "AI bubble appeared" via DOM stability (chat container's last child is role=assistant with question-mark) instead of `style.background` heuristic
4. Chromium pool reuse: share single browser instance across B4 runs to reduce resource pressure

5. Alternative: drop SustainableKorean from gate, treat as observability-only persona (it's the most variable)

**Status:** 8+ cycles consecutive. Worth a Sprint of dedicated harness rework now that IMP-6 is the structural fix in place.

---

## Tier 5 (Investigation 22 Phase 1 — ongoing)

M1 + M4 + M1_cap_forced telemetry continues to flow. With `stage='1'` field shipping in Sprint C, post-Tier-1-canary the IMP-6-enabled vs IMP-6-disabled cohorts will have observable distinguishing markers (legacy `parse_query` calls have no `stage` field; Stage 1 calls have `stage='1'`).

Phase 1 query (carryover; updated for IMP-6 era):

```python
from apps.recommendation.models import SessionEvent
from datetime import datetime, timedelta, timezone
import collections

since = datetime.now(timezone.utc) - timedelta(days=30)
events = SessionEvent.objects.filter(
    event_type='parse_query_timing',
    created_at__gte=since,
).values('payload')

by_class = collections.defaultdict(lambda: {'fired': 0, 'not_fired': 0, 'cap_forced': 0,
                                              'stage1_count': 0, 'legacy_count': 0,
                                              'gemini_ms_stage1': [], 'gemini_ms_legacy': []})
for e in events:
    p = e['payload']
    cls = p.get('query_complexity_class', 'unknown')
    if p.get('clarification_fired') is True:
        by_class[cls]['fired'] += 1
    elif p.get('clarification_fired') is False:
        by_class[cls]['not_fired'] += 1
    if p.get('m1_cap_forced_terminal') is True:
        by_class[cls]['cap_forced'] += 1
    if p.get('stage') == '1':
        by_class[cls]['stage1_count'] += 1
        if p.get('gemini_total_ms'): by_class[cls]['gemini_ms_stage1'].append(p['gemini_total_ms'])
    else:
        by_class[cls]['legacy_count'] += 1
        if p.get('gemini_total_ms'): by_class[cls]['gemini_ms_legacy'].append(p['gemini_total_ms'])

import statistics
for cls, stats in by_class.items():
    total = stats['fired'] + stats['not_fired']
    rate = stats['fired'] / total if total else 0
    stage1_pct = stats['stage1_count'] / total if total else 0
    s1_med = statistics.median(stats['gemini_ms_stage1']) if stats['gemini_ms_stage1'] else None
    legacy_med = statistics.median(stats['gemini_ms_legacy']) if stats['gemini_ms_legacy'] else None
    print(f'{cls}: clarif={stats["fired"]}/{total}={rate:.1%} | stage1={stage1_pct:.1%} | '
          f'gemini_ms (stage1 vs legacy): {s1_med} vs {legacy_med}')
```

Schedule: query weekly post-canary-flip. Tier 5 is observational, not a code task.

---

## What does NOT need fixing in this batch

The static review found 0 issues. All 3 commits are clean:

- **20df524 (carryover)**: docs-only reporter bookkeeping; reviewed PASSED in prior cycle. Governance-clean (only `algorithm.md` touched in research/, narrow exception respected).
- **31d5164**: load-bearing HF URL fix (single-line, unblocks Topic 03 HyDE + IMP-6 Stage 2 from 0% to 100% success); validate_imp6 management command (867 lines, mirrors validate_imp5 pattern, in-process flag override + try/finally restore + cache.clear cleanup); empirical findings honestly captured with data-driven diagnosis.
- **4d98793**: minimal-scope env override (single-line settings change + 4 tests + canary procedure documentation); strict parsing (case-insensitive `'true'` only); session-level cohorting + cohort telemetry deferred per scope.

**This file is purely about Sprint D Commit 5 operational follow-up (Tier 1 canary flip) + carryover items (Tier 2-5). Not about the commits being reviewed.**
