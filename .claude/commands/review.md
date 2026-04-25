---
description: Unified pre-push review of the unpushed range. Static 7-axis deep review + (conditional) strict browser verification + HEAD/origin/main drift checks. Emits one of REVIEW-PASSED / REVIEW-ABORTED / REVIEW-FAIL to Task.md Handoffs. Invoked via `/review` or natural language ("리뷰해줘", "review", "검토해줘" — see CLAUDE.md "Natural language review trigger").
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, mcp__playwright__browser_navigate, mcp__playwright__browser_click, mcp__playwright__browser_type, mcp__playwright__browser_screenshot, mcp__playwright__browser_snapshot, mcp__playwright__browser_evaluate, mcp__playwright__browser_close, mcp__playwright__browser_press_key, mcp__playwright__browser_wait_for, mcp__playwright__browser_network_requests, mcp__playwright__browser_console_messages
argument-hint: "[range]"
---

You are now acting as the dedicated **pre-push review terminal** for this session. This
is the single canonical pipeline that gates `git push`. It combines:

- **Part A — Static deep review** (7 axes, slow retrospective analysis, writes report)
- **Part B — Browser deep web test** (strict spec-aligned UX verification — runs only when UI-affecting paths are in scope; skipped otherwise)
- **Part C — Drift checks + final verdict** (HEAD + origin/main drift; emits one signal to Task.md Handoffs)

Do not modify source code. Do not commit. Do not push — on the final `REVIEW-PASSED`,
the user runs `git push` manually from this same terminal.

This pipeline is **complementary**, not a replacement, for the fast `reviewer` and
`security-manager` subagents that run inside the orchestrator pipeline. Those produce
PASS/FAIL commit gates on API contracts, logic bugs, and obvious security issues. You
do the slow analysis they explicitly skip (refactoring, optimization opportunities, test
coverage, cross-commit drift, architecture alignment) PLUS the strict browser
verification they don't do at all.

## Boundary

- **Read-only on source code.** Backend / frontend / docs / `research/` are READ-ONLY.
- **`research/` is strictly READ-ONLY** (all subdirectories: `research/spec/`,
  `research/search/`, `research/investigations/`, `research/algorithm.md`). The reporter's
  narrow exception for `algorithm.md` does NOT apply to this command. You may read any
  file under `research/` for context (spec, ground truth, prior research) but never
  write, create, modify, delete, or stage. See CLAUDE.md `## Rules`.
- The only permitted writes are:
  - `.claude/reviews/<sha_short>.md` and `.claude/reviews/latest.md` (the unified report)
  - One handoff line in `.claude/Task.md ## Handoffs` (Part C exit signal)
  - Transient artifacts under `test-artifacts/review/` during Part B (cleaned before exit)

## Argument handling

If the user provided an argument after `/review` (or after their natural-language
phrase), use it as the git revision range (e.g. `HEAD~5..HEAD`, `<sha>..<sha>`).
Otherwise default to `origin/main..HEAD` — the unpushed commits on the current branch.
This makes the workflow a true **push gate**: it reviews exactly what would go public on
`git push`.

---

# Part A — Static Deep Review

## Step A1 — Establish scope

First, refresh the remote tracking ref (non-fatal if offline):

- `git fetch origin main --quiet 2>/dev/null || true`

Validate that the range's left-hand side resolves to a commit before running scope
commands (abort on typo or missing ref):

```bash
RANGE_LHS="${range%%..*}"   # strip everything from first '..'
git rev-parse --verify "$RANGE_LHS" >/dev/null 2>&1 || {
  echo "REVIEW: invalid range — '$RANGE_LHS' does not resolve to a commit."
  exit 1
}
```

Then run these git commands (via Bash) and capture output:

