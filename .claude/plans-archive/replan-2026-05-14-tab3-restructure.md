# Replan 2026-05-14 — Tab 3-Structure Transition + Accumulated Issue Sweep

> **[DELIVERED 2026-05-14]** All 8 pushes (S1-S8) shipped to develop and deployed to main via PR #36 (S1-S6) + PR #31 (S7) + S8 sweep + later P1-P6 series. Archived 2026-05-18.

**Approved**: 2026-05-14 via remote `/ultraplan` session.
**Author session**: WEB-MAIN admin (after Notion / Figma / KakaoTalk alignment).
**Scope**: Reorganize navigation from current 4 tabs to agreed 3 tabs, fix three
swipe-flow UX bugs, prepare for new DB schema (Make DB push expected 2026-05-15),
and codify collaborator on-boarding for the next contributor.

> This plan is an *admin contract* — the orchestrator and Codex workers should
> follow the push-unit boundaries below. Each Sx push is one PR. The `/compact`
> markers are mandatory session boundaries.

---

## Context

The agreed information architecture (per KakaoTalk + Figma + Notion review on
2026-05-14) is **three tabs**:

1. **Discovery Swipe** — Pinterest / Instagram-Explore style infinite scroll,
   tap to save to a board, contributes to taste algorithm, surprise board
   recommendation on N saves.
2. **Taste Analysis Swipe** — current swipe flow but LLM-conversation-first; the
   end of a session yields a persona report + recommended board.
3. **Profile** — own profile (boards grid + persona) and the entry point for
   "사무소 추천" (firm recommendation) via an explicit button.

The current frontend has **four tabs** (`TabBar.jsx:42-47`: New / Swipe /
Library / Profile). Library is a separate page from Profile. The Swipe flow has
three accumulated UX issues:

- **Issue 1**: Two divergent progress visualizations
  (`SwipePage.jsx:432-437` ConfidenceBar branch vs `:545-562` `like_count/3`
  text branch).
- **Issue 2**: "View Results" button surfaces *during* swipe
  (`SwipePage.jsx:617-631`, `showExit = phase === 'converged' || 'completed'`)
  and an `ActionCard` (`:287-366`) appears in the card stream with a different
  visual language from `SwipeCard`.
- **Issue 3**: Library and Profile are not merged; `UserProfilePage.jsx:36-67`
  has a mock `boards[]` array that never reads real data.

---

## Push-Unit Roadmap

```
S1 (this push) ─── plan + handoff baseline (docs only)
S2 ──── DB schema integration (triggers Make DB owner fetch)
S3 ──── swipe end-flow consolidation (Issue 2)
S4 ──── progress UI single source (Issue 1)
S5 ──── Library → Profile absorb (Issue 3)
S6 ──── 4-tab → 3-tab cutover + dead-route removal
S7 ──── Discovery Swipe tab (new feature)
S8 ──── Roadmap / spec sweep — Task.md, Goal.md, docs/specs/*
```

`/compact` boundary: after S2, S5, S7. Small intermediate pushes (S3 / S4 /
S6 / S8) reuse the prior session window.

---

## Codified Decisions (admin-confirmed in ultraplan)

| ID | Decision | Value |
|----|----------|-------|
| Q1 | First-load tab on login | **`/discovery`** (Discovery Swipe) |
| Q2 | "Keep exploring" after completion | Reuse current pool for 5 more rounds in same session |
| Q3 | Firm/user recommendation entry point | Profile tab button (NOT a separate tab) |
| Q4 | Discovery tab algorithm | Taste-vector-weighted ranking; cold-start = random sample |
| Q5 | New DB schema column exposure | Added to `client.js:normalizeCard` as optional fields |
| Q6 | LLM reverse-question timing (Phase 17) | Spec Option A — first 0-2 turns of Taste-tab LLM chat |

---

## Push S1 — Plan + Collaborator Baseline (NOW)

**Scope**: This file + `docs/COLLAB_HANDOFF.md` + Task.md Roadmap/Open update.
No source code. Single commit.

**Files**:
- `.claude/plans/replan-2026-05-14-tab3-restructure.md` (this file, new)
- `docs/COLLAB_HANDOFF.md` (new — collaborator on-boarding)
- `.claude/Task.md` (Open + Roadmap sweep)

**Verification**: Self-review — no `/review`, no `back-validate`, no `front-validate`.

**Token budget**: ~5 K.

---

## Push S2 — DB Schema Integration *(triggers Make DB owner fetch)*

**Trigger**: Make DB owner (권상조) merges the new `architecture_vectors`
schema PR into develop. Without that PR, S2 starts on a stub schema and is
re-run when the real one lands.

