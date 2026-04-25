# ArchiTinder -- Agent Workflow

> **Read this when:** You want to understand how agents work, what triggers what, and when you
> will be flagged for manual review. All 6 workflow cases are covered here.
> For feature status: see `Report.md`. For task status: see `Task.md`. For vision: see `Goal.md`.

---

## Agent Roster

| Agent | Model | Role | Touches |
|-------|-------|------|---------|
| **orchestrator** | opus | Main pipeline supervisor -- plans, delegates, manages fix loops | nothing directly |
| **back-maker** | sonnet | Django/DRF backend code | `backend/` only |
| **front-maker** | sonnet | React/Vite frontend **data layer** (useState, useEffect, callApi, hooks, error handling) | `frontend/` data layer only — UI layer is owned by `designer` |
| **reviewer** | sonnet | API contracts, logic bugs, error handling | read-only |
| **security-manager** | sonnet | SQL injection, auth bypass, XSS, token leaks | read-only |
| **web-tester** | sonnet | Live Playwright browser tests | read-only |
| **git-manager** | haiku | Single commit per task | git only |
| **reporter** | sonnet | Updates Report.md + Task.md, emits REVIEW-REQUESTED handoff | `.claude/` only |
| **algo-tester** | sonnet | Runs optimizer script, interprets results, triggers orchestrator | runs script + calls orchestrator |
| **research** | opus | Explores complex problems, writes to research/ | `research/` only |
| **designer** | opus | **Design pipeline supervisor** — owns DESIGN.md + frontend UI layer + design-* sub-agents (parallel of `orchestrator` for the design terminal). Spawns `design-<role>` sub-agents on demand. | `DESIGN.md`, `frontend/` UI layer (JSX styles, animations, colors, layout, MOCK_*), `.claude/agents/design-*.md`, `.claude/Task.md` Handoffs (MOCKUP-READY append-only) |
| **`/review`** (slash command, no subagent) | opus (review terminal) | **Unified pre-push gate.** Part A: 7-axis static review (writes `.claude/reviews/*.md`). Part B: conditional strict browser verification (3 personas × ≥25 swipes, spec-aligned latency budgets, zero-tolerance error gates, edge cases) when UI-affecting paths in scope. Part C: HEAD + origin/main drift checks. Emits one of REVIEW-PASSED / REVIEW-ABORTED / REVIEW-FAIL to Task.md Handoffs. Invoked via `/review` or natural language ("리뷰해줘", "review", "검토해줘"). | read-only on source; writes `.claude/reviews/` + Task.md Handoffs line + transient `test-artifacts/review/` (Part B, cleaned after run) |

---

## Multi-Terminal Coordination

The project is developed across **four parallel terminals**, each with a focused role and
isolated context window. All terminals work on the `main` Git branch — coordination is by
file/layer ownership + handoff signals in `Task.md`, not branches.

### Terminal Roster

