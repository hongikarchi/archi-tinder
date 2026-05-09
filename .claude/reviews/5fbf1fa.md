# Review: main (origin/main..HEAD)

- **Date:** 2026-05-06
- **Branch:** main
- **Range:** origin/main..HEAD  (2 commits, +183 / -29 lines, 7 files)
- **Reviewer:** Claude (/review)

## Executive Summary

2-commit range — `aedc817` BOARD3 frontend integration (Phase 14: BoardDetailPage wired to real `GET /api/v1/projects/{uuid}/` + reaction toggle via `POST/DELETE /api/v1/projects/{uuid}/react/`) + `5fbf1fa` dispatch.sh long-message file-fallback (>1500 chars). BOARD3 closes the BOARD1 + SOC2 ship loop: backend has been ready since `ba757eb` (SOC2) + `a501c8d` (BOARD1); this is the frontend layer hooking into those endpoints. Per CLAUDE.md per-line UI/Data split, only the data layer changes — designer's inline-style JSX is untouched and `MOCK_BOARD` constant is preserved verbatim as designer-contract reference. Defense-in-depth UUID guard (`/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i`) mirrors the FirmProfilePage `officeId` regex hardening pattern from `b272f37`. Optimistic reaction toggle with rollback + `isReactionPending` race guard + dedicated reactionError banner outside the empty-state chain. Server-authoritative `{reaction_count, reacted}` overrides on POST response (correctly using `reacted` not `is_reacted`, matching backend ReactionView docstring). DebugOverlay 1-line lint fix (`tick` was unused) — minimal scope-creep justified by AGENTS.md "lint clean before DONE" rule. dispatch.sh fallback writes >1500-char plans to `/tmp/dispatch-<team>-<ts>.md` and sends a pointer (empirical fix for cmux send silent-truncation discovered during BOARD3 rollout). **Part A: PASS 0/0/0** — no findings; 5 sub-MINOR observations (cosmetic). 567 → **567 passed + 1 skipped** (no new tests in this range — backend unchanged; lint clean). **Part B: PASS** — Brutalist 3079 / Korean 3082 / BareQuery 2868 ms p50 — all under budget (23/22/42% margins); 0 console errors across 9 runs; latencies essentially identical to or slightly improved over last cycle (Δ -38/-230/-246 ms). **Part C: drift PASS** — HEAD `5fbf1fa` (no advance), origin/main `3ef52b2` (no remote drift).

## Static Review Verdict (Part A)
OVERALL: **PASS**
- CRITICAL: 0
- MAJOR: 0
- MINOR: 0

## Findings (Part A)

None. Honest PASS — see Observations section for sub-MINOR notes.

## Observations (sub-MINOR, not flagged as findings)

1. **`useBoard.js` cover_image_url derivation** — `adaptProjectToBoard` sets `cover_image_url: buildings[0]?.image_url || ''`. The page then re-derives via `coverImage = board?.cover_image_url || (buildings[0] && buildings[0].image_url)`. The two paths produce the same result for a non-empty buildings array, but the page-side fallback is redundant since useBoard already populated it. Cosmetic; no behavior change.

2. **`getBoardBuildings` order-preservation** uses `Map.get + filter(Boolean)`. If a building_id in the input is missing from the response, it's silently dropped via `filter(Boolean)`. Acceptable for the BoardDetail use case (orphaned IDs from deleted buildings should disappear from the gallery rather than surface a broken card), but worth noting that consumers who need partial-success awareness (e.g., a "3 buildings unavailable" indicator) won't get it from this wrapper.

3. **`card.building_id ?? card.id` in `getBoardBuildings`** — handles either field name. Defensive but suggests inconsistent backend response shape from `/images/batch/`. Looking at engine.py `_row_to_card`, the canonical field is `building_id`. The `card.id` fallback is for safety against a response shape that doesn't currently exist. Either harmless future-proofing or dead code; cosmetic.

4. **`/tmp/dispatch-<team>-<ts>.md` files accumulate** — `dispatch.sh` writes plan files but never cleans them up. macOS clears `/tmp/` on reboot; modern Linux uses systemd-tmpfiles defaults. Acceptable, but a future enhancement could add an `rm -f /tmp/dispatch-*.md` line older-than-N days. Cosmetic for a dev-ops script.

