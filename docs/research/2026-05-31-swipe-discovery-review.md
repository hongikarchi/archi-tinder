# Swipe / Discovery Consistency Review — 2026-05-31

Reviewer: session (Opus 4.8, max effort) + Explore agent + advisor.
Scope: `SwipeCard.jsx`, `SwipePage.jsx`, `DiscoveryPage.jsx`, their parent wiring in `App.jsx`,
the `react-tinder-card` library, and the backend like-persistence endpoints.
Method: static read of the three core files + library source (definitive for event wiring) +
backend grep (definitive for storage). Three gesture findings flagged for browser verification.

## Headline — Two Drifting Swipe Engines

`SwipePage` (Taste) and `DiscoveryPage` (Discovery) independently re-implement the same concerns
— deck management, keyboard handling, swipe routing, like-persistence, gallery wiring — and share
only the `SwipeCard` *view*. They have drifted apart far enough that the gallery bugs below are
*symptoms* of a missing shared contract, not isolated defects. No single module owns the
"gallery-open → block-swipe" contract, and `stopPropagation` does not compose across the pointer
(SwipeCard) vs mouse/touch (DiscoveryPage) vs native-listener (react-tinder-card) event models.

## Confirmed Findings (severity-ordered)

### F1 — Discovery's own likes are write-only: they never feed Discovery's taste ranking or exclusion (HIGH)
Two like stores exist, and the data flow between them is asymmetric and broken on the Discovery side.

- **Taste like**: `recordSwipe` → `POST /analysis/sessions/{id}/swipes/` → `project.liked_ids`
  (`sessions.js:65`, `App.jsx:495`). Feeds the recommendation engine, the persona report
  (`reports.py:29`), AND the Discovery taste vector. Project-scoped.
