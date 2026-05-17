# S7 Frontend — Discovery Page + Save-to-Board Modal

## Slug
`s7-discovery-frontend-page`

## Decision Owner
Claude-main owns architecture, product, schema, auth, release. Codex implements
only the bounded task below.

## Goal
Replace the `DiscoveryPlaceholder` route with the real Discovery page —
infinite scroll grid of buildings, tap card → BuildingDetailPage, ⭐ button
opens a SaveToBoardModal that bookmarks the card to a chosen Project.
Surprise-board modal is a separate (next) task and not in scope here.

## Allowed Files
- `frontend/src/pages/DiscoveryPage.jsx` (NEW, ~250 LOC)
- `frontend/src/components/SaveToBoardModal.jsx` (NEW, ~120 LOC)
- `frontend/src/api/discovery.js` (NEW, ~30 LOC)
- `frontend/src/api/client.js` (EDIT — 1 line re-export, barrel pattern at
  `client.js:14`)
- `frontend/src/App.jsx` (EDIT — replace `<DiscoveryPlaceholder>` reference at
  the `/discovery` route with `<DiscoveryPage />`; **delete** the
  `DiscoveryPlaceholder` function block currently at `App.jsx:95-134`)

Anything else → `FRONT-NEEDS-CLARIFICATION`.

## Inputs / Contracts

### API contract (back-worker is shipping this in parallel)

`GET /api/v1/discovery/?cursor=<int>&limit=<int>` returns:
```json
{
  "cards": [<ImageCard>...],
  "next_cursor": <int|null>,
  "has_more": <bool>,
  "taste_state": "cold" | "warm"
}
```

Existing `POST /api/v1/projects/<project_id>/bookmark/` (call via existing
`bookmarkBuilding(projectId, cardId, 'save', rank, sessionId=null)` exported
from `api/projects.js:96-103` and re-exported by `api/client.js:14`).

Existing `GET /api/v1/projects/` (call via existing `listProjects()` from
`api/projects.js:8-19`). Returns `{ results: Project[], has_more, total }`
where each Project has `project_id`, `name`, `visibility`, etc.

### `api/discovery.js` (NEW)

```js
import { callApi } from './core.js'
import { normalizeCard } from './images.js'

export async function fetchDiscoveryFeed(cursor = 0, limit = 12) {
  const data = await callApi('GET', `/discovery/?cursor=${cursor}&limit=${limit}`)
  return {
    cards: (data.cards || []).map(normalizeCard),
    nextCursor: data.next_cursor,
    hasMore: !!data.has_more,
    tasteState: data.taste_state || 'cold',
  }
}
```

(No `fetchBoardSurprise` yet — next task.)

### `api/client.js` (EDIT — barrel re-export)

Add a re-export line near `client.js:14`:
```js
export { fetchDiscoveryFeed } from './discovery.js'
```

### `DiscoveryPage.jsx` (NEW)

Behavior:
- On mount, fetch `fetchDiscoveryFeed(0, 12)` and render a 2-column grid of
  cards (≥360px breakpoint: 2 cols; ≥768px: 3 cols).
- Each card:
  - `<img>` with the card's image (use `getImageSource(card)` from
    `api/images.js:11-103`).
  - Bottom overlay with `card.image_title`, optional `card.metadata?.architect`.
  - Corner ⭐ button (44×44 touch target, ~32px visual circle — mirrors
    `FavoritesPage.jsx` precedent the codebase had pre-S6; reuse the same
    visual pattern as the bookmark button you can see in the git log under
    `frontend/src/components/profile/BoardCard.jsx` for the action-bar
    button styling).
  - Tap card body → `navigate(`/buildings/${card.building_id}`)` (the route
    exists at `App.jsx:689` — DO NOT add a new route).
- `IntersectionObserver` on a sentinel `<div>` at the bottom of the list;
  when intersecting + `hasMore` + not `loading`, fetch the next page and
  append to `cards`.
