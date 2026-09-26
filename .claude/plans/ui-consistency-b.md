# UI-CONSISTENCY-B — rules/tokens → shared components → per-page migration

## 한국어 요약
- 순서(유저 결정 2026-09-26): ① 규칙·토큰 정비 → ② 공통 부품 → ③ 페이지별 교체.
- 근거: 2026-09-26 감사 — radius 리터럴 ~160 vs 토큰 ~25, 폰트 23종, 원형 버튼 28/32/34/36/44, 사진 카드 7종, 탭 4종, 모달 공통 부품 없음, DESIGN.md 자체 결함(calc 깨짐, 타입 토큰 미사용, scrim 모순).
- 각 단계 = 별도 PR. 페이지 교체는 페이지군별 PR 분할.

## Phase 1 — rules + tokens (DESIGN.md + tokens.css)
- Fix broken `calc(var(--radius-*) * 1px)` guidance (tokens already carry px) → WorkDetailModal square corners fixed.
- Radius scale decision (open): which role → which token; retire off-scale 10/14/16/6/4.
- Type scale: redefine `--fs-*` / `--fw-*` to match real usage (decision open), ban 800.
- Scrim: single value for modal backdrop (0.4 vs 0.65, decision open).
- Add `--tabbar-height`, shell height token incl. safe-area inset.
- Floating circle button: visual 28 + hit area rule (decision open).
- Remove dead §3.5.x references; §7.1 tab labels → actual 4 tabs.

## Phase 2 — shared components
- `FloatingIconButton` (extract from PageBackButton; used by back / logout / profile cluster / share / board hero).
- `PageShell` (height incl. inset + TabBar + centered container width variants) + `PageTitle` / `SectionTitle`.
- `Modal` / `Sheet` (radius, width 480, title size, 28/44 close button, scrim).
- `Tabs` (single underline tab for profile + architects) — `SocialSegment`/filter chips stay as chips.
- `EmptyState`, one skeleton style.
- Photo tile: consolidate onto `photoCardShell` (one radius / overlay caption); delete orphans ProjectCard / ArticleCard.
- TabBar → Instagram-style (icon-only, active = filled/heavier, hairline top border) + active-route mapping fix + aria-current. (design details = decision)

## Phase 3 — per-page migration (worst first)
1. BoardDetailPage (hero → shared shell + logo header, buttons → FloatingIconButton, i18n)
2. Studios carousel / LikedOfficesPage (extract OfficeCard to components/, drop unreachable page, slide size cap, click → building)
3. ArchitectProfilePage (1100 container, underline tabs, shared hero/avatar, grid)
4. UserProfilePage leftovers (empty states, liked card unify, inline style hack)
5. Competition list/detail (logo header, drop glass bar, 800 weight)
6. Modal family → Modal/Sheet
7. BuildingDetailPage, settings family (ScreenHeader/.headerTitle dedupe)

## Decisions log
1. Radius (2026-09-26): (a) — photo cards / swipe cards / tiles = `--radius-lg` 20; panels, buttons, inputs, surface cards = `--radius-md` 12; primary CTA = 12; pill 999 only for chips/tags/segments. Off-scale 10/14/16 fold to nearest (10,14→12; 16→20). sm 8 stays for small inner elements (badges, skeleton lines); xl 24 for sheet top corners.
2. Type scale (2026-09-26): (c) — 5 steps 12 / 14 / 16 / 20 / 24 as `--fs-*` tokens. Roles: page title 24, section/modal title 20, emphasis/card title 16, body 14, caption/label/meta 12. Fold: 9,10,11,13 → 12 or 14 by role (labels/tabs/chips 11→12, secondary body 13→14 or 12 by role), 15→14 or 16, 17,18→16 or 20, 22→20 or 24, clamp() hero titles → 24 (BuildingDetail/PersonaReport keep a separate display clamp only if user approves later). Weights 400/500/600/700 only; 800 banned. Watch density on 11px tab labels / chips (bigger text may overflow) — verify visually per page.
3. Modal scrim (2026-09-26): (a) — all modal/sheet backdrops = 0.4 via a single token (`--color-scrim-modal` or retune existing scrim token; keep 0.65 as a separate photo-overlay token for white-text-on-photo). Fix DESIGN.md §1.4/§8.10 contradiction to match.
4. Floating circle button (2026-09-26): (a) — visual 28px, hit area 44px (invisible expanded target, e.g. ::before inset -8px or padding+negative margin), icon 16/stroke 2. One shared component for every floating/overlay circle: back, logout, profile cluster, share, board hero, carousel arrows, modal close.
5. TabBar (2026-09-26): (a) Instagram-style — icon-only, no labels, no active pill; active tab = FILLED icon variant, inactive = outline; hairline top border; height 64 → 56 (`--tabbar-height` 56, DESIGN §3.3). Taste (취향) icon → magnifying glass (search) per user. aria-label + aria-current kept for screen readers. Profile tab stays an icon (avatar-in-tab not requested). Also fix getActiveTab mapping (upload/notifications/liked-projects → profile, not discovery).
5b. TabBar REVISED (2026-09-26, user screenshots of current Instagram iOS): FLOATING glass capsule, not a full-width bottom band. Detached from screen edges (side inset ~16px, bottom = safe-area + ~8-12px), fully rounded pill container, translucent surface + backdrop blur + soft shadow/hairline border, content scrolls BEHIND it (no reserved white strip). Active tab = rounded pill highlight behind the icon (lighter/darker tint of the capsule) + filled icon where one exists; inactive = outline. Icon-only, magnifier for 취향 (unchanged). Layout consequence: `--page-height` becomes the full viewport (100dvh) and every scroll container instead gets bottom clearance `--tabbar-clearance` (capsule height + gap + safe-area) so the last content can scroll above the capsule; viewport-locked pages (Discovery/Swipe/Assessment) center their stage within the area above the capsule. Implement as phase 2c AFTER 2b lands (2b is editing the same page files).
6. Photo tile (2026-09-26): (a) caption OVERLAID on the photo bottom (dark gradient via --color-scrim family, white building name + architect), 4:5 portrait, radius lg 20. One shared PhotoTile replaces the 7 building-card variants (profile Liked tab caption-below → overlay).

Defaults applied without a separate question (follow existing spec):
- Tabs: one underline Tabs component (profile style) — ArchitectProfile Built/Unbuilt dark pills → same underline tabs. Chips/filters stay chips.
- Modal/Sheet: DESIGN §8.10 already decided (mobile bottom sheet, desktop centered modal 480, radius md 12, backdrop --color-scrim-modal, close = floating circle button).
- Skeleton: DESIGN §8.8 "no shimmer" — one static skeleton style (radius sm), shimmer removed.

## Phase 2 execution split (serial front-maker runs, same stacked branch line)
- 2a: TabBar Instagram redesign + FloatingIconButton (extract + adopt in PageBackButton, PageTopControls logout, UserProfile cluster, ArchitectProfile share, carousel arrows).
- 2b: PageShell + PageTitle/SectionTitle, Modal/Sheet, Tabs, EmptyState, Skeleton, PhotoTile components (built + adopted only where they replace an identical duplicate; page restructures stay phase 3).
