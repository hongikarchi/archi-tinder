# Plan — #51 Sprint 4 Result Page (Top-K + Bookmark UI)

**Status**: Plan-only (drafted 2026-05-07 session-end). Implementation deferred to next session.
**Spec anchor**: `research/spec/requirements.md` § 8 "Result Page & Bookmark Design"
**Investigation**: `research/investigations/08-vinitial-bit-validation-plan.md` (V_initial bit-gain measurement; informs `rank_corpus` logging hooks but NOT a frontend dependency).
**Task ID**: Task.md `#51 Sprint 4 Result page + bookmark endpoint` — currently `[in_progress]`.

---

## What's already shipped (no work needed)

| Layer | Component | Notes |
|---|---|---|
| Backend | `SessionResultView` GET `/analysis/sessions/{id}/result/` | Returns `liked_buildings` + `predicted_like_images` (Top-K MMR-diversified). Includes Topic 02 Gemini rerank, Topic 04 DPP composition when flags on. Captures `cosine_top10`/`gemini_top10`/`dpp_top10` for IMP-10 bookmark provenance. |
| Backend | `ProjectBookmarkView` POST `/projects/{id}/bookmark/` | Accepts `{card_id, action:'save'\|'unsave', rank, session_id?}`. Updates `Project.saved_ids`. Returns `{saved_ids, count}`. |
| Backend | Persona report endpoints | `/projects/{id}/report/generate/` + `/report/generate-image/` (Imagen). Already wired. |
| Frontend API | `getResult({session_id})` (`api/sessions.js:96`) | Returns `{liked_buildings, predicted_like_images, ...}`. |
| Frontend API | `bookmarkBuilding(projectId, cardId, action, rank, sessionId)` (`api/projects.js:96`) | POST wrapper. |
| Frontend API | `generateReport(projectId)` + `generateReportImage(projectId)` | Persona Imagen async generation. |
| Frontend state | App.jsx fetches `getResult` on `is_analysis_completed`, stores in `project.predictedLikes` (line ~392) | Data is already in state — just no page consuming it. |
| Frontend handler | App.jsx `bookmarkBuilding` call wired (line ~519) | Caller exists somewhere; verify integration vs new ResultsPage. |

**Net**: 100 % of backend + API client + state management is in place. Pure frontend UI work remains.

---

## What's missing (the actual #51 deliverable)

1. **No dedicated `ResultsPage.jsx`** — `frontend/src/pages/` has no result page.
2. **No `/result` route in `App.jsx`** — `<Route path="search/...">`, `<Route path="swipe">`, `<Route path="matched/:sessionId">` exist but no result.
3. **No Top-K carousel UI** — rank-1-10 zone with bookmark stars.
4. **No lazy-load (rank 11-50) UI** — IntersectionObserver + extension.
5. **No persona header UI** — `persona_type` + `one_liner` + `report_image` (Imagen async with skeleton).
6. **No "더 많은 추천" divider** between rank 10 and 11.
7. **No "더 볼 게 없어요" empty-state** when pool < 50.
8. **No detail-page link** — card click → building detail (might be deferred / out of scope; spec § 8 lists it but card detail page may be a separate task).

---

## Spec § 8 constraints (must satisfy)

1. **Layout viewport split**: persona header ≤ 40 %, Top-K carousel ≥ 60 %.
2. **First card visibility**: at least one Top-K card visible without scroll (metric integrity — bookmarks below the fold inflate denominator).
3. **Persona Imagen async**: skeleton placeholder while Imagen generates; page entry must NOT block on Imagen.
4. **Top-K loading behavior**:
   - Initial: ranks 1-10 (primary recommendation zone)
   - Lazy-scroll: ranks 11-50 (exploration zone)
   - 10 at a time via IntersectionObserver
   - Divider + "더 많은 추천" heading at the 10/11 boundary
   - Primary metric denominator = **10 (fixed)** — lazy-load doesn't affect metric
   - Pool exhaustion: < 50 available → show what's there + "더 볼 게 없어요"
5. **Bookmark semantics**: ⭐ on Result page is the **primary success metric**. Distinct from like (swipe-time, intensity 1.0) / love (swipe-time, intensity 1.8) / dislike (swipe-time). Bookmark = "최종 선별".
6. **Detail page** (out-of-scope candidate for first commit): card click → `/building/{id}` showing gallery + metadata + long description + external link + bookmark toggle + back-to-result.

