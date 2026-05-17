# Plan — Building Detail Page (option A)

**Status**: Phase 1 SHIPPED (BuildingDetailPage.jsx live on develop). **P4 redesign in progress 2026-05-17** — see "P4 Update" section below. Older sections (Phase 2/3 click-handler + bookmark) shipped separately.
**Spec anchor**: `research/spec/requirements.md` § 8 "Detail Page" (last subsection).

---

## P4 Update (2026-05-17) — Pinterest gallery redesign + multisource

**Scope**: Gallery section ONLY. Replaces current horizontal scroll-snap carousel (~50vh, full-width per slide) with 2-section masonry grid + per-image kind badge + top filter toggle. Rest of page (header, metadata grid, description, atmosphere, bookmark) unchanged.

**Multisource definition**: photos + drawings split with per-image `kind` label (exterior / interior / drawing / aerial / detail) sourced from extended backend gallery shape.

### Backend change (additive — keeps `gallery` URL array intact)

`backend/apps/recommendation/engine.py` `_row_to_card`:

Emit NEW field `gallery_meta: [{url, kind}]` parallel to existing `gallery: [url]` URL array. `gallery` field stays unchanged (consumers: SwipeCard.jsx, GalleryOverlay.jsx, current BuildingDetailPage carousel — none break). `gallery_drawing_start` stays as-is.

Implementation: at the same loop in `_row_to_card` that builds `gallery_urls` (lines ~191-203), also build `gallery_meta` from `all_images_raw`. Each entry: `{url: img['url'], kind: img.get('kind') or 'gallery'}`. Filter empty urls + dedupe by url (same logic as `gallery_urls`).

Test fixtures (`backend/tests/conftest.py:28`, `test_imp7_pool_cache.py:448/537/655/743/814`, `test_imp10_topic06_telemetry.py:56`, `test_imp8_async_prefetch.py:42`, `test_hyde.py:234/358/526/568`, `test_hybrid_retrieval.py:485/530/580/621/774`, `test_confidence.py:42`, `test_sessions.py:36`, `test_projects.py:18`) using `'gallery': []` — add `'gallery_meta': []` parallel where the fixture must match the row-to-card output. Pytest must stay green.

### Frontend change

`frontend/src/api/images.js` `normalizeCard` — add `gallery_meta: card.gallery_meta || []` passthrough next to existing `gallery` line (line 96-97).

`frontend/src/pages/BuildingDetailPage.jsx` — gallery section rewrite (current lines 295-326):
- Top: filter toggle 3 chip — `[All] [Photos] [Drawings]` (default All)
- Compute `photos = gallery_meta.filter(g => g.kind !== 'drawing')`, `drawings = gallery_meta.filter(g => g.kind === 'drawing')`
- Render 2-section masonry: Photos masonry (CSS columns or grid-template-rows masonry) → "Drawings" h2 → Drawings masonry. Each section hidden if 0 items.
- Each image: `<div>` with image + small absolute-positioned badge bottom-left showing kind capitalized ("Exterior" / "Interior" / "Drawing" / "Aerial" / "Detail" / "Gallery"). Badge: small inline-style chip on rgba(0,0,0,0.6) background, white text, fontSize 10, padding 2px 6px, borderRadius 4.
- Filter toggle: when "Photos" selected, hide Drawings section; when "Drawings" selected, hide Photos section; default All shows both.
- Masonry CSS: `columnCount: 2` (mobile), `columnCount: 3` at `@media (min-width: 768px)` via inline media query OR CSS class. Each item: `breakInside: avoid; marginBottom: 8`. Image: `width: 100%; height: auto; display: block; borderRadius: 8`.
- Fallback: if `gallery_meta` empty (older backend response not yet deployed), fallback to current carousel using existing `gallery` URL array.

### Acceptance

- `/buildings/bld_007848` loads → top toggle visible → 2 masonry sections render with per-image kind badges
- Toggle "Photos" hides Drawings section; "Drawings" hides Photos; "All" shows both
- Backward compat: if backend not yet redeployed (`gallery_meta` absent), page falls back to current carousel
- `cd backend && pytest -x` green
- `cd frontend && npm run lint` green
- `cd frontend && npm run build` green
- No console errors / warnings in browser

