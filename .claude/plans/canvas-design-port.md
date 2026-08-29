# Canvas Design Port — Claude Design → Frontend Code

**Status:** approved by user 2026-08-29 — executing. PR-0 + PR-1 committed locally.

**Mode change (user, 2026-08-29):** the user could not run the dev server, and chose to **build all PRs first and review visually afterward**. Consequences, all deliberate:
- **Every PR stays LOCAL** — branch + commit only. No push, no PR open, no merge, for any of them, until the user reviews and says which to ship. `develop` stays clean.
- The pilot's validate-then-fan-out loop is replaced by the §6c defect map: a full static scan of `frontend/src` done up front, so each PR burns down a concrete checklist instead of relying on an eyeball pass that has not happened.
- Per-PR gates (lint / build / code-review, + security where the surface warrants) still run. They catch regressions, not taste.
- Each PR must end with a **"needs eyeball" list**: judgment calls made, places the mock was deliberately not followed, and anything with uncertain contrast. That list is what the user reviews later instead of re-deriving it.
- PRs stay one-per-page-group. Do not consolidate — separate branches are what makes "ship these, redo that one" possible after the review.
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
5. **Primary CTA is FLAT `var(--accent-1)`, not the gradient** (user, 2026-08-29). Evidence: of the 37 pulled boards, **34 draw the CTA as flat `var(--accent-1)` and ZERO use `linear-gradient(135deg, var(--accent-1), var(--accent-2))`**; the remaining 3 (`discovery`, `overlay-card-skeleton`, `overlay-swipecard-expanded`) contain no CTA button at all, so the flat rule is unanimous among boards that have one. The user confirmed this was deliberate. `DESIGN.md` §8.1 updated accordingly (interaction spec unchanged). The 31 existing gradient call sites across 22 files migrate **per host-page PR**, never in a sweep — same discipline as the modal scrims.
6. **ResultsPage gets `max-width: 680px` centered content** (user, 2026-08-29). A deliberate, user-authorized exception to translation rule 4 (no layout change). Intent stated as "BoardReportPage처럼 양쪽에 여백" — and `BoardReportPage.module.css` `.container` is already `max-width: 680px; margin: 0 auto`, so the mock's 680px is *parity with an existing page*, not a new desktop-only layout. Mirror the existing value rather than the mock's.
7. **Tag chips follow the accent series** (user, 2026-08-29 — "버그 수정해줘"). `dominant_programs` already uses `--accent-1` at 10%/22%; `dominant_styles` moves from hardcoded Tailwind indigo-500 to `--accent-2` at the same percentages; `dominant_materials` moves from `rgba(255,255,255,0.06)` (invisible on light themes — a real bug) to `--color-tag-bg` / `--color-tag-border`.

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

### Standard conversions (apply on every page)

| From | To | Note |
|---|---|---|
| `linear-gradient(135deg, var(--accent-1), var(--accent-2))` **on a CTA background** | `var(--accent-1)` | Decision ⑤. Preserve any disabled-state branch (`--color-surface-2` etc.) — convert only the enabled background. The gradient stays legal on non-CTA decorative surfaces. |
| `#ec4899` (Tailwind pink-500) | the appropriate accent token, usually `var(--accent-1)` | Pre-token legacy. 13 occurrences remain across 10 files after PR-1. |
| `rgba(255,255,255,0.0X)` used as a **surface wash** | `var(--color-tag-bg)` or the right surface token | Dark-theme-assumed; renders invisible on light themes. Not to be confused with on-photo whites, which stay literal. |


### Legacy pink gradient — a third CTA variant