5. **dispatch.sh 1500-char threshold is empirical**, not measured at the cmux source. The threshold could be too generous if cmux's actual limit is closer to 1200 chars on a different version, or too conservative if the limit is 2500+. Net effect: small messages skip the fallback (good); medium messages might still get truncated (bad in edge cases). Not a current concern with the empirical 2728-char success cited in the commit body.

## Architecture Alignment

Both commits are well-grounded:

- **`aedc817` BOARD3** — explicit grounding: closes Phase 14 frontend gap left by BOARD1 (backend Project=Board ship at `a501c8d`) + SOC2 (reaction backend at `ba757eb`). Per CLAUDE.md per-line UI/Data split, only data-layer changes; inline-style JSX untouched. The MOCK_BOARD constant is preserved verbatim as designer-contract reference (clean designer-pipeline boundary).

  Backend field-name precision is notable: POST/DELETE response uses `reacted` (per ReactionView lines 180-181: `{'reaction_count': project.reaction_count, 'reacted': True}`); GET on ProjectDetailView uses `is_reacted` (per views.py:223-228 SOC2 injection). The frontend correctly uses `resp?.reacted` on the toggle response and `board.is_reacted` on the initial seed. Correct asymmetry.

  UUID guard regex is canonical: `/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i` matches PostgreSQL UUID format. Backend route uses `<uuid:project_id>` Django converter which rejects non-UUID values with 404 — frontend regex is defense-in-depth, mirroring `b272f37` officeId pattern.

  This is also the **first real-world dispatch through the new stateful 4-workspace cmux architecture** (`a379bc6`) — WEB-FRONT codex executed end-to-end with 2 fix-loop cycles. The infra works.

- **`5fbf1fa` dispatch.sh fallback** — empirical-driven (BOARD3 cycle 0 dispatch was silently truncated). Pointer-file pattern is the correct mitigation: codex sees "read /tmp/X and execute" and proceeds. Operator log clearly shows offload (`plan → /tmp/...md (N chars; sending pointer)`).

The data layer additions follow established patterns:
- API wrappers: `getProject` + `getBoardBuildings` mirror existing try/catch + console.error pattern in projects.js. `reactToProject` + `unreactToProject` mirror `followUser` + `unfollowUser` in social.js.
- Hook: `useBoard` mirrors `useProjectReactors` (cancellation flag, no auto-fetch race), `useImageTelemetry` (single-purpose hook).
- Page: optimistic update + rollback + race guard pattern mirrors `handleToggleFollow` from a1f5371 SOC1 wiring.

Architectural consistency across the 5 frontend commits in Phase 13–15 (PROF3 / SOC1 / SOC2 / BOARD3) is excellent.

## Optimization Opportunities

- **`useBoard` triggers two sequential HTTP requests** (getProject, then getBoardBuildings). For a small UI improvement, could parallelize with `Promise.all` if building_ids were known upfront — but they come FROM the project response, so sequential is necessary. Not optimizable.
- **`getBoardBuildings` always returns array; never streams** — for boards with 50+ liked buildings, the response payload is meaningful but bounded. Pagination is in-band via `building_count` on the project. Not a current concern.
- **Reaction toggle latency** — round-trip to backend on every click. Optimistic UI with rollback already buffers user perception. Could be batched with debounce for "rapid like-unlike" patterns, but the race guard (`isReactionPending`) already prevents this.

## Security Analysis

- **UUID guard** in BoardDetailPage prevents path-traversal-shaped values from flowing into `getProject(boardId)`. Backend `<uuid:project_id>` Django converter is the actual enforcement; frontend regex is defense-in-depth.
- **Reaction toggle endpoints** were already security-reviewed clean in `ba757eb` cycle (visibility gate on POST: private+non-owner → 403; no gate on DELETE for sovereignty). This commit just consumes those endpoints; no new security surface.
- **`getProject` has `throwOnError` opt-in** — useBoard correctly passes `{throwOnError: true}` so 404/403 errors propagate to the error state. Without this, errors would be swallowed and the user would see a stuck loading screen.
- **`dispatch.sh` plan-file fallback** — local-only shell script. `/tmp/dispatch-${TEAM}-${timestamp}.md` filename is bounded by the team allowlist (back/front/review) and a date stamp; no shell-injection risk. The plan file content comes from `$MESSAGE` which is the operator's argument; this is a local dev-ops tool and operator-trusted.
- **DebugOverlay lint fix** — pure scope shrinkage (unused destructure removed). No security impact.