| Terminal | Model | Role | Owns / Touches | Typical signals |
|----------|-------|------|----------------|-----------------|
| **main** | Claude Code (orchestrator: opus) | Full pipeline — backend, frontend integration, E2E tests, commit | `backend/`, `frontend/` (data layer), `.claude/` (excluding anything inside `research/`, and excluding `.claude/agents/designer.md` + `.claude/agents/design-*.md`) | reporter emits `REVIEW-REQUESTED` to Handoffs; consumes `MOCKUP-READY`, `REVIEW-FAIL`, `REVIEW-ABORTED`, `SPEC-UPDATED` from Handoffs; `[SPEC-READY]` from Research Ready section. **READ-ONLY on `research/` and on design-owned paths.** |
| **research** | Claude Code (research agent: opus) | Ongoing algorithm / UX research dialog with user; consolidates findings into `research/spec/requirements.md` (living spec). `research/search/**` deep-dive reports are reasoning archive — accessed directly via filesystem, not via Task.md pointers. | **EXCLUSIVE owner of `research/`** (all subdirectories: `spec/`, `search/`, `investigations/`, `algorithm.md`). Also appends `[SPEC-READY]` to Task.md `## Research Ready` + `SPEC-UPDATED` to `## Handoffs` on version bump. Commits its own research/ changes from its own session. | emits `[SPEC-READY]`, `SPEC-UPDATED` |
| **review** | Claude Code (`/review` slash command: opus) | Unified pre-push gate. Single workflow at `.claude/commands/review.md` invoked via `/review` OR natural language ("리뷰해줘", "review please", "검토해줘"). Runs Part A (static 7-axis review) → Part B (conditional strict browser verification when UI-affecting paths in scope) → Part C (HEAD/`origin/main` drift checks) → emits one unified handoff signal. PASS → user runs `git push` from this terminal. | read-only on source; writes `.claude/reviews/*.md`, the handoff line in Task.md `## Handoffs`, and transient `test-artifacts/review/` during Part B. **READ-ONLY on `research/` and on design-owned paths** (same rule as main). | emits `REVIEW-PASSED` (clean Part A + Part B + drift-verified), `REVIEW-ABORTED` (clean review but drift detected), or `REVIEW-FAIL` (Part A had CRITICAL/MAJOR OR Part B browser test failed) to Handoffs. |
| **design** | Claude Code (designer: opus; spawns `design-*` sub-agents on demand) | Frontend UI/UX iteration — DESIGN.md DNA updates, new mockups, post-integration polish, design-system propagation. Replaces the prior antigravity (Gemini) terminal. | **EXCLUSIVE owner of `DESIGN.md`** + `.claude/agents/designer.md` + `.claude/agents/design-*.md`. Shared owner of `frontend/` on a **per-line layer split** (UI layer = design; data layer = main's front-maker). **READ-ONLY on `research/` and on `backend/`.** Commits its own work directly from this terminal (research analog). | emits `MOCKUP-READY` to Handoffs; drops inline `TODO(claude): ...` markers in source for main pipeline. Consumes reciprocal `TODO(designer): ...` markers from main pipeline. |

> **⚠️ `research/` ownership is absolute, with one narrow exception.** The research terminal is the broad owner of `research/` (`research/spec/`, `research/search/`, `research/investigations/`, and any future subdirectory). Main, review, design, and all their spawned subagents/commands (orchestrator, back-maker, front-maker, reviewer, security-manager, git-manager, algo-tester, web-tester, designer, design-* sub-agents, and the `/review` slash command) are strictly READ-ONLY on `research/`. This is also the user's active study workspace — do not touch.
>
> **Narrow exception**: the `reporter` agent (and only the reporter) may UPDATE `research/algorithm.md` to keep it in sync with implementation — see `reporter.md` Step 6 for the exact scope (Production Value column sync + inline annotations + Last Synced line; no rewriting of theory, no other files). Bookkeeping commits explicitly stage `research/algorithm.md` for this purpose; `git-manager`'s default exclude still applies to all other `research/` paths. See CLAUDE.md `## Rules` for the authoritative statement.
>
> **⚠️ `DESIGN.md` + `.claude/agents/design-*.md` ownership is absolute.** The design terminal (`designer` agent + any `design-<role>` sub-agents it creates) is the exclusive writer of `DESIGN.md` and any `.claude/agents/design-*.md` file. Main, review, and research terminals — and ALL their subagents — are strictly READ-ONLY on those paths. The frontend `UI` layer (JSX styles, animations, colors, layout, `MOCK_*` constants) is design-owned per the layer-split rule below; the frontend `data` layer (useState, useEffect, callApi, custom hooks, error handling, data transformations) remains main pipeline's. See `.claude/agents/designer.md` for the full rules and the reciprocal `TODO(claude):` / `TODO(designer):` handoff markers.

> **Note on Task.md sections:**
> - `## Handoffs` (near top) = short-lived review/mockup signals, rolling window.
> - `## Research Ready` (further down) = research terminal's append-only queue. Do not mix the two.

### Frontend Layer Ownership (designer vs main)

Both the design terminal (`designer`) and main (`front-maker`) edit files under
`frontend/`, so ownership is split **by layer within the same file**:

| Layer | Owner | Allowed edits |
|-------|-------|---------------|
| **UI** | designer | JSX return, `styles` objects, animations, transitions, colors, spacing, `MOCK_*` constants (pre-integration only) |
| **Data / Logic** | main (`front-maker`) | `useState`, `useEffect`, `callApi()`, error handling, data transformations, custom hooks |

Post-integration rules for designer returning to a polished page (full table in `.claude/agents/designer.md`):
- Allowed: JSX structure, styles, animations, colors
- Forbidden: re-inserting `MOCK_*`, editing `useState/useEffect/callApi`, removing `profile?.xxx` optional chaining

**Reciprocal TODO markers** (drop the marker, move on — no cross-terminal sync overhead):

When designer needs behavior that requires API/backend work, it drops `TODO(claude):`:

```jsx
<button onClick={() => { /* TODO(claude): DELETE /api/v1/boards/${board_id}/ */ }}>
  Delete
</button>
```

Main's orchestrator batches these via `grep -r "TODO(claude)" frontend/` during the next
integration session.

When `front-maker` (main) needs a UI change but is data-layer-bound, it drops
`TODO(designer):`:

```jsx
{/* TODO(designer): swap the spinner for a skeleton card here */}
```

Designer batches these via `grep -r "TODO(designer)" frontend/` at the start of each
session.

### Git Discipline

- **All four terminals work on `main` branch.** No feature branches.
- **Always `git pull` before starting a session.**
- **Commit early, commit small** — avoid saving up many changes for one large commit.
  Git's 3-way merge handles most cases when two terminals touched the same file in
  different sections (e.g., designer edited JSX, main edited `useEffect`).
- Only `git-manager` commits from the orchestrator pipeline (one commit per task).
  The **design terminal** commits directly from its own terminal (research analog).
- **Research terminal commits its own `research/` changes** from its own session
  (the research terminal is the ONLY writer of `research/`; main cannot stage them per
  the ownership rule above). If `git status` in the main terminal shows uncommitted
  modifications under `research/`, those belong to the research terminal — leave them
  untouched and unstaged. `git-manager` actively excludes `research/` from staging.
- **Design terminal commits its own `DESIGN.md` and `.claude/agents/design-*.md`
  changes** from its own session. Main's `git-manager` excludes `DESIGN.md` and
  `.claude/agents/design-*.md` from default staging — those belong to the design
  terminal's own commit flow. Frontend `.jsx` files touched on the UI layer by
  designer typically land in design-terminal commits; main's `front-maker`
  data-layer edits to the same files land in main commits. Git's 3-way merge handles
  the per-line split.

### Research ↔ Main: Spec-based Coordination

Research terminal does not ship code or implementation plans to main directly. Instead,
research consolidates findings into a **living spec** at `research/spec/requirements.md`,
versioned via `**Version**: X.Y` in its header.

**Handoff protocol**:
- `[SPEC-READY]` in `## Research Ready` — the primary entry point. Main terminal reads
  `research/spec/requirements.md` when it sees this marker. No per-topic markers are
  published to Task.md; the 12 topic deep-dives at `research/search/**` are reasoning
  archive, accessed directly by filesystem only when main needs deep justification
  behind a Section 11 directive.
- `SPEC-UPDATED: vX.Y → vX.Z — <sections> — <summary>` in `## Handoffs` on every
  non-trivial spec revision. Main terminal reads this at session start to discover
  changes since its last pickup.

**Main's re-read policy** (incremental, not full):
- On session start: scan Handoffs for new `SPEC-UPDATED` entries since last known version.
- If new entries: read only the affected sections in the spec (not the whole document).
- Full re-read is NOT required per task — only when the version bump touches work
  currently in progress.

**When a SPEC-UPDATED invalidates in-progress work**: orchestrator stops, flags the
conflict to the user, does NOT silently continue with the old spec. User decides
whether to finish the current task on the old spec or restart on the new.

**Concurrency (two terminals editing `.claude/Task.md`)**:
- Research appends to `## Research Ready` (or `## Handoffs` for SPEC-UPDATED).
- Main's reporter removes resolved markers from `## Research Ready` as each topic lands.
- Appends to different sections never conflict. Appends to the same section usually
  merge cleanly via git 3-way.
- On merge conflict: one terminal pulls + re-appends. No data loss because both
  terminals work append-only or remove-only.

**What research NEVER does**:
- Does not prescribe task breakdown, sprint ordering, or implementation pacing — those
  are entirely main's judgment. Research documents (like
  `research/spec/research-priority-rebaselined.md`) carry proposed groupings but are
  explicitly non-binding (see its "Authority Boundary" section).