### Out of scope (deferred)

- Pinch-zoom / image lightbox / fullscreen viewer
- Per-image rank ordering UI (image_order is just display order, not interactive)
- New backend endpoint dedicated to building (single-element batch fetch still used)
- Filter chips beyond All / Photos / Drawings

### Files touched

| File | Change | LOC |
|---|---|---|
| `backend/apps/recommendation/engine.py` | `_row_to_card` emit `gallery_meta` parallel field | ~15 |
| `backend/tests/*` (many fixtures) | Add `'gallery_meta': []` parallel to `'gallery': []` where needed | ~25 |
| `frontend/src/api/images.js` | `normalizeCard` passthrough | ~2 |
| `frontend/src/pages/BuildingDetailPage.jsx` | Gallery section rewrite (top toggle + 2-section masonry + per-image badge + fallback) | ~120 |

**Total**: ~160 LOC. Push-worthy: closes spec § 8 Detail Page "multisource gallery" requirement.

---

## Below: original Phase 1/2/3 plan (2026-05-07) — Phase 1 SHIPPED, Phase 2/3 also shipped via separate PRs.

---

## What's already shipped

| Layer | Component | Notes |
|---|---|---|
| Backend | `POST /api/v1/images/batch/` | Accepts `{building_ids: [...]}`. Returns array of building card objects from `architecture_vectors` raw row → `normalizeCard` shape. |
| Backend | `ProjectBookmarkView POST /api/v1/projects/{id}/bookmark/` | Already used by ResultsPage. Same handler covers building-detail bookmark. |
| Frontend API | `getBuildings(buildingIds)` (`api/projects.js:60`) | Calls images/batch, returns normalized cards. Single-element call works. |
| Frontend API | `getBoardBuildings(buildingIds)` (`api/projects.js:72`) | Same but raw (no normalize) — preserves `city` field. |
| Frontend API | `bookmarkBuilding(projectId, cardId, action, rank, sessionId)` | Already shipped. Used by ResultsPage. |
| Spec definition | `research/spec/requirements.md` § 8 "Detail Page" | Lists exact field mapping (gallery, title, metadata, long description, external link, actions). |

**Net**: backend zero-change, API client already wired. Pure new frontend page + route + click-target wiring across 3 existing pages.

---

## What's missing

1. **No `BuildingDetailPage.jsx`** — `frontend/src/pages/` doesn't have one.
2. **No `/buildings/:buildingId` route** in `App.jsx`.
3. **No click handler** in `ProjectCard.jsx` (TODO at line 19), `BoardDetailPage.jsx:182` (TODO), `ResultsPage.jsx` (no detail link yet).
4. **No image gallery component** for swipe-through `image_photos` + `image_drawings`. Could reuse existing `GalleryOverlay.jsx` from `frontend/src/components/` or build new.
5. **Optional backend gap**: dedicated `GET /api/v1/buildings/{id}/` endpoint. Not strictly needed (single-element batch works); can add later if perf becomes an issue.

---

## Spec § 8 "Detail Page" element-by-element

| Element | Source field on card / architecture_vectors | UI placement |
|---|---|---|
| Image gallery | `image_photos[]`, `image_drawings[]` (already merged into `gallery[]` by `normalizeCard`) | Top section, swipeable carousel |
| Title | `name_en`, `project_name` (fallback) | Below gallery |
| Architect | `architect` | Sub-line; clickable → `/office/{office_id}` if `architect_canonical_ids[0]` resolves to an Office (defer; for Phase 1 just plain text) |
| Year | `year` | Metadata strip |
| Program | `program` (normalized vocab) | Metadata strip / chip |
| Style | `style` | Metadata strip / chip |
| Atmosphere | `atmosphere` (free-form text) | Below metadata |
| Material | `material` | Metadata strip |
| Location | `location_country`, `city` | Metadata strip |
| Area | `area_sqm` | Metadata strip |
| Long description | `visual_description`, `description` | Below metadata, expandable / scrollable |
| External link | `url` | Action row, opens new tab |
| Bookmark action | ⭐ toggle | Action row (Phase 2) |
| Back action | ← arrow | Top-left header |