- `git rev-parse --abbrev-ref HEAD` → branch name
- `git rev-parse --short HEAD` → sha_short (for display)
- `git rev-parse HEAD` → **REVIEWED_SHA** (full SHA — stash this for the Part C HEAD-drift check)
- `git rev-parse origin/main` → **REVIEWED_ORIGIN_MAIN** (full SHA — stash this for the Part C remote-drift check; non-fatal if `origin/main` is absent offline, in which case record `UNAVAILABLE` and skip remote-drift check in Step C2)
- `git log <range> --oneline` → commit list (two-dot is correct here)
- `git diff <range_three_dot> --stat` → file scope + insertion/deletion counts
  (convert the range's `..` to `...` for divergent-history safety; on linear history this is equivalent)
- `git log <range> --format='%h %s (%an, %ad)' --date=short` → detailed commit metadata

If the log is empty (no unpushed commits), abort with exactly:

`REVIEW: nothing to review — HEAD matches origin/main. No report written.`

and exit without writing any file.

## Step A2 — Read changed files

- Run `git diff <range_three_dot> --name-only` to get the file list (three-dot for divergent-history safety). **Stash this list as `CHANGED_FILES` — Part B will inspect it for UI-affecting paths.**
- For each file: `Read` the full file — context beats isolated hunks for architecture analysis.
- For files > 1000 lines: use `git diff <range_three_dot> -- <file>` to find touched regions, then `Read` with `offset` / `limit` to read those regions ±80 lines.
- Also read for grounding:
  - `.claude/Goal.md` → acceptance criteria
  - `.claude/Report.md` → System Architecture + Algorithm Pipeline sections
  - `research/spec/requirements.md` → spec sections relevant to changed code
  - Any file referenced from changed files (e.g. `research/algorithm.md` if `engine.py` changed)

## Step A3 — Apply the 7-axis checklist

Reason carefully, one axis at a time. This is slow retrospective review, not a PASS/FAIL gate. Use severity **CRITICAL / MAJOR / MINOR**.

1. **Architecture alignment** — Do changes match Goal.md acceptance criteria and Report.md's System Architecture? Are new modules/layers justified? Any drift from established patterns (raw SQL on `architecture_vectors`, inline-style React components, trailing slashes on URLs, `building_id` as canonical key)?
2. **Correctness & logic depth** — Edge cases, race conditions, async/await correctness, state-machine integrity, off-by-one, null/undefined paths, idempotency, concurrent-request safety, transaction boundaries.
3. **Performance & optimization** — Beyond "obvious N+1": algorithmic complexity, caching opportunities (and cache key correctness), allocation patterns, DB query shape, unbounded loops, repeated work across requests, image/asset handling, JWT refresh storm risks.
4. **Security in depth** — Auth flow integrity, token lifecycle, input validation at system boundaries (not just keyword scans), CSRF/CORS/rate-limit posture, SSRF risks, information disclosure in errors, dependency supply-chain, authorization (not just authentication), access control on IDOR-prone endpoints.
5. **Code quality** — Cyclomatic complexity, duplication, naming clarity, abstraction appropriateness, dead code, inappropriate comments (explaining *what* vs *why*), consistent error-handling idioms.
6. **Test coverage** — Which new paths are untested? Which edge cases lack assertions? Is any change integration-test-worthy? Existing pytest suite lives at `backend/tests/`; flag gaps.
7. **Cross-commit drift** — Patterns introduced across ≥2 commits that would not be visible in a single-commit review. Rushed refactors. Temporary shims likely to calcify. Accumulated complexity without compensating cleanup.

## Step A4 — Write the static-review report

Create the output directory if needed: `mkdir -p .claude/reviews`

Write the report to **both** `.claude/reviews/<sha_short>.md` and `.claude/reviews/latest.md` (identical content). Leave a placeholder for the Part B section — you'll append browser-test results there at the end of Part B.

### Report format

```markdown
# Review: <branch_name> (<range>)

- **Date:** YYYY-MM-DD
- **Branch:** <branch_name>
- **Range:** <range>  (N commits, +X / -Y lines, F files)
- **Reviewer:** Claude (/review)

## Executive Summary
<2-3 sentences: overall verdict, top theme of findings, browser-test plan (Part B run / skipped / pending).>

## Static Review Verdict (Part A)
OVERALL: PASS | PASS-WITH-MINORS | FAIL
- CRITICAL: <count>
- MAJOR: <count>
- MINOR: <count>

## Findings (Part A)

### 1. [CRITICAL|MAJOR|MINOR] <Short title>
- **File:** path/to/file.py:42
- **Axis:** <axis number and name>
- **Issue:** <what's wrong, concretely>
- **Why it matters:** <consequence>
- **Suggested fix:** <how to address>

<repeat per finding, ordered by severity then axis>

## Architecture Alignment
<Prose: does the branch match Goal.md and Report.md? Any drift?>

## Optimization Opportunities
<Enumerated non-blocking perf improvements with rationale.>

## Security Analysis
<In-depth walk of the auth/token/input-validation/authorization surface touched by this branch.>

## Test Coverage Gaps
<Specific untested paths with severity.>

## Commit-by-Commit Notes
### <sha_short> <commit message>
- <1-3 bullets per commit: what it did well / what raises questions>

## Part B — Browser Verification
<placeholder; will be filled in by Step B9 with PASS/FAIL + per-gate breakdown,
or "skipped — no UI-affecting paths in scope" if Part B did not run>

## References
- Goal.md sections consulted: <list>
- Report.md sections consulted: <list>
- Spec sections consulted: <list>
- Other files consulted: <list>
```

## Step A5 — Print the static-review summary line

Emit to stdout:

`STATIC REVIEW: <OVERALL verdict> — <N> CRITICAL, <M> MAJOR, <K> MINOR. Report: .claude/reviews/latest.md`

## Step A6 — Branch on Part A verdict

- **FAIL** (CRITICAL ≥1 OR MAJOR ≥1): SKIP Part B and Part C drift. Jump straight to Step C3 to emit `REVIEW-FAIL` and STOP. The browser test would be wasted effort on broken code.
- **PASS / PASS-WITH-MINORS**: continue to Part B's path-detection gate.

---

# Part B — Browser Deep Web Test (conditional)

Only runs when Part A passed (PASS or PASS-WITH-MINORS) AND `CHANGED_FILES` from Step A2 contains at least one UI-affecting path.

## Step B0 — UI-affecting paths gate

Inspect `CHANGED_FILES` (the file list from Step A2) for any of these patterns:

**UI-affecting (run Part B if any present):**
- `frontend/**` — any frontend file
- `backend/apps/recommendation/views.py` — swipe / session / project endpoints
- `backend/apps/recommendation/engine.py` — algorithm semantics the swipe UI depends on
- `backend/apps/accounts/**` — auth / login flow
- `backend/config/urls.py` — URL routing exposed to the client
- `backend/apps/recommendation/migrations/**` — DB schema affecting reads from the UI
- `backend/config/settings.py` if the diff touches the `RECOMMENDATION` dict (algorithm hyperparameters that change runtime behavior the UI exercises)

**Non-UI (these alone do NOT trigger Part B):**
- `.claude/**`
- `*.md` outside source code (CLAUDE.md, GEMINI.md, DESIGN.md, README, etc.)
- `research/**` (read-only for this terminal)
- `backend/tests/**`
- `backend/tools/**`
- `web-testing/**`
- `.gitignore`, `Makefile`, dev-only configs

**If no UI-affecting paths**: skip Part B entirely. In Step A4's report, fill the "Part B — Browser Verification" section with `Skipped — no UI-affecting paths in scope (only docs/config/test/tooling files changed).` Emit to stdout: `BROWSER TEST: skipped — no UI-affecting paths.` Then jump to Part C.

**If UI-affecting paths present**: continue to Step B1 with the matched paths logged.

## Step B1 — Preflight & authentication

### B1a. Artifact directory
```bash
mkdir -p test-artifacts/review
```

### B1b. Dev server health
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5174/
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/api/v1/auth/dev-login/
```
Expect `200` (or `304`) from frontend and `400` from dev-login POST without body. If either fails: Part B FAIL with reason `Local dev server not running. Start frontend (npm run dev in frontend/) and backend (python3 manage.py runserver 8001) before re-running.`

### B1bb. Migration sanity check (pre-launch backstop)

Before spending time on dev-login + browser launch, verify the running dev DB has all
declared migrations applied. This catches the common "migration file shipped but never
applied locally" gap fast (~1 second) rather than letting it surface as a 500 error
mid-test.

```bash
cd backend && python3 manage.py showmigrations 2>&1 | grep -E '\[ \]'
```

- **No output**: all migrations applied; proceed to B1c.
- **Any `[ ]` entry**: Part B FAIL with reason `Unapplied migration detected (<list of [ ] entries>). Run \`cd backend && python3 manage.py migrate\` and restart backend (\`python3 manage.py runserver 8001\`) before re-running /review.`
  - Backend is presumed already running at this point (B1b passed). Even though the
    code reads the new schema correctly via Django ORM after migrate, restarting
    runserver is recommended so cached connection state aligns with the new schema.

This is Tier 2 of the systemic fix from `.claude/reviews/88f0532.md` "Post-test
Addendum" — back-maker.md "After writing > 2. Apply migrations" is Tier 1 (source);
this is the push-gate backstop that catches the gap if back-maker (or a manual edit)
slipped through.

### B1c. Authenticate via dev-login
```bash
DEV_SECRET=$(grep '^DEV_LOGIN_SECRET=' backend/.env | cut -d= -f2)
[ -z "$DEV_SECRET" ] && echo "FAIL: DEV_LOGIN_SECRET not set in backend/.env"
curl -s -X POST http://localhost:8001/api/v1/auth/dev-login/ \
  -H "Content-Type: application/json" \
  -d "{\"secret\":\"$DEV_SECRET\"}"
```
Capture access + refresh + user_id from the JSON response. If 404 → Part B FAIL `dev-login endpoint missing (DEV_LOGIN_SECRET not in env)`. Unlike the fast `web-tester` agent, this command does NOT have a "skip authenticated flows" fallback — if dev-login is unavailable, deep verification cannot proceed, so FAIL hard.

### B1d. Inject tokens + debug overlay
Via `browser_evaluate`:
```js
() => {
  localStorage.setItem('archithon_access', '<access>');
  localStorage.setItem('archithon_refresh', '<refresh>');
  sessionStorage.setItem('archithon_user', '<user_id>');
  localStorage.setItem('__debugMode', 'true');
  localStorage.setItem('archithon_tutorial_dismissed', 'true');
}
```
Reload. Confirm debug overlay shows logged-in state via `browser_snapshot`.

## Step B2 — Network + console diagnostics baseline

Establish a clean baseline before user-flow steps so any new error during the run is attributable to the test, not pre-existing app state.

```bash
node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    storageState: { origins: [{ origin: 'http://localhost:5174', localStorage: [
      { name: 'archithon_access', value: '<access>' },
      { name: 'archithon_refresh', value: '<refresh>' },
      { name: '__debugMode', value: 'true' },
      { name: 'archithon_tutorial_dismissed', value: 'true' },
    ]}]}
  });
  const page = await ctx.newPage();
  const errors = [], requests = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('response', r => requests.push({ status: r.status(), url: r.url(), timing: r.timing() }));
  await page.goto('http://localhost:5174', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  console.log(JSON.stringify({ errors, requests }, null, 2));
  await browser.close();
})().catch(e => { console.error('SCRIPT ERROR:', e.message); process.exit(1); });
" > test-artifacts/review/baseline.json 2>&1
```

Parse `baseline.json`:
- **Strict gate**: `errors.length === 0` else Part B FAIL `pre-existing console errors detected`.
- Record baseline request count + status histogram for delta comparison later.

## Step B3 — Persona scenarios setup

Define **3 persona scenarios** with distinct queries and expected behaviors. Run each in its own browser context (no shared cookies / localStorage) to test multi-session no-contamination.

```js
const PERSONAS = [
  {
    name: 'Brutalist',
    query: 'concrete brutalist museum',
    expected_program: 'Museum',
    min_swipes: 25,
    convergence_expected: true
  },
  {
    name: 'Sustainable Korean',
    query: '한국 친환경 주거 건축',
    expected_program: 'Housing',
    min_swipes: 25,
    convergence_expected: true
  },
  {
    name: 'Bare Query',
    query: 'modern',
    expected_program: null,
    min_swipes: 15,
    convergence_expected: false
  }
];
```

For each persona, execute Steps B4–B7 below. After all 3 complete, run Step B8 (cross-persona aggregation), then Step B9 (cleanup + report append).

## Step B4 — Time-to-first-card latency gate

For each persona, measure **time from NL submit → first card visible** and assert against spec Section 4: `< 3-4s`.

1. Navigate to `/`.
2. Open AI search input (home tab).
3. Inject a fetch interceptor:
```js
() => {
  window.__reviewState = window.__reviewState || {};
  window.__reviewState.t_submit = null;
  window.__reviewState.t_first_card = null;
  window.__reviewState.api_calls = [];
  const origFetch = window.fetch;
  window.fetch = async (...args) => {
    const t0 = performance.now();
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url;
    const res = await origFetch(...args);
    const t1 = performance.now();
    if (url) window.__reviewState.api_calls.push({ url, status: res.status, latency_ms: Math.round(t1 - t0) });
    return res;
  };
}
```
4. Type the persona query and record `performance.now()` as `t_submit` right before submit.
5. Wait for first card to be visible (DOM check: image element with `r2.dev` URL is loaded AND `naturalWidth > 0`). Record this as `t_first_card`.
6. **Strict gate**: `t_first_card - t_submit < 4000` ms (spec target 3-4s; we use 4s as the hard ceiling). For persona `Bare Query`, allow up to **5000 ms** since bare queries widen the pool (Topic 11 / spec C-3).

If gate fails: Part B FAIL with `Persona X: time-to-first-card = Y ms (spec budget 4000 ms)`.

## Step B5 — Swipe lifecycle: 25 swipes with per-swipe latency gate

Inject a fetch interceptor BEFORE the first swipe so every `/swipes/` POST is timed.

For each swipe (i = 1 to 25):
1. Wait for card to be visible (`browser_wait_for` with element selector for the card image).
2. If action card appears, swipe right to accept and break (recording action card reached at swipe i).
3. Otherwise: alternate left/right (i odd → swipe right via ArrowRight key; i even → swipe left via ArrowLeft).
4. Record gesture timestamp `t_gesture` and response timestamp `t_response` from the fetch interceptor.
5. **Strict gate per swipe**: `t_response - t_gesture < 700 ms` (spec target <500ms; 700ms hard ceiling allows for drift). If breached on **2 or more swipes within the run**, Part B FAIL.

After 25 swipes (or earlier if action card fired):
- Collect `__reviewState.api_calls` and compute p50, p95, p99 of swipe latencies.
- Report breakdown.
- **Strict gate**: `p95(swipe_latency) < 700 ms`. p99 outliers up to 1500 ms are warned, not failed.

## Step B6 — Strict state + API shape validation

After the swipe loop, verify state integrity via `browser_evaluate`:

```js
() => {
  const state = window.__reviewState;
  return {
    swipe_count: state.api_calls.filter(c => c.url.includes('/swipes/')).length,
    unique_card_ids: state.cardIds ? new Set(state.cardIds).size : null,
    total_card_ids: state.cardIds ? state.cardIds.length : null,
    phases_seen: state.phases ? [...new Set(state.phases)] : [],
    console_errors: window.__pageErrors || [],
    networking_errors: state.api_calls.filter(c => c.status >= 500 || (c.status >= 400 && !c.url.includes('/auth/'))),
  };
}
```

**Strict gates**:
- `unique_card_ids === total_card_ids` (zero duplicates)
- `phases_seen` contains at least `'exploring'` and `'analyzing'` (transition observed); for personas with `convergence_expected: true`, also `'converged'`
- `console_errors.length === 0`
- `networking_errors.length === 0` (4xx/5xx outside auth-401-refresh path are failures)

If any gate fails: Part B FAIL with detail on which.

### API response shape strict assertion

For each `/swipes/` response, assert these fields are present and not null where applicable:
- `accepted: bool`
- `session_status: string` (in `{exploring, analyzing, converged, completed}`)
- `progress.phase: string`
- `progress.current_round: int`
- `next_image: object | null` (null only at session end)
- `prefetch_image`, `prefetch_image_2: object | null`
- `is_analysis_completed: bool`

Pull a sample from the recorded fetch responses and verify shape. If any field is missing or null where it shouldn't be: Part B FAIL.

## Step B7 — Edge case coverage

### B7a. Refresh-resume mid-session
After ~10 swipes in the first persona, hit `location.reload()`. Verify:
- Session resumes at the same `current_round` (not a new session)
- Same card displayed as before refresh (or one of the prefetch buffer cards)
- No 404 or new-session creation in network log

If session does NOT resume: Part B FAIL `session resume broken on refresh`.

### B7b. Action card flow
For the first persona reaching `converged`:
- Verify action card payload shape (action_card_message, action_card_subtitle, building_id === '__action_card__')
- Swipe right on action card
- Verify navigation to results / completed phase
- Verify session_status transitions to `'completed'`

### B7c. Persona report generation
For the first persona reaching `completed`:
- Click "Generate Persona Report" if button present
- Wait up to 30s for response
- If 200: verify response contains `persona_type`, `description`, `dominant_programs`, etc.
- If 502 (Gemini unavailable in test env): WARN, do not FAIL
- If timeout (>30s): WARN, do not FAIL

### B7d. Network failure injection
For the third persona, inject a one-time fetch failure on `/swipes/`:
```js
() => {
  let blocked = false;
  const orig = window.fetch;
  window.fetch = (...args) => {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url;
    if (!blocked && url?.includes('/swipes/')) {
      blocked = true;
      return Promise.reject(new Error('Injected network failure'));
    }
    return orig(...args);
  };
}
```
Then trigger one swipe. Verify graceful degradation (toast or error UI), then trigger another swipe and confirm it works (recovery).

If the app crashes / blanks the screen: Part B FAIL `network failure handling broken`.

## Step B8 — Spec primary-metric infrastructure sentinel (conditional)

This step verifies the infrastructure for the spec's primary success metric (top-10 bookmark rate) is reachable. Conditional on Sprint 0 A3 having shipped:

1. Read `backend/apps/recommendation/models.py` (READ-ONLY).
2. Check for `saved_ids` field on the `Project` model.
   - If present: proceed to runtime check.
   - If absent: skip with note `Spec metric infrastructure not yet shipped (Sprint 0 A3 pending) — skipped`.
3. If `saved_ids` exists: verify a bookmark endpoint exists by inspecting `urls.py` / `views.py` for a path matching `*/bookmark/` or `*/save/`. If it does:
   - Hit the endpoint with one of the liked building_ids from Step B5.
   - Verify the response is 200 / 201 and the `Project.saved_ids` array has grown by 1.
4. If endpoint does NOT exist but `saved_ids` field does: WARN, do not FAIL.

## Step B9 — Cross-persona aggregation, cleanup, and report append

After all 3 personas complete:
- Aggregate p50 / p95 / p99 across all swipes from all personas.
- Per-endpoint breakdown: `/swipes/` POST, `/sessions/` POST, `/auth/refresh/` POST, static asset GETs.
- Multi-session contamination check: confirm session UUIDs are distinct and that no persona's likes/disliked appear in another persona's `exposed_ids`.
- Optional visual regression: if `test-artifacts/baseline/` exists, run per-image SHA-256 diff. Mismatch → WARN (not FAIL).

Cleanup transient artifacts (preserve user-curated baseline directory if present):
```bash
rm -rf test-artifacts/review
```

Open `.claude/reviews/<sha_short>.md` and `.claude/reviews/latest.md` and **replace** the `## Part B — Browser Verification` placeholder section with the full per-persona + per-gate breakdown (PASS or FAIL with detail). Include latency table, persona summaries, edge-case results, infrastructure sentinel result.

Emit to stdout:

`BROWSER TEST: <PASS|FAIL> — <one-line summary>. Per-persona detail in .claude/reviews/latest.md`

## Step B10 — Branch on Part B verdict

- **Part B FAIL**: jump to Step C3 to emit a unified `REVIEW-FAIL` signal that combines Part A's MINORs (if any) with Part B's failure summary. Skip Part C drift checks (the failure is bigger than concurrent-push concerns).
- **Part B PASS** (or Part B skipped earlier in Step B0 due to no UI paths): continue to Part C.

---

# Part C — Drift checks + final unified verdict

All exit paths converge here. Step C3 emits exactly one line to the `## Handoffs` section at the top of `.claude/Task.md` (via the `Edit` tool). Use today's date (`date +%F`) and the `sha_short` captured in Step A1.

**Insertion rule (applies to all signals below):** insert the new line after any existing handoff entries but before the closing `---` that ends the Handoffs section. If the section still shows `(none yet)`, replace that placeholder with the new entry.

## Step C1 — HEAD-drift check

Skip C1 + C2 if Step A6 / Step B10 routed straight to FAIL.

Re-run `git rev-parse HEAD` and compare to `REVIEWED_SHA` from Step A1. If they differ, a new commit has landed on the local branch during the review — the report no longer describes the push candidate. Compute `<new_sha_short> = git rev-parse --short HEAD` and append to Handoffs:

```
- [YYYY-MM-DD] REVIEW-ABORTED: <sha_short> — HEAD advanced to <new_sha_short> during review; re-run /review
```

STOP. Do not proceed to C2 or C3.

## Step C2 — Remote-drift check

Only run this if Step C1 passed. Refresh the remote tracking ref and re-read:

```bash
git fetch origin main --quiet 2>/dev/null || true
CURRENT_ORIGIN_MAIN=$(git rev-parse origin/main 2>/dev/null || echo "UNAVAILABLE")
```

Skip the comparison if both `REVIEWED_ORIGIN_MAIN` and `CURRENT_ORIGIN_MAIN` are `UNAVAILABLE` (offline throughout — the subsequent user-initiated `git push` will surface any network issue). Otherwise, if `CURRENT_ORIGIN_MAIN ≠ REVIEWED_ORIGIN_MAIN`, someone pushed to `origin/main` during the review. Append:

```
- [YYYY-MM-DD] REVIEW-ABORTED: <sha_short> — origin/main moved during review; pull and re-review
```

STOP. Do not proceed to C3.

## Step C3 — Emit final handoff signal

Append exactly ONE line to `## Handoffs` based on the combined Part A + Part B outcome:

### C3a — Part A FAIL (regardless of Part B)

```
- [YYYY-MM-DD] REVIEW-FAIL: <sha_short> — <N> CRITICAL, <M> MAJOR; see .claude/reviews/latest.md
```

### C3b — Part A PASS but Part B FAIL

```
- [YYYY-MM-DD] REVIEW-FAIL: <sha_short> — static review PASS but browser test FAIL (<one-line cause from Part B>); see .claude/reviews/latest.md
```

### C3c — Both clean (Part A PASS, Part B PASS or skipped, no drift)

Use one of the two variants below depending on whether Part A recorded any MINOR findings (`K` = MINOR count from Step A3):

- **PASS** (clean, `K = 0`):
  ```
  - [YYYY-MM-DD] REVIEW-PASSED: <sha_short> — drift checks passed; run `git push` manually from this terminal
  ```

- **PASS-WITH-MINORS** (`K > 0`):
  ```
  - [YYYY-MM-DD] REVIEW-PASSED: <sha_short> — drift checks passed, <K> MINOR noted (see .claude/reviews/latest.md); run `git push` manually from this terminal
  ```

If Part B was actually executed (UI-affecting paths in scope), the signal is implicitly "browser test PASSED too" — no need to inline this.

The MINOR count travels inline so the human runner sees it without opening the full report. MINORs are non-blocking for push by definition. Follow-up fix commits for MINORs are at the user's discretion.

## Step C4 — Stop

After Step C3 emits the signal, **STOP**. Do not run `git push` yourself — push is always user-initiated. The user stays in this review terminal, reads the one-line signal, and issues `git push`; no context-switch back to the main terminal is needed. If the push surfaces a non-fast-forward reject, network error, auth failure, etc., the user resolves it directly — no follow-up signal from you, no retry by you.

**Note for the human runner:** if `git push` fails non-ff and you recover with `git pull --rebase`, the rebase rewrites local commit SHAs. The `REVIEW-PASSED: <sha_short>` entry above now points to a SHA that no longer exists locally, and the rewritten commits have never been reviewed at their new SHAs. **Re-run `/review` (or just say "리뷰해줘") before retrying `git push`.** Only `REVIEW-PASSED` at the current HEAD's SHA is a valid push ticket.

The main terminal's orchestrator reads the Handoffs section at the start of its next session: `REVIEW-FAIL` and `REVIEW-ABORTED` re-enter the fix loop; `REVIEW-PASSED` closes the cycle.

---

## Rules

- **Be honest.** If the branch is genuinely clean, say so — do not invent problems to pad the report. An honest PASS with a short body is more valuable than a padded report.
- Every Part A finding must cite a file path (+ line number where applicable).
- Do not suggest changes outside the diff scope unless you explicitly flag the suggestion as "out of scope for this branch".
- **Do not commit. Do not push — `git push` is always user-initiated from the review terminal after a `REVIEW-PASSED` signal (drift-verified).** Source code remains read-only. The only permitted writes are `.claude/reviews/*.md` (the report), the handoff line in `.claude/Task.md`'s `## Handoffs` section, and transient `test-artifacts/review/` (cleaned in Step B9).
- **`research/` is strictly READ-ONLY** (including `research/spec/`, `research/search/`, `research/investigations/`, `research/algorithm.md`). The reporter's narrow exception for `algorithm.md` does NOT apply to this command. You may read for context; never write. If commits under review modify `research/` files, flag that as a governance finding (unless the commit was made by the research terminal itself — check git log author/context).
- **No retries on flaky Part B steps.** If a step fails, hard-fail and report. The fast `web-tester` retries gestures up to 1×; this command does not. The point is to catch flakiness rather than mask it.
- **Pre-existing console errors fail the run** (Step B2 baseline gate). Do not "subtract" pre-existing errors and only flag new ones — the user shipped a clean app and any console error is a regression target.
- **Auth refresh** (401 → /auth/refresh/ → retry) is allowed and not counted as a network error. All other 4xx/5xx outside the auth path are failures.
- **Bash commands permitted** (Part A): `git log`, `git diff`, `git rev-parse`, `git show`, `git fetch origin main --quiet` (drift checks only), `mkdir -p`, `date`. Part B additionally permits `curl` (dev-server health + dev-login) and `node` (Playwright baseline diagnostics).
- **Do not attempt to "fix" issues** — this command is diagnostic only.
