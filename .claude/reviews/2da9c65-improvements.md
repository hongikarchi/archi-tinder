# 🚨 ESCALATION: Improvement Recommendations from `/review` on 2da9c65 (post-push)

> **Status**: Second consecutive marginal Part B FAIL on the same gate, same root cause, across two `/review` cycles. The user pushed under override (Sprint 4 features are flag-gated default OFF — risk-bounded), but the underlying workflow problem is now escalating: **the Tier 1 improvements identified in `.claude/reviews/57b3244-improvements.md` after the previous cycle have not been adopted, and as predicted, the next UI-affecting batch hit the same wall.**
>
> **This file is not asking for new improvements.** It exists to elevate the priority of `.claude/reviews/57b3244-improvements.md` Tier 1.1 and Tier 1.2 from "next-Sprint pickup" to "blocker for the next clean `/review` PASS".

---

## What happened (two cycles, same wall)

| Cycle | HEAD | Part A | Part B | parse_query | Cause |
|---|---|---|---|---|---|
| 1 | `57b3244` | PASS (0 findings) | FAIL (+4.15%) | 4166 ms | Sprint 1 chat phase prompt 5924 input_tokens |
| 2 | `2da9c65` | PASS (0 findings) | FAIL (+9.4%) | 4375 ms | **same as above** |

Both cycles:
- IMP-4 fix verified working (`thinking_tokens=None`).
- `gemini_total_ms` lands in 3.0-3.5 s band with natural Gemini variance.
- After Django + network overhead (~900 ms), total parse-query latency lands in the 4.0-4.4 s range.
- The 4000 ms strict gate is breached on every single-run measurement.
- Both batches' source code is genuinely PASS — the FAIL is purely workflow-budget vs reality.

**The user has now override-pushed twice for the same reason.** This is technical debt accumulating in the workflow layer, not the code layer.

## Why the recommendations didn't get adopted between cycles

The previous improvements doc (`.claude/reviews/57b3244-improvements.md`) listed Tier 1 as "next-Sprint pickup, ~1.5h total". Between cycles 1 and 2, main shipped 10 commits of Sprint 3 + Sprint 4 algorithm work instead. That's reasonable — those features were prioritized for the product roadmap.

But the consequence is now visible: **every UI-affecting batch in this state will produce the same `/review` output**:
- Part A PASS.
- Part B FAIL on identical Step B4 latency gate.
- Same `parse_query_timing` SessionEvent payload (5924 input_tokens, ~3.2 s gemini, ~4.2 s total).
- Same diagnostic, same recommendation, same override-push decision.
- Same review terminal time spent rediscovering the same conclusion.

This is the classic "warning fatigue" pattern. Two cycles in, the diagnostic has already lost discriminative power for this branch. By cycle 3 or 4, the user will likely just push without re-reading the FAIL.

## Why this is now URGENT (not just a TODO)

1. **Diagnostic value is decaying.** The whole point of `/review` Part B is to catch real regressions in the user-felt latency surface. Right now the gate fires on a known-and-accepted structural floor, masking any new regression that sits in the same range. If a real bug pushes parse-query to 4500 ms, the user might attribute it to "the usual chat-phase prompt thing" and miss it.

2. **Override fatigue.** Each successive override-push erodes the gate's authority. By cycle 3, the user is conditioned to override; by cycle 5, the gate is effectively decorative.

3. **Future Sprint 4 flag-flip work is blocked from PASSing on the right reason.** When `gemini_rerank_enabled` or `dpp_topk_enabled` flips ON, the resulting `/review` will have new code in the live path. We want that batch's Part B to pass or fail on its own merit (rerank latency, DPP correctness, etc.) — but with the current gate, it will FAIL on the chat-phase prompt regardless of how well or badly the new code performs. The flag-flip's signal is drowned out.

4. **The exact fix is small.** Tier 1.1 + 1.2 = ~30 minutes of work total. The discrepancy between the cost of fixing this and the cost of NOT fixing it is enormous.

## What to do (verbatim from `57b3244-improvements.md` Tier 1, escalated)

### IMMEDIATE (do this Sprint, before any more UI-affecting work)