- Does not modify `backend/`, `frontend/`, `web-testing/`, or any `.claude/` file
  outside Task.md's research sections and this WORKFLOW.md's research rows.
- Does not commit or push.

**What research DOES continuously**:
- Ongoing user ↔ research dialog: elicitation, clarification, gap hunting, algorithm
  audit, optimization ideas.
- Updates `research/spec/requirements.md` in place (version bump + changelog entry).
- Appends `SPEC-UPDATED` handoff signal so main picks up changes efficiently.
- Keeps `research/search/**` as reasoning archive — expanded when a new question
  requires fresh exploration.

### Pre-Push Review Gate

The orchestrator pipeline **commits but does not push**. `/review` is the unified
pre-push gate that combines static review + (conditional) browser verification + drift
checks into a single workflow:

```
main orchestrator
  |-> git-manager commits  (stays local)
  |-> reporter updates Report.md + Task.md
  |        -> appends `REVIEW-REQUESTED: <sha>` to Task.md Handoffs
  -> orchestrator STOPS and tells user:
       "run /review (or just say '리뷰해줘') in the review terminal;
        on REVIEW-PASSED run git push from that same terminal"
     (no push here)

(user opens / switches to review terminal — stays there through the rest of the cycle)

review terminal — `/review` (or natural language "리뷰해줘")
  PART A — Static deep review
  |- A1 captures REVIEWED_SHA = git rev-parse HEAD
  |               REVIEWED_ORIGIN_MAIN = git rev-parse origin/main
  |               CHANGED_FILES = git diff --name-only origin/main..HEAD
  |- A2-A4 read all changed files + Goal.md + Report.md + spec, apply 7-axis checklist,
  |        write report to .claude/reviews/<sha>.md + latest.md
  |- A5 stdout summary: STATIC REVIEW: <verdict> — <N> CRITICAL, <M> MAJOR, <K> MINOR
  -> A6 branch on verdict:
       FAIL (CRITICAL≥1 OR MAJOR≥1) → skip Part B + Part C drift, jump to C3 → REVIEW-FAIL
       PASS / PASS-WITH-MINORS → continue to Part B's path-detection gate

  PART B — Strict browser verification (CONDITIONAL)
  |- B0 path gate: scan CHANGED_FILES for UI-affecting paths
  |     (frontend/, recommendation/views.py, engine.py, accounts/, urls.py,
  |      recommendation/migrations/, RECOMMENDATION settings)
  |     - no UI paths → skip Part B, fill report's Part B section as "Skipped",
  |                     stdout "BROWSER TEST: skipped — no UI-affecting paths"
  |     - UI paths present → continue to B1
  |- B1 preflight: dev server health, dev-login, inject tokens, debug overlay
  |- B2 baseline: zero-tolerance pre-existing console-error gate
  |- B3-B7 run 3 personas × ≥25 swipes each:
  |    time-to-first-card < 4 s (5 s for bare query), per-swipe p95 < 700 ms,
  |    zero console errors, zero unexpected 4xx/5xx (auth-401 refresh allowed),
  |    no duplicate cards, expected phase transitions, strict API response shape,
  |    edge cases (refresh-resume, action card, persona report, network failure injection)
  |- B8 spec-metric infrastructure sentinel (saved_ids field, bookmark endpoint
  |     — conditional on Sprint 0 A3 having shipped)
  |- B9 cross-persona aggregation + cleanup + report append
  -> B10 branch:
       Part B FAIL → jump to C3 → REVIEW-FAIL combining Part A MINORs + Part B failure
       Part B PASS (or skipped earlier) → continue to Part C

  PART C — Drift checks + final verdict
  |- C1 HEAD-drift check: re-read HEAD. If ≠ REVIEWED_SHA
  |     → append REVIEW-ABORTED: <sha> — HEAD advanced to <new_sha> → STOP
  |- C2 remote-drift check: fetch + re-read origin/main. If ≠ REVIEWED_ORIGIN_MAIN
  |     → append REVIEW-ABORTED: <sha> — origin/main moved → STOP
  -> C3 emit final handoff signal:
       Part A FAIL                           → REVIEW-FAIL: <sha> — N CRITICAL, M MAJOR
       Part A PASS + Part B FAIL             → REVIEW-FAIL: <sha> — static PASS but browser FAIL (...)
       Part A PASS + (Part B PASS or skipped) + clean drift:
         K=0 MINORs → REVIEW-PASSED: <sha> — drift checks passed; run `git push` manually
         K>0 MINORs → REVIEW-PASSED: <sha> — drift checks passed, K MINOR noted (...)

(still in the review terminal)
  - REVIEW-PASSED  → user runs `git push` directly
  - REVIEW-ABORTED → user returns to main terminal; orchestrator handles the follow-up
                      (re-run /review after HEAD drift; pull --rebase + re-review after remote drift)
  - REVIEW-FAIL    → user returns to main terminal; orchestrator re-enters fix loop (max 2 cycles)
```