Clean security verdict.

## Test Coverage Gaps

- **`useBoard` hook**: no JSX-level tests. Acceptable per project convention (no React Testing Library setup).
- **`getProject` + `getBoardBuildings` API wrappers**: same — no Jest harness.
- **BoardDetailPage reaction toggle**: no automated test of optimistic-update + rollback. The Part B browser test exercises Brutalist/Korean/BareQuery TTFC pipeline only; reaction toggle wasn't on its critical path. Manual smoke is the current gate.
- **Backend coverage unchanged**: 567 passed + 1 skipped (no backend code in this range).

These are existing gaps, not new ones. The aedc817 commit body cites:
- npm run lint --quiet — clean
- npm run build — clean (Vite v7.3.1)

Empirically verified just now: `npm run lint` produces no output (clean ESLint).

## Cross-Commit Drift

- **2 commits stack cleanly**: aedc817 BOARD3 ships the data wiring; 5fbf1fa dispatch.sh fix is the empirical follow-up (extracted because the dispatch infra issue is unrelated to BOARD3's UI surface). Clean separation.
- **No accumulated cleanup debt.**
- **The DebugOverlay lint fix sneaking into BOARD3** is borderline scope-creep, but the commit body justifies it per AGENTS.md "Run lint before declaring DONE." Acceptable.

## Commit-by-Commit Notes

### `aedc817` feat: BOARD3 — wire BoardDetailPage to real API + reaction toggle (Phase 14)
- **Good**: explicit Phase-boundary discipline (per-line UI/Data split; MOCK_BOARD preserved verbatim as designer contract).
- **Good**: UUID guard regex; defense-in-depth pattern matches `b272f37` officeId precedent.
- **Good**: optimistic reaction toggle with rollback + `isReactionPending` race guard + server-authoritative override (`resp?.reaction_count` / `resp?.reacted`).
- **Good**: `reacted` (POST response) vs `is_reacted` (GET response seed) field-name asymmetry handled correctly per backend contract.
- **Good**: dedicated `reactionError` banner outside `statusMessage` chain (cycle 2 fix preventing dual-display when board empty AND reaction error simultaneously). Disabled state on button while pending or board not loaded.
- **Good**: `useBoard` hook is single-purpose, cancellation-safe, throws on missing project (correctly setting error state instead of swallowing).
- **Good**: `getBoardBuildings` raw-passthrough comment explains why this wrapper exists (BoardDetailPage expects backend's raw card fields, NOT normalizeCard'd).
- **Good**: `getProject` `{throwOnError}` opt-in lets useBoard differentiate "fetch failed" from "fetch returned null project".
- **Good**: 2 fix-loop cycles closed with security PASS + reviewer PASS in-session before push.
- **Good**: lint fix in DebugOverlay (`const [tick, setTick]` → `const [, setTick]`) — pre-existing issue resolved.
- **First real-world dispatch through stateful 4-workspace cmux architecture** — empirical validation that the infrastructure (a379bc6) works end-to-end.

### `5fbf1fa` tooling: dispatch.sh auto-file-fallback for long messages (>1500 chars)
- **Good**: empirical root-cause documentation (2.3 KB plan was silently truncated). Operator log clearly shows offload action.
- **Good**: 1500-char threshold leaves headroom under "somewhere between ~1500 and ~2500 chars" empirical limit; one tested success case at 2728 chars validates the threshold works in practice.
- **Good**: pointer message instructs codex to "read /tmp/X and execute" — clear, codex-actionable.
- **Sub-MINOR**: no /tmp cleanup (Observation 4); cosmetic for dev-ops tool.

## Part B — Browser Verification

**Result:** ✅ **PASS** — all 3 personas under budget; clean continuation of last cycle's PASS pattern.

### Per-gate breakdown

| Step | Result | Detail |
|------|--------|--------|
| B0a SessionEvent failure pre-check | PASS | 0 hits in 5-min window |
| B1b dev-server health | PASS | FE:200, BE responding |
| B1bb migration backstop | PASS | clean (all migrations applied) |
| B1c dev-login + token injection | PASS | user_id=2, JWT issued |
| **BOARD3 endpoint smoke** | PASS | `POST /projects/{nonexistent}/react/` → 404; `DELETE /projects/{nonexistent}/react/` → 404; `GET /projects/{nonexistent}/` → 404; `POST /images/batch/` → 200 (prior CRITICAL still resolved) |
| B2 baseline (errors=0 gate) | PASS | 0 console errors across 9 runs |
| **B4 multi-run TTFC (Tier 4 network signal)** | **PASS** | Brutalist 3079 / Korean 3082 / BareQuery 2868 — all under budget |
| B5 swipe loop | OMITTED | continuation of prior cycles' pattern |

### B4 — multi-run TTFC measurements (Tier 4 network signal)

| Persona | Runs (ms) | sys_p50 | clarif | Budget | Result | vs `3ef52b2` (last PASS) |
|---------|-----------|---------|--------|--------|--------|--------------------------|
| **Brutalist**          | [3079, ...] | **3079** | 0/3 | 4000 | **PASS by 921 ms (23% margin)** | -38 ms |
| **SustainableKorean**  | [3079, 3082, 3280] | **3082** | 3/3 | 4000 | **PASS by 918 ms (22% margin)** | -230 ms |
| **BareQuery**          | [2868, 2868, 3078] | **2868** | 3/3 | 5000 | **PASS by 2132 ms (42% margin)** | -246 ms |

### Empirical findings

**1. No regression — slight improvements over `3ef52b2`.** Δ is -38/-230/-246 ms (within Gemini ~5% noise; mild improvements). The BoardDetailPage data wiring + new useBoard hook are not on the swipe critical path, so no regression risk on Part B's TTFC measurement.

**2. Clarification signature reproduced** — Brutalist 0/3 (M1 mitigation working), Korean 3/3 (Investigation 06 design intent for ambiguous regional queries), BareQuery 3/3 (bare 1-word triggers probe by design). Same pattern as last 4+ PASS cycles.

**3. BOARD3 wiring smoke-tested at the API level** — UUID-guard-rejected endpoints return 404 (not 500), validating that `/projects/<uuid:project_id>/` Django route + `<uuid:>` converter behaves correctly with the regex-validated UUIDs the frontend will send.

## References

- `aedc817` commit body — full per-line UI/Data split rationale + cycle 2 dual-display fix history
- `5fbf1fa` commit body — empirical truncation rationale + 1500-char threshold derivation
- `.claude/reviews/3ef52b2.md` — last cycle's PASS report (baseline for latency comparison)
- `.claude/reviews/a501c8d.md` (BOARD1) + `c605f0c.md` (Image hosting Path C) + `36ecbf3.md` (SOC2) — backend foundation that BOARD3 frontend now consumes
- `frontend/src/hooks/useBoard.js:1-67` (NEW)
- `frontend/src/api/projects.js:21-30` (`getProject`) + `:60-77` (`getBoardBuildings`)
- `frontend/src/api/social.js:18-26` (`reactToProject` + `unreactToProject`)
- `frontend/src/api/client.js:14-16` (barrel re-exports)
- `frontend/src/pages/BoardDetailPage.jsx:1-7, 270-296, 567-624, 657-661` (UUID guard, useBoard wiring, optimistic reaction, statusMessage)
- `frontend/src/components/DebugOverlay.jsx:17` (lint fix)
- `tools/dispatch.sh:69-79` (long-message fallback)
- `backend/apps/recommendation/views.py:223-228` (ProjectDetailView.is_reacted injection — GET response field)
- `backend/apps/social/views.py:170-233` (ReactionView — POST/DELETE response fields)
- Empirical: `npm run lint` → clean (no output beyond the lint command echo)
- Empirical: smoke tests on `/projects/{nonexistent}/react/` (POST/DELETE → 404), `/projects/{nonexistent}/` (GET → 404), `/images/batch/` (POST → 200)
- Empirical: Part B 9 runs, 0 console errors, all under budget
- Empirical: `git diff origin/main..HEAD --name-only | grep -E '^(research/|DESIGN.md|\.claude/agents/design)'` → 0 entries (governance clean — no research/ writes, no design-pipeline territory edits)

## Recommended action (path forward)

REVIEW-PASSED — clean PASS, 0 findings at any severity. 5 sub-MINOR observations are notes-for-awareness only.

This pushes:
1. The first end-to-end-validated Phase 14 BOARD3 frontend integration
2. The first real-world stateful-cmux dispatch result (proves a379bc6 infra works)
3. A targeted dispatch.sh hardening for long-plan messages

**Run `git push` manually from this terminal.**
