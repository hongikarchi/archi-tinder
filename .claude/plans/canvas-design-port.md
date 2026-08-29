# Canvas Design Port — Claude Design → Frontend Code

**Status:** approved by user 2026-08-29 — executing, PR-0 in progress
**Created:** 2026-08-29
**Source:** Claude Design project "Archibe Front Design" (`2d94fa98-05e3-4678-8857-ac0a1ea563cc`)
**Local pull:** `<scratchpad>/design-pull/canvas/boards-desktop/*.html` (37/41 assembled) + `pull-report.md`

---

## 요약 (Korean)

Claude Design의 canvas 작업물 41개 보드를 실제 React 코드에 반영하는 작업.
토큰은 이미 완전 일치하므로 재작업 없음. 신규 기능 0개 — 전부 기존 화면의 리디자인.
시안은 1440×900 데스크탑이지만 앱의 기존 레이아웃 골격을 그대로 쓰고 있으므로,
**레이아웃은 건드리지 않고 스타일·카피·컴포넌트 구성 값만 이식**한다.
PR-0에서 scrim 토큰을 먼저 깔고, ResultsPage로 파이프라인을 검증한 뒤 나머지를 묶음 PR로 진행.

---

## 1. Findings that shape this plan

| Finding | Evidence | Consequence |
|---|---|---|
| **Token drift = zero** | Canvas token block whitespace-normalized byte-equal to `frontend/src/tokens.css`; 51 vars vs 51 vars, 0 added / 0 removed / 0 changed. Verified against a file fetched from the authoritative project. | No 4-theme token derivation work. The originally-feared "foundation PR" collapses to just the scrim additions. |
| **Zero new features** | All 41 boards map to an existing route (21) or existing modal/component (16). Login family = 5 boards → 1 route. | No Product Constitution scope check needed. Pure redesign. |
| **Canvas = existing app at desktop width** | Canvas doc self-labels "데스크탑 실제 화면 (develop) · 21/21". Boards reuse the app's own skeleton: centered ~420px card column + 64px bottom TabBar. Real app has no `max-width` and only 8 non-reduced-motion media queries. | Port is a **value delta**, not a layout redesign. Decision ① below. |
| **Real work = hardcoded colors** | 98 page-specific literals across 259 usages. Recurring overlay scrims `rgba(0,0,0,0.93/0.65/0.6/0.55)` have no token. 4 literals duplicate existing token values. | PR-0. Decision ② below. |
| **Canvas pinned at `e4d54f6`** | `/assessment`, `/people` (added in `bc40fbf`) have no boards. | Decision ④ below. |
| **1045 inline styles are load-bearing** | CLAUDE.md Frontend Conventions: treat existing inline styles as load-bearing. | **Hard guardrail** — every dispatch must forbid CSS-Module conversion. |
| **DesignSync is main-session-only** | Two independent sub-agents correctly reported the tool absent. | The session fetches boards itself and passes them to makers **by file path**, never as prompt text. |
| **`PersonaReport.jsx` is shared, and its two mocks agree** | Imported by BOTH `ResultsPage.jsx` and `BoardReportPage.jsx`. Verified: the Korean label sets of `results.html` and `persona-report.html` are identical (zero labels unique to either). `results.html` is larger only because it carries the page shell. | No conflict. PR-1 restyles PersonaReport once and BoardReportPage inherits it — so **BoardReportPage is folded into PR-1**, and the separate persona-report PR row is dropped. |
| **Other shared components** | `CardSkeleton.jsx` is imported by both `DiscoveryPage` and `SwipePage`; `QuestionCard.jsx` by `SwipePage`. | See the shared-component rule in §5. |

---

## 2. Decisions (settled with user, 2026-08-29)