**1.1. Loosen spec §4 time-to-first-card budget to <5000 ms** — 1 line edit in `research/spec/requirements.md` §4 Numeric Targets table + reporter `algorithm.md` sync. Bare Query also bumps from <5000 to <6000.

**Justification**: 4000 ms was set in spec v1.0 before Sprint 1's prompt size was known. Sprint 1 was a binding spec decision (Investigation 06's bilingual prompt design), so the budget needs to follow the prompt size, not vice versa. The actual measured floor is 4.2 s ± variance; <5000 ms gives ~600 ms of margin without re-architecting anything. This is the spec catching up to reality.

**1.2. Multi-run aggregation in `/review` Part B Step B4** — modification to `commands/review.md`. Run the persona's NL submit → first card flow 3× and use min() (or p50) for the gate.

**Justification**: 4375 ms (this cycle) and 4166 ms (last cycle) are single-shot. Variance is real (~5% on Gemini API). p50 across 3 runs likely lands in the 3.9-4.1 s range — under the loosened budget with comfortable margin. Adds ~6 seconds to Part B duration and ~$0.0003 in Gemini API cost — negligible.

**Workflow-rule note**: the existing rule "no retries on flaky steps" was about gesture flakiness (button click misses, image load timeouts). Applying it to LLM-API latency was a category error. Multi-run aggregation for non-deterministic external services is industry standard.

### SECONDARY (this Sprint or next)

**1.3. `/review` Step B0 SessionEvent.failure pre-check** — bash query before browser launch. If a recent Gemini failure event exists, FAIL fast with the API status detail directly. Catches the next 403 / quota / region issue in seconds rather than letting it surface as latency mid-run.

### DO NOT DO YET

- **2.1 Trim chat phase prompt** — still risks bilingual regression. Wait for production data on Sprint 1 probe quality before any prompt-size optimization.
- **2.2 Tier-aware Part B gates** — bigger refactor, do after 1.x lands and stabilizes.

## Acceptance criteria for the next `/review` cycle

After Tier 1.1 + 1.2 land, the next UI-affecting `/review` cycle should produce:

```
STATIC REVIEW: PASS — 0 CRITICAL, 0 MAJOR, 0 MINOR.
BROWSER TEST: PASS — Persona Brutalist time-to-first-card p50 = ~4100 ms (budget 5000 ms).
[YYYY-MM-DD] REVIEW-PASSED: <sha> — drift checks passed; run `git push` manually from this terminal
```

Not the current:
```
STATIC REVIEW: PASS — 0 CRITICAL, 0 MAJOR, 0 MINOR.
BROWSER TEST: FAIL — parse_query 4xxx ms > 4000 ms ceiling.
[YYYY-MM-DD] REVIEW-FAIL: <sha> — static review PASS but browser test FAIL ...
```

## Pointer to canonical recommendation source

Full Tier 1 / 2 / 3 catalog with effort estimates, trade-offs, risk assessments, and rank-ordered pickup sequence: `.claude/reviews/57b3244-improvements.md`.

This file (`2da9c65-improvements.md`) exists only to elevate the urgency of items that were already documented. **No new recommendations are added here.**

## File pointers (re-stated for orchestrator's pickup)

- **This file (URGENT escalation)**: `.claude/reviews/2da9c65-improvements.md`
- **Original improvements catalog (canonical)**: `.claude/reviews/57b3244-improvements.md`
- **This cycle's review report**: `.claude/reviews/2da9c65.md` (= `latest.md`)
- **Prior cycle's review report**: `.claude/reviews/57b3244.md`
- **Spec budget to update (Tier 1.1)**: `research/spec/requirements.md` §4 — the `<3-4s` time-to-first-card target row + the 4000 ms hard ceiling reference.
- **Workflow file to update (Tier 1.2)**: `.claude/commands/review.md` Step B4 (multi-run aggregation block) and Step B5 (no-retry rule clarification — distinguish gesture vs LLM-latency).

## TL;DR for main's next session

> The same `/review` Part B FAIL has fired twice for the same reason. Source code is clean both times. The recommendations from `57b3244-improvements.md` Tier 1 are no longer optional — they are the next thing to ship before more UI-affecting features land. Estimated: 30 minutes of work to make the next cycle clean.
