# 1491c5d Improvements (for main implementation terminal)

**Source:** `/review` cycle on range `f1ad051..1491c5d` (4 commits: e430cf2 docs, 0394220 telemetry, da547cb settings retune, 1491c5d IMP-8 async prefetch).

**Static review verdict:** PASS (0 CRITICAL / 0 MAJOR / 0 MINOR). All 4 commits surgical, well-grounded in spec + investigations. 281 tests pass + 1 skipped (verified locally).

**Browser verification (Part B):** mechanical FAIL on B4 multi-run TTFC — but 7th consecutive cycle hitting the same structural Gemini parse-query + Neon RTT floor + multi-turn clarification UX. None of the 4 commits in this batch affects either floor.

This file is the **same systemic problem** identified in `0394220-improvements.md`, escalated by one more cycle of evidence. It is **not** new findings about commits 1491c5d / da547cb — those are clean.

---

## Tier 1 — Spec §4 TTFC budget redefinition for multi-turn era (URGENT, blocks every UI-affecting batch)

### What broke

The `/search` page's AI clarification dialog is now firing **non-deterministically per query**, not just on ambiguous queries. This cycle's measurements:

| Persona | Query | Run 1 | Run 2 | Run 3 |
|---------|-------|-------|-------|-------|
| Brutalist | `concrete brutalist museum` | card 5746 ms | card 4781 ms | **clarification** (no canned reply) |
| SustainableKorean | `한국 친환경 주거 건축` | clarification × 3 (no card) | 2 turns + canned + card = 9973 ms | 2 turns + canned + card = 10135 ms |
| BareQuery | `modern` | 2 turns + canned + card = 8589 ms | clarification × 3 (no card) | clarification × 3 (no card) |

Even Brutalist (which the prior 6 cycles all measured as a "narrow query that skips clarification") now sometimes triggers a clarification turn. Gemini's clarification firing is not strictly query-content-based — there's run-to-run variance.

### Why the current budget structure is broken

Spec §4 sets time-to-first-card at <4 s (5 s for bare queries) as a hard ceiling. This budget assumes:
- One `parse_query/` call (~3.0 s with current 5924-token chat-phase prompt)
- One `sessions/` call (~1.0-1.8 s for initial pgvector + pipeline)
- Total ~4.0-4.8 s

When Gemini fires clarification, you get:
- N additional `parse_query/` calls × ~3.0 s each (user-paced reading time on top)
- 1 final `sessions/` call

So a 2-turn clarification adds **~6 s to the system-side latency alone**, before user reading time. There's no way for the system to compress this — by design, multi-turn dialog is user-paced.

### Two redefinition options

**Option A — Per-stage budget (RECOMMENDED).**
Define §4 TTFC as "time from the user's *final clarification-turn submit before session creation* to first card visible." This isolates system latency from user-paced turns. Each `parse_query/` call gets its own ≤3.5 s budget; the final session-creation transition gets ≤1.5 s. Total system-attributable latency for the final-turn → card path is ≤5 s.

This means:
- Single-turn happy path: TTFC = parse_query + sessions ≤ 5 s ← still tight, but achievable post-IMP-5.
- Multi-turn path: each turn ≤ 3.5 s for `parse_query/`; the final-turn-to-card budget ≤ 5 s. Total wall-clock can exceed the 5 s gate without violating any per-stage budget.

The harness measures TTFC as "from the LAST submit (canned-reply or original query, whichever was last) to first card." This is the system-attributable latency.

**Option B — Track multi-turn separately.**
Keep §4 single-turn TTFC at 4-5 s, add §4.5 multi-turn-TTFC at 8-10 s, harness routes per persona. More complex; less clean.

**Recommendation: Option A.** It mirrors how spec §4 budgets are framed at all other turning-point benchmarks (per-Gemini-call p95 ≤ 3.5 s already exists in v1.4).

### Files to update