- State:
  - `cards` (ImageCard[])
  - `cursor` (int)
  - `hasMore` (bool, default true so first fetch fires)
  - `loading` (bool)
  - `tasteState` ("cold" | "warm")
  - `saveModalCard` (card object | null) — when non-null, render
    SaveToBoardModal.
- Header chip / small badge top-right showing `Discovery · cold` or
  `Discovery · warm`. Keep the chip subtle (gray text, no background).
- Empty state: if first fetch returns `cards.length === 0`, show a centered
  "Nothing to show yet" message + CTA "Start Taste Analysis" → `navigate('/new')`.
- Loading state: skeleton (use existing `.skeleton-shimmer` class) for the
  first page; small spinner for subsequent pages.
- Error state: if `fetchDiscoveryFeed` throws, show a centered "Couldn't
  load Discovery. Tap to retry." button.

Layout constraints (per `DESIGN.md`):
- Viewport-lock: outer `<div>` style `{ height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflowY: 'auto', background: 'var(--color-bg)' }`.
- Accent: `#ec4899` hardcoded (existing convention).
- No Tailwind classes.

### `SaveToBoardModal.jsx` (NEW)

Props: `card` (the card object), `onClose` (() => void), `onSaved` (() => void).

Behavior:
- On mount: `listProjects()` → display the user's boards as a vertical list
  (re-use the visual pattern from `BoardCard.jsx` if it slots cleanly, else a
  simple list of `<button>` rows showing project name + building count).
- "New board" CTA at top opens an inline name input → on submit, calls the
  existing `POST /projects/` endpoint via the existing `api/projects.js`
  helper. (If there is no `createProject` helper, use `callApi('POST',
  '/projects/', { name, visibility: 'private' })` inline — do NOT add a new
  exported helper just for this; that's S2 territory.)
- On project selection: `bookmarkBuilding(projectId, card.building_id,
  'save', 1, null)` then call `onSaved()` and `onClose()`.
- Modal styling: centered overlay, semi-transparent backdrop, white card
  surface in dark mode (`var(--color-surface-2)`), border-radius 16px,
  z-index 10000.
- Close on backdrop click OR an explicit close button (✕ top-right).
- Loading + error states minimal but present.

### `App.jsx` edits

1. Add `import DiscoveryPage from './pages/DiscoveryPage.jsx'` near the
   other page imports.
2. Replace the `<DiscoveryPlaceholder onStart={...} />` element in the
   `/discovery` route with `<DiscoveryPage />`.
3. **Delete** the `DiscoveryPlaceholder` function block defined at
   `App.jsx:95-134` (the inline placeholder component). It is no longer
   referenced after the route swap; ESLint will flag it as unused if left
   in place.

## Implementation Notes
- Inline styles only. No Tailwind, no CSS modules, no styled-components.
- All `useEffect` cleanup must be present (cancel flag pattern from
  existing pages like `UserProfilePage.jsx:97-127`).
- Treat `intensity` / `saved_at` / etc. as opaque — do not parse them in
  the frontend.
- DO NOT add prefetch logic, image preloading, or service-worker tricks —
  S7 is the minimum viable feed.
- DO NOT touch `MainLayout.jsx` (no header changes; the existing header
  rules already apply to `/discovery`).
- DO NOT touch `TabBar.jsx` (already configured by S6).

## Verification
```bash
tools/front-validate.sh
```
Must pass `npm run lint` (ESLint clean) + `npm run build` (Vite production
build). No new lint suppressions.

Manual smoke (run a quick dev server check if convenient):
- `cd frontend && npm run dev` → http://localhost:5173 → login → `/discovery`
  loads → cards render → scroll triggers next page → tap ⭐ opens modal →
  pick a board → bookmark succeeds → modal closes.

## Handoff
On green → append to `.claude/Task.md`:
```
FRONT-DONE: s7-discovery-frontend-page
```

On blocked → append (with evidence):
```
FRONT-BLOCKED: s7-discovery-frontend-page — <root cause>
```
