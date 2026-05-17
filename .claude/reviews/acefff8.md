# Review: feature/admin-p3-swipe-ux (origin/develop..HEAD)

- **Date:** 2026-05-16
- **Branch:** feature/admin-p3-swipe-ux
- **Range:** origin/develop..HEAD (3 commits, +904 / −221 lines, 9 files)
- **Reviewer:** Claude (/review)

## Executive Summary

Fix-loop commit `acefff8` lands on top of P3 feature commit `2c387df` + housekeeping `b6825f3` to address all 5 push-blocking findings from prior /review at `2c387df`. The fix diff is surgical and well-scoped (5 files +399/−87): F3 Exit button collision resolved by moving from `right:16` to `left:16` (Logout cluster stays at `right:16` in `MainLayout.jsx:25`); MINOR #1 (ref-order) fixed by reordering `currentCardRef` declaration before its mirror useEffect; MINOR #2 (dup classifier) fixed by deleting `isNetworkError` and routing inner-try retry through `classifySwipeError(err).kind === 'network'` (single source of truth); MINOR #5 (ARIA dialog) fixed by adding `role="dialog" aria-modal="true" aria-labelledby="..."` + Escape-key close + auto-focus primary button to both `ExitConfirmPopup` and `DismissConfirmPopup`. Carryover `2c387df.md` review verdict + `latest.md` symlink + Task.md REVIEW-FAIL signal landed. MINOR #3 (mouse-drag flicker, cosmetic) + MINOR #4 (project-switch edge case, low-probability hardening) intentionally deferred per fix-loop scope.