- **Discovery like**: `addLikedBuilding` → `POST /liked-buildings/` → `UserProfile.liked_building_ids`
  (`liked.js:8`, `accounts/views.py:916-922`). Feeds ONLY the profile liked grid (PR #157). Global,
  capped at 200. `liked_building_ids` is written by `LikedBuildingsView` and read by nothing else.

**Verified READ side** — `DiscoveryFeedView` (`discovery.py:28-101`):
- `taste_state` (cold/warm) + ranking come from `get_or_build_taste(profile)` →
  `engine.compute_user_taste_vector(profile)`, which reads `Project.objects...values_list('liked_ids')`
  ONLY (`engine.py:2352`). It does NOT read `UserProfile.liked_building_ids`.
- The feed exclude-set is built from `Project.liked_ids/disliked_ids/saved_ids` only
  (`discovery.py:55-73`) — `liked_building_ids` is NOT in it.

**Two concrete functional bugs fall out:**
- **F1a (HIGH)** — A Discovery-only user (right-swipes to like, never runs a Taste session) gets a
  PERMANENTLY COLD, random Discovery feed no matter how many buildings they like, because their
  likes land in `liked_building_ids`, which the taste vector ignores. This violates the core
  product promise ("the app already noticed my taste") on the Discovery surface itself.
  (Note: a Taste-heavy user IS fine — `project.liked_ids` does warm Discovery.)
- **F1b (MED)** — Because `liked_building_ids` is absent from the exclude-set, a building the user
  already liked in Discovery can REAPPEAR in the Discovery feed later. Right-swiping it again is a
  no-op dedup server-side (`accounts/views.py`), but the user re-sees it.
- **Fix direction**: feed `UserProfile.liked_building_ids` into BOTH `compute_user_taste_vector`
  (weighted same as project likes) AND the Discovery exclude-set. The profile-grid vs persona-report
  split can stay (that part IS a defensible feature boundary); the bug is that Discovery likes are
  invisible to Discovery's own engine. Remember `evict_taste(profile.id)` must fire on
  `addLikedBuilding` if the taste vector starts depending on it (`caches.py:42` invalidation note).

### F2 — Question-answer silent failure (HIGH)
`App.jsx:683-692`:
```js
async function handleQuestionAnswer(option) {
  const q = pendingQuestion
  setPendingQuestion(null)                       // UI cleared before backend confirms
  if (!activeProject?.sessionId) return
  api.submitQuestionResponse({...}).catch(() => {})  // error swallowed; answer lost
}
```
On a failed POST (network / 5xx) the user's answer is dropped — no retry, no toast — yet the UI
advanced as if it succeeded, so the taste-axis adjustment from that question silently never lands.
Optimistic clear is fine for UX; the `.catch(() => {})` is the defect.

### F3 — SwipeCard `onGalleryOpen` is a dead prop → SwipePage gallery never blocks swipe (MED, desktop)
- `SwipeCard` signature is `{ card, onGalleryClose }` (`SwipeCard.jsx:41`) — it does NOT accept
  `onGalleryOpen`, and `openGallery()` (`:60-63`) notifies no parent.
- `SwipePage` passes `onGalleryOpen={() => setGalleryOpen(true)}` (`:659`) — never invoked. So
  `galleryOpen` is permanently `false`, making `preventSwipe={galleryOpen ? [...] : ['up','down']}`
  (`:653`) always resolve to `['up','down']`, and the ESC branch `if (galleryOpen) ...` (`:403/409`)
  dead.
- **Consequence**: with the gallery open on desktop, a horizontal MOUSE drag swipes the card
  underneath (like/dislike fires). On mobile the gallery's `onTouchStart/Move` stopPropagation
  masks it, so this is desktop-only → MED.
- **Fix viability**: `preventSwipe` IS read live — react-tinder-card rebinds its gesture listeners
  when `preventSwipe` changes (`handleSwipeReleased` useCallback dep `:146`, consumed by the
  listener `useLayoutEffect` dep `:262`). So wiring `onGalleryOpen` would work without a remount
  (no flip reset). BUT see "Root cause" — the card still visually drag-wobbles before snap-back
  because the native mousedown listener fires regardless; `preventSwipe` only blocks the release
  flick.

### F4 — Mobile gallery vertical scroll likely broken (HIGH, BROWSER-VERIFY REQUIRED)
Two independent code-level mechanisms both point to "native touch scroll inside the gallery is
killed on mobile":
1. `SwipeCard.jsx:183` sets `touchAction: 'none'` on the card root; the gallery scroll div
   (`:346-355`) sets no `touch-action` of its own → in WebKit/Blink an ancestor `none` disables
   pan on descendant scroll containers.
2. `react-tinder-card/index.js:174-176` calls `ev.preventDefault()` on `touchstart` for any element
   whose className does NOT include `'pressable'`. The gallery scroll div has no such class → the
   library cancels the native scroll gesture.
- This is plausibly a regression introduced when PR #158 restored the in-card flip (the F5 band-aid
  had replaced flip with navigation, so this surface is freshly re-exposed).
- **Cannot be confirmed by reading** — `touch-action` composition + `preventDefault` interaction is
  engine-specific. Drive a mobile viewport (e.g. 390×844), open the gallery, attempt a vertical
  drag-scroll. If scroll fails, the fix is `touchAction: 'pan-y'` on the gallery scroll div AND/OR
  the `'pressable'` className escape hatch on it.

### F5 — Discovery long-press fires over the gallery (MED, desktop)
- `DiscoveryPage.jsx:316-325` wires the card-stack container with `onMouseDown={handleMouseDown}`,
  starting a 400 ms long-press timer that opens `SaveToBoardModal`.
- `SwipeCard`'s gallery ✕ / View-Gallery buttons stop only `onPointerDown`/`onPointerUp`
  (`:313-314, 390-391`); the gallery scroll area stops only `onTouchStart`/`onTouchMove`
  (`:347-348`). Pointer-event `stopPropagation` does NOT stop the separate `mousedown` synthetic
  event, and there is no mouse handler on the gallery at all.
- **Consequence**: on desktop, pressing-and-holding (>400 ms) the mouse anywhere on the Discovery
  gallery opens the Save-to-Board modal over it. Touch is masked by the touch stopPropagation, so
  desktop-only.