This means:
1. **One unified command, one verdict.** `/review` runs Part A (static review),
   conditionally Part B (browser verification when UI-affecting paths in scope), and
   Part C (drift checks), then emits one combined signal. Natural language
   ("리뷰해줘", "review please", "검토해줘") triggers the same workflow per CLAUDE.md
   "Natural language review trigger".
2. `git push` happens from the review terminal, not the main terminal — after the review
   verified that the range is clean (Part A), the UX is intact (Part B if applicable),
   AND HEAD/origin/main still match what was reviewed (Part C). No context-switch, no
   "review one range, push another" race.
3. Part B is the strict pre-push browser verification — separate from the fast
   `web-tester` that runs inside the orchestrator inner loop. It enforces spec-aligned
   latency budgets, multi-persona convergence cycles, and zero-tolerance error gates.
   The user does not invoke it separately; `/review` runs it automatically when the
   diff includes UI-affecting paths.
4. The review terminal still never edits source code and never runs `git push` itself —
   the push is always user-initiated by explicit `git push` in the review terminal.
4. `git-manager`'s "never pushes unless explicitly told to" default (see Key Rules
   below) is what keeps the orchestrator side clean; no existing agent code changes.

---

## Case 1: Normal feature or bug fix

```
User request
  |-> orchestrator
       |- reads CLAUDE.md + Goal.md + Task.md + Report.md
       |- adds/updates task in Task.md (-> In Progress)
       |- breaks task into back-maker spec + front-maker spec
       |
       |-> back-maker          backend code, runs flake8
       |    -> BACK-MAKER DONE + API contract
       |
       |-> front-maker         frontend code, runs ESLint
       |    -> FRONT-MAKER DONE + API calls made
       |
       |-> reviewer --+  (parallel)
       |-> security --+  (parallel)
       |
       |   Both PASS?
       |   |- YES --> web-tester (10+ swipes, dev-login auth)
       |   |           |- PASS --> git-manager --> reporter --> done
       |   |           -> FAIL --> Fix Loop (counts as 1 cycle)
       |   |
       |   -> NO  --> Fix Loop (max 2 cycles total)
       |               |- reviewer (Mode B) translates issues -> fix orders
       |               |-> back-maker / front-maker fix
       |               |-> reviewer + security again
       |               |- PASS --> web-tester --> git-manager --> reporter
       |               -> still FAIL after cycle 2 --> STOP, report to user
       |
       -> git-manager --> reporter (updates Report.md + marks Task.md resolved)
```