1. **Viewport reading → delta port.** Keep the app's viewport-lock layout (`body height:100vh; overflow:hidden`, TabBar 64px fixed bottom, ~420px centered card column). Change only values: color, spacing, radius, font-size, copy, in-component composition. Verify each page at **both 1440px and ~390px**. Per-board exception: flag any board whose edit genuinely exploits desktop width (multi-column grid) and surface it rather than porting silently.
2. **scrim tokens → add to `tokens.css`.** New `--color-scrim-*` family with derived values for all 4 themes, plus swap the 4 literals that duplicate existing token values. Lands as PR-0 so page PRs consume a stable token set.
3. **Pilot page → `ResultsPage`** (user override of the initial discovery recommendation; chosen for its high text/visual density).
4. **`/assessment`, `/people` → apply common patterns only.** No canvas design exists, so port only the mechanically-derived shared patterns (scrim tokens, card/list styling, spacing rules) to keep all 41 pages tonally consistent. Do **not** invent layout or copy. Note in the PR description that design intent was unverified for these two.

---

## 3. Shared translation rules (paste into EVERY maker dispatch)

> **Task shape:** you are porting *visual values* from a static HTML mock onto an existing React page. You are NOT redesigning, NOT refactoring, and NOT restructuring.
>
> 1. **Inline styles are load-bearing.** Per `CLAUDE.md`, treat existing `style={{}}` as intentional. Edit the *values* inside them. Do NOT convert inline styles to CSS Modules, do NOT extract them into new files, do NOT "clean up" the component.
> 2. **Styling model** per `DESIGN.md` §4 hybrid: themeable values → `tokens.css` variables; `:hover`/`:focus`/`:active` on interactive components → co-located `*.module.css`; layout / one-off / dynamic → inline `style={{}}`. If the mock introduces a hover state the page lacks, that goes in the module CSS, not inline.
> 3. **No hardcoded colors.** Every color from the mock must resolve to a `var(--…)` token. Reverse-map literals using the table in §4. If a literal has no token, STOP and report it rather than hardcoding.
> 4. **Do not touch:** routing, data fetching, API calls, hooks, state shape, event handlers, business logic. Visual layer only.
> 5. **Verify before returning:** `npm run lint` and `npm run build` both clean, plus a self-review that every color you touched resolves to a token and no layout property (`position`, `height:100vh`, TabBar offsets, flex skeleton) changed. You have no browser — do NOT claim you verified themes or viewport widths. The 4-theme × 2-width visual check is the session's + user's step (§6.5); just leave the code in a state where it can pass.
> 6. **Mock is reference, not truth.** The mock is a static snapshot with placeholder data (`.photo`/`.photo2`/`.photo3` gradient classes stand in for real images — never port those). Real data is longer, empty, or missing; preserve the page's existing empty/loading/error states.
> 7. **Shared components:** if a component you touch is imported by more than one page, say so in your report. Do not restyle it to fit one page at another's expense.

---

## 4. Literal → token reverse map

Existing tokens hardcoded **in the mocks** (swap when porting mock markup — see the exemption list below before touching any of these in existing code):

| Literal | Token |
|---|---|
| `#1F2328` | `var(--color-text)` |
| `#E1E4E8` | `var(--color-surface-3)` (or `--color-user-bubble` / `--color-progress-track` by context) |
| `#e6edf3` | `var(--color-text)` (github-dark value — the mock froze a dark-theme color) |
| `#3D4047` | `var(--color-text)` (ayu-light value — same) |

### Exemptions — literals that are CORRECT and must NOT be tokenized

Verified 2026-08-29 against the real codebase. A maker that "fixes" any of these breaks the app:

1. **Theme-preview tiles** — `components/AppearanceSettings.jsx` `THEMES[]` (bg / text / accents hex per theme). Each tile intentionally renders one theme's palette while a *different* theme is active. Tokenizing collapses all four tiles into the active theme. **This file is in scope for restyling during the settings PR — the risk is live, not hypothetical.**
2. **Box-shadows** — e.g. `0 25px 50px rgba(0,0,0,0.6)` in `SwipeCard.jsx`, `SwipeDeck.jsx`. Shadows are not scrims and are not theme-dependent. Leave them.
3. **Photo-overlay gradients** — e.g. `linear-gradient(to top, rgba(0,0,0,0.93) …)` in `SwipeCard.jsx`, `profile/BoardCard.jsx`, `profile/ProjectCard.jsx`, `ArchitectProfilePage.jsx`. These sit over a photographic image, not a theme surface — same policy as the on-photo `#fff` rule below.
4. **`var(--token, #fallback)` fallback forms** — inert (tokens.css always loads). Removing them is churn.

