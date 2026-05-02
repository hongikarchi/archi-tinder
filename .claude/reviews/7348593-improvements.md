# 7348593 Improvements (for main + research terminals)

**Source:** `/review` cycle on range `1b2bd21..7348593` (2 commits — Sprint C IMP-6 ship: 1f55ec6 plumbing + 7348593 structural fix).

**Static review verdict:** PASS (0 CRITICAL / 0 MAJOR / 0 MINOR). Both commits surgical, Investigation 23 §8 directives followed, governance-clean. 381 tests pass + 1 skipped. Migration 0014 applied.

**Browser verification (Part B):** Brutalist sys_p50 4111 ms over 4000 budget by 2.8% (closest to passing in 10 cycles, M1 mitigation continues to hold 0/3 clarification rate); Korean + BareQuery PASS via sys-metric artifacts on multi-turn flows. **`stage_decouple_enabled=False` default in this commit means Part B measured pre-IMP-6 baseline** — the structural fix is dormant until the flag is flipped in staging.

---

## Tier 1 (Sprint D, Investigation 23 §8 Commit 3) — IMP-6 canary 1% staging validation, URGENT

The implementation is mechanically clean (verified by 381 tests + reviewer PASS). The empirical question is whether IMP-6's predicted ~45-55% Gemini wall drop materializes when the flag flips. Same posture as IMP-5 (which was disproved by validate_imp5 staging: predicted 50%, got 5.5%).

### Validation procedure

Per Sprint D Commit 3 plan in 7348593 commit body:

1. **Deploy** with flag OFF (this commit, no behavior change). Confirm production is healthy.
2. **In dev environment**: flip `stage_decouple_enabled=True` (single-line settings change or env var override).
3. **Run 10+ chat → SessionCreate flows** through the UI:
   - Brutalist class: "concrete brutalist museum" + variations
   - Korean class: "한국 친환경 주거 건축" + variations
   - BareQuery class: "modern" + variations
4. **Query SessionEvents**:
   ```python
   from apps.recommendation.models import SessionEvent
   from datetime import datetime, timedelta, timezone

   since = datetime.now(timezone.utc) - timedelta(hours=1)

   # Stage 1 timing (parse_query_timing with stage='1')
   stage1 = SessionEvent.objects.filter(
       event_type='parse_query_timing',
       created_at__gte=since,
       payload__stage='1',
   ).values('payload')

   # Stage 2 timing (NEW event type)
   stage2 = SessionEvent.objects.filter(
       event_type='stage2_timing',
       created_at__gte=since,
   ).values('payload')

   # Aggregates
   stage1_gemini_ms = [e['payload']['gemini_total_ms'] for e in stage1]
   stage2_outcomes = [e['payload']['outcome'] for e in stage2]
   stage2_total_ms = [e['payload']['stage2_total_ms'] for e in stage2]

   import statistics
   print(f'Stage 1 gemini_total_ms median: {statistics.median(stage1_gemini_ms)}')
   print(f'Stage 2 success rate: {sum(1 for o in stage2_outcomes if o == "success") / len(stage2_outcomes):.1%}')
   print(f'Stage 2 total_ms median: {statistics.median(stage2_total_ms)}')
   ```
5. **Expected pattern (per spec v1.10)**:
   - **Stage 1 `gemini_total_ms` median: ~1500 ms** (vs current ~2900 ms = 48% drop)
   - **Stage 2 success rate ≥97%** (Gemini + HF + cache write all succeed)
   - **Stage 2 `stage2_total_ms` median: ~1200-2000 ms** (Gemini ~1000-1500 + HF ~200-500)
   - **Brutalist single-turn TTFC ~2400-2700 ms** (well under 4000 budget with ~30% margin)
6. **If empirical pattern matches**: green-light Sprint D Commit 4 (canary 25% → 50% → 100% rollout).
7. **If pattern diverges** (e.g., Stage 1 drop is <30% or Stage 2 success rate <90%): document discrepancy in 7348593-improvements-followup.md, decide whether to ship at lower expected savings or revisit.

### Cost framing (per spec v1.10)

- 2-call architecture adds ~$0.14/day storage at <100 sessions/day; cost-neutral or marginally negative until ~250+ sessions/day.
- Acceptable as the structural latency fix; cost question is decoupled from latency question (unlike IMP-5 where cost was the only remaining justification post-disproof).

### Risk: Stage 2 timing exceeds 1.5s in production

If Stage 2 takes longer than the user takes to read Stage 1 + click "Go to AI Search", SessionCreate's V_initial cache lookup misses → Regime 2/3 fallback (filter-only farthest-point pool, no V_initial channel). Per Investigation 17 §3a + Investigation 23 §4: UX still transparent (RRF rank-level fusion is order-independent). Worst case: cards 1-3 are slightly less personalized but still relevant.

Investigation 23 §4 mitigation: Stage 2 spawns IMMEDIATELY after Stage 1's terminal turn (not delayed); Stage 2 typical latency ≤1.5s; user typically reads paraphrase + clicks ≥2s — race usually resolves favorably. Production telemetry will confirm.

---

## Tier 2 (carryover, scheduled) — IMP-6 Commit 3 (Regime 2/3 swipe-loop wire-up)

`rerank_pool_with_v_initial` ships in this batch with cosine ranking implemented but no production callers (TODO marker grep-able at `engine.py:1473`). Commit 3 work:

1. **SwipeNextView (or equivalent)**: after each swipe response, attempt `get_cached_v_initial(user.id, session.raw_query)`.
2. **On cache hit + session in early rounds (<5 swipes done)**: invoke `engine.rerank_pool_with_v_initial(pool_ids, exposed_ids, initial_batch_ids, v_initial)` and update `session.pool_ids`.
3. **Telemetry**: emit `stage2_timing` with `pool_rerank_ms` populated (replaces None placeholder), `v_initial_ready_at_first_card`, `cards_exposed_when_ready`.

Estimated: ~1 day dev + 0.5 day testing. Lands after Tier 1 canary validation confirms IMP-6 latency story. Out of scope for this batch.

---

## Tier 3 (research task, ongoing) — M4 vocabulary reconciliation

Per `834d36e` reviewer MINOR 6: three vocabulary mismatches:
- (a) M4 implementation: `'brutalist' / 'narrow' / 'barequery' / 'unknown'`
- (b) Investigation 20 row 22 SQL: `'narrow'` (should query `'brutalist'`)
- (c) Investigation 22 §6: `'narrow' / 'medium' / 'bare'`

Carryover from prior cycle. Not blocking — analytics queries can be amended without code changes. Routed to research vocab unification.

---

## Tier 4 (carryover, escalating) — Harness chromium pool reuse + reliable deadline enforcement

This cycle's B5 hung **again**:
- SustainableKorean B5: `no_card_after_clarification` (recurring multi-turn issue)
- BareQuery B5: chromium resource exhaustion at 2:01 elapsed; killed manually

This is the **6th consecutive cycle** with B5 incomplete. Mitigations:

1. **Chromium pool reuse** — share a single `browser` across all B4 + B5 runs with `browser.newContext()` per run. Reduces resource pressure 10× (1 process vs ~10).
2. **AbortSignal-based timeouts** — replace `Promise.race + setTimeout` (which starves under event-loop pressure) with `AbortController + signal.timeout()`. Native browser support; deadline always fires.
3. **Restart-browser-per-persona** — explicitly close/launch chromium between B5 personas. Avoids accumulated state.
4. **Headless Chrome flags** — `--disable-dev-shm-usage`, `--no-sandbox` may stabilize on macOS dev.

This is review-terminal infrastructure work, not main pipeline. Could be tackled by adding a script under `web-testing/` that the harness can invoke.

---

## Tier 5 (Investigation 22 Phase 1 — telemetry accumulation)

M1 + M4 telemetry continues to flow on production + dev traffic. With `stage='1'` field newly shipping in this batch, post-Tier-1-canary the IMP-6 enabled vs disabled cohorts will have observable distinguishing markers.

Phase 1 query (carryover):

```python
# Stratify clarification rate by query_complexity_class
from apps.recommendation.models import SessionEvent
from datetime import datetime, timedelta, timezone
import collections

since = datetime.now(timezone.utc) - timedelta(days=30)
events = SessionEvent.objects.filter(
    event_type='parse_query_timing',
    created_at__gte=since,
).values('payload')

by_class = collections.defaultdict(lambda: {'fired': 0, 'not_fired': 0, 'cap_forced': 0, 'stage1_count': 0})
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

for cls, stats in by_class.items():
    total = stats['fired'] + stats['not_fired']
    rate = stats['fired'] / total if total else 0
    s1_rate = stats['stage1_count'] / total if total else 0
    print(f'{cls}: clarif={stats["fired"]}/{total}={rate:.1%} | cap_forced={stats["cap_forced"]} | stage1={s1_rate:.1%}')
```

Expected post-canary:
- `brutalist`: <20% clarification rate (M1 working — confirmed by this cycle's Brutalist 0/3 rate)
- `narrow` / `barequery`: 20-50% / >50% (legitimate per Investigation 06)
- `m1_cap_forced_terminal`: near zero (cap is defensive)
- `stage='1'` rate: 100% (when Tier 1 canary flag flips on)

Schedule: query weekly. Tier 5 is observational, not a code task.

---

## What does NOT need fixing in this batch

The static review found 0 issues. Both commits are exemplary:

- **1f55ec6 Commit 1 (2d) plumbing**: scaffolding-only with 0% latency change at flag OFF. V_initial cache key SHA-256 PII-safe. Pool re-rank scope correct (`pool_ids \ (exposed ∪ initial_batch)` with locked prefix preserved in input order, not set order). 26 new tests covering cache key format, read/write, scope, branching gate.
- **7348593 Commit 2 (2c) structural fix**: Stage 1 schema enforcement (Approach A — structural, not soft prompt). Stage 2 outcome state machine cleanly classifies failures. Threading pattern matches IMP-8 prefetch. `_rank_with_v_initial` cosine ranking uses IMP-7 in-memory cache (no new DB fetch). 27 net new tests including 5 real `SessionCreateView.post()` integration tests. Migration 0014 reverse-safe.
- **Governance-clean**: zero `research/` writes, zero design pipeline writes, IMP-4 / IMP-5 / M4 / M1 logic preserved verbatim through Stage 1 split.
- **Documentation-clean**: all reviewer MINORs from back-maker pipeline disclosed in commit bodies; TODO(IMP-6 Commit 3) markers grep-able; deferred fields documented with cross-request timing requirement explanation.

**This file is purely about Sprint D operational follow-up (Tier 1 canary validation) + carryover items (Tier 3-5). Not about the commits being reviewed.**