---

## Bookmark context problem (Phase 2 design decision)

ResultsPage entered with `sessionId` → `projectId` known → bookmark targets that project's `saved_ids`.

BuildingDetailPage entered from various sources:
- **From ResultsPage card click** — has `sessionId` / `projectId` context. Pass via route state.
- **From BoardDetailPage card click** — has `boardId` (= `projectId`). Pass via route state.
- **From ProjectCard on a profile** — viewing someone else's project. Bookmark to whose project? Probably the **viewer's most-recent active project** (defer; for Phase 2 simplest: hide bookmark button when viewer-not-owner context).
- **Direct URL** (deep link) — no context. Hide bookmark.

Simple rule for Phase 2:
- Bookmark visible if route state has `fromProjectId` AND `viewer === projectOwner`.
- Otherwise hide ⭐ button (still show building info).

For Phase 1: skip bookmark entirely. Add in Phase 2 with route-state plumbing.

---

## Phase split (3 commits)

### Phase 1 — page shell + gallery + metadata + back (push-worthy: closes spec § 8 Detail; ~150 LOC)

**Deliverable**: User clicks building anywhere → navigates to `/buildings/{building_id}` → sees gallery + metadata + description + back arrow. No bookmark yet.

Files:
- NEW `frontend/src/pages/BuildingDetailPage.jsx` (~120-180 LOC)
  - `useParams` to extract `buildingId` (with regex defense-in-depth: `/^B\d{5}$/` or fallback alphanumeric, mirror officeId pattern)
  - On mount, call `getBuildings([buildingId])` and `setBuilding(result[0] || null)` with cancellation guard
  - Layout: header (back arrow, fixed top) + gallery (top 50% viewport) + metadata strip + description (scrollable bottom)
  - Loading state: skeleton placeholder for gallery + metadata strip
  - Error: 404 / network failure → "건물 정보를 찾을 수 없어요" with back button
  - Reuse existing `GalleryOverlay.jsx` if structure matches; otherwise build minimal carousel inline
- MODIFY `frontend/src/App.jsx` — add `<Route path="buildings/:buildingId" element={<BuildingDetailPage />} />` (note plural "buildings" matches spec convention)
- (Optional) NEW `frontend/src/hooks/useBuilding.js` — wraps getBuildings([id]) into single-building hook for reuse

Acceptance:
- Direct URL (`http://localhost:5174/buildings/B00042`) loads + renders building info
- Invalid ID format → graceful error
- Network failure → graceful error + retry button
- Back arrow → `navigate(-1)` (browser history) OR `/library` fallback
- `npm run lint` clean, `npm run build` clean
- No JSX style refactor on other pages (per-line rule)

Estimate: 150-200 LOC. Single WEB-FRONT codex dispatch (~3-5 min on /fast).

### Phase 2 — click handlers in 3 source pages + bookmark visibility logic (push-worthy)

**Deliverable**: Clicking a card on ResultsPage / BoardDetailPage / ProjectCard navigates to BuildingDetailPage with project context. Bookmark visible when applicable.

Files:
- MODIFY `frontend/src/pages/ResultsPage.jsx` — card click → `navigate('/buildings/' + cardId, { state: { fromProjectId, fromSessionId } })`
- MODIFY `frontend/src/pages/BoardDetailPage.jsx` — line 182 TODO → `navigate('/buildings/' + buildingId, { state: { fromProjectId: boardId } })`
- MODIFY `frontend/src/components/profile/ProjectCard.jsx` — line 19 TODO → `navigate('/buildings/' + project.building_id, { state: { fromProjectId: project.project_id } })`
- MODIFY `frontend/src/pages/BuildingDetailPage.jsx`:
  - Read route state via `useLocation()` for `fromProjectId` / `fromSessionId`
  - If `fromProjectId` exists AND viewer is the project owner (compare `userId` from sessionStorage to `project.user_id`) → show bookmark ⭐ button
  - Bookmark handler: `bookmarkBuilding(fromProjectId, buildingId, action, rank?, fromSessionId)` — rank may be unknown when entered from BoardDetailPage; pass null or look up from project.savedIds
  - Optimistic update + rollback (mirror useResults pattern)