**Modal scrims** (`SaveToBoardModal.jsx` 0.55, `TutorialPopup.jsx` 0.65, `VerifyGateModal.jsx` 0.55, `ShareCardModal.jsx` 0.60, `SurpriseBoardModal.jsx` 0.65, `PersonaReport.jsx` 0.55, …) ARE legitimate targets for the new scrim tokens — but they migrate **inside their host page's PR**, where the user can eyeball the result, not in PR-0.

New scrim family from PR-0 (values below are the light-theme baseline; see PR-0 for per-theme derivation):

| Literal | Token |
|---|---|
| `rgba(0,0,0,0.93)` / `rgba(0,0,0,0.94)` | `var(--color-scrim-strong)` |
| `rgba(0,0,0,0.65)` | `var(--color-scrim)` |
| `rgba(0,0,0,0.55)` / `rgba(0,0,0,0.52)` | `var(--color-scrim-soft)` |
| `rgba(0,0,0,0.12)` | `var(--color-scrim-faint)` |

Known unmapped — report, do not hardcode:
- `rgba(99,102,241,…)` — indigo, appears in `results.html`. Not in any theme's accent family. Likely should be `var(--accent-2)`; confirm with user during PR-1.
- `#fff` — highest-frequency literal (22 pages). Context-dependent: on-photo text/icons vs. surface. On-photo white is arguably correct as a literal (it sits over an image, not a theme surface); surface white must become `var(--color-bg)`. Resolve case-by-case, document the rule in PR-1.
- `rgba(255,255,255,0.72/0.68/0.16/0.12/0.10/0.08/0.06)` — on-photo overlay whites. Same judgment as `#fff`; if they survive PR-1 review as legitimately image-relative, they stay literal and this is recorded as an accepted exception.

---

## 5. Execution sequence

Branches fork fresh off `develop` (currently clean). Each PR targets `develop`.

### PR-0 — `feature/claude-design-scrim-tokens`
Add the `--color-scrim-*` family to `frontend/src/tokens.css` for all 4 themes, and swap the duplicate literals that already exist in the codebase.
- Derivation: light themes use black-alpha; `github-dark` and `synthwave-84` need their own values (a black scrim over a `#262335` purple ground reads differently than over white).
- **Literal swaps: scope turned out to be ZERO** (deviation from decision ②, reported rather than silently skipped). All 6 real-code occurrences were inspected and none should be touched:
  - `components/AppearanceSettings.jsx` ×3 (`#1F2328`, `#e6edf3`, `#3D4047`) — the **theme-picker preview tiles**. Its own header comment says: *"so each tile always shows its own colors regardless of active theme. Accent hex sourced directly from tokens.css blocks."* Each tile deliberately freezes one theme's palette so the github-dark tile looks dark while ayu-light is active. Tokenizing these would make every tile render in the active theme and break the component outright. These are the most *intentional* literals in the codebase, not the worst.
  - `App.jsx:1186`, `DiscoveryPage.jsx:804,812` ×3 — all `var(--token, #FALLBACK)` form. `tokens.css` always loads, so the fallback never fires. Removing them is churn with zero visual effect.
  - Conclusion: the 4 "duplicate literals" from the report are a **mock-only** phenomenon. PR-0 adds tokens; it swaps nothing.
- Also update `DESIGN.md` §1 with the new token family.
- Also commit this plan file (it is currently untracked on `develop` — see §6 step 2).
- Gate: eslint + build + code-review. No app-test (no runtime surface change).
- Size: small. Delegate to `front-maker` (sonnet).