---

## Case 2: Question or explanation

```
User question
  -> Claude answers directly
       No agents spawned. No code changed.
```

---

## Case 3: Algorithm optimizer run

```
User: "run the algorithm tester"
  -> algo-tester
       |- reads CLAUDE.md + research/algorithm.md
       |- runs: python3 tools/algorithm_tester.py --personas N --trials T
       |   (~5-10 min, shows progress)
       |
       |- reads: backend/tools/optimization_results.json
       |
       |- WEAKNESS DETECTED?
       |   (precision < 0.02, avg_swipes > 40, std > 0.15, archetype near-zero)
       |   -> YES --> STOP. Report exact numbers to user.
       |               Wait for manual guidance. No files changed.
       |
       |- IMPROVEMENT vs baseline?
       |   -> NO  --> "Current params are optimal." --> reporter --> done
       |
       -> YES: improvement found
            |- Print summary table (current vs best, % improvement)
            -> orchestrator: "apply changed params to settings.py"
                 |-> back-maker (updates RECOMMENDATION dict only)
                 |-> reviewer + security
                 |-> git-manager ("chore: apply optimized hyperparameters")
                 -> reporter
```

---

## Case 4: Fix loop detail

```
reviewer or security returns FAIL
  -> orchestrator sends all issues to reviewer (Mode B: Fix Translation)
       -> reviewer returns precise fix orders per maker
            |-> back-maker (if backend fix)
            |-> front-maker (if frontend fix)
            -> reviewer + security (parallel, second pass)
                 |- PASS --> web-tester --> git-manager --> reporter
                 -> FAIL --> cycle 2 (same loop)
                      -> still FAIL --> STOP, report to user, ask guidance
```