- `research/spec/requirements.md` §4 (research terminal owns; trigger via SPEC-UPDATED handoff)
- `.claude/commands/review.md` Step B4 budget values (lockstep with spec — per the slash command's own sync notice)
- Harness measurement code: t_submit_final = time of LAST query/clarification submit before card; t_first_card = first card image visible. TTFC = t_first_card - t_submit_final.

---

## Tier 1 — IMP-5 (Gemini context caching) ship (URGENT, repeats from prior reviews)

The 5924-token Sprint 1 chat-phase prompt is the single biggest TTFC component (~3.0 s every parse_query). Spec v1.5 §11.1 IMP-5 already has the design + cost matrix. Investigation 16 has the implementation pattern (lazy first-call init + content-hash-suffixed cache name + Redis backend + auto-recreate on 404).

Expected savings: per-Gemini-call p95 3246 → 1400-1800 ms. With Tier 1 above (per-stage budget) AND IMP-5, the single-turn happy path lands at ~3.0-3.5 s comfortably under a 5 s budget.

This is the next implementation task in spec roadmap order. Already research-ready.

---

## Tier 2 — IMP-8 staging validation

Commit 1491c5d is mechanically clean and flag-gated default OFF, so it ships with zero risk. But the empirical "does it actually save 310 ms?" question is unverified by Part B (gated on B4 PASS).

After push:
1. Deploy to dev/staging.
2. Set `async_prefetch_enabled=True` in settings.py (or via env var if wired).
3. If multi-worker: also swap CACHES to django-redis (settings.py LocMemCache comment block has the swap path).
4. Run a 25-swipe session.
5. Query `swipe.timing_breakdown` SessionEvent: assert `prefetch_strategy='async-thread'` AND `total_ms` median drops by ~310 ms vs. a comparison run with flag OFF.
6. If empirical drop confirms, flip flag in production.

Unit tests already verify the contract (`test_imp8_async_prefetch.py` — 21 tests pass). This is purely the live-measurement validation step.

---

## Tier 3 — Investigate Gemini clarification non-determinism (out of scope, research task)

This cycle's surprising data point: Brutalist run 3 hit clarification despite runs 1-2 going direct. The `concrete brutalist museum` query is concrete enough that it shouldn't need clarification. Possibilities:

1. **Prompt-induced**: `_CHAT_PHASE_SYSTEM_PROMPT` (Investigation 06 design) may be over-encouraging clarification. A prompt audit could find a tightening pass.
2. **Temperature/top-k variance**: Gemini's response sampling is not deterministic. Even with `temperature=0`, the same prompt can yield different intent decisions across runs.
3. **Context drift**: parse_query may be passing more context than needed and confusing intent extraction.

Research terminal task: review Investigation 06's prompt design + temperature settings vs. observed clarification rate. Goal: drop clarification rate on narrow queries to <10%; keep for genuinely ambiguous queries.

---

## Tier 4 — Harness improvements (recurring)

The harness now handles 1-3 clarification turns with a canned reply, but:
- Brutalist has no canned reply set (assumed it would skip clarification — proven wrong this cycle). Add a minimal canned reply for every persona.
- Detection heuristic for "AI bubble appeared" uses `style.background.includes('ai-bubble')` which seems unreliable in practice. Use a more robust DOM signature (e.g., MutationObserver on the chat container, or a data-attribute on AI bubbles if the frontend adds one).

Once Tier 1 spec redefinition lands, harness measurement code also needs to be updated to track t_submit_final correctly (last submit before session creation, not first submit).

---

## What does NOT need fixing in 1491c5d / da547cb

The static review found 0 issues at any severity. Both commits are clean:

**da547cb:**
- Single-line settings retune with explanatory comment.
- Two-threshold distinction explicitly preserved + documented (settings vs engine).
- 2 new tests (TestSpecV18Topic06N4Mitigation), 2 existing tests bumped to range(4) — semantics preserved.
- No migration, no schema change, no algorithm code change.

**1491c5d:**
- `_async_prefetch_thread` design is conservative + correct (snapshot args, connection lifecycle, GIL note, race handling, cache key uniqueness, telemetry honesty).
- Half-A-only scope is documented as intentional (Half B deferred for staleness safety).
- Flag default OFF; 21 new tests covering flag gating, cache writes, failure modes, connection lifecycle, backward compat, settings defaults.
- Multi-worker prod path (LocMemCache → Redis swap) documented in settings comment + commit body.
- Zero frontend changes; existing `normalizeCard(null) → null` already handles nullable prefetch fields gracefully.

**This file is purely about the systemic gaps the cycle (and 6 prior cycles) keep surfacing — not about the commits being reviewed.**