### PR-1 — `feature/claude-design-results` (PILOT)
`pages/ResultsPage.jsx` (480 lines, 36 inline styles, no module.css) + `components/PersonaReport.jsx` (469 lines, 29 inline styles) + `pages/BoardReportPage.jsx`.
- Boards: `canvas/boards-desktop/results.html` (45KB, 28 distinct literals / 209 usages) and `persona-report.html` (26KB).
- **BoardReportPage is folded in** because it shares `PersonaReport.jsx` with ResultsPage. Verified the two boards' Korean label sets are identical, so one restyle satisfies both — but the maker must render-check both pages, not just Results.
- What actually changes here: the pentagon chart, the spectrum bars (형태/물성/스케일/에너지/전통성 with polar labels), the persona card, and the two action buttons (이미지 생성 / 리포트 재생성). Most on-screen prose is LLM-generated data, not code strings — do not hardcode mock copy.
- i18n: `t()` is used 3× in ResultsPage, 9× in PersonaReport. New UI strings go through `i18n/locales.js`, never inline.
- **This PR validates the pipeline.** After it merges, review what went wrong in the maker dispatch and amend §3 before fanning out.
- Gate: eslint + build + code-review + security. app-test skipped per standing policy (not the swipe path).

### PR-2..N — page groups (order flexible, each independently shippable)

| PR | Boards | Real files |
|---|---|---|
| discovery | discovery, overlay-trigger-card, overlay-cap-reached, overlay-leave-modal | `DiscoveryPage.jsx`, `DiscoveryTriggerCard.jsx` |
| login family | login, login-credentials, login-consent, login-profile, login-returning | `LoginPage.jsx` + `LoginPage.module.css` (5 card states of one route) |
| settings family | settings, settings-account, settings-appearance, settings-edit-profile, settings-notifications, notifications | `pages/settings/*` |
| profiles | profile, user-other, architect, office | `UserProfilePage.jsx`, `pages/userProfile/`, `ArchitectProfilePage.jsx`, `FirmProfilePage.jsx`, `pages/firmProfile/` |
| boards | board-detail, liked-projects, overlay-save-board, overlay-save-to-board, overlay-surprise-board | `BoardDetailPage.jsx`, `pages/boardDetail/`, `LikedProjectsPage.jsx`, `SaveBoardModal.jsx`, `SaveToBoardModal.jsx`, `SurpriseBoardModal.jsx` |
| search | llm-search, llm-search-update | `LLMSearchPage.jsx`, `LLMSearchUpdateWrapper.jsx` |
| building | building-detail, overlay-photo-lightbox, overlay-work-detail | `BuildingDetailPage.jsx`, `pages/buildingDetail/` |
| upload + share | upload, overlay-share-card, overlay-verify-gate | `UploadWorkPage.jsx`, `ShareCardModal.jsx`, `VerifyGateModal.jsx` |
| **swipe (LAST)** | taste-swipe, overlay-swipecard-expanded, overlay-tutorial, overlay-swipe-confirms, overlay-card-skeleton, overlay-question-card, overlay-action-card | `SwipePage.jsx`, `SwipeCard.jsx`, `SwipeDeck.jsx`, `TutorialPopup.jsx`, `CardSkeleton.jsx`, `QuestionCard.jsx` |
| pattern-only | (no boards) | `AssessmentPage.jsx`, `PeopleDiscoveryPage.jsx` — decision ④ |

(`persona-report` is not its own row — it is covered by PR-1, see above.)

**Rules for the groups:**
- A page and its overlays ship in the SAME PR. A restyled page with an old-styled modal is a half-done page.
- **Shared components:** before restyling any component, grep for its importers. If more than one page consumes it, check whether those pages' boards agree; if they disagree, escalate to the user rather than letting one page's mock win silently. Known cases: `PersonaReport.jsx` (ResultsPage + BoardReportPage — mocks agree, handled in PR-1), `CardSkeleton.jsx` (DiscoveryPage + SwipePage — the swipe PR runs last, so it must rebase on and respect whatever the discovery PR already did).
- **swipe goes last** and is the only PR that triggers `app-test` FULL (recommendation/swipe path per standing policy). It also carries the `react-tinder-card` gotchas (callback identity kills in-progress drag; interactive card children need `className="pressable"`).
- 4 boards are not yet fetched (`overlay-share-card`, `overlay-surprise-board`, `overlay-verify-gate`, `overlay-work-detail`). The **session** fetches each via DesignSync at the start of its host PR and writes it to the pull dir.

