# MOBILE-FIX-1 — swipe card + top-controls mobile fixes

## 한국어 요약
- 사용자 보고 7건 (2026-10-03). 분석 완료, 구현은 다른 세션(perf-measure-2) 종료 후 같은 클론에서 `feature/claude-mobile-fix-1` 로 진행.
- 전부 frontend. 백엔드 변경 없음 (이미지 2번은 외부 CDN 원인 가능성 → 텔레메트리로 판별).
- 결정: 7번 = (a) 테마 pill 은 모든 페이지 왼쪽 위, 왼쪽 버튼(뒤로가기/종료/알림·설정) 있으면 그 옆에 이어 붙임. 한/EN 은 오른쪽.

## Findings (develop @ 5f7026e)

1. **Gallery button dead on mobile** — `lib/tinderCard.js:155` `onTouchStart` calls `preventDefault()` unless `ev.srcElement.className.includes('pressable')`. The gallery button (`SwipeCard.jsx:629`) has no `pressable` class → touchstart default prevented → no synthesized click on touch devices. Desktop (mouse) unaffected. Second bug in the same line: tapping the inner `<svg>` gives `className` = `SVGAnimatedString` → `.includes` throws TypeError.
   Fix: guard with `ev.target.closest?.('.pressable')` (robust for SVG/text children); add `className="pressable"` to the gallery button + gallery close button. Also fix svg `rect width=28` typo (`SwipeCard.jsx:643`, should be 18).

2. **Images sometimes blank** — two candidate classes:
   - External (likely dominant): card `image_url` = third-party source-CDN hotlinks (archdaily, dezeen, archello, divisare/Cloudinary, imgix) chosen in `backend/apps/recommendation/engine_cards.py:76-100`; slow/blocked on mobile.
   - Our code (`SwipeCard.jsx:252-278`):
     a. Mount `useEffect` resets `imgLoaded=false` AFTER paint; for an already-cached image (under-card preload, `App.jsx` preloadImage) `onLoad` can fire before the effect → reset to false → image stays `opacity:0` (LQIP/shimmer only).
     b. 4s timeout reads stale `imgLoaded` closure and never checks `img.complete` → a slow-but-successful load (>4s on cellular) is swapped to a different fallback photo or to "image unavailable".
   Fix: reset in `useLayoutEffect` (or key-remount), on mount check `imgRef.current.complete && naturalWidth > 0` → mark loaded; timer checks `node.complete && node.naturalWidth` instead of stale state; raise/adjust timeout only to trigger fallback when the request actually errored or truly stalled.
   Evidence step (before/with fix): query image-load telemetry (100% of failures logged via `useImageTelemetry` → `/api/v1/telemetry/image-load/`) grouped by host/outcome — local branch first; prod read-only SELECT by user if needed.

3. **Detail info sits mid-card** — expanded detail panel is `height: 72%` anchored bottom with content flowing top-down (`SwipeCard.jsx:595-603`) → text starts ~28% from top. Fix: panel `height:auto; max-height: 100%` + `justify-content:flex-end` so content hugs the bottom; gradient stays.

4. **Card size local vs prod** — code identical (develop == main 5f7026e). `CARD_WIDTH/HEIGHT` are module-level constants frozen at first import (`SwipeCard.jsx:22-25`: `min(420, vw-32)`, `min(w*1.55, vh-220)`) → depend on viewport at load time (browser chrome / devtools emulation / rotation / PWA vs tab). Fix: measure the stage container (ResizeObserver hook) and derive card size reactively; same formula. Verify by loading both URLs at the same device/viewport.

5. **Drag feels jerky** — `lib/tinderCard.js:142-143,185`: rotation = instantaneous velocity × 15, velocity from `Date.now()` deltas between touchmoves (ms resolution, dt can be 0 → Infinity → clamped ±25°). Per-frame rotation swings → "덜그덕". Fix: rotation from position (`dx / width * maxTilt`), velocity via `ev.timeStamp` with smoothing (used only for release). Secondary: big moving `box-shadow` (0 25px 50px) on the dragged card → add `will-change: transform`; check frame cost on device.

6. **Bottom hint text** — remove `SwipePage.jsx:646` (`← skip · tap card · save →`, hardcoded EN) and `DiscoveryPage.jsx:770-773` (`discovery.swipeHintBar`); drop the unused i18n key.

7. **Top controls placement + profile share**
   - Today: `PageTopControls` fixed top-right; `splitMobile` prop (PeopleDiscovery `:135`, CompetitionList `:46`) moves 한/EN pill to top-left at ≤600px — that is why Social differs.
   - User wish: all pages theme pill LEFT, 한/EN RIGHT. Conflict: top-left already holds PageBackButton (detail pages), Swipe exit button, own-profile bell/settings cluster.
   - DECISION (2026-10-03): (a) — theme pill top-left on every page; where a left control exists (back / exit / profile bell+settings), the theme pill sits immediately to the RIGHT of that cluster in one left row (same gap/height). 한/EN (+ logout) stays top-right. Remove `splitMobile` prop entirely. Implementation hint: split PageTopControls into left (theme) + right (lang/logout) slots, or a shared `TopLeftCluster` that pages pass their left buttons into, so spacing is one source of truth; check wordmark/logo header doesn't collide at 320-375px widths.
   - Remove profile share: `UserProfilePage.jsx` L11 import, L78-79 state, L538-549 button, L1079-1082 modal; delete `components/ShareCardModal.jsx` (single consumer) + `profile.shareCard` key.

## Execution (after other session finishes)
- One front-maker run (Sonnet), single PR. Order: 1, 6, 7(share), 3, 2, 5, 4, 7(placement).
- Gate: eslint + build + inline review; user device check on 5174 (phone via LAN) for 1/2/5.
- reporter-inline → PR on explicit user keyword.
