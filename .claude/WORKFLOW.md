# ArchiTinder -- Agent Workflow

> **Read this when:** You want to understand how agents work, what triggers what, and when you
> will be flagged for manual review. All 6 workflow cases are covered here.
> For feature status: see `Report.md`. For task status: see `Task.md`. For vision: see `Goal.md`.

---

## Agent Roster

| Agent | Model | Role | Touches |
|-------|-------|------|---------|
| **orchestrator** | opus | Supervisor -- plans, delegates, manages fix loops | nothing directly |
| **back-maker** | sonnet | Django/DRF backend code | `backend/` only |
| **front-maker** | sonnet | React/Vite frontend code | `frontend/` only |
| **reviewer** | sonnet | API contracts, logic bugs, error handling | read-only |
| **security-manager** | sonnet | SQL injection, auth bypass, XSS, token leaks | read-only |
| **web-tester** | sonnet | Live Playwright browser tests | read-only |
| **git-manager** | haiku | Single commit per task | git only |
| **reporter** | sonnet | Updates Report.md + Task.md, emits REVIEW-REQUESTED handoff | `.claude/` only |
| **algo-tester** | sonnet | Runs optimizer script, interprets results, triggers orchestrator | runs script + calls orchestrator |
| **research** | opus | Explores complex problems, writes to research/ | `research/` only |
| **deep-reviewer** | opus | Pre-push deep review across 7 axes; writes `.claude/reviews/*.md` and REVIEW-PASSED/REVIEW-FAIL handoff | read-only on source; writes `.claude/reviews/` + Task.md Handoffs line |

---

## Multi-Terminal Coordination

The project is developed across **four parallel terminals**, each with a focused role and
isolated context window. All terminals work on the `main` Git branch — coordination is by
file/layer ownership + handoff signals in `Task.md`, not branches.

### Terminal Roster

| Terminal | Model | Role | Owns / Touches | Typical signals |
|----------|-------|------|----------------|-----------------|
| **main** | Claude Code (orchestrator: opus) | Full pipeline — backend, frontend integration, E2E tests, commit | `backend/`, `frontend/` (data layer), `.claude/` | reporter emits `REVIEW-REQUESTED` to Handoffs; consumes `MOCKUP-READY`, `REVIEW-FAIL`, `REVIEW-ABORTED` from Handoffs, and `[RESEARCH-READY]` from Research Ready section |
| **research** | Claude Code (research agent: opus) | Algorithm / search exploration, paper review, design proposals | `research/` only + appends `[RESEARCH-READY]` to Task.md `## Research Ready` section (its own append-only queue) | emits `[RESEARCH-READY]` |
| **review** | Claude Code (deep-reviewer: opus) | Pre-push deep review across all axes (architecture, perf, security, drift) + HEAD/`origin/main` drift checks on PASS | read-only on source; writes `.claude/reviews/*.md` and the handoff line in Task.md `## Handoffs`; user manually runs `git push` from this terminal on `REVIEW-PASSED` | emits `REVIEW-PASSED` (drift-verified, ready for manual push), `REVIEW-ABORTED` (PASS but drift detected), or `REVIEW-FAIL` to Handoffs |
| **antigravity** | Gemini (Chrome integration) | Continuous UI iteration — new mockups AND existing-page polish | `frontend/` (UI layer) | emits `MOCKUP-READY` to Handoffs; drops inline `TODO(claude): ...` markers in source |

> **Note on Task.md sections:**
> - `## Handoffs` (near top) = short-lived review/mockup signals, rolling window.
> - `## Research Ready` (further down) = research terminal's append-only queue. Do not mix the two.

### Frontend Layer Ownership (antigravity vs main)

Both antigravity and main edit files under `frontend/`, so ownership is split **by layer within the same file**:

| Layer | Owner | Allowed edits |
|-------|-------|---------------|
| **UI** | antigravity | JSX return, `styles` objects, animations, transitions, colors, spacing, `MOCK_*` constants (pre-integration only) |
| **Data / Logic** | main | `useState`, `useEffect`, `callApi()`, error handling, data transformations, custom hooks |