### F6 — Consistent silent error-swallowing on meaningful writes (pattern, LOW-MED)
The same fire-and-forget `.catch(() => {})` anti-pattern appears on two user-meaningful writes:
`addLikedBuilding(...).catch(() => {})` (`DiscoveryPage.jsx:206`, already logged as FRONT-UX-7) and
`submitQuestionResponse(...).catch(() => {})` (F2). The codebase is *consistent* here — consistently
losing write failures silently. A shared `reportWriteError(toast)` helper would fix both.

## Divergence Catalog (the drift — one row per re-implemented-differently concern)
| Concern | SwipePage (Taste) | DiscoveryPage (Discovery) |
|---|---|---|
| Keyboard | `swipeManual()` wrapper, guards on `galleryOpen`/`questionTrigger`/popups (`:395-415`) | direct `cardRef.swipe(dir)`, guards on modals only (`:93-108`) |
| Swipe routing | `pendingAction` → `onCardLeftScreen` → parent `onSwipe` (backend) | `pendingAction` → `onCardLeftScreen` → inline `addLikedBuilding` (fire-and-forget) |
| Like store | `project.liked_ids` (session) | `UserProfile.liked_building_ids` (profile) — see F1 |
| Gallery wiring | tries to manage `galleryOpen` (broken, F3) | empty no-op handlers (`:409-410, 429-430`) |
| `preventSwipe` | dynamic on `galleryOpen` (dead) (`:653`) | static `['up','down']` (`:403`) |
| Save-to-board | none (no mid-session save) | 400 ms long-press → modal (`:229-278`) |
| Deck remount guard | `cardResetToken` + `localResetTick` (`:388-393`) | none |
| Lifecycle | reported always-mounted in MainLayout, `display:none` off-route (agent, unverified) | unmounts on nav, sessionStorage cache (`:14-28, 170-180`) |
| In-flight guard | `swipePending` gates Finish button (`App.jsx:443, 616-633`) | none |

## Root Cause (architecture)
The gallery is a child of `<TinderCard>`. `react-tinder-card` binds NATIVE `mousedown`/`touchstart`
listeners on its own element (`index.js:183/192`); React synthetic `stopPropagation` on a descendant
fires AFTER those native listeners (native bubble reaches the card before React's delegated root
handler), so a child cannot reliably suppress the parent's drag via synthetic events. This is why
F3 (desktop), F5, and the F4 `preventDefault` all bite. A clean fix lifts the gallery OUT of the
TinderCard into a sibling overlay (own scroll, own ESC, own backdrop), removing the need for any
`stopPropagation` gymnastics and collapsing the galleryOpen→preventSwipe contract. That also lets
both pages consume the gallery identically — addressing the "two engines" drift at its root.

## Recommended Next Steps (priority order)
1. **F1a — wire Discovery likes into the Discovery engine** (HIGH, backend). Feed
   `UserProfile.liked_building_ids` into `compute_user_taste_vector` + the feed exclude-set, and
   `evict_taste` on `addLikedBuilding`. This is the clearest functional defect against the core
   promise. Pure backend, testable with pytest, no servers.
2. **Quick wins** (small, low-risk, frontend): F2 + F6 — add a toast on the two swallowed `.catch`
   writes (question answer, Discovery like).
3. **Browser-verify F4** (mobile-first, highest gesture-severity) before any gallery fix lands —
   mobile viewport, open gallery, try to scroll. Confirms F3 desktop + F5 desktop in the same pass.
4. **Structural fix** (larger): lift gallery out of TinderCard into a shared overlay; unify the two
   pages' keyboard + swipe routing. Foundation-correctness over feature breadth.

## Cross-refs to existing backlog
- F3 ⊃ Task.md `FRONT-UX-6` (gallery flip parent state desync) — this review supplies the exact
  root cause (dead `onGalleryOpen` prop + native-listener architecture).
- F6/Discovery half ⊃ `FRONT-UX-7` (Discovery right-swipe silent failure).
- F1/F1a/F1b touch `BACK-AUTH-3` (LikedBuildingsView guest guard) — same store.
- F1a, F1b, F2, F4, F5 are NEW (not previously logged).