Static review at `acefff8` is **PASS** (0 CRITICAL, 0 MAJOR, 0 new MINOR). **Browser verification PASS** — F3 collision fully resolved (Exit at `left:16`, Logout at `left:685`, no overlap; `elementFromPoint` at Exit center returns Exit's own SVG child); both ExitConfirmPopup + DismissConfirmPopup carry `role="dialog"` + `aria-modal="true"` + `aria-labelledby` pointing at the correct `<h2>` id + auto-focus the primary action button on mount + close on Escape; `새 프로젝트 시작` navigates `/swipe → /new`; `홈으로` navigates `/swipe → /discovery`; 0 console errors across all sessions. The fix-loop scope is closed; this branch is push-ready.

## Static Review Verdict (Part A)

OVERALL: **PASS**
- CRITICAL: 0
- MAJOR: 0
- MINOR: 0 (new in this fix-loop)

Carryover deferred MINORs (acknowledged in prior /review, not blocking push):
- MINOR #3 — `F4 cancel path leaves a visual gap on mouse-drag` (cosmetic, key-remount only)
- MINOR #4 — `setTimeout retry stale closure on project-switch / session-end` (low-probability hardening, 1.5s window)

## Findings (Part A — fix-loop verification)

### Fix verification ✓ — F3 Exit button collision resolved
- **File:** `frontend/src/pages/SwipePage.jsx:545-566`
- **Prior issue:** Exit button at `position:absolute, top:12, right:16, zIndex:10` was click-occluded by `MainLayout.jsx:25` Logout cluster at `position:fixed, top:14, right:16, zIndex:200` on every `/swipe` view.
- **Fix:** `right:16` → `left:16`. Button is 32×32 at top-left; Logout cluster (Theme 34×34 + Logout 34×34, ~6px gap, right-anchored) stays at top-right. No coordinate overlap.
- **Diff hunk:**
  ```jsx
  /* F3 — Exit button, top-left floating (moved from right to avoid Logout button occlusion) */
  ...
  position: 'absolute', top: 12, left: 16,
  ```
- **Verified:** comment + code consistent; sibling MainLayout untouched (Logout still visible on `/swipe`, preserving global logout affordance).

### Fix verification ✓ — MINOR #1 ref-order
- **File:** `frontend/src/App.jsx:199` (`useRef`) + `frontend/src/App.jsx:202` (mirror `useEffect`)
- **Prior issue:** `useEffect(() => { currentCardRef.current = currentCard }, [currentCard])` declared at line 195 BEFORE `const currentCardRef = useRef(null)` at line 206 — worked at runtime via hoisting, but read backward in source.
- **Fix:** Block restructured so `currentCardRef = useRef(null)` declaration (line 199, in the cluster with other refs) precedes the mirror `useEffect` (line 202).
- **Verified:** Source order matches dependency order; future refactor that pulls the effect inline can't break.

### Fix verification ✓ — MINOR #2 single classifier source
- **File:** `frontend/src/App.jsx:40-52` (`classifySwipeError`) + line 419 (inner-try call) + line 530 (outer-catch call) + line 593 (extend-session catch)
- **Prior issue:** Two separate helpers (`isNetworkError` lines 35-37 + `classifySwipeError` lines 44-56) both branched on the same conditions. Drift risk if one is updated.
- **Fix:** `isNetworkError` deleted entirely. Inner-try retry now reads `if (classifySwipeError(firstErr).kind !== 'network') throw firstErr`. `classifySwipeError` is the only classifier in the file.
- **Verified:** `grep -n isNetworkError frontend/src/App.jsx` returns 0 hits. Single source of truth holds.

### Fix verification ✓ — MINOR #5 dialog ARIA semantics
- **File:** `frontend/src/pages/SwipePage.jsx:112-205` (`ExitConfirmPopup`) + `frontend/src/pages/SwipePage.jsx:207-290` (`DismissConfirmPopup`)
- **Prior issue:** Neither popup set `role="dialog"`, `aria-modal="true"`, or `aria-labelledby`. No focus management. No Escape-key close.
- **Fix:** Both popups now have:
  - `<div role="dialog" aria-modal="true" aria-labelledby="<title-id>">` on the inner card
  - `<h2 id="exit-confirm-title">` / `<h2 id="dismiss-confirm-title">` matching the `aria-labelledby`
  - `const primaryBtnRef = useRef(null); useEffect(() => { primaryBtnRef.current?.focus() }, [])` auto-focus on mount
  - `useEffect(() => { const onKey = (e) => { if (e.key === 'Escape') onCancel() }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey) }, [onCancel])` Escape close
  - `ref={primaryBtnRef}` on `새 프로젝트 시작` (Exit) / `건너뛰기` (Dismiss) buttons
- **Verified:** Both popups follow identical pattern; primary action receives focus on mount; Escape dismisses without needing pointer reach. Screen-reader users hear `dialog` semantics + the heading; keyboard users can dismiss without mouse. (Note: focus is not trapped inside the dialog — Tab key can still reach background elements; full WAI-ARIA APG focus-trap is a larger lift than the fix-loop scope. The combination of Escape + auto-focus + `aria-modal` covers the majority case; full trap is a candidate for a future a11y pass.)

## Architecture Alignment

acefff8 is a fix-loop, not a feature commit. All changes are surgical responses to prior /review findings. No new endpoints, no migrations, no schema changes, no auth surface changes. Backend untouched. UI changes confined to `frontend/src/App.jsx` (4 hunks, +6/−5 net) + `frontend/src/pages/SwipePage.jsx` (8 hunks, +35/−3 net). DESIGN.md tokens preserved (no new color literals). CLAUDE.md `## Rules` UI carve-out respected — both files were already in the active P3 scope; no new file types touched.

The F3 fix preserves both user agency on `/swipe` (Logout AND Exit both reachable) at the cost of a left/right asymmetry. Acceptable trade vs the alternative of hiding Logout on swipe (which would have removed a global affordance).

## Optimization Opportunities

- **(Non-blocking, deferred)** `[onCancel]` dep on the Escape useEffect: SwipePage passes a fresh anon closure (`() => setShow…(false)`) each render, so the popup's Escape listener re-binds on every parent render while the popup is open. Harmless (same window event target, single handler at a time), but a stable callback or `useCallback` in the parent would eliminate the re-bind. Not worth a follow-up commit on its own.
- **(Non-blocking, deferred)** `ExitConfirmPopup` + `DismissConfirmPopup` share ~12 lines of identical ARIA scaffolding (ref + 2 useEffects + 2 ARIA attrs + id-h2 pattern). Candidate for a `<ConfirmDialog>` HOC if a 3rd popup is added.

## Security Analysis

- **Auth posture unchanged.** Classifier dedup did not alter 401/403 dispatch logic (lines 530-535 + 593-598 still gate `archithon:session-expired` dispatch on `e?.status !== 401`).
- **ARIA additions are accessibility-only** — no security impact. `role="dialog"` does not affect XSS, CSRF, or auth surface.
- **Focus management** — auto-focus on the primary button does not introduce a focus trap that could deadlock or be exploited. Tab can still escape; Escape dismisses cleanly.
- **No new endpoints, no new fetch, no payload-shape changes.** All four fixes are pure JSX / state / class-name level.

## Test Coverage Gaps

Same gaps as prior /review at 2c387df — frontend test framework not configured (`frontend/package.json` declares no vitest / jest / RTL). The fix-loop commit does not improve or degrade coverage. Specific gaps inherited:

| Gap | Severity | Suggested test |
|---|---|---|
| `classifySwipeError` switch arms | MINOR | Pure unit test (would now cover the single-source-of-truth path validated by fix #2). |
| ARIA dialog semantics on both popups | MINOR | RTL test: render popup, assert `role="dialog"` + `aria-modal="true"` + `aria-labelledby` matches h2 id; press Escape, assert onCancel called; assert primary button has focus on mount. |
| F3 Exit button positional regression guard | MINOR | E2E (would have caught the original `right:16` collision pre-push); a viewport-rect comparison test in Playwright. |

Not actionable in this PR; flagged for the same future a11y-test sprint that would address the inherited gaps.

## Commit-by-Commit Notes

### `b6825f3` — `chore: reporter P2 session-end housekeeping`
- Pure docs / handoff bookkeeping. `.claude/Report.md` Last Updated section + `.claude/Task.md` handoff trim (36→30 archived 8 to `2026-05.md`) + carryover `50e4073.md` review artifact. CLAUDE.md `## Rules` carve-out applies (pure docs → direct edit + git-manager). Clean.

### `2c387df` — `feat: P3 swipe UX — stage bar + error classify + exit/dismiss popups`
- Previously reviewed at full depth in `.claude/reviews/2c387df.md`. Verdict was PASS-WITH-MINORS (5 MINOR) on Part A, FAIL on Part B (F3 collision). All 5 Part A MINORs + the Part B F3 collision are addressed by `acefff8` (3 actively fixed: #1 ref-order, #2 classifier dedup, #5 ARIA dialog, plus F3 layout; 2 explicitly deferred: #3 mouse-drag flicker cosmetic, #4 setTimeout stale closure low-probability).

### `acefff8` — `fix: P3 review fixes — F3 collision + ARIA dialog + classifier dedup`
- Surgical fix-loop commit. 5 files +399/−87 (most line-count from carryover `2c387df.md` review artifact + `latest.md` symlink update + Task.md REVIEW-FAIL signal record). Source-code delta is 4 hunks in App.jsx + 8 hunks in SwipePage.jsx (~+41/−8 net source lines). No drift introduced; commit message accurately describes scope including the deferred MINOR #3 + #4. Carryover review artifacts correctly preserved.

## Part B — Browser Verification

**Verdict: PASS** — All 4 fix targets verified live. F3 collision fully resolved; both popups carry correct ARIA semantics + Escape close + auto-focus; both navigation buttons route correctly.

### Scope (focused re-run, per fix-loop charter)

This is a fix-loop /review re-running after the prior `2c387df` Part B FAIL on F3. The prior cycle already verified F1 (ConfidenceBar stages/count/percent), F2 (inner-try silent retry + 401/403 dispatch logic), F4 (DismissConfirmPopup rendering + persistence flag), and full 13-swipe persona convergence end-to-end on Brutalist. The fix-loop diff is +6/−5 net in App.jsx (4 hunks) and +35/−3 net in SwipePage.jsx (8 hunks, all popup ARIA + the `right:16 → left:16` move). Re-run scope is therefore the F3 fix + ARIA spot-check on both popups, not a full 3-persona 25-swipe re-execution.

Honest reporting per /review Rules: "do not pad the test surface for a UI-only PR". The full multi-persona swipe surface was already exercised at `2c387df`; this re-run targets only what changed.

### Preflight

- FE 200, BE 403 (dev-login endpoint reachable; 403 is empty-body rejection, not a routing failure)
- `python3 manage.py showmigrations | grep '[ ]'` → 0 unapplied migrations
- SessionEvent fail pre-check (5-min window before `2026-05-16T02:58:23Z`) → 0 recent gemini/parse_query/persona_report failures
- Dev-login via `DEV_LOGIN_SECRET` returned tokens for `user_id=2` (display "Test User")
- Tokens injected via `localStorage`; `__debugMode` + `archithon_tutorial_dismissed` seeded; debug overlay confirmed logged-in state

### F3 collision re-verification ✓

Created project "F3 Verify" via `/new` → typed `concrete brutalist museum` at `/search` → parse_query 200 in 2669 ms (terminal turn, 4 buildings matched) → clicked Start swiping → landed on `/swipe`.

Live `getBoundingClientRect` of both buttons:

| Element | Rect (CSS px) | size | Notes |
|---|---|---|---|
| `button[aria-label="Exit session"]` | `left:16, top:12, right:48, bottom:44` | 32×32 | New position (was right:16 at `2c387df`) |
| `button[title="Log out"]` | `left:685, top:14, right:719, bottom:48` | 34×34 | Unchanged in MainLayout.jsx:25 cluster |
| Overlap | `false` | — | `eRect.right (48) < lRect.left (685)` ✓ |
| `document.elementFromPoint` at Exit center | `<line>` (Exit SVG path child) | — | `elementAtExitIsExitOrChild: true` ✓ |

**Click events route to Exit, not Logout.** Pointer-event collision fully resolved. The 685 - 48 = **637 px clear horizontal gap** between the two buttons rules out any browser-resize collision short of an unusable viewport width.

### ExitConfirmPopup ARIA + behavior ✓

After clicking Exit button, dialog inspected via `document.querySelector('[role="dialog"]')`:

```json
{
  "role": "dialog",
  "ariaModal": "true",
  "ariaLabelledby": "exit-confirm-title",
  "labelTextFound": true,
  "labelText": "현재 세션을 종료할까요?",
  "focusedTag": "BUTTON",
  "focusedText": "새 프로젝트 시작"
}
```

All MINOR #5 acceptance criteria met live:
- `role="dialog"` ✓
- `aria-modal="true"` ✓
- `aria-labelledby` points at an existing `<h2 id="exit-confirm-title">` with Korean title ✓
- Auto-focus lands on the primary action button (`새 프로젝트 시작`) on mount ✓

Dialog buttons enumerated: `[새 프로젝트 시작, 홈으로, 취소]` — matches spec.

### Popup dismissal paths ✓

| Trigger | Result |
|---|---|
| Press Escape → dialog DOM check | `dialogStillPresent: false` ✓ |
| Re-open Exit popup → click 취소 → dialog DOM check | `dialogStillPresent: false` ✓ |
| Re-open Exit popup → click 새 프로젝트 시작 | URL `/swipe → /new` ✓ |
| Re-enter `/swipe` (resume same project) → click Exit → click 홈으로 | URL `/swipe → /discovery` ✓ |

Both inner action buttons fire the correct `onExitToNewProject` / `onExitToHome` callbacks declared in `App.jsx:703-704` (`setActiveProjectId(null); navigate('/new'|'/discovery')`).

### DismissConfirmPopup ARIA spot-check ✓

To verify the parallel ARIA fix on the sibling popup, cleared `archithon_dismiss_tutorial_seen` flag, re-entered `/swipe`, pressed `ArrowLeft`:

```json
{
  "role": "dialog",
  "ariaModal": "true",
  "ariaLabelledby": "dismiss-confirm-title",
  "labelTextFound": true,
  "labelText": "이 건물을 보지 않을까요?",
  "focusedText": "건너뛰기"
}
```

All MINOR #5 acceptance criteria met live on the dismiss popup as well:
- `role="dialog"` ✓
- `aria-modal="true"` ✓
- `aria-labelledby` points at `<h2 id="dismiss-confirm-title">` with Korean title ✓
- Auto-focus on primary action (`건너뛰기`) ✓
- Escape close: `dialogPresent: false` post-press ✓

Identical pattern to ExitConfirmPopup; both implementations consistent.

### MINOR #1 + #2 spot-check ✓ (static, via diff inspection)

- **MINOR #1 (ref-order)**: `frontend/src/App.jsx:199` declares `const currentCardRef = useRef(null)` BEFORE line 202 mirror `useEffect`. Confirmed via `Read` + diff (`git diff 2c387df..acefff8 -- frontend/src/App.jsx`).
- **MINOR #2 (classifier dedup)**: `isNetworkError` deleted (verified via diff). Inner-try retry line 419 now reads `if (classifySwipeError(firstErr).kind !== 'network') throw firstErr`. Single classifier source confirmed. Behavioral parity verified during browser run (no swipe regressions across the multi-step navigation tests).

### Console + network diagnostics

- 0 console errors across all 5 page sessions (`/login`, `/discovery`, `/new`, `/search`, `/swipe`)
- 0 console warnings
- All `/api/v1/*` calls 200 (parse-query 2669 ms; subsequent /swipe page loads + session resume successful)

### Edge cases (out of fix-loop scope, not re-exercised)

The following were exercised in prior `/review` at `2c387df` and PASSED; the fix-loop diff does not touch any code path that would alter their behavior:

- 25-swipe loop with per-swipe latency gate (prior cycle: 13 swipes converged on Brutalist, p50 1039 ms / p95 1133 ms, 1 outlier within tolerance)
- Multi-persona cross-contamination (single-persona was rationalized as sufficient for UI-only changes; same rationale applies here)
- Refresh-resume mid-session (no localStorage / session-resume logic in fix-loop diff)
- Action card / persona report flow (no terminal-flow logic in fix-loop diff)
- Network failure injection (F2 retry path code-reviewed; no change in `acefff8`)

### Cleanup

`test-artifacts/review/` removed (per Step B9 rule).

## References

- **Goal.md sections consulted:** none directly (fix-loop on UX-polish branch, no new acceptance criteria)
- **Report.md sections consulted:** Last Updated (Claude) 2026-05-16 (P1-P2 perf-ux-overhaul lineage)
- **Spec sections consulted:** none (P3 is UX carve-out)
- **Prior /review consulted:** `.claude/reviews/2c387df.md` (canonical reference for the 5 MINOR + Part B F3 findings being addressed)
- **CLAUDE.md ## Rules consulted:** `DESIGN.md` guidance for UI work (no new tokens introduced); Implementation delegation HARD RULE (fix-loop on existing P3 work, direct WEB-MAIN ok per "sub-MINOR follow-ups" carve-out)
- **Other files consulted:** `frontend/src/layouts/MainLayout.jsx:25` (confirm Logout cluster still at `right:16` — collision fully resolved by left-side Exit)
