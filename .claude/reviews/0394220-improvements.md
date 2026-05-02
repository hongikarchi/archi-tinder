# 0394220 Improvements (for main implementation terminal)

**Source:** `/review` cycle on commit `0394220 feat: IMP-10 sub-task A + Topic 06 telemetry extensions (v1.7 + v1.8)` (range `f1ad051..0394220`)

**Static review verdict:** PASS (0 CRITICAL / 0 MAJOR / 0 MINOR). Telemetry-only diff; nothing in the code needs fixing.

**Browser verification (Part B):** mechanical FAIL — but the failure causes are PRE-EXISTING and unrelated to this branch. The improvements below address the systemic gaps that surfaced during this run, not bugs in the diff under review.

---

## Tier 1 — Review-harness update (URGENT, blocks future cycles)

### What broke

`/search` now has a **multi-turn AI clarification dialog**. When the user's free-text query is ambiguous, `POST /api/v1/parse-query/` returns a clarifying question (e.g. "친환경 주거 건축의 방향성을 좁혀볼게요: 자연 재료... 또는 첨단 기술...?") instead of immediately creating a session. The user must answer the follow-up before a session is created and cards appear.

The current `/review` Part B harness (encoded in the slash command's Step B3-B4) sends the persona's query once, presses Enter, and waits for the first card image. For queries that bypass clarification (e.g. "concrete brutalist museum"), this works. For queries that trigger clarification (e.g. "한국 친환경 주거 건축", "modern"), it never observes a card and the run times out at 18 s.

This affects **2 of the 3 default personas** (SustainableKorean, BareQuery). In the 0394220 cycle, both personas were marked `card_not_visible_18s` — looks like a regression but is actually a harness gap. The third persona (Brutalist) still works and exposed the legitimate structural-latency issue (Tier 1, item 2 below).

### Fix options for the harness

Pick one — they have different ergonomics but all unblock the cycle:

**Option A — answer the clarification turn with a canned reply:**
- After typing the persona query and pressing Enter, wait up to ~5 s for either (a) a card image with `r2.dev`/`cloudflarestorage` URL, OR (b) an AI bubble appearing on the dialog.
- If (b), type a fixed "either / 둘 다 좋아" / persona-specific reply (e.g. for SustainableKorean: "자연 재료를 적극적으로 사용한 유기적 형태"), press Enter, and wait again.
- Track total elapsed time inclusive of all turns. The TTFC budget interpretation must change accordingly (see Tier 2).

**Option B — change personas to clarification-bypassing queries only:**
- Brutalist already works. Find two more queries known to bypass clarification (likely longer, more specific queries): e.g. `"James Stirling Stuttgart Staatsgalerie 1984 postmodern museum"`, `"Tadao Ando Naoshima Benesse House minimal concrete museum 1992 Japan"`. Test once manually to confirm they skip the dialog.
- This loses coverage of "ambiguous query" UX but unblocks the gate.

**Option C — measure TTFC end-to-end through the dialog:**
- t_submit = time of FIRST persona-query submit. t_first_card = time of first card visible. The harness drives the dialog automatically (option A) but the gate budget reflects the full-dialog latency.
- This requires the spec §4 budget to be redefined (Tier 2, item 1 below).

**Recommended:** Option A + Tier 2 budget redefinition. It preserves coverage and matches the actual user experience.

### Files to update

- `.claude/commands/review.md` (slash command, canonical for Part B logic)
- `.claude/skills/review/SKILL.md` if a skill mirror exists (currently the slash command is invoked via Skill).
- The Step B3-B4 helper code in the harness needs to wait for either the first-card image OR an AI bubble (use a Promise.race-like waitForFunction predicate).

---

## Tier 1 — Spec §4 TTFC budget vs. structural latency floor (URGENT, repeats from `57b3244-improvements.md`, `2da9c65-improvements.md`, `e391c95.md`)

### What broke (again)

For the one persona that did pass through (Brutalist, `concrete brutalist museum`):
- run 1: 6846 ms
- run 2: 4314 ms
- run 3: 4649 ms
- **p50: 4649 ms (gate 4000 ms — FAIL by 649 ms median)**

API breakdown per run: `parse-query/` 2700-3000 ms (Gemini RTT, even with `thinking_config=ThinkingConfig(thinking_budget=0)` from IMP-4) + `sessions/` 1300-1900 ms (initial pgvector hybrid retrieval + Topic 02 Gemini rerank + Topic 04 DPP). Both are dominantly external-network latencies.

This is the **5th cycle in a row** (`f607e73`, `57b3244`, `2da9c65`, `e391c95`, now `0394220`) where Brutalist or equivalent narrow query lands in the 4300-6800 ms range. The 4000 ms ceiling has not been achievable in practice since the spec was last updated.

### Decision needed

One of these must happen — staying in the current state is not free; it produces a Part B FAIL on every review cycle even when the diff is correct, and the user's pattern of override-pushing to keep momentum is degrading the review terminal's signal value.

**Option 1: Update spec §4 TTFC budget to reflect current structural floor.**
- Brutalist p50 across the last 5 cycles is ~4500-5500 ms. Set the hard ceiling at 6000 ms with a soft target of 4000 ms (warn, not fail), with a migration plan: tighten back to 4000 ms when IMP-8 (async-thread prefetch of next-card embeddings) and INFRA-1 (regional Neon move) ship and the median drops.
- File: `research/spec/requirements.md` §4. Owner: research terminal (must be invoked via Plan + SPEC-UPDATED handoff signal).
- Once the spec changes, update `.claude/commands/review.md` Step B4 budget values in lockstep (the slash command notes this sync requirement).

**Option 2: Prioritize IMP-8 + INFRA-1 as the next implementation tasks.**
- IMP-8 — Move next-card embedding prefetch to a background thread so the render path doesn't wait on the next pgvector fetch. Estimated 200-400 ms savings per swipe; less direct effect on TTFC since TTFC is parse-query + initial-session-create dominant. But pairs well with IMP-9 instrumentation to measure hot-path components separately.
- INFRA-1 — Regional Neon move (US-East → AP-Northeast or similar to be co-located with the user's typical egress). Estimated 80-120 ms RTT savings per query × 5 queries on session-create = ~500 ms TTFC reduction.
- Combined estimated TTFC reduction: 600-900 ms. Still not enough for guaranteed sub-4 s on Brutalist; would land at ~3700-4000 ms p50. Marginal.

**Option 3: Re-architect parse-query to local-first.**
- The 2700-3000 ms parse-query latency is the single biggest TTFC component and is a Gemini round-trip. If the persona / programmatic intent extraction can be done with a local SLM or rule-based parser for common patterns, parse-query latency could drop to <100 ms. Gemini becomes the fallback for genuinely ambiguous queries.
- This is a substantial change — Sprint 2+ scope. Worth scoping if Options 1+2 can't get below 4000 ms.

**Recommended:** Option 1 immediately + plan Option 2 in current sprint + scope Option 3 next sprint. Don't keep failing Part B on a budget the system can't structurally meet.

---

## Tier 2 — Multi-turn UX TTFC redefinition

If the multi-turn AI clarification dialog is the **intended permanent** UX (not a temporary test bed), the spec §4 budget needs a new definition that respects user-paced turns:

> **Time-to-first-card** is measured from the user's *last* clarification-turn submit before the session is created, not from the *initial* free-text submit.

Rationale: clarification turns are user-driven (the user is reading and choosing). The system can't compress a user's reading time. Measuring TTFC inclusive of clarification penalizes the system for time the user is actively spending on intent refinement.

This redefinition should land in the same spec update as Tier 1, item 2 above.

---

## Tier 3 — Out-of-scope but observed

- The new `/new` page (folder name + scale slider) and the `+` Create-new-folder button on home are good UX additions that surfaced during this cycle's harness exploration. Not new in this branch — already on origin/main. Just noting that the review terminal's harness needs to know about them now.
- The 3-step nav (`/` → `/new` → `/search`) increases the number of API calls needed before the AI search submit. `POST /api/v1/projects/` runs during "Go to AI Search →" — adds ~200-400 ms before TTFC starts counting. This is excluded from TTFC by definition (TTFC starts after persona query is typed and submitted) but bears mentioning for end-to-end latency budgets.

---

## What does NOT need fixing in 0394220 itself

The static review found 0 issues at any severity. The diff is clean:
- `compute_corpus_rank` SQL is parameterized + falls back safely on every error class.
- `aggregate_session_clustering_stats` returns safe-empty dict on any failure path; never raises.
- `_clustering_stats` reads from a module-global with the same race-window pattern as IMP-7's `_last_embedding_call_stats` — correctness-OK, telemetry-noise-only.
- The 3 new JSONFields are server-side-only writes; no IDOR or new auth surface.
- `session.save(update_fields=[...])` is idempotent (re-calling SessionResultView produces the same values).
- 222 baseline tests preserved, +36 new tests covering each new field.

**This file is purely about the systemic gaps the cycle surfaced — not about the commit being reviewed.**