Post-integration rules for antigravity returning to a polished page (full table in `GEMINI.md`):
- Allowed: JSX structure, styles, animations, colors
- Forbidden: re-inserting `MOCK_*`, editing `useState/useEffect/callApi`, removing `profile?.xxx` optional chaining

When antigravity needs behavior that requires API/backend work, it drops an inline marker
instead of wiring it:

```jsx
<button onClick={() => { /* TODO(claude): DELETE /api/v1/boards/${board_id}/ */ }}>
  Delete
</button>
```

Main's orchestrator batches these via `grep -r "TODO(claude)" frontend/` during the next
integration session.

### Git Discipline

- **All four terminals work on `main` branch.** No feature branches.
- **Always `git pull` before starting a session.**
- **Commit early, commit small** — avoid saving up many changes for one large commit.
  Git's 3-way merge handles most cases when two terminals touched the same file in
  different sections (e.g., antigravity edited JSX, main edited `useEffect`).
- Only `git-manager` commits from the orchestrator pipeline (one commit per task).
  Antigravity and research commit directly from their own terminal.

### Pre-Push Review Gate

The orchestrator pipeline **commits but does not push**. `/deep-review` is the pre-push gate,
and the review terminal performs two drift checks before signalling that push is safe:

```
main orchestrator
  |-> git-manager commits  (stays local)
  |-> reporter updates Report.md + Task.md
  |        -> appends `REVIEW-REQUESTED: <sha>` to Task.md Handoffs
  -> orchestrator STOPS and tells user:
       "run /deep-review in the review terminal; on REVIEW-PASSED
        run git push from that same terminal"
     (no push here)

(user opens / switches to review terminal — stays there through the rest of the cycle)

review terminal — `/deep-review`
  |- Step 1 captures REVIEWED_SHA = git rev-parse HEAD
  |                  REVIEWED_ORIGIN_MAIN = git rev-parse origin/main
  |- Steps 2-5 produce .claude/reviews/<sha>.md + latest.md + stdout summary
  -> Step 6 branches on verdict:
       FAIL → append REVIEW-FAIL: <sha> — ... → STOP
       PASS / PASS-WITH-MINORS:
         6b HEAD-drift check: re-read HEAD. If ≠ REVIEWED_SHA
              → append REVIEW-ABORTED: <sha> — HEAD advanced to <new_sha> ... → STOP
         6c remote-drift check: fetch + re-read origin/main. If ≠ REVIEWED_ORIGIN_MAIN
              → append REVIEW-ABORTED: <sha> — origin/main moved ... → STOP
         6d both drifts clear
              → append REVIEW-PASSED: <sha> — drift checks passed; run `git push` manually from this terminal
                (on PASS-WITH-MINORS the signal inlines "<K> MINOR noted (see .claude/reviews/latest.md)")

(still in the review terminal)
  - REVIEW-PASSED  → user runs `git push` directly (the review terminal never pushes by itself)
  - REVIEW-ABORTED → user returns to main terminal; orchestrator handles the follow-up
                      (re-run /deep-review after HEAD drift; pull --rebase + re-review after remote drift)
  - REVIEW-FAIL    → user returns to main terminal; orchestrator re-enters fix loop (max 2 cycles)
```

This means:
1. `git push` happens from the review terminal, not the main terminal — after the review
   verified both that the range is clean AND that HEAD and origin/main still match what
   was reviewed. No context-switch, no "review one range, push another" race.
2. The review terminal still never edits source code and never runs `git push` itself —
   the push is always user-initiated by explicit `git push` in the review terminal.
3. `git-manager`'s "never pushes unless explicitly told to" default (see Key Rules
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

## Case 6: Research flow

```
Orchestrator detects complex problem (algorithm, UX, performance)
  -> research agent
       |- reads Goal.md + existing research/ files
       |- WebSearch for papers, best practices
       |- reads current code for constraints
       |
       -> writes research/<topic>.md
            |- Question
            |- Findings (with sources)
            |- Options (2-3 approaches)
            |- Recommendation
            -> Open questions
       |
       -> returns to orchestrator:
            summary + recommended approach + proposed Task.md items
```

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
| Reporter updates, never appends | Report.md is live state (but preserve Gemini section for Last Updated); Task.md Resolved is historical |
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