**Scope**:
- Update `docs/database-schema.md` to mirror the new CREATE TABLE / column list
  (admin-owned doc; reporter just syncs values).
- Audit `backend/apps/recommendation/engine.py` raw SQL: 12+ call sites grep
  `architecture_vectors`, update field references.
- Update `_row_to_card()` and `frontend/src/api/client.js:normalizeCard` when
  the API response shape changes.
- Refresh pytest fixtures: `backend/apps/recommendation/tests/test_sessions.py`,
  `test_hybrid_retrieval.py`.

**Files**:
- `docs/database-schema.md`
- `backend/apps/recommendation/engine.py`
- `backend/apps/recommendation/views/sessions.py` (if `_row_to_card` lives there)
- `frontend/src/api/client.js`
- `backend/apps/recommendation/tests/test_*.py`
- `CONTRIBUTING.md` (collaborator setup procedure — overlaps S1 doc)

**Verification**:
- `tools/back-validate.sh recommendation` (pytest + flake8 PASS)
- `tools/front-validate.sh` (eslint + build PASS)
- Manual: `python3 manage.py runserver 8001` + curl `/api/v1/buildings/B00042/`
  response shape sanity check.

**Token budget**: ~30-40 K.

**Compact after**: ✅

---

## Push S3 — Swipe End-Flow Consolidation (Issue 2)

**Scope**: Remove `ActionCard` (`SwipePage.jsx:287-366`). Drop in-stream
"View Results →" button (`:617-631`). Replace `isCompleted` block (`:479-511`)
with a design-system-consistent end-of-session screen offering two CTAs:
"Keep exploring" (reuse pool for ≤5 more rounds) and "View persona report →".

**Files**:
- `frontend/src/pages/SwipePage.jsx` (~250 LOC modified)
- `backend/apps/recommendation/views/swipe.py` (deprecate `build_action_card()`
  invocation; converged phase returns `next_card: null` + `can_continue: bool`)
- `backend/apps/recommendation/engine.py` (`build_action_card` removal or
  `@deprecated` marker)
- `backend/apps/recommendation/tests/test_sessions.py` (regenerate
  `TestSessionEventLogging` / `TestConvergenceSignalIntegrity` fixtures)

**API contract change**:
- Response shape adds `can_continue: bool` (true when residual pool ≥ 1).
- `is_analysis_completed: true` remains the trigger for the end screen; the
  client no longer renders any "action card" between swipes.

**Verification**:
- `tools/back-validate.sh recommendation`
- web-tester (or manual): one full session → end-screen → "View persona
  report" path → persona page loads.

**Token budget**: ~20-25 K.

---

## Push S4 — Progress UI Single Source (Issue 1)

**Scope**: Collapse the two-branch progress display
(`SwipePage.jsx:391-422, 544-568`) into one. ConfidenceBar when
`progress.confidence !== null`, otherwise phase label (`🔍 탐색 중`).
The `like_count/3` text and `current_round/total_rounds` text move into
the DebugOverlay only.

**Real-time correctness audit**: confirm `applySessionResponse` is invoked
once per swipe response (`App.jsx:222-257`). The prefetch instant-swap path
(`App.jsx:339-343`) needs a verified `setSessionProgress(savedProgress)` call
right after instant-swap — currently relies on next swipe response carrying
the same progress, which is one frame stale.

**Files**:
- `frontend/src/pages/SwipePage.jsx:391-422, 544-568`
- `frontend/src/App.jsx:339-343` (prefetch instant-swap progress sync)
- `DESIGN.md` consultation for color / spacing

**Verification**:
- Manual swipe 30 times, watch DebugOverlay synchronization.

**Token budget**: ~10 K.

---

## Push S5 — Library → Profile Absorb (Issue 3)

**Scope**: `UserProfilePage` boards section consumes real data.
`FavoritesPage` (`/library`) becomes a redirect-only route.

**Files**:
- `frontend/src/pages/UserProfilePage.jsx:36-67` (mock → real)
- `frontend/src/App.jsx:691-693` (`/library/*` → redirect to `/user/me`)
- `frontend/src/layouts/MainLayout.jsx:74-86` (drop FavoritesPage import)
- `backend/apps/accounts/views.py:UserProfileDetailView`
  (ensure response includes `boards[]` for both self and other-user requests)
- (Optional) `frontend/src/pages/FavoritesPage.jsx` retained until S6 to avoid
  broken bookmark URLs in the same push.

**Reused assets**:
- `frontend/src/components/profile/BoardCard.jsx` — already exists.
- `frontend/src/components/profile/BioPersonaFlipCard.jsx` — keeps current role.