Beyond the tokenized `linear-gradient(135deg, var(--accent-1), var(--accent-2))`, there is an OLDER pre-token gradient still in the codebase: `linear-gradient(135deg, #ec4899, #f43f5e)` (Tailwind pink-500 → rose-500). Found at `components/profile/BioPersonaFlipCard.jsx:98`, `pages/buildingDetail/Header.jsx:53`, `pages/LikedProjectsPage.jsx:231`. These are the same class as the other Tailwind leftovers and are covered by decision ⑤ where they back a CTA. Where one backs a decorative surface rather than a button, tokenize the hexes but keep the gradient, and say so.

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
| **logo header** (cross-page) | all boards | every page rendering a two-tone page-title `<h1>` in the top slot → `Arch\|ibe`. Own PR (`feature/claude-design-logo-header`) so the pages cannot drift; see §6d item 1 |
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

   **SUPERSEDED 2026-08-29 — `feature/claude-design-scrim-tokens` is the BASE BRANCH for the whole initiative.** Every page branch forks from it, never from `develop`. Three hard reasons, each a silent failure otherwise:
   1. Page PRs consume `--color-scrim-*`. On a develop-based branch those variables do not exist, so the declaration is invalid and the background silently falls back to transparent — no error, no lint failure.
   2. The `code-review` gate reads `DESIGN.md` from the working tree. On a develop-based branch §8.1 still mandates the gradient, so the reviewer flags every correct flat-CTA conversion as a violation.
   3. Dispatches instruct the maker to read `.claude/plans/canvas-design-port.md`. That file does not exist on `develop`.

   **Docs discipline:** `DESIGN.md` and this plan are edited ONLY on the base branch, between page PRs (finish PR-N → switch to base → record findings → commit → fork PR-N+1). Page branches touch `frontend/` only. Otherwise 12 branches each edit this file and every one conflicts at publish time.

   **Publish-time consequence** (dormant during the local-only phase): the base branch merges to `develop` first — it carries PR-0's tokens plus the docs — then each page branch rebases onto fresh `develop` before its PR opens. The old "retarget before the parent merges" note generalizes to every child. PR-1 (`feature/claude-design-results`) already carries doc commits; they dedupe to empty hunks on rebase.
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
- **A wrapping element added late does NOT get its children re-indented.** ResultsPage's `max-width: 680px` wrapper encloses ~218 lines; re-indenting them would bury a 3-line semantic change under 200 lines of whitespace in a squashed PR diff, defeating the per-PR visual review this plan is built on. Lint enforces no indent rule here. Same call applies to any later PR that adds a container element.
- **Uniformity across boards is evidence of INTENT, not of template noise.** PR-2 reasoned "36 of 37 boards show the same `Arch|ibe` header, therefore it is canvas chrome" and skipped it. The user's answer: it was a deliberate instruction to show the logo on every page. The inference ran backwards — a change the author repeated on 36 screens is the *most* deliberate kind, not the least. When a delta appears everywhere, ask the user; do not rationalize it away.
- **"Do not touch, it's deliberate" claims must be verified against the actual values.** PR-2 declined to port the trigger-card change citing a theme-independent "paper look." The file it cited, `cardLanguage.js`, is built entirely from `var(--color-surface)` / `var(--color-text)` — fully theme-adaptive, as its own header comment states. The theme-independent file is a different one (`profile/BusinessCard.jsx`). A protective-sounding comment near a component is not proof it applies to the thing being changed — open the file and read the values.
- **Verify a dispatch's premise before the maker does.** PR-1's dispatch wrongly claimed PersonaReport lacked a pentagon chart; it already had a local `RadarChart` matching the mock exactly, and the `PentagonChart.jsx` the dispatch named renders a *different taxonomy* (assessment axes 작업방식/역할성향/… via a hardwired `AXIS_LABELS` import), so following the instruction would have shipped work-style labels over taste data. The maker caught it. Check component internals, not just names, when writing a dispatch.

## 6c. Defect map — the checklist each page PR burns down

Produced by a full static scan of `frontend/src` on 2026-08-29, BEFORE fanning out.