---

## 6. Per-PR mechanics

1. Session fetches any missing board → writes to `<scratchpad>/design-pull/canvas/boards-desktop/`.
2. Session branches off `develop`: `git checkout develop && git pull && git checkout -b feature/claude-design-<topic>`. **Never `git add` on `develop`** — this plan file included; it gets committed from PR-0's branch.

   **Exception — PR-1 is stacked on PR-0** (branched from `feature/claude-design-scrim-tokens`, not `develop`) because it consumes the scrim tokens PR-0 introduces. Consequence, per the stacked-PR gotcha: **retarget PR-1 to `--base develop` BEFORE PR-0 merges** — merging a parent with `--delete-branch` auto-closes the child PR. Later PRs branch off `develop` normally once PR-0 has landed.
3. Session dispatches `front-maker` (sonnet) with: board HTML **file path** (not content), target JSX paths, §3 translation rules verbatim, §4 reverse map, and the page-specific notes from the table above.
4. Gate: eslint + build + `code-review` + `security-manager`. `app-test` skipped except the swipe PR (standing policy: 4-gate stack PASS → skip with inline drift check).
5. **User eyeballs the dev server** (`cd frontend && npm run dev`) before the publish gate. This loop is per-PR and non-negotiable — the whole point is visual work verified visually.
6. `reporter-inline` skill → `git-commit` skill → STOP at publish gate (explicit trigger required).

---

## 6b. Findings from PR-1 (carry into later PRs)

- **The mocks faithfully reproduce existing bugs.** The canvas rendered real develop screens, so a literal in a mock may simply be a copy of a literal already in the code — not a design decision. Never treat "the mock does X" as intent without checking whether the code already did X.
- **`rgb(99,102,241)` = `#6366F1` = Tailwind indigo-500.** A pre-token-system leftover, not a palette color. Appears on PersonaReport's `dominant_styles` chips. Same class as `#ec4899` (Tailwind pink-500), which still has 15 occurrences across 10 files (TabBar, profile cards, LikedProjectsPage, BuildingTile, buildingDetail/Header, UserProfilePage.module.css). Treat any Tailwind-default hex found in this codebase as legacy to tokenize, not as design.
- **`rgba(255,255,255,0.0X)` surface washes are a light-theme bug pattern.** They assume a dark ground. On `github-light` / `ayu-light` this renders white-on-white — an invisible element. Correct fix is `var(--color-tag-bg)` (or the appropriate surface token), which is already defined per-theme with black-alpha on light themes. Confirmed occurrences beyond PR-1: `profile/BoardCard.jsx`, `profile/ProjectCard.jsx`, `SaveToBoardModal.jsx` ×2, `SurpriseBoardModal.jsx` ×4, `SwipeCard.jsx`. Fix each inside its host page's PR.
- **Chip styling series:** `dominant_programs` uses `color-mix(… var(--accent-1) 10%/22%)`; `dominant_styles` should follow with `--accent-2` at the same percentages; `dominant_materials` should use `--color-tag-bg` / `--color-tag-border`. Pending user decision.
- **Verify a dispatch's premise before the maker does.** PR-1's dispatch wrongly claimed PersonaReport lacked a pentagon chart; it already had a local `RadarChart` matching the mock exactly, and the `PentagonChart.jsx` the dispatch named renders a *different taxonomy* (assessment axes 작업방식/역할성향/… via a hardwired `AXIS_LABELS` import), so following the instruction would have shipped work-style labels over taste data. The maker caught it. Check component internals, not just names, when writing a dispatch.

## 7. Open items

- `rgba(99,102,241,…)` indigo in `results.html` — resolve during PR-1.
- `#fff` / on-photo white alpha policy — establish the rule in PR-1, then apply globally.
- 4 unfetched overlay boards — fetched lazily per host PR.
- Whether any board genuinely exploits desktop width — flag per-PR as encountered.
- `LikedOfficesPage.jsx` is a confirmed orphan (imported, never rendered; `/my/liked-offices` is a redirect). Out of scope for this initiative; noted in case it surfaces during the profiles PR.