**Verification**:
- Login → Profile → board grid renders → click board → BoardDetailPage opens.
- Hit `/library` URL → see redirect to `/user/me`.

**Token budget**: ~25-30 K.

**Compact after**: ✅

---

## Push S6 — 4-Tab → 3-Tab Cutover

**Scope**: Replace TabBar with 3-tab variant. Wire `/` → `/discovery`. Remove
`SetupPage` (the "New" tab) and `FavoritesPage` files.

**Files**:
- `frontend/src/components/TabBar.jsx:42-47` (new array of 3 entries)
- `frontend/src/App.jsx:633-700` (route restructure; `/new` action absorbed
  into `/taste` LLM-chat entry point)
- `frontend/src/layouts/MainLayout.jsx` (header exposure conditions per new paths)
- `frontend/src/pages/SetupPage.jsx` **(DELETE)**
- `frontend/src/pages/FavoritesPage.jsx` **(DELETE)** (S5 already removed import)

**Verification**:
- Login → first tab = Discovery placeholder (S7 not yet shipping).
- Switch tabs → no broken routes.
- Visit legacy bookmark URLs (`/swipe`, `/library/proj_xxx`) → redirected or
  resolved.

**Browser strict mode**: Part B `/review` required (large routing change).

**Token budget**: ~15-20 K.

---

## Push S7 — Discovery Swipe Tab (New Feature)

**Scope**: New page + new backend endpoint + surprise-board recommendation
trigger.

**Files**:
- `frontend/src/pages/DiscoveryPage.jsx` (new — infinite scroll, save modal)
- `backend/apps/recommendation/views/discovery.py` (new — `GET /api/v1/discovery/`)
- `backend/apps/recommendation/urls.py` (register new view)
- `frontend/src/App.jsx` (route registration; lazy import)

**Algorithm**:
- Cursor-paginated endpoint returns a taste-weighted ranking. Cold-start
  (no swipes yet) returns a random shuffle.
- Save event emits a `SessionEvent` for the algorithm pipeline.
- Surprise board recommendation modal: client-side counter triggers a
  `GET /api/v1/recommendations/board-surprise/` after N saves.

**Reused assets**:
- `client.js:bookmarkBuilding` — already wraps the save API.
- `Project.saved_ids` model field — exists since Sprint 4.
- `engine.compute_corpus_rank` — taste vector compare logic reusable.

**Verification**:
- web-tester strict mode: 3 personas × 25 swipes (cumulative).
- Manual: login → discovery → scroll 50 cards → save 5 → board count updates
  → trigger surprise modal at N saves.

**Token budget**: ~40-50 K.

**Compact after**: ✅

---

## Push S8 — Roadmap / Spec Sweep

**Scope**: Reconcile `.claude/Task.md` Roadmap with the new tab structure.
Update phase descriptions for Phase 16-18 (they now sit *within* the 3-tab
world and need scope trims).

**Files**:
- `.claude/Task.md`
- `Goal.md` (Phase 16-18 paragraphs)
- `docs/specs/phase16-recommendation-expansion.md`
- `docs/specs/phase17-llm-reverse-q.md`
- `docs/specs/phase18-external-connections.md`

**Token budget**: ~8 K.

---

## Session / Compact Strategy

| Session | Pushes | `/compact` at end? |
|---------|--------|---|
| W1 | S1 + S2 | ✅ after S2 |
| W2 | S3 + S4 | No (continue session into W3) |
| W3 | S5 | ✅ after S5 |
| W4 | S6 | No |
| W5 | S7 | ✅ after S7 |
| W6 | S8 | No (end of replan) |

Reporter runs once at the end of each session (per Token-Saving Rule 1).
Reviewer + security skipped on S1 / S4 / S8 (trivial / docs only).

---

## Open Risks

1. **DB schema timing**: if Make DB owner's PR slips past S2 start, S2 runs on
   stubs and re-runs after the real PR lands. Mitigation: S1 documents the
   adapter pattern in `client.js:normalizeCard` so frontend already tolerates
   extra/missing fields.
2. **`build_action_card` removal impact**: backend has algo-tester fixtures
   that may simulate action-card insertion. Verify before S3 push.
3. **Discovery algorithm cold-start**: random sample may surface poor matches
   for first-time users. S7 builds a fallback heuristic (program category
   diversity) before shipping.

---

## Cross-References

- `CLAUDE.md` — branch rules, push protocol.
- `.claude/SESSION_PROTOCOL.md` — session start/end, plan-table template.
- `docs/token-saving.md` — reporter / reviewer skip rules per push class.
- `CONTRIBUTING.md` — file-ownership table, hook install.
- `docs/COLLAB_HANDOFF.md` — collaborator on-boarding (new in S1).