> **⚠️ Counts revised upward 2026-08-29 (at PR-2 start) — the first scan undercounted every pattern.** It used whitespace-exact regexes and so missed the `var(--accent-1, #0969DA)` fallback form and the spaced `rgba(255, 255, 255, …)` form. **Always grep whitespace-tolerant**: `linear-gradient(135deg, *var(--accent-1`, `rgba(255, *255, *255, *0\.0[0-9])`, `#ec4899`.
>
> | Pattern | First scan | Corrected |
> |---|---|---|
> | Gradient CTA | 30 | **37** |
> | White wash | 13 | **22** raw (19 excluding `tokens.css`'s own 3 definitions) |
> | `#ec4899` | 13 | **17** |
>
> Files the first scan missed entirely: `layouts/MainLayout.jsx`, `pages/LikedOfficesPage.jsx`, `pages/DiscoveryPage.jsx` (4 gradient sites), `pages/firmProfile/FirmProfileHeader.module.css`, `pages/firmProfile/FirmProfileHero.jsx`.
>
> **These counts were measured on a develop-based tree, i.e. they are PRE-PR-1.** The results branch already clears: `PersonaReport.jsx`'s gradient (line 415), its materials-chip white wash, and 2 `#ec4899` sites. Do not hunt those again. **Re-run the corrected greps at the start of each PR** rather than trusting any number written here.
>
> `layouts/MainLayout.jsx`'s gradient belongs to the **swipe PR** (MainLayout wraps `/swipe`); `pages/LikedOfficesPage.jsx` is the confirmed orphan (see §7) — leave it. Because the user chose to run all PRs before doing a visual pass, each PR works this list rather than relying on eyeballing the mock. **Every page PR must clear the entries for the files it owns**, and report anything it deliberately left.

**A. Light-theme-invisible white washes** (`rgba(255,255,255,0.0X)` used as a surface background — renders white-on-white on `github-light`/`ayu-light`). Fix → `var(--color-tag-bg)` or the right surface token. **Not** to be confused with on-photo whites, which stay literal.

| File | Count | PR |
|---|---|---|
| `components/profile/BoardCard.jsx` | 1 | boards |
| `components/profile/ProjectCard.jsx` | 1 | profiles |
| `components/SaveToBoardModal.jsx` | 2 | boards |
| `components/SurpriseBoardModal.jsx` | 4 | boards |
| `components/SwipeCard.jsx` | 1 | swipe |
| `pages/boardDetail/BuildingTile.jsx` | 1 | boards |
| `pages/boardDetail/RecommendedTile.jsx` | 1 | boards |
| `pages/LLMSearchPage.jsx` | 2 | search |
| `pages/ResultsPage.jsx` | 1 | **NOT a defect** — verified on-photo badge over a tile image; correctly stays literal |

**B. Tailwind default-palette leftovers** (pre-token-system; no design intent — see §6b). `#ec4899` = pink-500, `#ef4444` = red-500, `#fbbf24` = amber-400, `#f43f5e` = rose-500, `#a78bfa` = violet-400, `#6366F1` = indigo-500 (resolved in PR-1).

| Hex | Files | PR |
|---|---|---|
| `#ec4899` ×13 | `profile/ArticleCard.jsx(+css)`, `profile/BioPersonaFlipCard.jsx` ×4, `profile/BoardCard.jsx` ×2, `profile/ProjectCard.jsx`, `TabBar.jsx`, `boardDetail/BuildingTile.jsx` ×2, `buildingDetail/Header.jsx`, `LikedProjectsPage.jsx`, `UserProfilePage.module.css` | profiles / boards / building / **TabBar = its own follow-up** |
| `#ef4444` | `PersonaReport.jsx`, `profile/BoardCard.jsx`, `BoardDetailPage.jsx`, `UserProfilePage.module.css` | boards / profiles |
| `#fbbf24` | `DebugOverlay.jsx`, `buildingDetail/Header.jsx`, `ResultsPage.jsx` | building (DebugOverlay = dev-only, skip) |
| `#f43f5e` | `profile/ArticleCard.module.css`, `profile/BioPersonaFlipCard.jsx`, `buildingDetail/Header.jsx`, `LikedProjectsPage.jsx` | profiles / building / boards |
| `#a78bfa` | `DebugOverlay.jsx` | dev-only, skip |

**C. Token values hardcoded** (the literal equals a token's value — swap to the `var()`):
`#D73A49` → `var(--color-destructive)` (7 files) · `#0969DA` → `var(--accent-1)` (4) · `#8250DF` → `var(--accent-2)` (4) · `#F6F8FA` → `var(--color-surface)` (2) · `#8C959F` → `var(--color-text-dim)` (2).

**D. Gradient CTA → flat `var(--accent-1)`** (decision ⑤), 30 sites across 21 files after PR-1: `App.jsx`, `Button.module.css`, `CalibrationChat.module.css`, `profile/BoardCard.jsx`, `SaveBoardModal.module.css`, `SaveToBoardModal.jsx` ×2, `ShareCardModal.jsx`, `SurpriseBoardModal.jsx` ×2, `ThemePreviewCard.jsx`, `ArchitectProfilePage.jsx` ×2, `AssessmentPage.module.css` ×2, `BoardDetailPage.jsx`, `BoardReportPage.jsx`, `firmProfile/FirmProfileHero.jsx` ×2, `LLMSearchPage.jsx`, `PeopleDiscoveryPage.module.css` ×2, `SwipePage.jsx` ×2, `UploadWorkPage.jsx`, `UploadWorkPage.module.css` ×2, `userProfile/ProfileHero.jsx`, `UserProfilePage.jsx` ×2.
Only convert CTA **backgrounds** — check each site; the gradient stays legal on decorative surfaces. `ThemePreviewCard.jsx` needs the same scrutiny as `AppearanceSettings.jsx` (it may be showing a theme sample deliberately).

**E. Hardcoded English UI strings.** PR-1 found axis labels frozen in English. Each PR must check its pages for user-visible text not routed through `t()`.

**F. Theme-frozen hex** — scan found **zero** outside `AppearanceSettings.jsx` (intentional, exempt). No action.

## 6d. Cross-cutting questions raised by the mocks (NOT per-page decisions)

Surfaced during page PRs, deliberately not acted on. Each needs a single global decision from the user; a page PR must never resolve one unilaterally.

1. ~~Every page header reads "Archibe"~~ **RESOLVED — user 2026-08-29: INTENTIONAL. Port it.** The mock's top-of-page 20px two-tone `<h1>` occupies the exact same slot, with the same styles, as the app's current per-page title (Discovery renders `Disc|overy`). The user's instruction: **the Archibe logo should be visible at the top of every page.** Routes/URLs and page identity are unaffected — only this visual title slot.
   - **The maker's reasoning was inverted and I accepted it**: "36 of 37 boards are identical, therefore template chrome." The uniformity was the *evidence of intent*, not evidence of an artifact. Recorded as a lesson — see §6b.
   - **Scope: this is a cross-page change and gets its OWN PR** (`feature/claude-design-logo-header`), not a line in each page's PR — otherwise the pages drift out of sync. Every page that renders a two-tone page-title `<h1>` in that slot converts to `Arch|ibe`. `board-detail.html` is the one board without it — check what it does before assuming.
   - Untouched: the uppercase `ARCHIBE` *wordmark* on cards (`LoginPage`, `SwipePage`, `CardSkeleton`) — different element, different role.

2. ~~`DiscoveryTriggerCard` retheme~~ **RESOLVED — user 2026-08-29: the in-card design change was INTENTIONAL. Port it.**
   - **The "paper look is theme-independent, do not touch" objection was WRONG**, and it was based on a file mix-up. `components/cardLanguage.js` defines `PAPER = 'var(--color-surface)'` and `INK = {strong: 'var(--color-text)', …}` — **all theme tokens**; its own header says "theme-adaptive … inverts correctly across all 4 app themes." The genuinely theme-independent file is a *different* one, `components/profile/BusinessCard.jsx` ("hardcoded white-paper-always, an intentional printed-artifact exception"). "Paper card" names a business-card-shaped *layout* (surface + border + shadow + wordmark), not a fixed palette.
   - Actual mock delta, verified: the card **drops its top row** — the `ARCHIBE` wordmark and the `10 LIKES` mono stamp. Title, body copy, and both swipe affordances are unchanged. So this is element removal, not a retheme.
   - Belongs to the discovery PR's scope; PR-2 shipped without it, so it needs a follow-up commit on `feature/claude-design-discovery`.

3. **`DESIGN.md` §1.4 vs §8.10 tension on modal backdrops.** §1.4 calls `--color-scrim` (0.65) "the standard modal / dialog backdrop", but §8.10 separately specs `sheet-backdrop: rgba(0,0,0,0.4)`, and `rgba(0,0,0,0.4)` is what the codebase actually uses everywhere (`DiscoveryPage`, `BoardDetailPage`, `SwipePage`, `UploadWorkPage`, `SaveBoardModal.module.css`) — and what the mocks use too. No scrim tier equals 0.4. Options: add a 5th token at 0.4, or reconcile the two sections. **Until decided, leave `rgba(0,0,0,0.4)` backdrops alone** — converting them one page at a time creates inconsistency.

4. **English copy polish.** `discovery.capReachedCount` interpolates a bare `{n}`, so English renders "50 You've hit the limit…" while Korean reads naturally. Korea-first policy means this is not urgent, but the mocks' English copy is better written throughout. A copy pass is its own task, not part of a color/token port.

5. **Non-surface white literals.** The §6c defect map only catches `rgba(255,255,255,0.0X)` used as a *background*. PR-2 found the same light-theme legibility problem in a **border/spinner track** (`DiscoveryPage.jsx:758`, `rgba(255,255,255,0.2)` on a page-level spinner over `--color-bg`). Later PRs should check borders and outlines too, not just backgrounds.

6. **Sticky glassmorphic header bar → plain in-flow title.** Raised independently by the settings PR after the logo-header PR had already shipped, so it is a *separate* question from §6d item 1. Every mock replaces the app's current `position: sticky` + `backdrop-filter: blur(12px)` header bar (back button · centered 17px/700 title · spacer) with a plain in-flow, **left-aligned 20px/700 `<h2>`** in the content column, and moves "back" to a floating circular button at the canvas top-left. Verified in `settings-account.html`: zero `position:sticky` in the whole board. This touches every page sharing the `.header` / `.headerTitle` pattern (~40 files), and it changes scroll behaviour, not just paint — the title stops following the scroll. **Needs its own decision + PR**, exactly like the logo header. Until then, page PRs leave existing headers alone.


## 7. Open items

- ~~`rgba(99,102,241,…)` indigo~~ **RESOLVED (PR-1)** — Tailwind indigo-500, pre-token legacy. Now `--accent-2` at the same 10%/22% percentages, mirroring the `--accent-1` programs chip.
- ~~`#fff` / on-photo white alpha policy~~ **RESOLVED (PR-1)** — on-photo whites and photo-gradient literals stay literal (image-relative, not theme-relative); `rgba(255,255,255,0.0X)` used as a *surface wash* is a light-theme bug and becomes `--color-tag-bg` or the right surface token. Both rules are in §4.
- ~~Whether any board exploits desktop width~~ **RESOLVED (PR-1, decision ⑥)** — `results.html` pairs `max-width:680px` with `repeat(4,1fr)`, i.e. deliberately narrower tiles (~158px at 1440 vs ~344px uncapped), and 680px is parity with `BoardReportPage`'s existing `.container`. Not desktop-exploitation; it is a centered reading column. Still flag per-PR if a later board differs.
- 4 unfetched overlay boards — fetched lazily per host PR.
- **ayu-light accent-on-background contrast is weak system-wide** (surfaced by PR-1 review, NOT introduced by it). Accent-colored small text on ayu-light's near-white `#FCFCFC` ground measures roughly 2.3–2.5:1, below WCAG AA for small text: `--accent-1` `#FA8D3E` orange ≈ 2.3:1 (the already-shipped `dominant_programs` chip), `--accent-2` `#86B300` olive ≈ 2.5:1 (the `dominant_styles` chip as of PR-1). PR-1 mirrored the existing pattern rather than diverging from it, so this is a pre-existing theme characteristic, not a regression. Fixing it means either darkening ayu-light's accents in `tokens.css` (affects every accent surface in that theme) or giving accent-tinted chips a darker text token — a design-system decision for the user, out of scope for a per-page port PR.
- **PR-1 visual verdict still pending.** The user has not yet run the dev server on this branch. Their eyeball pass is what validates the translation pipeline; amend §3 with whatever it reveals BEFORE fanning out to PR-2+.
- `LikedOfficesPage.jsx` is a confirmed orphan (imported, never rendered; `/my/liked-offices` is a redirect). Out of scope for this initiative; noted in case it surfaces during the profiles PR.

---

## 8. Visual verification harness (built 2026-08-29)

The user's insight: correctness = "does the page look like its board?" That is checkable, not a matter of taste.

- **Mocks are served by the dev server.** All 37 boards copied to `frontend/public/__mocks/` (gitignored). Reachable at `http://localhost:5173/__mocks/<board>.html`.
- **Side-by-side harness**: `http://localhost:5173/__mocks/_compare.html` — pick a board, it loads the mock on the left and the mapped app route on the right; overlay mode with an opacity slider for pixel-diffing. Board→route map (including which page hosts each overlay) lives in that file.
- **Port matters**: the backend's `CORS_ALLOWED_ORIGINS` allows only `5173,5174`, so the dev server MUST run on 5173 (`npm run dev -- --port 5173 --strictPort`) or dev-login fails with a bare "Failed to fetch". A concurrent session holding 5174 can push Vite to 5175 silently — check the port before debugging auth.
- **`file://` URLs are blocked** by the browser tooling; serving through Vite is the way to view a mock.

**This immediately caught what static reading missed:** `login.html` does not merely swap the card's title for a logo — it moves the wordmark AND the language toggle *out of the card* to page level, and drops the card's `<h2>`. PR-3's maker read the static HTML and concluded the language switcher was being deleted (a functionality loss it correctly refused). Overlaying the two renders showed it relocating instead. **Compare renders, not markup.**

## 9. Remaining work — defect counts per PR group

Measured 2026-08-29 with whitespace-tolerant greps, on top of the base branch:

| PR group | Defect sites | Notes |
|---|---|---|
| profiles | 25 | heaviest: `profile/BoardCard.jsx` 6, `firmProfile/FirmProfileHero.jsx` 4, `profile/BioPersonaFlipCard.jsx` 4 |
| boards | 17 | |
| search | 5 | |
| upload | 4 | |
| swipe | 4 | plus `layouts/MainLayout.jsx`; the only group needing app-test FULL |
| building | 3 | |
| settings | 0 | clean — pure mock-delta port |

## 10. Reading design-diff output — what is signal, what is not

`tools/design-diff.py` renders each mock and the matching app route and diffs computed styles. Its findings are not all real. Triage before dispatching:

**Real, act on it**
- A control the mock has and the app has nowhere (verified by grepping the component tree, not by trusting the tool). The top-right language/theme cluster was this: 42 boards, genuinely absent.
- A control the app has only on the success branch. The tool renders unseeded, so it lands in loading/error branches — that is how it caught three pages where a logged-in user had no way to log out while data was in flight. Invisible to a static read.
- A property value that differs and has no data explanation: the settings titles at 17px against the mock's 20px.

**Not real, skip and say why**
- **Placeholder data.** Mocks are populated with 김아키, `@archibe_user`, "Kanazawa 21st Century" and similar. An unseeded or differently-seeded app reports all of it as missing text. This is most of the raw count.
- **Data-gated controls.** `profile`'s 14×14 Instagram/email icons read as missing, but `userProfile/ProfileHero.jsx` renders them from `user.external_links` — the test account simply has none. Check whether the feature exists before calling it absent.
- **Geometry.** The mock is a fixed 1440×900 canvas; the app is fluid. Position and size differences are by design, which is why the tool does not compare them.
- **Element-matching artifacts.** Fixed once already (labels wrapped in a styleless `<span>` were compared against the app's `<button>`), but assume more remain.
- **Mocks copying existing bugs forward.** `font-weight: 800` appears in several boards; DESIGN.md §2.5 caps weight at 700. The mock reproduced a violation rather than prescribing one.

**Rule of thumb**: a *missing control* is worth investigating; *missing text* is usually placeholder noise. Verify each finding against the component before acting — the tool locates candidates, it does not adjudicate them.