---

## Suggested phase split (3-4 commits across 1-2 sessions)

### Phase 1 — basic ResultsPage shell + Top-K rank 1-10 + bookmark stars (push-worthy: closes Task.md #51 partial)

**Deliverable**: User completes swipe → navigates to `/result/{sessionId}` → sees persona header (text only, Imagen skeleton placeholder) + first 10 Top-K cards with ⭐ bookmark toggle.

Files:
- NEW `frontend/src/pages/ResultsPage.jsx` — main page component
  - `useParams` to extract sessionId
  - Hook (new or inline) to consume App.jsx's `predictedLikes` state OR re-fetch via `getResult` if direct-loaded
  - Layout: header (40 %) + carousel (60 %) using `calc(100vh - 64px)` viewport-lock pattern
  - Persona header: `persona_type` (big) + `one_liner` (smaller) + `report_image` skeleton (if not yet loaded) or actual `<img>` (if loaded)
  - Top-K rank 1-10 grid: render `predictedLikes.slice(0, 10)`, each card with image + name_en + architect + ⭐ button
  - Bookmark handler: optimistic update `savedIds` state + call `bookmarkBuilding(projectId, cardId, 'save'\|'unsave', rank, sessionId)`; rollback on error
  - Initial-viewport guarantee: first card height + persona < 100vh (test on mobile width)
- MODIFY `frontend/src/App.jsx`:
  - Add `<Route path="result/:sessionId" element={<ResultsPage ... />} />` — pass `projects`, `setProjects`, etc.
  - In `handleSwipeCard` after `is_analysis_completed`, after `getResult` returns, navigate to `/result/{sessionId}` (instead of staying in /swipe)
- (Optional) NEW `frontend/src/hooks/useResults.js` — encapsulate `getResult` fetch + `predictedLikes` consumption + bookmark optimistic updates. Mirror `useBoard` pattern.

Acceptance:
- Swipe to completion → navigates to `/result/...` automatically
- Persona header renders with Imagen skeleton (image not loading is OK — Phase 3 fixes)
- 10 cards visible (or fewer if pool exhausted, with "더 볼 게 없어요" placeholder for missing)
- Bookmark ⭐ toggles, persists across reload (verify via `Project.saved_ids` after PATCH-then-GET)
- `npm run lint && npm run build` clean

