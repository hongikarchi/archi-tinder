# Improvement Recommendations from `/review` on 57b3244 (post-push)

> **Status**: 57b3244 was pushed under user override despite Part B FAIL by 166 ms (4.15% over the 4000 ms ceiling). The branch is functionally healthy — the FAIL was a borderline budget overshoot caused by Sprint 1 chat phase prompt size + Gemini API base latency, not a code regression. The user accepted the 4% margin and asked the review terminal to write up improvements for main to consider in upcoming sprints.
>
> **Audit trail**: see `.claude/reviews/57b3244.md` Part B sections for the full diagnostic data including SessionEvent payloads. Original measurement: parse_query 4166 ms (frontend) / 3246 ms (Gemini API alone, from `parse_query_timing` SessionEvent) at HEAD `57b3244` after billing restoration.
>
> **Empirical floor for `parse_query` on this branch:** ~3246 ms Gemini + ~920 ms Django/network = ~4166 ms total. This is the realistic best-case until prompt size or API call shape changes.

---

## Where the gap lives

The Sprint 1 §3 chat phase rewrite (commit `e290287`, Investigation 06's full bilingual prompt) brought the input-token count from ~500 (old `_PARSE_QUERY_PROMPT`) to **5924** (new `_CHAT_PHASE_SYSTEM_PROMPT`). Spec v1.3 §11.1 IMP-4's "1000-1500 ms p50" prediction modeled only the thinking-token removal (3-5s saved) and didn't account for the simultaneous ~10× input-size growth pushing input-processing time up by ~2-2.5s. Net: IMP-4 fix worked exactly as designed (`thinking_tokens: None` confirmed empirically), but the budget margin got eaten by prompt size.

This is not a "fix didn't fix" failure — it is two design decisions (faster-flash + larger-prompt) made in parallel that net out to a borderline.

## Improvements ranked by impact / effort

### Tier 1 — Fastest wins (one focused change each)

**1.1. Loosen spec §4 time-to-first-card budget to <5000 ms**
- **Effort**: 1 line spec edit + reporter algorithm.md sync.
- **Reason**: 4166 ms is the empirical floor for the current chat prompt design (Investigation 06's 9 bilingual few-shot examples). The <4000 ms ceiling was set before Sprint 1's prompt size was final. Either ratify the new floor or commit to optimizing the prompt.
- **Trade-off**: easier path. Spec v1.3 §4 hard ceiling becomes <5000 ms (with target 3-4s preserved as aspiration); Bare Query stays at <5500-6000 ms. Future runs pass the gate cleanly with ~800 ms headroom.
- **Risk**: spec drift toward "whatever the system happens to do" — but in this case the prompt design is itself a spec decision (Investigation 06 was binding), so the budget should follow the prompt size, not vice versa.

**1.2. Multi-run aggregation in `/review` Part B Step B4**
- **Effort**: Step B4 modification — run the persona's parse-query 3× and use min() (or p50) for the gate.
- **Reason**: 4166 ms is a single-shot measurement. Gemini API has natural variance. p50 across 3 runs would likely sit at 3700-4000 ms, comfortably under ceiling.
- **Trade-off**: 3× longer Part B duration. But Part B already takes ~5 minutes; adding two more parse-query calls is ~6 extra seconds.
- **Risk**: 3× the Gemini API cost during reviews. At ~$0.0001 per parse-query call, this is negligible.
- **Implementation note**: spec rule "no retries on flaky steps" is about gesture flakiness (button click misses, image load timeouts) — applying it to LLM-API latency was a category error. Multi-run aggregation for non-deterministic external services is industry standard.

**1.3. `/review` Step B0 → SessionEvent.failure pre-check**
- **Effort**: One bash query before browser launch.
- **Reason**: prior 4 Part B FAILs (88f0532 / 5d85b90 / f607e73 / 57b3244-first-run) were all Gemini 403; A5 logging would have surfaced this in <1 second if Step B1 had `tail SessionEvent.failure` integrated.
- **Snippet to add at Step B1 (after migration backstop B1bb)**:
  ```python
  # New B1cc: Recent Gemini failure check
  recent_failures = SessionEvent.objects.filter(
      event_type='failure', created_at__gte=now-10min
  ).count()
  if recent_failures > 0:
      latest = SessionEvent.objects.filter(event_type='failure').latest('created_at')
      if 'PERMISSION_DENIED' in str(latest.payload.get('error_message', '')):
          FAIL "Gemini API permission denied — check billing/key/quota"
  ```
- **Trade-off**: more checks in preflight. Saves ~minutes of misdiagnosis when API is broken.

### Tier 2 — Spec-level decisions (Sprint of work)

**2.1. Optimize chat phase prompt size**
- **Effort**: 1 Sprint, design + verification.
- **Reason**: 5924 input tokens is the dominant latency driver. Reducing to 3000 tokens would drop Gemini latency to ~2000 ms, leaving 5000+ ms headroom under <4000 ms.
- **Approach options**:
  - **(a) Trim few-shot examples**: Investigation 06 chose 9 examples (3 skip / 3 1-turn / 3 2-turn × KO/EN/mix). Could test 5 (1 of each pattern × bilingual coverage). Risk: probe quality regression.
  - **(b) English-only initial pass + Korean fallback re-prompt**: detect language, run smaller English prompt first, only switch to bilingual on Korean detection. Risk: 2 LLM calls on Korean queries (worse for them).
  - **(c) Move language-handling rules into structured schema**: `response_schema` with strict JSON typing rather than verbose prose. Smaller prompt + same constraints.
  - **(d) Cache the system prompt server-side**: send only deltas. Limited Gemini support but worth checking.
- **Trade-off**: ships only after Sprint 1 chat phase has had production data for 1-2 weeks; premature optimization risks regressing the bilingual probe quality that v1.3 §3 explicitly required.

**2.2. Tier-aware Part B gates**
- **Effort**: Step B4-B5 restructure.
- **Reason**: time-to-first-card is mostly about parse-query (a service call); per-swipe latency is about the swipe hot path (the algorithmic loop where IMP-1's NumPy vectorization ships value). They have different sensitivities and budgets. Conflating them in a single "browser test PASS/FAIL" loses signal.
- **Proposal**:
  - **Hard FAIL gates**: per-swipe p95 < 700 ms (the actual user-felt loop), session resume works, no console errors, no unexpected 4xx/5xx, no duplicate cards, no cross-session contamination.
  - **Warn-not-FAIL gates**: time-to-first-card (LLM-bound, externally variable), persona-report timeout (Gemini-bound).
- **Trade-off**: makes /review more permissive in one specific way (LLM latency drift no longer blocks push). Buyer's remorse risk if LLM latency degrades pathologically (>10s) — but that's reportable as a quality issue, not a push blocker.

### Tier 3 — Process / workflow

**3.1. Spec prediction discipline**
- v1.3 IMP-4's "1000-1500 ms p50" prediction was 2× off because it didn't compose with the simultaneous Sprint 1 prompt growth. Future spec predictions for latency should:
  - State explicitly which Sprint is being compared against (here: pre-Sprint 1 prompt vs post-Sprint 1 prompt).
  - Net the changes from concurrent in-flight Sprints, not just the direct fix.
  - Have an "instrumentation companion" (which IMP-4 already did via `parse_query_timing` event) so the prediction is empirically checkable on first deploy.
- This branch already does (3) via A5 logging — that pattern is worth preserving as a meta-rule for any future "performance fix" spec directive.

**3.2. `/review` Part B retry-policy clarification**
- The current rule "no retries on flaky steps" is about gesture flakiness. It should be amended to:
  - "No retry on **deterministic** failures" (gesture, contract, drift).
  - "Multi-run aggregation allowed on **stochastic** failures" (LLM latency, external API timing).
- Practically: latency gates should aggregate p50/p95 across N runs; correctness gates fail-fast.

---

## Recommended next-Sprint pickup order

1. **Tier 1.1 + 1.3** (this Sprint, ~30 min total): loosen spec §4 budget to match empirical reality + add `/review` Step B failure-event pre-check.
2. **Tier 1.2** (this Sprint, ~30 min): multi-run aggregation for Step B4 latency gate.
3. **Tier 3.2** (this Sprint, in same `/review` workflow edit pass): clarify retry policy distinction.
4. **Tier 2.1** (next Sprint or post-data): chat prompt optimization, only if real production data shows Investigation 06's design isn't pulling weight on probe quality.
5. **Tier 2.2** (next Sprint): tier-aware Part B gates — bigger refactor, do after 1.x lands.

Tier 1 is ~1.5 hours of total work and would have made this very review a clean PASS (modulo the actual Gemini call working).

## What this branch already shipped that helps

- **A5 logging (`2c7be51`)** — the `parse_query_timing` SessionEvent payload was the load-bearing diagnostic that turned "another mysterious latency wall" into "specifically: 5924 input tokens × Gemini-flash baseline = 3246 ms; Django + network adds ~920 ms; total 4166 ms". Without it, this would have been the 5th consecutive misdiagnosed FAIL.
- **A4 pool exhaustion guard (`f17cb5e`)** — orthogonal to the latency issue, but ships a real production-correctness improvement.
- **IMP-4 (`e290287`)** — verified working (`thinking_tokens: None`); just over-predicted on net effect.
- **IMP-1 (`a9305e4`)** — the swipe-loop NumPy vectorization is in production; once tier-aware gating (Tier 2.2 above) lands, its benefit will be observable in `swipe.timing_breakdown.select_ms` deltas.

## File pointers for orchestrator's pickup

- This file: `.claude/reviews/57b3244-improvements.md` (improvements catalog)
- Diagnostic data: `.claude/reviews/57b3244.md` (Part B "Re-run after Gemini billing restoration" + earlier sections)
- Postmortem of misdiagnosis chain: `.claude/reviews/57b3244.md` "Historical record" section + prior `f607e73.md` / `5d85b90.md` / `88f0532.md`
- Current spec budgets: `research/spec/requirements.md` v1.3 §4 + §11.1 IMP-4
- A5 SessionEvent table: live, queryable via `python3 manage.py shell -c 'from apps.recommendation.models import SessionEvent; ...'`