Estimate: 100-150 LOC delta across 4 files. Single dispatch.

### Phase 3 — back button "back to top-K" semantics + edge polish (bundle-worthy)

**Deliverable**: Back arrow goes to source page (ResultsPage / Board / Project), not just history. Handle direct-URL entry.

- MODIFY `frontend/src/pages/BuildingDetailPage.jsx`:
  - Back arrow: prefer `fromSessionId` → `/result/{fromSessionId}`, then `fromProjectId` → `/board/{id}`, then history back, then `/library`.
  - Persist last-visit Top-K rank on click so back arrow restores scroll position (advanced; defer)

Estimate: ~30-50 LOC delta. Bundle-worthy.

---

## Hard rules (per AGENTS.md + team-front.md)

- BuildingDetailPage is a NEW page — no MOCK_* contract from designer (no constraint to match)
- Inline-style JSX is allowed for new elements (no existing designer mockup to preserve)
- Use existing app accent color `#ec4899` for active states (matches TabBar / index.css / TutorialPopup convention per BOARD2)
- Per-line rule: when modifying ProjectCard / BoardDetailPage to add click handlers, ONLY touch the data/logic layer, not the inline-style JSX surrounding it
- All API via `callApi()`; trailing slashes on URLs

---

## Codex dispatch plan (Phase 1) — for autonomous execution after #51 sweep settles

```
BUILDING-DETAIL-P1: read .claude/plans/building-detail-page.md and execute the section "Phase 1 — page shell + gallery + metadata + back". Goal: NEW frontend/src/pages/BuildingDetailPage.jsx + /buildings/:buildingId route in App.jsx. Calls getBuildings([buildingId]) for data. Gallery from card.gallery[] (already merged photos+drawings via normalizeCard). Metadata strip from card.metadata.* fields. Long description from card.metadata.axis_atmosphere or card.atmosphere fallback. Back arrow uses navigate(-1).

Defense-in-depth: buildingId regex /^[A-Za-z0-9_-]{1,32}$/ before fetch (mirror FirmProfilePage officeId pattern). Cancellation guard on async effect. Loading skeleton + error state.

NO bookmark in Phase 1 (Phase 2 plumbs route state + bookmark visibility logic).

Acceptance: direct URL loads building info. Lint+build clean. Append `FRONT-DONE: BUILDING-DETAIL-P1 — BuildingDetailPage with gallery + metadata + back. <N> files. lint/build clean.` to .claude/Task.md § Handoffs.

Hard rules per AGENTS.md + team-front.md self-review checklist (8 items including fix-loop regression check). Codex /fast may be on — proceed normally.
```

---

## Open questions for next session

1. **Gallery component reuse vs new** — `frontend/src/components/GalleryOverlay.jsx` exists; check if it fits BuildingDetailPage layout or needs forking.
2. **Architect → Office link** (Phase 1.5) — spec says architect text only on Project / Board / Profile pages, NOT on swipe cards (per memory `project_phase13_ux_office_links.md`). BuildingDetailPage is "detail" — counts as Project-detail-class? Let user clarify if architect should be clickable.
3. **Bookmark on cards entered from someone else's profile** (Phase 2) — viewer's vs owner's project. Hide for now (simplest); revisit when social signals (likes, follows on building) are added (Phase 16+).
4. **Back-button target hierarchy** (Phase 3) — `fromSessionId > fromProjectId > history > library` or different?
5. **Mobile gallery UX** — pinch-zoom? swipe between images? defer until designer reviews.

---

## Memory hooks

After Phase 1 ships, save:
- `project_building_detail.md` — page exists, Phase 2 (bookmark) and Phase 3 (back-target) deferred
- Possibly update `project_phase13_ux_office_links.md` if architect linking decision lands

---

## Why this is push-worthy

Per CLAUDE.md Rule 6:
- New page in `frontend/src/pages/` (production code logic) → push-worthy
- Closes spec §8 final subsection ("Detail Page") + 3 TODO(claude) markers
- Phase 1 alone qualifies as a milestone.

Phase 2 (click handlers + bookmark) → push-worthy (touches multiple production files).
Phase 3 (back-target polish) → bundle-worthy (small refinement).