Estimate: 200-300 LOC. 1 dispatch (WEB-FRONT codex). Push-worthy (production-frontend logic + closes #51 deliverable).

### Phase 2 — Lazy-load rank 11-50 + divider (bundle-worthy if Phase 1 already pushed)

Deliverable: Scroll to bottom of rank-1-10 → divider + "더 많은 추천" heading → rank 11-20 lazy-loads via IntersectionObserver → continues until rank 50 or pool exhaustion.

Files:
- MODIFY `frontend/src/pages/ResultsPage.jsx`:
  - Add IntersectionObserver on a sentinel below rank 10 (and at rank 20, 30, 40)
  - Track `loadedRank` state; on observer trigger, render next batch of 10 from `predictedLikes`
  - Render divider between rank 10 and 11 with "더 많은 추천" heading + visual separator
  - Pool-exhaustion: if `predictedLikes.length < 50`, show "더 볼 게 없어요" at the actual end

Estimate: ~80-120 LOC delta. Bundle-worthy.

### Phase 3 — Imagen async prefetch + skeleton state machine (bundle-worthy)

Deliverable: Persona Imagen image arrives async; skeleton → progressive load → final image. Doesn't block page entry.

Files:
- MODIFY `frontend/src/pages/ResultsPage.jsx`:
  - On mount, if `report_image` not present in fetched data, kick off `generateReportImage(projectId)` in background (fire-and-forget with state updates)
  - Skeleton placeholder while pending; on resolve, fade-in actual `<img>`
  - Error path: keep skeleton + error toast (don't block page)
- (Possibly) MODIFY `frontend/src/api/projects.js` to expose status polling helper if needed

Estimate: ~50-80 LOC delta. Bundle-worthy.

### Phase 4 — Building Detail page (separate Task.md entry — defer)

Out of scope for #51 minimum viable. Card-click navigation. Add as a new Task entry (e.g. `#X — Building Detail page`) after Phase 1-3 ship.

---

## Open questions for next session

1. **`projectId` source** — App.jsx tracks `activeProjectId` (local `proj_xxx`) and `project.backendId` (server UUID). ResultsPage needs the backend UUID for `bookmarkBuilding` call. Easiest: pass via route state OR look up via context.
2. **Detail page navigation** — `/building/{building_id}` route doesn't exist. Click handler stub for now or full Phase 4?
3. **Rank-corpus logging hook** (Investigation 08) — bookmark POST currently includes `rank` (1-50). Backend `ProjectBookmarkView` may also need to log `rank_corpus` for the V_initial bit-gain experiment. Verify with Investigation 08 author (research terminal) — is the logging field already there, or does it need backend addition?
4. **`/swipe` → `/result` transition flicker** — Currently swipe completion sets `isSessionCompleted=true`. Need to choose: (a) navigate immediately to `/result`, (b) show "Generating results..." overlay on `/swipe` for ~1 s then navigate, (c) preload everything before navigation. Recommend (a) with skeleton on ResultsPage.
5. **Mobile responsive** — Persona ≤ 40 % + Top-K ≥ 60 % is viewport-relative. Test on 360 × 720 (small mobile) and 414 × 896 (iPhone 11) to ensure first card is still visible without scroll. May need `min-height: 200px` constraint on first card.

---

## Codex dispatch plan (Phase 1) — for next session

```
PHASE 1: ResultsPage skeleton + Top-K rank 1-10 + bookmark stars (Task.md #51).

Goal: build dedicated /result/{sessionId} page consuming App.jsx's predictedLikes state + getResult API. Persona header (40% viewport, text only with Imagen skeleton) + Top-K rank 1-10 carousel (60% viewport, ⭐ bookmark toggle per card). Lazy-load + Imagen async = Phase 2/3, defer.

Backend already shipped: SessionResultView GET /analysis/sessions/{id}/result/ returns {liked_buildings, predicted_like_images, persona report fields}. ProjectBookmarkView POST /projects/{id}/bookmark/ accepts {card_id, action, rank, session_id}. Frontend api/sessions.js getResult + api/projects.js bookmarkBuilding both already wrapped.

Files to write/edit:
1. NEW frontend/src/pages/ResultsPage.jsx — main page component (estimated 200-300 LOC).
2. NEW frontend/src/hooks/useResults.js — optional, encapsulates predictedLikes consumption + bookmark optimistic.
3. MODIFY frontend/src/App.jsx — add <Route path="result/:sessionId" element={<ResultsPage projects={projects} setProjects={setProjects} ... />} />, plus handleSwipeCard navigates to /result/{sessionId} after is_analysis_completed.

Spec § 8 constraints:
- Persona header ≤ 40% viewport, Top-K ≥ 60%
- First card visible without scroll (mobile-first)
- Persona Imagen async with skeleton (don't block page entry — Imagen can be skipped this phase, just show skeleton placeholder)
- ⭐ bookmark = primary success metric (Project.saved_ids)
- "더 많은 추천" divider after rank 10 (visual placeholder; lazy-load Phase 2)

Hard rules per AGENTS.md + team-front.md:
- DO NOT edit MOCK_* (none exists for results page yet — first version OK to introduce)
- DO NOT edit inline-style JSX of other pages
- ALL API via callApi() through api/* — never raw fetch
- Trailing slashes on URLs

Test:
- npm run lint --quiet — clean
- npm run build — clean
- Manual: complete a swipe session in dev → verify /result/{sessionId} loads + 10 cards display + bookmark toggles persist

When done append: `- [<date>] FRONT-DONE: RESULTS-P1 — ResultsPage Phase 1 (Top-K rank 1-10 + bookmark + persona text). N files. lint/build clean.` to .claude/Task.md § Handoffs.
```

---

## Why this is push-worthy (when implemented)

Per CLAUDE.md Rule 6: Phase 1 closes Task.md #51 (a Development Roadmap task ID) AND touches `frontend/src/pages/` + `App.jsx` (production code logic change). Both criteria → push-worthy → /review + push immediately on commit.

Phase 2 + 3 are bundle-worthy (no new task ID, incremental refinements). Sweep with next push-worthy commit.

---

## Memory hooks

After Phase 1 ships, save memory entries:
- `project_results_page.md` — page exists, lazy-load deferred
- Update `feedback_token_saving_workflow.md` with empirical: Phase 1 vs Phase 2 batching pattern
