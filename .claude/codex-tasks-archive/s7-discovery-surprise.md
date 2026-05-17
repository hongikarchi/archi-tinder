# S7 Surprise Board — Backend Endpoint + Frontend Modal

## Slug
`s7-discovery-surprise`

## Decision Owner
Claude-main. Implement only the bounded task below.

## Goal
Add the surprise-board feature: `GET /api/v1/recommendations/board-surprise/`
returns 10 curated cards for the user; on the frontend, after the user saves
5 buildings during a Discovery visit, a `SurpriseBoardModal` opens once and
offers "Save this board" → creates a new Project + bulk-bookmarks the 10
surprise cards into it. This is commit 3 of S7.

## Allowed Files (NOTE: split across backend + frontend in a single task)

### Backend
- `backend/apps/recommendation/views/discovery.py` (EDIT — append a new
  `BoardSurpriseView` class at the bottom of the file; do NOT touch
  `DiscoveryFeedView` already in place)
- `backend/apps/recommendation/views/__init__.py` (EDIT — re-export
  `BoardSurpriseView`)
- `backend/apps/recommendation/urls.py` (EDIT — register one new path
  `path('recommendations/board-surprise/', BoardSurpriseView.as_view())`)
- `backend/apps/recommendation/tests/test_discovery.py` (EDIT — append
  test cases for the new view)

### Frontend
- `frontend/src/components/SurpriseBoardModal.jsx` (NEW, ~150 LOC)
- `frontend/src/api/discovery.js` (EDIT — add `fetchBoardSurprise()` helper)
- `frontend/src/api/client.js` (EDIT — add re-export for the new helper)
- `frontend/src/pages/DiscoveryPage.jsx` (EDIT — add save-counter logic +
  conditional render of `<SurpriseBoardModal>`; trigger once when
  `savesThisVisit >= 5`)

Anything else → stop and report.

## Inputs / Contracts

### Backend endpoint shape

`GET /api/v1/recommendations/board-surprise/` (trailing slash mandatory):
- `IsAuthenticated`.
- Response 200:
  ```json
  {
    "cards": [<ImageCard>, ... up to 10],
    "title": "Curated for you",
    "rationale": "Based on your taste so far"
  }
  ```
- Algorithm:
  1. `v_taste = engine.compute_user_taste_vector(profile)` (already exists from
     commit 1).
  2. Build the same exclusion set as `DiscoveryFeedView` (union of
     `liked_ids`, `disliked_ids`, `saved_ids` across the user's Projects).
  3. If `v_taste is None` → `cards = engine.get_diverse_random(10)` minus
     excluded IDs; `title = "Discover something new"`, `rationale = "A diverse
     starter pack"`.
  4. Else → `cards = engine.taste_ranked_page(v_taste, exclude_ids, limit=10,
     offset=0)`. `title = "Curated for you"`, `rationale = "Based on your
     taste so far"`.
- **No persistence** — this view is read-only. The frontend modal handles
  any "Save this board" action by calling the existing `POST /projects/`
  endpoint + a loop of `bookmarkBuilding` calls.

### Backend tests to add to `test_discovery.py`

1. `test_surprise_cold_start_returns_random` — zero likes → 10 cards, no
   excluded IDs, `title` contains "Discover".
2. `test_surprise_warm_returns_taste_ranked` — ≥1 like → 10 cards, cards
   exclude liked/disliked/saved, `title` contains "Curated".
3. `test_surprise_unauthenticated_returns_401`.

(Mock `engine.compute_user_taste_vector` for the warm test, same as the
existing `test_warm_returns_taste_ordered` does.)

### Frontend changes

#### `api/discovery.js` (EDIT — append one function)
```js
export async function fetchBoardSurprise() {
  const data = await callApi('GET', '/recommendations/board-surprise/')
  return {
    cards: (data.cards || []).map(normalizeCard),
    title: data.title || 'Curated for you',
    rationale: data.rationale || '',
  }
}
```

#### `api/client.js` (EDIT — barrel re-export, add to the existing
`fetchDiscoveryFeed` re-export line):
```js
export { fetchDiscoveryFeed, fetchBoardSurprise } from './discovery.js'
```

#### `SurpriseBoardModal.jsx` (NEW)
Props: `onClose` (() => void), `onSaved` (() => void).

Behavior:
- On mount: `fetchBoardSurprise()` → render the 10 cards as a 2×5 mini-grid.
- Header: title + rationale + subtitle "Your saves shaped this — save it as
  a board?"
- Action bar bottom:
  - "Not now" → `onClose()`
  - "Save this board" → opens an inline name input → on submit:
    1. `callApi('POST', '/projects/', { name, visibility: 'private' })` → get
       new `project_id`.
    2. For each card in the 10: `bookmarkBuilding(project_id, card.building_id,
       'save', i + 1, null)` — sequential (or `Promise.all` for parallel —
       acceptable either way).
    3. `onSaved()` → `onClose()`.
- Loading state: skeleton or spinner while initial `fetchBoardSurprise` runs.
- Error state: "Couldn't load. Try again." button.
- Styling: same overlay/backdrop/card pattern as `SaveToBoardModal.jsx`
  shipped in commit 2; reuse the same visual constants where convenient.
- Close-on-backdrop-click + ✕ button.

#### `DiscoveryPage.jsx` (EDIT — add save counter + modal trigger)

Add to existing state:
- `savesThisVisit` (number, initial 0)
- `surpriseShown` (bool, initial false) — gate to ensure the modal fires
  only once per visit
- `surpriseOpen` (bool, initial false)

In the `SaveToBoardModal`'s `onSaved` callback (which currently just dismisses
the per-card save modal), increment `savesThisVisit`. If `savesThisVisit + 1
>= 5 && !surpriseShown`, set `surpriseShown = true` AND `surpriseOpen = true`.

Render `<SurpriseBoardModal />` when `surpriseOpen` is true, passing:
- `onClose={() => setSurpriseOpen(false)}`
- `onSaved={() => { setSurpriseOpen(false); /* optionally a small "Saved!" toast */ }}`

Trigger threshold constant at top of file: `const SURPRISE_THRESHOLD = 5`.

## Implementation Notes
- Backend: reuse `compute_user_taste_vector` + `taste_ranked_page` from
  engine.py (already present).
- Backend tests: mock `engine.compute_user_taste_vector` for the warm path
  (mirror existing `test_warm_returns_taste_ordered`).
- Frontend: do NOT add a new route — modal renders inside DiscoveryPage.
- Frontend: do NOT touch TabBar or MainLayout.
- Use inline styles only.
- The "Save this board" loop calling 10 bookmark requests is acceptable for
  v1; in practice users save < 50 buildings — not a perf concern.

## Verification
```bash
# Backend
cd backend && python3 -m pytest apps/recommendation/tests/test_discovery.py -v
# Frontend
tools/front-validate.sh
```

Both must pass. Backend new tests = 3 more passing alongside the existing
5 → 8 total in test_discovery.py.

## Handoff
- On green: append `BACK-DONE: s7-discovery-surprise` AND
  `FRONT-DONE: s7-discovery-surprise` to `.claude/Task.md` (single combined
  task; one DONE per role).
- On blocked: append `<ROLE>-BLOCKED: s7-discovery-surprise — <reason>`.