Web test FAIL counts as 1 fix cycle. Max 2 cycles total across all loops.

---

## Case 5: Web tester flow

```
web-tester starts
  |
  |- Step 0: dev-login
  |   -> POST /api/v1/auth/dev-login/  ->  inject JWT to browser localStorage
  |       if 404 (DEV_LOGIN_SECRET not set): test page-load only
  |
  |- Step 1: Playwright Bash script
  |   -> captures: network requests, console errors, page errors
  |
  |- Step 2: MCP visual tests
  |   |- page load + screenshot
  |   |- UI structure (TabBar, theme toggle, search input)
  |   |- AI search -> submit -> wait for Gemini response
  |   |- start swiping -> 5-10 swipes -> verify next_image on every swipe
  |   -> check phase transitions (exploring -> analyzing)
  |
  -> returns: WEB TEST: PASS or FAIL
      FAIL includes: exact error, failing URL, console log excerpt
```

---

## Case 6: Research flow (separate terminal, ongoing)

Research runs in its **own dedicated terminal** (see "Multi-Terminal Coordination" →
Terminal Roster above). It is **not orchestrator-triggered** — it is a long-running,
user-driven dialog.

```
User starts/resumes research terminal
  |
  |- [ongoing dialog: user ↔ research terminal]
  |    elicitation, clarification, gap-hunting, algorithm audit, optimization ideas
  |
  |- research terminal writes / updates:
  |    research/spec/requirements.md   (living spec, versioned X.Y)
  |    research/spec/research-priority-rebaselined.md   (research recommendation, non-binding)
  |    research/search/NN-*.md   (reasoning archive, 12 topic deep-dives)
  |
  |- On spec revision:
  |    1. bumps **Version**: X.Y in requirements.md header
  |    2. appends Changelog entry at bottom of requirements.md
  |    3. appends `SPEC-UPDATED: vX.Y → vX.Z — <sections> — <summary>` to
  |        .claude/Task.md ## Handoffs
  |    4. if first publication: appends `[SPEC-READY]` to ## Research Ready
  |
  -> main terminal (separate, in its own session):
       |- at session start, reads ## Handoffs for new SPEC-UPDATED
       |- if new version: reads only affected sections in requirements.md
       |- plans task breakdown + sequencing INDEPENDENTLY
       |    (research/spec/research-priority-rebaselined.md is reference, not mandate)
       |- runs its orchestrator pipeline (Case 1) to implement
```

**Research terminal writes only**: `research/**` (full), `.claude/Task.md` (append-only
research sections), `.claude/WORKFLOW.md` (research rows only, by explicit user grant).
Never `backend/`, `frontend/`, agent definitions, `Report.md`, or git commits from main's pipeline.

**Main terminal reads** (in order): spec → plans → code. Main does NOT read
`research/search/**` under normal flow — Section 11 of `requirements.md` absorbs
all actionable directives. Main may consult `research/search/NN-*.md` for deep
justification only when debugging a spec decision or exploring a variant.

The **old orchestrator-triggered research pattern** (main's orchestrator invoking the
research agent mid-pipeline for a complex sub-question) is still available in
principle, but in practice all substantial research now lives in the dedicated
research terminal.

---

## Case 6.5: Design flow (separate terminal, ongoing)

