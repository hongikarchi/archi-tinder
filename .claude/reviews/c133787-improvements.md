# c133787 Improvements (for main implementation terminal)

**Source:** `/review` cycle on commit `c133787 feat: IMP-5 Gemini context caching for chat-phase prompt (default OFF, v1.5)`.

**Static review verdict:** PASS (0 CRITICAL / 0 MAJOR / 0 MINOR). The diff is genuinely clean: 80% TTL invariant load-bearing, 404 reactive fallback, content-hash safety invariant, flag default OFF. 281 baseline + 20 new IMP-5 tests = 301 pass + 1 skipped (verified locally).

**Browser verification (Part B):** mechanical INCONCLUSIVE — IMP-5 is dormant (flag OFF default) so Part B measured pre-IMP-5 baseline behavior. The structural floor is unchanged because the feature isn't running yet. **8th consecutive cycle on the same wall.**

This file is the same systemic-gap progression as `1491c5d-improvements.md`, with one new urgent item (Tier 2 IMP-5 staging validation — the empirical confirmation that this commit's logic actually delivers the spec-predicted savings).

---

## Tier 2 (URGENT, post-push) — IMP-5 staging validation

The static review confirms the implementation is correct. The unit tests confirm the contracts hold. **What's NOT verified is the live empirical behavior** with real Gemini calls.

### Why this matters

IMP-5 is the structural mitigation for the 8-cycle TTFC latency floor. If it doesn't deliver in production what the spec predicts (3246ms → 1400-1800ms per parse_query), the next /review cycle's Part B will still hit the same wall. Staging validation gates the production flag flip.

### Validation procedure

1. **Deploy** with flag OFF (this commit, no behavior change). Confirm production is healthy.
2. **In dev environment**:
   ```python
   # backend/.env or environment variable override
   RECOMMENDATION['context_caching_enabled'] = True
   ```
3. **Multi-worker dev**: ensure CACHES is django-redis (per the settings.py CACHES comment block — same prerequisite as IMP-8). Single-worker dev can run with LocMemCache.
4. **Trigger 10+ parse_query calls** through the UI search flow.
5. **Query parse_query_timing SessionEvents**:
   ```python
   from apps.recommendation.models import SessionEvent
   evts = SessionEvent.objects.filter(event_type='parse_query_timing').order_by('-created_at')[:20]
   for e in evts:
       p = e.payload
       print(f"{e.created_at} mode={p['caching_mode']} hit={p['cache_hit']} cached_in={p['cached_input_tokens']} total_ms={p['gemini_total_ms']}")
   ```
6. **Expected pattern**:
   - First call: `caching_mode='explicit', cache_hit=False, cached_input_tokens=0, gemini_total_ms ~3000-3500ms` (cache create + cold call).
   - Subsequent calls (within TTL): `caching_mode='explicit', cache_hit=True, cached_input_tokens=5924, gemini_total_ms ~1400-1800ms` (cached).
   - Cache hit rate ≥ 95% after first call.
   - Median `gemini_total_ms` drops ≥ 50% on cache_hit=True calls vs cache_hit=False.
7. **If observed savings match prediction**: flag flip to production.
8. **If savings are smaller than predicted**: investigate before flipping. Possible causes: Gemini SDK version mismatch (verify `cached_content_token_count` is populated), Django cache not persisting (check Redis backend wiring), TTL expiring too aggressively (recheck 80% invariant math).

### Cost framing (per spec v1.5)

- <89 sessions/day: storage cost > savings (latency case carries — UX value, not $).
- >250 sessions/day: cost-positive.
- Current production volume: TBD; review terminal should measure on rollout.

---

## Tier 1 (carryover from `1491c5d-improvements.md`) — Spec §4 TTFC budget redefinition

Same Tier 1 as before. Multi-turn AI clarification dialog adds user-paced turns that the system can't compress. Spec §4 TTFC needs to be defined as "from the user's *last* clarification-turn submit before session creation, to first card visible" — system-attributable latency only.

This is a research-terminal task. Trigger via SPEC-UPDATED handoff once IMP-5 staging validation completes (so the new budget can be set with realistic post-IMP-5 numbers).

---

## Tier 3 (carryover, escalating) — Gemini clarification non-determinism

Across the last 3 cycles, the Brutalist clarification rate has climbed:
- Cycle `0394220`: 0/3 runs (no clarification — single-turn TTFC measured)
- Cycle `1491c5d`: 1/3 runs hit clarification
- Cycle `c133787`: 2/3 runs hit clarification

This is data, not noise. The trend suggests Gemini's `_CHAT_PHASE_SYSTEM_PROMPT` is getting more aggressive about firing clarification turns. Possibilities:
1. **Prompt drift**: the prompt has been edited between cycles in subtle ways that bias toward clarification.
2. **Gemini model update**: Google may have updated `gemini-2.5-flash` to favor clarification as a UX-improving behavior.
3. **Genuine variance**: 3 cycles is too small a sample to claim a trend; could regress next cycle.

Research terminal task: Investigation 06 follow-up — audit the chat-phase prompt for over-aggressive clarification triggers. Goal: drop clarification rate on narrow/concrete queries (Brutalist-class) to <10%; preserve for genuinely ambiguous queries (BareQuery-class).

---

## Tier 4 (carryover) — Harness robustness

This cycle's harness hang during SustainableKorean B5 session-init is a Tier-4 issue. The harness's `runFullPersonaSession` clarification-handling loop has a 4-iteration max but the canned-reply approach is brittle: each turn requires Gemini to detect the canned reply as "answer to the question" (vs another ambiguous query that triggers ANOTHER clarification).

Mitigations:
- Stricter clarification-loop bound (e.g., 2 turns max — beyond that, treat as a hung session and FAIL the persona run cleanly).
- Per-iteration deadline (e.g., 30s total max for the clarification handling phase).
- Track whether the canned reply has been consumed; if multiple clarifications fire in a row without yielding a card, abort the persona.
- Use a **persona-specific multi-turn script** instead of a single canned reply: pre-author 2-3 plausible answer turns per persona, queue them, fall back to "either/both" only if exhausted.
- More robust DOM detection for "AI bubble appeared": frontend could add a `data-role="ai-bubble"` attribute, harness can MutationObserver the chat container.

This Tier 4 work is owned by the review terminal's slash command (`/review` Step B3-B4 helper code) but main pipeline can also help by:
- Adding the `data-role="ai-bubble"` attribute to the AI bubble component (frontend, designer pipeline).
- Documenting the "frontend `<input>` has class `data-search-input`" or similar stable selector for the harness.

---

## What does NOT need fixing in c133787

The static review found 0 issues. The implementation is exemplary:

- **80% TTL invariant** baked into `django_cache.set(timeout=int(ttl * 0.8))` — load-bearing safety, prevents stale-name 404 in normal operation.
- **404 reactive fallback** — defense-in-depth for clock-drift edge case beyond 20% window. Bounded blast radius (one slow request, then recreate cycle resumes).
- **Content-hash safety invariant** — prompt content change → hash changes → cache name changes → forces recreate. Prevents serving stale cached content after a prompt edit.
- **Flag default OFF** — same conservative rollout pattern as IMP-7 / IMP-8.
- **Decision documented (skipping proactive caches.get)** — well-justified trade (50-100ms per call vs near-impossible event with 80% TTL).
- **20 new tests** covering settings defaults, hash stability, ensure_chat_cache lifecycle, parse_query branching, 404 reactive recovery, timing event extension, backward compat — comprehensive.
- **Governance-clean** — zero `research/` writes, zero design pipeline writes.
- **IMP-4 preserved** — `thinking_config=ThinkingConfig(thinking_budget=0)` on both cached and uncached call paths.
- **Telemetry honest** — 4 new fields (`cache_hit / cached_input_tokens / cache_name_hash / caching_mode`) are additive; existing 6 base fields preserved; `cache_name_hash` exposes only 8-hex prefix (PII-safe).
- **Production rollout sequence** documented in commit body.

**This file is purely about the systemic gaps the cycle (and 7 prior cycles) keep surfacing — not about the commit being reviewed.**