The design pipeline runs in its **own dedicated terminal** (see "Multi-Terminal
Coordination" → Terminal Roster above). It is the parallel of `orchestrator` for
UI/UX work, supervised by the `designer` agent. Like research, it is not
orchestrator-triggered — it is a long-running, user-driven design dialog.

```
User starts/resumes design terminal
  |
  |- [ongoing dialog: user ↔ designer]
  |    DESIGN.md DNA refinement, mockup planning, post-integration polish, sub-agent
  |    creation when delegation is needed
  |
  |- designer reads at session start:
  |    DESIGN.md (visual system bible)
  |    CLAUDE.md (project conventions, design pipeline ownership rule)
  |    relevant frontend/ files
  |    grep -r "TODO(designer)" frontend/   (reciprocal markers from main)
  |
  |- designer writes / updates:
  |    DESIGN.md   (design DNA)
  |    frontend/  (UI layer only — JSX styles, animations, colors, layout, MOCK_*)
  |    .claude/agents/designer.md    (this file, on convention drift)
  |    .claude/agents/design-*.md    (creates new sub-agents on demand)
  |
  |- designer may spawn `design-<role>` sub-agents via the Agent tool when delegation
  |   is needed (e.g., multi-file refactor, full mockup page, visual QA pass).
  |
  |- On new mockup ready for API integration:
  |    appends `MOCKUP-READY: <page>` to .claude/Task.md ## Handoffs
  |
  |- On UI changes that need backend work:
  |    drops `// TODO(claude): <what>` markers in source for main pipeline pickup
  |
  -> design terminal commits its own work directly (research analog)
       (main's git-manager excludes DESIGN.md + .claude/agents/design-*.md by default)
```

**Design terminal writes only**: `DESIGN.md`, `frontend/` UI layer (JSX styles,
animations, colors, layout, `MOCK_*` constants), `.claude/agents/designer.md`,
`.claude/agents/design-*.md`, `.claude/Task.md` `## Handoffs` (`MOCKUP-READY`
append-only). Never `backend/`, `frontend/` data layer, `research/`, agent
definitions outside `design-*`, `CLAUDE.md`, `WORKFLOW.md`, `Goal.md`, or
`Report.md`.

**Main terminal reads** (in order): `DESIGN.md` (when front-maker integration
work touches surrounding JSX) → `MOCKUP-READY` Handoffs (to know which pages are
ready for API wiring) → `grep -r "TODO(claude)" frontend/` (to batch design's
backend requests).

---

## Case 7: Reporter (updates system docs + emits REVIEW-REQUESTED)

```
reporter runs after every git-manager commit
  |
  |- git log -1 --stat           (what changed)
  |- reads .claude/Report.md    (system documentation)
  |- reads .claude/Task.md      (task board)
  |
  |- updates Report.md:
  |   |- Last Updated section for Claude ONLY (Do NOT overwrite Gemini's section)
  |   |- Structure tables (if new files created)
  |   |- API Surface (if new endpoints)
  |   |- Feature Status (if features completed)
  |   -> Mermaid diagrams (if architecture changed)
  |
  |- updates Task.md:
  |   -> moves completed tasks to Resolved with date
  |
  -> appends REVIEW-REQUESTED to Task.md Handoffs:
       `- [YYYY-MM-DD] REVIEW-REQUESTED: <sha_short> — <one-line summary>`
       (uses Edit tool; does NOT touch the Research Ready section)
```

---

## Key rules

| Rule | Detail |
|------|--------|
| All changes go through orchestrator | Never implement directly from main conversation |
| Questions answered directly | No agents needed for explanations |
| Makers are sandboxed | back-maker: `backend/` only -- front-maker: `frontend/` only |
| orchestrator never writes code | Always delegates to makers |
| git-manager never pushes | Unless explicitly told to push |
| Reporter updates, never appends | Report.md is live state (but preserve `Last Updated (Designer)` section — design terminal owns it); Task.md Resolved is historical |
| Algorithm weakness = manual review | orchestrator stops and flags; does not auto-fix |
| Fix cycle limit = 2 | After 2 failed cycles, stop and report to user |
| Research before complex coding | Algorithm/UX tasks without precedent trigger research first |

---

## File locations

| File | Purpose |
|------|---------|
| `.claude/agents/*.md` | Agent definitions (this system) |
| `.claude/Goal.md` | Vision + acceptance criteria (north star) |
| `.claude/Task.md` | Problem board -- open/in-progress/resolved by category |
| `.claude/Report.md` | Live system documentation -- architecture, API, diagrams |
| `.claude/WORKFLOW.md` | This file -- agent workflow documentation |
| `research/` | Deep exploration files (algorithm, UX patterns) |
| `backend/tools/algorithm_tester.py` | Hyperparameter optimizer script |
| `backend/tools/optimization_results.json` | Latest tester output |
| `CLAUDE.md` | Project conventions (read by all agents) |
